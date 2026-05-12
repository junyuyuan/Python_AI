import base64
import hashlib
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse, urlencode

import requests


EVE_AUTH_URL = "https://login.eveonline.com/v2/oauth/authorize"
EVE_TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
EVE_VERIFY_URL = "https://esi.evetech.net/verify/"
DEFAULT_REDIRECT_PORT = 8080

ALL_SCOPES = [
    "publicData",
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-wallet.read_character_wallet.v1",
    "esi-assets.read_assets.v1",
    "esi-location.read_location.v1",
    "esi-location.read_ship_type.v1",
    "esi-location.read_online.v1",
    "esi-fittings.read_fittings.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-mail.read_mail.v1",
    "esi-characters.read_notifications.v1",
    "esi-characters.read_contacts.v1",
    "esi-characters.read_standings.v1",
    "esi-killmails.read_killmails.v1",
    "esi-contracts.read_character_contracts.v1",
    "esi-markets.read_character_orders.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-industry.read_character_mining.v1",
    "esi-characters.read_blueprints.v1",
    "esi-characters.read_fw_stats.v1",
    "esi-characters.read_loyalty.v1",
    "esi-characters.read_medals.v1",
    "esi-characters.read_corporation_roles.v1",
    "esi-characters.read_titles.v1",
    "esi-calendar.read_calendar_events.v1",
    "esi-characters.read_fatigue.v1",
]

ESI_BASE = "https://esi.evetech.net/latest"


class _CallbackHandler(BaseHTTPRequestHandler):
    auth_code = None
    auth_error = None

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if "code" in query:
            _CallbackHandler.auth_code = query["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>Login successful!</h1><p>You can close this window.</p>")
        elif "error" in query:
            _CallbackHandler.auth_error = query.get("error_description", [query["error"][0]])[0]
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"<h1>Login failed</h1><p>{_CallbackHandler.auth_error}</p>".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def _generate_pkce():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


def _start_callback_server(port, timeout_event):
    server = HTTPServer(("localhost", port), _CallbackHandler)
    server.timeout = 1
    while not timeout_event.is_set():
        server.handle_request()
    server.server_close()


