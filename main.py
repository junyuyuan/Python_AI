import tkinter as tk
from tkinter import ttk, messagebox
import threading

import eve_auth
import eve_sde

EVE_CLIENT_ID = "9905be5356d7420caf87bdd8b639f6f4"

CATEGORIES = [
    "概览", "技能", "钱包", "资产", "舰船", "克隆",
    "邮件/通知", "市场/工业", "合同/蓝图", "击杀记录", "联系人", "军团",
]


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Python_AI")
        self.root.geometry("400x250")
        self.root.resizable(True, True)

        self.char_info = None
        self.all_data = None
        self.notebook = None
        self.tab_frames = {}
        self.sde = None

        self._build_login_ui()
        self._check_sde()

    # ── Login UI ──────────────────────────────────────────────

    def _clear_root(self):
        for w in self.root.winfo_children():
            w.destroy()

    def _build_login_ui(self):
        self._clear_root()
        self.root.geometry("400x250")

        frame = ttk.Frame(self.root, padding=20)
        frame.pack(expand=True, fill=tk.BOTH)

        ttk.Label(frame, text="Python_AI", font=("Microsoft YaHei", 16, "bold")).pack(pady=(0, 10))
        ttk.Label(frame, text="请登录以继续", font=("Microsoft YaHei", 12)).pack()
        ttk.Button(frame, text="使用 EVE Online 登录", command=self._start_login).pack(pady=20)
        self.status_label = ttk.Label(frame, text="", foreground="gray")
        self.status_label.pack()

        # SDE status footer
        self.sde_status_label = ttk.Label(
            self.root, text="SDE: 检查中...", foreground="gray", font=("Microsoft YaHei", 8)
        )
        self.sde_status_label.pack(side=tk.BOTTOM, pady=(0, 4))

    def _start_login(self):
        if not EVE_CLIENT_ID:
            messagebox.showerror("未配置 Client ID",
                "请先在 main.py 中设置 EVE_CLIENT_ID\n获取地址: https://developers.eveonline.com")
            return

        self.status_label.config(text="正在打开浏览器，请完成授权...")
        threading.Thread(target=self._do_login, daemon=True).start()

    # ── SDE check & download ──────────────────────────────────

    def _check_sde(self):
        threading.Thread(target=self._do_sde_check, daemon=True).start()

    def _do_sde_check(self):
        try:
            sde = eve_sde.SDE()
            if sde.needs_download():
                self.root.after(0, self._sde_start_download, sde)
            else:
                self.sde = sde
                self.root.after(0, lambda: self.sde_status_label.config(
                    text="SDE: 就绪", foreground="green"))
        except Exception as e:
            self.root.after(0, lambda: self.sde_status_label.config(
                text=f"SDE: 初始化失败 ({e})", foreground="red"))

    def _sde_start_download(self, sde):
        win = tk.Toplevel(self.root)
        win.title("下载 SDE 数据库")
        win.geometry("400x120")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="正在下载 EVE 静态数据库...",
                  font=("Microsoft YaHei", 11, "bold")).pack(pady=(12, 6))
        stage_label = ttk.Label(win, text="下载中...", font=("Microsoft YaHei", 9))
        stage_label.pack()
        progress = ttk.Progressbar(win, mode="determinate", length=350)
        progress.pack(pady=(6, 10))

        def on_progress(stage, pct):
            stage_texts = {
                "download": f"下载中... ({pct:.0f}%)",
                "decompress": f"解压中... ({pct:.0f}%)",
                "extract": f"提取表... ({pct:.0f}%)",
                "done": "完成",
            }
            if stage == "error":
                stage_label.config(text=f"错误: {pct}", foreground="red")
                return
            stage_label.config(text=stage_texts.get(stage, f"{stage}... ({pct:.0f}%)"))
            progress["value"] = pct
            if stage == "done":
                self.root.after(0, win.destroy)

        def _download():
            try:
                sde.download_and_build(on_progress)
                self.sde = sde
                self.root.after(0, lambda: self.sde_status_label.config(
                    text="SDE: 就绪", foreground="green"))
            except Exception as e:
                import traceback
                err_msg = str(e)[:80]
                with open("sde_error.log", "w", encoding="utf-8") as f:
                    f.write(traceback.format_exc())
                self.root.after(0, lambda: self.sde_status_label.config(
                    text=f"SDE: 下载失败 ({err_msg})", foreground="red"))
                self.root.after(0, win.destroy)

        threading.Thread(target=_download, daemon=True).start()

    def _do_login(self):
        try:
            self.char_info = eve_auth.login(EVE_CLIENT_ID)
            self.root.after(0, self._on_login_success)
        except Exception as e:
            import traceback
            with open("login_error.log", "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            self.root.after(0, lambda: self.status_label.config(
                text=f"登录失败: {type(e).__name__}: {e}", foreground="red"))

    # ── Loading UI (login success → fetch data → show tabs) ────

    def _on_login_success(self):
        self._clear_root()
        self.root.geometry("500x150")
        self.root.resizable(False, False)

        frame = ttk.Frame(self.root, padding=30)
        frame.pack(expand=True, fill=tk.BOTH)

        self.loading_label = ttk.Label(frame, text=f"登录成功，欢迎 {self.char_info['character_name']}！",
                                       font=("Microsoft YaHei", 12, "bold"))
        self.loading_label.pack(pady=(0, 10))

        self.progress = ttk.Progressbar(frame, mode="determinate", length=400)
        self.progress.pack(pady=(0, 8))

        self.progress_label = ttk.Label(frame, text="正在连接 ESI...", font=("Microsoft YaHei", 9))
        self.progress_label.pack()

        self.root.update()
        threading.Thread(target=self._fetch_all_data, daemon=True).start()

    def _fetch_all_data(self):
        token = self.char_info["access_token"]
        cid = self.char_info["character_id"]

        # (category, endpoint_path) — must match tab categories
        endpoints = [
            ("info", f"/characters/{cid}/"),
            ("online", f"/characters/{cid}/online/"),
            ("corp_history", f"/characters/{cid}/corporationhistory/"),
            ("attributes", f"/characters/{cid}/attributes/"),
            ("skills", f"/characters/{cid}/skills/"),
            ("skillqueue", f"/characters/{cid}/skillqueue/"),
            ("wallet", f"/characters/{cid}/wallet/"),
            ("wallet_journal", f"/characters/{cid}/wallet/journal/"),
            ("wallet_transactions", f"/characters/{cid}/wallet/transactions/"),
            ("assets", f"/characters/{cid}/assets/"),
            ("location", f"/characters/{cid}/location/"),
            ("ship", f"/characters/{cid}/ship/"),
            ("fittings", f"/characters/{cid}/fittings/"),
            ("clones", f"/characters/{cid}/clones/"),
            ("implants", f"/characters/{cid}/implants/"),
            ("fatigue", f"/characters/{cid}/fatigue/"),
            ("mail", f"/characters/{cid}/mail/"),
            ("mail_labels", f"/characters/{cid}/mail/labels/"),
            ("notifications", f"/characters/{cid}/notifications/"),
            ("contacts", f"/characters/{cid}/contacts/"),
            ("standings", f"/characters/{cid}/standings/"),
            ("killmails", f"/characters/{cid}/killmails/recent/"),
            ("contracts", f"/characters/{cid}/contracts/"),
            ("orders", f"/characters/{cid}/orders/"),
            ("industry_jobs", f"/characters/{cid}/industry/jobs/"),
            ("blueprints", f"/characters/{cid}/blueprints/"),
            ("fw_stats", f"/characters/{cid}/fw/stats/"),
            ("loyalty", f"/characters/{cid}/loyalty/points/"),
            ("medals", f"/characters/{cid}/medals/"),
            ("mining", f"/characters/{cid}/mining/"),
            ("planets", f"/characters/{cid}/planets/"),
            ("titles", f"/characters/{cid}/titles/"),
            ("roles", f"/characters/{cid}/roles/"),
            ("calendar", f"/characters/{cid}/calendar/"),
        ]

        total = len(endpoints)
        results = {}
        ok_count = 0
        failed = []

        for i, (key, path) in enumerate(endpoints):
            # Update UI progress
            def _update():
                pct = (i + 1) / total * 100
                self.progress["value"] = pct
                self.progress_label.config(text=f"正在获取 {key}... ({i + 1}/{total})")
            self.root.after(0, _update)

            try:
                results[key] = eve_auth.esi_get(token, path)
                ok_count += 1
            except Exception as e:
                results[key] = None
                failed.append((key, str(e)))

        self.all_data = results
        self.root.after(0, lambda: self._show_tab_ui(total, ok_count, failed))

    # ── Main tabbed UI ────────────────────────────────────────

    def _show_tab_ui(self, total, ok_count, failed=None):
        self.root.resizable(True, True)
        self.root.geometry("900x650")
        self._clear_root()

        header = ttk.Frame(self.root, padding=(10, 8))
        header.pack(fill=tk.X)
        ttk.Label(header, text=f"欢迎，{self.char_info['character_name']}！",
                  font=("Microsoft YaHei", 13, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text="退出登录", command=self._logout).pack(side=tk.RIGHT)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill=tk.BOTH, padx=8, pady=(0, 4))

        for cat in CATEGORIES:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=cat)
            self.tab_frames[cat] = frame

        statbar = ttk.Frame(self.root, padding=(10, 4))
        statbar.pack(fill=tk.X)
        status_text = f"数据加载完成 ({ok_count}/{total} 个端点成功)"
        if failed:
            names = ", ".join(k for k, _ in failed)
            status_text += f"  |  失败: {names}"
        ttk.Label(statbar, text=status_text, foreground="gray").pack(side=tk.LEFT)

        self._populate_tabs()

    def _logout(self):
        self.char_info = None
        self.all_data = None
        self.tab_frames = {}
        self._build_login_ui()

    # ── Populate tabs ─────────────────────────────────────────

    def _populate_tabs(self):
        d = self.all_data
        cid = self.char_info["character_id"]

        self._tab_overview(d, cid)
        self._tab_skills(d)
        self._tab_wallet(d)
        self._tab_assets(d)
        self._tab_ship(d)
        self._tab_clones(d)
        self._tab_mail(d)
        self._tab_market(d)
        self._tab_contracts(d)
        self._tab_killmails(d)
        self._tab_contacts(d)
        self._tab_corp(d)

    # ── Helper widgets ────────────────────────────────────────

    def _make_tree(self, parent, columns, col_widths=None, height=15):
        f = ttk.Frame(parent)
        f.pack(expand=True, fill=tk.BOTH)
        tree = ttk.Treeview(f, columns=columns, show="headings", height=height)
        for i, col in enumerate(columns):
            tree.heading(col, text=col)
            w = col_widths[i] if col_widths else 100
            tree.column(col, width=w, minwidth=40)
        sb = ttk.Scrollbar(f, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    def _clear_frame(self, frame):
        for w in frame.winfo_children():
            w.destroy()

    def _show_nodata(self, frame):
        self._clear_frame(frame)
        ttk.Label(frame, text="无数据或获取失败", foreground="gray").pack(expand=True)

    # ── Tab 1: 概览 ────────────────────────────────────────────

    def _tab_overview(self, d, cid):
        frame = self.tab_frames["概览"]
        self._clear_frame(frame)
        info = d.get("info")
        online = d.get("online")
        corp_hist = d.get("corp_history")
        standings = d.get("standings")
        fw = d.get("fw_stats")
        loyalty = d.get("loyalty")
        fatigue = d.get("fatigue")

        if not info:
            self._show_nodata(frame)
            return

        sde = self.sde

        text = tk.Text(frame, wrap=tk.WORD, font=("Microsoft YaHei", 10), padx=10, pady=10)
        text.pack(expand=True, fill=tk.BOTH)

        def w(s):
            text.insert(tk.END, s + "\n")

        def name_or(sde_fn, obj_id):
            if sde and obj_id:
                n = sde_fn(obj_id)
                return n if n else str(obj_id)
            return str(obj_id) if obj_id else "N/A"

        w(f"角色名: {info.get('name', 'N/A')}")
        w(f"Character ID: {cid}")
        w(f"生日: {info.get('birthday', 'N/A')}")
        w(f"安全等级: {info.get('security_status', 'N/A')}")
        w(f"性别: {info.get('gender', 'N/A')}")

        race_id = info.get('race_id')
        bloodline_id = info.get('bloodline_id')
        corp_id = info.get('corporation_id')
        alliance_id = info.get('alliance_id')
        faction_id = info.get('faction_id')

        if sde:
            w(f"种族: {name_or(sde.race_name, race_id)} (ID: {race_id})")
            w(f"血统: {name_or(sde.bloodline_name, bloodline_id)} (ID: {bloodline_id})")
            w(f"军团: {name_or(sde.corp_name, corp_id)} (ID: {corp_id})")
            w(f"联盟: {name_or(sde.item_name, alliance_id)} (ID: {alliance_id})")
            w(f"派系: {name_or(sde.faction_name, faction_id)} (ID: {faction_id})")
        else:
            w(f"种族ID: {race_id}")
            w(f"血统ID: {bloodline_id}")
            w(f"军团ID: {corp_id}")
            w(f"联盟ID: {alliance_id}")
            w(f"派系ID: {faction_id}")

        desc = info.get('description', '')
        if desc:
            w(f"描述: {desc}")
        w("")

        if online:
            w("[在线状态]")
            w(f"  在线: {'是' if online.get('online') else '否'}")
            w(f"  最后登录: {online.get('last_login', 'N/A')}")
            w(f"  登录次数: {online.get('logins', 'N/A')}")
            w("")

        if fatigue:
            w("[跳跃疲劳]")
            w(f"  疲劳到期: {fatigue.get('jump_fatigue_expire_date', 'N/A')}")
            w(f"  上次跳跃: {fatigue.get('last_jump_date', 'N/A')}")
            w(f"  上次更新: {fatigue.get('last_update_date', 'N/A')}")
            w("")

        if corp_hist:
            w("[军团历史]")
            for entry in corp_hist[:10]:
                cid_val = entry.get('corporation_id')
                corp_label = f"{name_or(sde.corp_name, cid_val)} (ID: {cid_val})" if sde else f"军团ID {cid_val}"
                w(f"  {corp_label}  开始: {entry.get('start_date')}  记录ID: {entry.get('record_id')}")
            w("")

        if standings:
            w("[声望]")
            for s_item in standings[:20]:
                from_type = s_item.get('from_type', '')
                from_id = s_item.get('from_id')
                if sde:
                    if from_type == 'npc_corp':
                        label = name_or(sde.corp_name, from_id)
                    elif from_type == 'faction':
                        label = name_or(sde.faction_name, from_id)
                    else:
                        label = str(from_id)
                    w(f"  {from_type} {label} → 值: {s_item.get('standing')}")
                else:
                    w(f"  {from_type} {from_id} → 值: {s_item.get('standing')}")
            w("")

        if fw:
            w("[势力战争]")
            fw_faction = fw.get('faction_id', 'N/A')
            w(f"  派系: {name_or(sde.faction_name, fw_faction)} (ID: {fw_faction})" if sde else f"  派系ID: {fw_faction}")
            w(f"  加入日期: {fw.get('enlisted_on', 'N/A')}")
            vp = fw.get("victory_points", {}) or {}
            w(f"  上周战绩: {vp.get('last_week', 'N/A')} | 总计: {vp.get('total', 'N/A')} | 昨日: {vp.get('yesterday', 'N/A')}")
            w("")

        if loyalty:
            w("[忠诚点数]")
            for lp in loyalty[:20]:
                lcid = lp.get('corporation_id')
                if sde:
                    corp_label = name_or(sde.corp_name, lcid)
                    w(f"  {corp_label} (ID: {lcid}): {lp.get('loyalty_points')} LP")
                else:
                    w(f"  军团ID {lcid}: {lp.get('loyalty_points')} LP")
            w("")

        text.config(state=tk.DISABLED)

    # ── Tab 2: 技能 ────────────────────────────────────────────

    def _tab_skills(self, d):
        frame = self.tab_frames["技能"]
        self._clear_frame(frame)
        attrs = d.get("attributes")
        skills = d.get("skills")
        queue = d.get("skillqueue")
        sde = self.sde

        if attrs:
            info = ttk.Frame(frame)
            info.pack(fill=tk.X, padx=8, pady=4)
            cols = ["魅力", "智力", "记忆", "感知", "毅力", "剩余重映射"]
            vals = [attrs.get('charisma'), attrs.get('intelligence'), attrs.get('memory'),
                    attrs.get('perception'), attrs.get('willpower'), attrs.get('bonus_remaps')]
            ttk.Label(info, text=" | ".join(f"{c}: {v}" for c, v in zip(cols, vals)),
                      font=("Microsoft YaHei", 10)).pack(anchor=tk.W)

        paned = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        paned.pack(expand=True, fill=tk.BOTH)

        f1 = ttk.LabelFrame(paned, text="已训练技能")
        paned.add(f1, weight=1)
        if skills and skills.get("skills"):
            tree = self._make_tree(f1, ["技能ID", "技能名称", "技能等级", "技能点数"], [80, 200, 80, 100], height=8)
            for s in skills["skills"]:
                sid = s["skill_id"]
                sname = sde.type_name(sid) if sde else ""
                tree.insert("", tk.END, values=(sid, sname or "", s["trained_skill_level"], s.get("active_skill_level", "")))
        else:
            ttk.Label(f1, text="无数据", foreground="gray").pack(expand=True)

        f2 = ttk.LabelFrame(paned, text="技能训练队列")
        paned.add(f2, weight=1)
        if queue:
            tree = self._make_tree(f2, ["技能ID", "技能名称", "目标等级", "开始时间", "结束时间", "位置"],
                                   [80, 180, 70, 130, 130, 50], height=6)
            for q in queue[:20]:
                qid = q.get("skill_id")
                qname = sde.type_name(qid) if sde else ""
                tree.insert("", tk.END, values=(
                    qid, qname or "", q.get("finished_level"),
                    q.get("start_date", ""), q.get("finish_date", ""),
                    q.get("queue_position")))
        else:
            ttk.Label(f2, text="无数据", foreground="gray").pack(expand=True)

    # ── Tab 3: 钱包 ────────────────────────────────────────────

    def _tab_wallet(self, d):
        frame = self.tab_frames["钱包"]
        self._clear_frame(frame)
        balance = d.get("wallet")
        journal = d.get("wallet_journal")
        transactions = d.get("wallet_transactions")

        if balance is not None:
            ttk.Label(frame, text=f"ISK 余额: {balance:,.2f}",
                      font=("Microsoft YaHei", 12, "bold")).pack(pady=4)

        paned = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        paned.pack(expand=True, fill=tk.BOTH)

        f1 = ttk.LabelFrame(paned, text="钱包流水")
        paned.add(f1, weight=1)
        if journal:
            tree = self._make_tree(f1, ["日期", "金额", "余额", "描述", "类型"], [130, 100, 100, 150, 80], height=8)
            for j in journal[:50]:
                tree.insert("", tk.END, values=(
                    j.get("date"), f"{j.get('amount', 0):,.2f}",
                    f"{j.get('balance', 0):,.2f}",
                    j.get("description", ""), j.get("ref_type")))
        else:
            ttk.Label(f1, text="无数据", foreground="gray").pack(expand=True)

        f2 = ttk.LabelFrame(paned, text="市场交易")
        paned.add(f2, weight=1)
        if transactions:
            sde = self.sde
            tree = self._make_tree(f2, ["日期", "数量", "单价", "交易类型", "物品ID", "物品名称"], [130, 60, 100, 70, 80, 180], height=8)
            for t in transactions[:50]:
                tid = t.get("type_id")
                tname = sde.type_name(tid) if sde else ""
                tree.insert("", tk.END, values=(
                    t.get("date"), t.get("quantity"),
                    f"{t.get('unit_price', 0):,.2f}",
                    "买入" if t.get("is_buy") else "卖出",
                    tid, tname or ""))
        else:
            ttk.Label(f2, text="无数据", foreground="gray").pack(expand=True)

    # ── Tab 4: 资产 ────────────────────────────────────────────

    def _tab_assets(self, d):
        frame = self.tab_frames["资产"]
        self._clear_frame(frame)
        assets = d.get("assets")
        if not assets:
            self._show_nodata(frame)
            return
        sde = self.sde
        tree = self._make_tree(frame, ["物品ID", "物品名称", "位置ID", "类型ID", "数量", "位置标识", "蓝图?"], [100, 200, 100, 80, 60, 120, 50], height=20)
        for a in assets[:200]:
            tid = a.get("type_id")
            fid = a.get("location_flag")
            tname = sde.type_name(tid) if sde else ""
            fname = sde.flag_name(fid) if sde else ""
            flag_text = f"{fname} ({fid})" if fname else fid
            tree.insert("", tk.END, values=(
                a.get("item_id"), tname or "", a.get("location_id"), tid,
                a.get("quantity"), flag_text,
                "是" if a.get("is_blueprint_copy") else ""))

    # ── Tab 5: 舰船 ────────────────────────────────────────────

    def _tab_ship(self, d):
        frame = self.tab_frames["舰船"]
        self._clear_frame(frame)
        ship = d.get("ship")
        location = d.get("location")
        fittings = d.get("fittings")
        sde = self.sde

        if ship or location:
            text = tk.Text(frame, height=4, font=("Microsoft YaHei", 10), padx=10, pady=6)
            text.pack(fill=tk.X)
            if ship:
                stid = ship.get('ship_type_id')
                sname = sde.type_name(stid) if sde else ""
                text.insert(tk.END, f"当前舰船: {sname} (type_id={stid}), name={ship.get('ship_name')}\n")
            if location:
                ssid = location.get('solar_system_id')
                ssname = sde.system_name(ssid) if sde else ""
                staid = location.get('station_id')
                staname = sde.station_name(staid) if sde else ""
                stuid = location.get('structure_id')
                stuname = sde.item_name(stuid) if sde else ""
                parts = []
                if ssid:
                    parts.append(f"星系: {ssname} (ID={ssid})" if ssname else f"solar_system_id={ssid}")
                if staid:
                    parts.append(f"空间站: {staname} (ID={staid})" if staname else f"station_id={staid}")
                if stuid:
                    parts.append(f"建筑: {stuname} (ID={stuid})" if stuname else f"structure_id={stuid}")
                text.insert(tk.END, f"当前位置: {' | '.join(parts)}\n")
            text.config(state=tk.DISABLED)

        if not fittings:
            ttk.Label(frame, text="装配方案: 无数据", foreground="gray").pack(expand=True)
            return
        tree = self._make_tree(frame, ["装配ID", "名称", "舰船类型ID", "舰船名称", "装备数"], [100, 180, 100, 180, 60], height=15)
        for fit in fittings[:50]:
            ftid = fit.get("ship_type_id")
            ftname = sde.type_name(ftid) if sde else ""
            items = fit.get("items", [])
            tree.insert("", tk.END, values=(fit.get("fitting_id"), fit.get("name"), ftid, ftname or "", len(items)))

    # ── Tab 6: 克隆 ────────────────────────────────────────────

    def _tab_clones(self, d):
        frame = self.tab_frames["克隆"]
        self._clear_frame(frame)
        clones = d.get("clones")
        implants = d.get("implants")

        if clones:
            text = tk.Text(frame, height=6, font=("Microsoft YaHei", 10), padx=10, pady=6)
            text.pack(fill=tk.X)
            text.insert(tk.END, f"home_location_id: {clones.get('home_location', {}).get('location_id')}\n")
            text.insert(tk.END, f"home_location_type: {clones.get('home_location', {}).get('location_type')}\n")
            text.insert(tk.END, f"最后克隆跳跃: {clones.get('last_clone_jump_date', 'N/A')}\n")
            text.insert(tk.END, f"最后空间站变更: {clones.get('last_station_change_date', 'N/A')}\n\n")
            text.insert(tk.END, "跳克隆列表:\n")
            for jc in clones.get("jump_clones", []):
                text.insert(tk.END, f"  location_id={jc.get('location_id')}, name={jc.get('name', 'N/A')}, "
                                    f"implants={jc.get('implants')}\n")
            text.config(state=tk.DISABLED)

        if implants:
            sde = self.sde
            tree = self._make_tree(frame, ["植入体 type_id", "名称"], [120, 250], height=10)
            for imp in implants:
                val = imp if isinstance(imp, int) else imp.get("type_id", imp)
                name = sde.type_name(val) if sde else ""
                tree.insert("", tk.END, values=(val, name or ""))
            tree.pack(expand=True, fill=tk.BOTH)

        if not clones and not implants:
            self._show_nodata(frame)

    # ── Tab 7: 邮件/通知 ────────────────────────────────────────

    def _tab_mail(self, d):
        frame = self.tab_frames["邮件/通知"]
        self._clear_frame(frame)
        mail = d.get("mail")
        notifications = d.get("notifications")

        paned = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        paned.pack(expand=True, fill=tk.BOTH)

        f1 = ttk.LabelFrame(paned, text="邮件")
        paned.add(f1, weight=1)
        if mail:
            tree = self._make_tree(f1, ["邮件ID", "发送者", "主题", "时间", "已读"], [100, 100, 200, 130, 50], height=8)
            for m in mail[:50]:
                tree.insert("", tk.END, values=(
                    m.get("mail_id"), m.get("from"), m.get("subject"),
                    m.get("timestamp"), "是" if m.get("is_read") else ""))
        else:
            ttk.Label(f1, text="无数据", foreground="gray").pack(expand=True)

        f2 = ttk.LabelFrame(paned, text="通知")
        paned.add(f2, weight=1)
        if notifications:
            tree = self._make_tree(f2, ["通知ID", "类型", "发送者", "时间", "已读"], [100, 150, 100, 130, 50], height=8)
            for n in notifications[:50]:
                tree.insert("", tk.END, values=(
                    n.get("notification_id"), n.get("type"),
                    n.get("sender_id"), n.get("timestamp"),
                    "是" if n.get("is_read") else ""))
        else:
            ttk.Label(f2, text="无数据", foreground="gray").pack(expand=True)

    # ── Tab 8: 市场/工业 ────────────────────────────────────────

    def _tab_market(self, d):
        frame = self.tab_frames["市场/工业"]
        self._clear_frame(frame)
        orders = d.get("orders")
        jobs = d.get("industry_jobs")
        mining = d.get("mining")
        sde = self.sde

        paned = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        paned.pack(expand=True, fill=tk.BOTH)

        f1 = ttk.LabelFrame(paned, text="市场订单")
        paned.add(f1, weight=1)
        if orders:
            tree = self._make_tree(f1, ["订单ID", "类型ID", "物品名称", "总量", "单价", "剩余", "买入?", "位置ID"], [80, 70, 180, 50, 90, 50, 50, 80], height=6)
            for o in orders[:50]:
                tid = o.get("type_id")
                tname = sde.type_name(tid) if sde else ""
                tree.insert("", tk.END, values=(
                    o.get("order_id"), tid, tname or "", o.get("volume_total"),
                    f"{o.get('price', 0):,.2f}", o.get("volume_remain"),
                    "买入" if o.get("is_buy_order") else "卖出", o.get("location_id")))
        else:
            ttk.Label(f1, text="无数据", foreground="gray").pack(expand=True)

        f2 = ttk.LabelFrame(paned, text="工业任务")
        paned.add(f2, weight=1)
        if jobs:
            tree = self._make_tree(f2, ["任务ID", "蓝图ID", "蓝图名称", "活动", "状态", "开始", "结束"], [80, 80, 180, 60, 60, 120, 120], height=6)
            for j in jobs[:50]:
                bid = j.get("blueprint_id")
                bname = sde.type_name(bid) if sde else ""
                tree.insert("", tk.END, values=(
                    j.get("job_id"), bid, bname or "", j.get("activity_type"),
                    j.get("status"), j.get("start_date"), j.get("end_date")))
        else:
            ttk.Label(f2, text="无数据", foreground="gray").pack(expand=True)

        f3 = ttk.LabelFrame(paned, text="采矿记录")
        paned.add(f3, weight=1)
        if mining:
            tree = self._make_tree(f3, ["日期", "太阳系ID", "星系名称", "类型ID", "物品名称", "数量"], [120, 80, 180, 70, 180, 50], height=6)
            for m in mining[:50]:
                ssid = m.get("solar_system_id")
                ssname = sde.system_name(ssid) if sde else ""
                tid = m.get("type_id")
                tname = sde.type_name(tid) if sde else ""
                tree.insert("", tk.END, values=(m.get("date"), ssid, ssname or "", tid, tname or "", m.get("quantity")))
        else:
            ttk.Label(f3, text="无数据", foreground="gray").pack(expand=True)

    # ── Tab 9: 合同/蓝图 ────────────────────────────────────────

    def _tab_contracts(self, d):
        frame = self.tab_frames["合同/蓝图"]
        self._clear_frame(frame)
        contracts = d.get("contracts")
        blueprints = d.get("blueprints")
        sde = self.sde

        paned = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        paned.pack(expand=True, fill=tk.BOTH)

        f1 = ttk.LabelFrame(paned, text="合同")
        paned.add(f1, weight=1)
        if contracts:
            tree = self._make_tree(f1, ["合同ID", "类型", "状态", "发起军团?", "接受者ID", "价格", "位置ID"],
                                   [80, 60, 60, 60, 70, 90, 90], height=8)
            for c in contracts[:50]:
                tree.insert("", tk.END, values=(
                    c.get("contract_id"), c.get("type"), c.get("status"),
                    "是" if c.get("issuer_corporation_id") else "否",
                    c.get("acceptor_id", ""),
                    f"{c.get('price', 0):,.2f}", c.get("start_location_id")))
        else:
            ttk.Label(f1, text="无数据", foreground="gray").pack(expand=True)

        f2 = ttk.LabelFrame(paned, text="蓝图")
        paned.add(f2, weight=1)
        if blueprints:
            tree = self._make_tree(f2, ["物品ID", "类型ID", "蓝图名称", "位置ID", "材料效率", "时间效率", "流程数"],
                                   [90, 80, 200, 90, 70, 70, 60], height=8)
            for b in blueprints[:50]:
                tid = b.get("type_id")
                tname = sde.type_name(tid) if sde else ""
                tree.insert("", tk.END, values=(
                    b.get("item_id"), tid, tname or "", b.get("location_id"),
                    b.get("material_efficiency"), b.get("time_efficiency"), b.get("runs")))
        else:
            ttk.Label(f2, text="无数据", foreground="gray").pack(expand=True)

    # ── Tab 10: 击杀记录 ────────────────────────────────────────

    def _tab_killmails(self, d):
        frame = self.tab_frames["击杀记录"]
        self._clear_frame(frame)
        kms = d.get("killmails")
        if not kms:
            self._show_nodata(frame)
            return
        sde = self.sde
        tree = self._make_tree(frame, ["击杀ID", "击杀船ID", "舰船名称", "总价值"], [110, 100, 220, 100], height=20)
        for km in kms[:50]:
            victim = km.get("victim", {}) or {}
            stid = victim.get("ship_type_id")
            stname = sde.type_name(stid) if sde else ""
            zkb = km.get("zkb", {}) or {}
            tree.insert("", tk.END, values=(
                km.get("killmail_id"), stid, stname or "",
                f"{zkb.get('totalValue', 0):,.2f}"))

    # ── Tab 11: 联系人 ─────────────────────────────────────────

    def _tab_contacts(self, d):
        frame = self.tab_frames["联系人"]
        self._clear_frame(frame)
        contacts = d.get("contacts")
        if not contacts:
            self._show_nodata(frame)
            return
        tree = self._make_tree(frame, ["联系人ID", "名称", "类型", "声望", "被阻拦", "被关注"],
                               [120, 120, 70, 60, 60, 60], height=20)
        for c in contacts[:100]:
            tree.insert("", tk.END, values=(
                c.get("contact_id"), c.get("contact_name", ""), c.get("contact_type"),
                c.get("standing"), "是" if c.get("is_blocked") else "",
                "是" if c.get("is_watched") else ""))

    # ── Tab 12: 军团 ────────────────────────────────────────────

    def _tab_corp(self, d):
        frame = self.tab_frames["军团"]
        self._clear_frame(frame)
        titles = d.get("titles")
        roles = d.get("roles")
        medals = d.get("medals")
        planets = d.get("planets")
        calendar = d.get("calendar")

        paned = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        paned.pack(expand=True, fill=tk.BOTH)

        f1 = ttk.LabelFrame(paned, text="头衔")
        paned.add(f1, weight=1)
        if titles:
            tree = self._make_tree(f1, ["头衔ID", "名称"], [150, 200], height=4)
            for t in titles:
                tree.insert("", tk.END, values=(t.get("title_id"), t.get("name")))
        else:
            ttk.Label(f1, text="无数据", foreground="gray").pack(expand=True)

        f2 = ttk.LabelFrame(paned, text="角色")
        paned.add(f2, weight=1)
        if roles:
            text = tk.Text(f2, height=4, font=("Microsoft YaHei", 10), padx=10, pady=6)
            text.pack(expand=True, fill=tk.BOTH)
            for rtype in ["roles", "roles_at_base", "roles_at_hq", "roles_at_other"]:
                rlist = roles.get(rtype, [])
                if rlist:
                    text.insert(tk.END, f"{rtype}: {rlist}\n")
            text.config(state=tk.DISABLED)
        else:
            ttk.Label(f2, text="无数据", foreground="gray").pack(expand=True)

        f3 = ttk.LabelFrame(paned, text="勋章")
        paned.add(f3, weight=1)
        if medals:
            tree = self._make_tree(f3, ["勋章ID", "名称", "描述", "颁发者", "日期"], [100, 150, 200, 100, 130], height=4)
            for m in medals[:20]:
                tree.insert("", tk.END, values=(
                    m.get("medal_id"), m.get("title"), m.get("description"),
                    m.get("issuer_id"), m.get("date")))
        else:
            ttk.Label(f3, text="无数据", foreground="gray").pack(expand=True)

        f4 = ttk.LabelFrame(paned, text="行星开发")
        paned.add(f4, weight=1)
        if planets:
            sde = self.sde
            tree = self._make_tree(f4, ["行星ID", "太阳系ID", "星系名称", "类型ID", "行星类型", "升级等级", "安装数量"],
                                   [80, 80, 180, 70, 180, 70, 70], height=4)
            for p in planets[:20]:
                ssid = p.get("solar_system_id")
                ssname = sde.system_name(ssid) if sde else ""
                ptid = p.get("planet_type")
                ptname = sde.type_name(ptid) if sde else ""
                tree.insert("", tk.END, values=(
                    p.get("planet_id"), ssid, ssname or "", ptid, ptname or "",
                    p.get("upgrade_level"), p.get("num_pins")))
        else:
            ttk.Label(f4, text="无数据", foreground="gray").pack(expand=True)

        f5 = ttk.LabelFrame(paned, text="日历")
        paned.add(f5, weight=1)
        if calendar:
            tree = self._make_tree(f5, ["事件ID", "标题", "日期", "持续时间(分钟)", "回复状态"],
                                   [100, 200, 130, 100, 80], height=4)
            for ev in calendar[:20]:
                tree.insert("", tk.END, values=(
                    ev.get("event_id"), ev.get("title"), ev.get("event_date"),
                    ev.get("duration"), ev.get("response")))
        else:
            ttk.Label(f5, text="无数据", foreground="gray").pack(expand=True)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()