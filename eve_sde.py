"""EVE SDE database manager — download, build, and query local static data."""

import bz2
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone

import requests

SDE_URL = "https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2"
DB_NAME = "eve_sde.db"

NEEDED_TABLES = [
    "invTypes",
    "invGroups",
    "invCategories",
    "mapSolarSystems",
    "mapConstellations",
    "mapRegions",
    "staStations",
    "chrFactions",
    "chrBloodlines",
    "chrRaces",
    "crpNPCCorporations",
    "invFlags",
    "invNames",
]

CACHE_SIZE = 20000


def _app_dir():
    """Directory where the script/exe lives — DB and temp files go here."""
    import sys

    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


class SDE:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(_app_dir(), DB_NAME)
        self._conn = None
        self._lock = threading.Lock()
        self._cache = {}

    # ── connection ────────────────────────────────────────────

    @property
    def conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── status checks ─────────────────────────────────────────

    def is_ready(self):
        if not os.path.exists(self.db_path):
            return False
        try:
            self.conn.execute("SELECT COUNT(*) FROM invTypes")
            return True
        except Exception:
            return False

    def get_local_version(self):
        """Return the recorded build date or file mtime as datetime."""
        try:
            row = self.conn.execute(
                "SELECT value FROM version_info WHERE key='build_date'"
            ).fetchone()
            if row:
                return datetime.fromisoformat(row[0])
        except Exception:
            pass
        ts = os.path.getmtime(self.db_path)
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    @staticmethod
    def get_remote_version():
        """Return remote file's Last-Modified as datetime."""
        resp = requests.head(SDE_URL, timeout=30)
        resp.raise_for_status()
        last_mod = resp.headers.get("Last-Modified", "")
        return datetime.strptime(last_mod, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)

    def needs_download(self):
        if not self.is_ready():
            return True
        try:
            local = self.get_local_version()
            remote = self.get_remote_version()
            return remote > local
        except Exception:
            return False

    # ── download & build ──────────────────────────────────────

    def download_and_build(self, progress_callback=None):
        """Download the full SDE SQLite, extract needed tables, clean up.

        progress_callback(stage, pct) where stage is 'download'|'extract'|'index'.
        """
        app_dir = _app_dir()
        bz2_path = os.path.join(app_dir, "sde_temp.sqlite.bz2")
        sqlite_path = os.path.join(app_dir, "sde_temp.sqlite")

        try:
            # 1. Download
            self._download(bz2_path, progress_callback)

            # 2. Decompress
            self._report(progress_callback, "decompress", 0)
            with open(sqlite_path, "wb") as out:
                with bz2.open(bz2_path, "rb") as f:
                    while True:
                        chunk = f.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
            self._report(progress_callback, "decompress", 100)
            os.remove(bz2_path)

            # 3. Extract tables to local DB
            tmp_conn = sqlite3.connect(sqlite_path)
            total_tables = len(NEEDED_TABLES)
            for i, table in enumerate(NEEDED_TABLES):
                pct = (i + 1) / total_tables * 100
                self._report(progress_callback, "extract", pct)

                # Get source column info
                cols = tmp_conn.execute(f"PRAGMA table_info('{table}')").fetchall()
                col_names = [c[1] for c in cols]

                self.conn.execute(f"DROP TABLE IF EXISTS {table}")
                # Create table in local DB
                col_defs = ", ".join(f'"{c[1]}"' for c in cols)
                self.conn.execute(f"CREATE TABLE {table} ({col_defs})")
                self.conn.commit()

                # Copy data in batches
                batch_size = 50000
                offset = 0
                while True:
                    rows = tmp_conn.execute(
                        f"SELECT * FROM {table} LIMIT {batch_size} OFFSET {offset}"
                    ).fetchall()
                    if not rows:
                        break
                    placeholders = ", ".join(["?"] * len(col_names))
                    self.conn.executemany(
                        f"INSERT INTO {table} VALUES ({placeholders})", rows
                    )
                    self.conn.commit()
                    offset += batch_size

                # Create index on the first (ID) column
                try:
                    self.conn.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{table}_id ON {table}({col_names[0]})"
                    )
                    self.conn.commit()
                except Exception:
                    pass

            tmp_conn.close()
            os.remove(sqlite_path)

            # 4. Write version info
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS version_info (key TEXT PRIMARY KEY, value TEXT)"
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO version_info VALUES ('build_date', ?)",
                (datetime.now(timezone.utc).isoformat(),),
            )
            self.conn.commit()
            self.conn.execute("PRAGMA optimize; VACUUM;")
            self._report(progress_callback, "done", 100)

        except Exception:
            # Clean up partial downloads
            for p in [bz2_path, sqlite_path]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            raise

    def _download(self, dest, progress_callback):
        resp = requests.get(SDE_URL, stream=True, timeout=120)
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    self._report(progress_callback, "download", pct)
        self._report(progress_callback, "download", 100)

    @staticmethod
    def _report(cb, stage, pct):
        if cb:
            cb(stage, pct)

    # ── queries ───────────────────────────────────────────────

    def _lookup(self, table, id_col, name_col, obj_id):
        if obj_id is None:
            return None
        cache_key = f"{table}:{obj_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            row = self.conn.execute(
                f'SELECT "{name_col}" FROM {table} WHERE "{id_col}" = ?', (int(obj_id),)
            ).fetchone()
            name = row[0] if row else None
        except Exception:
            name = None
        if len(self._cache) < CACHE_SIZE:
            self._cache[cache_key] = name
        return name

    def _batch_lookup(self, table, id_col, name_col, ids):
        """Batch lookup, returns {id: name}. Pops from cache first."""
        result = {}
        missing = []
        for obj_id in ids:
            if obj_id is None:
                continue
            cache_key = f"{table}:{obj_id}"
            if cache_key in self._cache:
                result[obj_id] = self._cache[cache_key]
            else:
                missing.append(int(obj_id))
        if not missing:
            return result
        try:
            placeholders = ",".join(["?"] * len(missing))
            rows = self.conn.execute(
                f'SELECT "{id_col}", "{name_col}" FROM {table} WHERE "{id_col}" IN ({placeholders})',
                missing,
            ).fetchall()
            for row in rows:
                sid = row[0]
                name = row[1]
                result[sid] = name
                cache_key = f"{table}:{sid}"
                if len(self._cache) < CACHE_SIZE:
                    self._cache[cache_key] = name
            # Missing results → cache as None
            for mid in missing:
                if mid not in result:
                    result[mid] = None
                    cache_key = f"{table}:{mid}"
                    if len(self._cache) < CACHE_SIZE:
                        self._cache[cache_key] = None
        except Exception:
            for mid in missing:
                result[mid] = None
        return result

    # ── convenience methods ───────────────────────────────────

    def type_name(self, type_id):
        return self._lookup("invTypes", "typeID", "typeName", type_id)

    def batch_type_names(self, ids):
        return self._batch_lookup("invTypes", "typeID", "typeName", ids)

    def group_name(self, group_id):
        return self._lookup("invGroups", "groupID", "groupName", group_id)

    def category_name(self, category_id):
        return self._lookup("invCategories", "categoryID", "categoryName", category_id)

    def system_name(self, system_id):
        return self._lookup("mapSolarSystems", "solarSystemID", "solarSystemName", system_id)

    def constellation_name(self, con_id):
        return self._lookup("mapConstellations", "constellationID", "constellationName", con_id)

    def region_name(self, region_id):
        return self._lookup("mapRegions", "regionID", "regionName", region_id)

    def station_name(self, station_id):
        return self._lookup("staStations", "stationID", "stationName", station_id)

    def faction_name(self, faction_id):
        return self._lookup("chrFactions", "factionID", "factionName", faction_id)

    def bloodline_name(self, bloodline_id):
        return self._lookup("chrBloodlines", "bloodlineID", "bloodlineName", bloodline_id)

    def race_name(self, race_id):
        return self._lookup("chrRaces", "raceID", "raceName", race_id)

    def corp_name(self, corp_id):
        return self._lookup("crpNPCCorporations", "corporationID", "corporationName", corp_id)

    def flag_name(self, flag_id):
        return self._lookup("invFlags", "flagID", "flagName", flag_id)

    def item_name(self, item_id):
        """Custom-named items (player structures, alliances)."""
        return self._lookup("invNames", "itemID", "itemName", item_id)