def login(client_id, redirect_port=DEFAULT_REDIRECT_PORT, scopes=None):
    """Open browser for EVE Online SSO and return character info dict.

    Returns dict with keys: character_id, character_name, access_token,
    refresh_token, expires_on.

    Raises RuntimeError on timeout or denied authorization.
    """
    if scopes is None:
        scopes = ALL_SCOPES
    redirect_uri = f"http://localhost:{redirect_port}/callback"
    code_verifier, code_challenge = _generate_pkce()
    state = secrets.token_urlsafe(16)

    _CallbackHandler.auth_code = None
    _CallbackHandler.auth_error = None

    params = {
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "scope": " ".join(scopes) if scopes else "",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    auth_url = f"{EVE_AUTH_URL}?{urlencode(params)}"

    timeout_event = threading.Event()
    server_thread = threading.Thread(
        target=_start_callback_server, args=(redirect_port, timeout_event), daemon=True
    )
    server_thread.start()

    webbrowser.open(auth_url)

    # Wait for callback up to 5 minutes
    import time
    for _ in range(300):
        if _CallbackHandler.auth_code or _CallbackHandler.auth_error:
            break
        time.sleep(1)

    timeout_event.set()
    server_thread.join(timeout=5)

    if _CallbackHandler.auth_error:
        raise RuntimeError(f"Authorization denied: {_CallbackHandler.auth_error}")
    if not _CallbackHandler.auth_code:
        raise RuntimeError("Authorization timed out.")

    # Exchange code for token
    token_data = {
        "grant_type": "authorization_code",
        "code": _CallbackHandler.auth_code,
        "client_id": client_id,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
    }
    resp = requests.post(
        EVE_TOKEN_URL,
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Token request failed ({resp.status_code}): {resp.text}") from e
    token_json = resp.json()

    access_token = token_json["access_token"]
    refresh_token = token_json.get("refresh_token")

    # Decode JWT payload to get character info
    try:
        payload_b64 = access_token.split(".")[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload_json = base64.urlsafe_b64decode(payload_b64)
        char_info = json.loads(payload_json)
    except Exception as e:
        raise RuntimeError(f"Failed to decode access token: {e}") from e

    # sub format: "CHARACTER:EVE:<character_id>"
    sub = char_info.get("sub", "")
    character_id = sub.split(":")[-1] if ":" in sub else sub

    return {
        "character_id": character_id,
        "character_name": char_info.get("name"),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_on": char_info.get("exp"),
    }


def refresh_access_token(client_id, refresh_token):
    """Use a refresh token to get a new access token."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    resp = requests.post(
        EVE_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()


def esi_get(access_token, path):
    """Generic ESI API GET call. Returns parsed JSON."""
    url = ESI_BASE + path
    resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def fetch_all_character_data(char_info):
    """Fetch all available character data from ESI endpoints.
    Returns dict keyed by category name. Failed endpoints return None.
    """
    token = char_info["access_token"]
    cid = char_info["character_id"]
    result = {}

    def _safe_fetch(key, path):
        try:
            return esi_get(token, path)
        except Exception:
            return None

    result["基本信息"] = _safe_fetch("info", f"/characters/{cid}/")
    result["在线状态"] = _safe_fetch("online", f"/characters/{cid}/online/")
    result["军团历史"] = _safe_fetch("corp_history", f"/characters/{cid}/corporationhistory/")
    result["角色属性"] = _safe_fetch("attributes", f"/characters/{cid}/attributes/")
    result["技能列表"] = _safe_fetch("skills", f"/characters/{cid}/skills/")
    result["技能队列"] = _safe_fetch("skillqueue", f"/characters/{cid}/skillqueue/")
    result["钱包余额"] = _safe_fetch("wallet", f"/characters/{cid}/wallet/")
    result["钱包流水"] = _safe_fetch("wallet_journal", f"/characters/{cid}/wallet/journal/")
    result["钱包交易"] = _safe_fetch("wallet_transactions", f"/characters/{cid}/wallet/transactions/")
    result["资产列表"] = _safe_fetch("assets", f"/characters/{cid}/assets/")
    result["当前位置"] = _safe_fetch("location", f"/characters/{cid}/location/")
    result["当前舰船"] = _safe_fetch("ship", f"/characters/{cid}/ship/")
    result["舰船装配"] = _safe_fetch("fittings", f"/characters/{cid}/fittings/")
    result["克隆状态"] = _safe_fetch("clones", f"/characters/{cid}/clones/")
    result["植入体"] = _safe_fetch("implants", f"/characters/{cid}/implants/")
    result["跳跃疲劳"] = _safe_fetch("fatigue", f"/characters/{cid}/fatigue/")
    result["邮件"] = _safe_fetch("mail", f"/characters/{cid}/mail/")
    result["邮件标签"] = _safe_fetch("mail_labels", f"/characters/{cid}/mail/labels/")
    result["通知"] = _safe_fetch("notifications", f"/characters/{cid}/notifications/")
    result["联系人"] = _safe_fetch("contacts", f"/characters/{cid}/contacts/")
    result["声望"] = _safe_fetch("standings", f"/characters/{cid}/standings/")
    result["击杀记录"] = _safe_fetch("killmails", f"/characters/{cid}/killmails/recent/")
    result["合同"] = _safe_fetch("contracts", f"/characters/{cid}/contracts/")
    result["市场订单"] = _safe_fetch("orders", f"/characters/{cid}/orders/")
    result["工业任务"] = _safe_fetch("industry_jobs", f"/characters/{cid}/industry/jobs/")
    result["蓝图"] = _safe_fetch("blueprints", f"/characters/{cid}/blueprints/")
    result["势力战争"] = _safe_fetch("fw_stats", f"/characters/{cid}/fw/stats/")
    result["忠诚点数"] = _safe_fetch("loyalty", f"/characters/{cid}/loyalty/points/")
    result["勋章"] = _safe_fetch("medals", f"/characters/{cid}/medals/")
    result["采矿"] = _safe_fetch("mining", f"/characters/{cid}/mining/")
    result["行星开发"] = _safe_fetch("planets", f"/characters/{cid}/planets/")
    result["头衔"] = _safe_fetch("titles", f"/characters/{cid}/titles/")
    result["军团角色"] = _safe_fetch("roles", f"/characters/{cid}/roles/")
    result["日历"] = _safe_fetch("calendar", f"/characters/{cid}/calendar/")

    return result
