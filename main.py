import tkinter as tk
from tkinter import ttk, messagebox
import threading

import eve_auth

EVE_CLIENT_ID = "9905be5356d7420caf87bdd8b639f6f4"

CATEGORIES = [
    "概览", "技能", "钱包", "资产", "舰船", "克隆",
    "邮件/通知", "市场/工业", "合同/蓝图", "击杀记录", "联系人", "军团",
]


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Python_AI")
        self.root.geometry("900x650")
        self.root.resizable(True, True)

        self.char_info = None
        self.all_data = None
        self.notebook = None
        self.status_var = tk.StringVar(value="")
        self.tab_frames = {}

        self._build_login_ui()

    # ── Login UI ──────────────────────────────────────────────

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

    def _start_login(self):
        if not EVE_CLIENT_ID:
            messagebox.showerror("未配置 Client ID",
                "请先在 main.py 中设置 EVE_CLIENT_ID\n获取地址: https://developers.eveonline.com")
            return

        self.status_label.config(text="正在打开浏览器，请完成授权...")
        threading.Thread(target=self._do_login, daemon=True).start()

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

    def _on_login_success(self):
        self.root.geometry("900x650")
        self._build_main_ui()
        self.status_var.set("正在加载全部角色数据...")
        threading.Thread(target=self._fetch_all_data, daemon=True).start()

    # ── Main UI ───────────────────────────────────────────────

    def _clear_root(self):
        for w in self.root.winfo_children():
            w.destroy()

    def _build_main_ui(self):
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
            ttk.Label(frame, text="加载中...", foreground="gray").pack(expand=True)

        status_bar = ttk.Frame(self.root, padding=(10, 4))
        status_bar.pack(fill=tk.X)
        ttk.Label(status_bar, textvariable=self.status_var, foreground="gray").pack(side=tk.LEFT)

    def _logout(self):
        self.char_info = None
        self.all_data = None
        self.tab_frames = {}
        self._build_login_ui()

    # ── Data fetching ─────────────────────────────────────────

    def _fetch_all_data(self):
        self.all_data = eve_auth.fetch_all_character_data(self.char_info)
        self.root.after(0, self._populate_tabs)

    def _populate_tabs(self):
        if not self.all_data:
            return
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

        ok = sum(1 for v in d.values() if v is not None)
        self.status_var.set(f"数据加载完成 ({ok}/{len(d)} 个端点成功)")

    # ── Helper widgets ────────────────────────────────────────

    def _make_tree(self, parent, columns, col_widths=None, height=15):
        """Create a Treeview with scrollbar inside a frame."""
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
        info = d.get("基本信息")
        online = d.get("在线状态")
        corp_hist = d.get("军团历史")
        standings = d.get("声望")
        fw = d.get("势力战争")
        loyalty = d.get("忠诚点数")
        fatigue = d.get("跳跃疲劳")

        if not info:
            self._show_nodata(frame)
            return

        text = tk.Text(frame, wrap=tk.WORD, font=("Microsoft YaHei", 10), padx=10, pady=10)
        text.pack(expand=True, fill=tk.BOTH)

        def w(s):
            text.insert(tk.END, s + "\n")

        w(f"角色名: {info.get('name', 'N/A')}")
        w(f"Character ID: {cid}")
        w(f"生日: {info.get('birthday', 'N/A')}")
        w(f"性别: {info.get('gender', 'N/A')}")
        w(f"安全等级: {info.get('security_status', 'N/A')}")
        w(f"种族: {info.get('race_id', 'N/A')}")
        w(f"血统: {info.get('bloodline_id', 'N/A')}")
        w(f"军团ID: {info.get('corporation_id', 'N/A')}")
        w(f"联盟ID: {info.get('alliance_id', 'N/A')}")
        w(f"派系ID: {info.get('faction_id', 'N/A')}")
        w(f"描述: {info.get('description', '')}")
        w("")

        if online:
            w("[在线状态]")
            w(f"  在线: {'是' if online.get('online') else '否'}")
            w(f"  最后登录: {online.get('last_login', 'N/A')}")
            w(f"  登录次数: {online.get('logins', 'N/A')}")
            w("")

        if fatigue:
            w("[跳跃疲劳]")
            w(f"  跳跃疲劳值: {fatigue.get('jump_fatigue_expire_date', 'N/A')}")
            w(f"  上次跳跃: {fatigue.get('last_jump_date', 'N/A')}")
            w(f"  上次更新: {fatigue.get('last_update_date', 'N/A')}")
            w("")

        if corp_hist:
            w("[军团历史]")
            for entry in corp_hist[:10]:
                w(f"  军团ID {entry.get('corporation_id')}  开始: {entry.get('start_date')}  (记录ID: {entry.get('record_id')})")
            w("")

        if standings:
            w("[声望]")
            for s in standings[:20]:
                w(f"  {s.get('from_type', 'N/A')} {s.get('from_id')} → 值: {s.get('standing')}")
            w("")

        if fw:
            w("[势力战争]")
            w(f"  派系ID: {fw.get('faction_id', 'N/A')}")
            w(f"  加入日期: {fw.get('enlisted_on', 'N/A')}")
            if fw.get("victory_points"):
                vp = fw["victory_points"]
                w(f"  上周战绩: {vp.get('last_week', 'N/A')} | 总计: {vp.get('total', 'N/A')} | 昨日: {vp.get('yesterday', 'N/A')}")
            w("")

        if loyalty:
            w("[忠诚点数]")
            for lp in loyalty[:20]:
                w(f"  军团ID {lp.get('corporation_id')}: {lp.get('loyalty_points')} LP")
            w("")

        text.config(state=tk.DISABLED)

    # ── Tab 2: 技能 ────────────────────────────────────────────

    def _tab_skills(self, d):
        frame = self.tab_frames["技能"]
        self._clear_frame(frame)
        attrs = d.get("角色属性")
        skills = d.get("技能列表")
        queue = d.get("技能队列")

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

        # Skills
        f1 = ttk.LabelFrame(paned, text="已训练技能")
        paned.add(f1, weight=1)
        if skills and skills.get("skills"):
            tree = self._make_tree(f1, ["技能ID", "技能等级", "技能点数"], [140, 80, 100], height=8)
            for s in skills["skills"]:
                tree.insert("", tk.END, values=(s["skill_id"], s["trained_skill_level"], s.get("active_skill_level", "")))
        else:
            ttk.Label(f1, text="无数据", foreground="gray").pack(expand=True)

        # Skill queue
        f2 = ttk.LabelFrame(paned, text="技能训练队列")
        paned.add(f2, weight=1)
        if queue:
            tree = self._make_tree(f2, ["技能ID", "目标等级", "开始时间", "结束时间", "位置"], [140, 70, 130, 130, 50], height=6)
            for q in queue[:20]:
                tree.insert("", tk.END, values=(
                    q.get("skill_id"), q.get("finished_level"),
                    q.get("start_date", ""), q.get("finish_date", ""),
                    q.get("queue_position")))
        else:
            ttk.Label(f2, text="无数据", foreground="gray").pack(expand=True)

    # ── Tab 3: 钱包 ────────────────────────────────────────────

    def _tab_wallet(self, d):
        frame = self.tab_frames["钱包"]
        self._clear_frame(frame)
        balance = d.get("钱包余额")
        journal = d.get("钱包流水")
        transactions = d.get("钱包交易")

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
            tree = self._make_tree(f2, ["日期", "数量", "单价", "交易类型", "物品ID"], [130, 60, 100, 70, 100], height=8)
            for t in transactions[:50]:
                tree.insert("", tk.END, values=(
                    t.get("date"), t.get("quantity"),
                    f"{t.get('unit_price', 0):,.2f}",
                    "买入" if t.get("is_buy") else "卖出",
                    t.get("type_id")))
        else:
            ttk.Label(f2, text="无数据", foreground="gray").pack(expand=True)

    # ── Tab 4: 资产 ────────────────────────────────────────────

    def _tab_assets(self, d):
        frame = self.tab_frames["资产"]
        self._clear_frame(frame)
        assets = d.get("资产列表")
        if not assets:
            self._show_nodata(frame)
            return
        tree = self._make_tree(frame, ["物品ID", "位置ID", "类型ID", "数量", "位置标识", "蓝图?"], [120, 120, 100, 60, 150, 60], height=20)
        for a in assets[:200]:
            tree.insert("", tk.END, values=(
                a.get("item_id"), a.get("location_id"), a.get("type_id"),
                a.get("quantity"), a.get("location_flag"),
                "是" if a.get("is_blueprint_copy") else ""))

    # ── Tab 5: 舰船 ────────────────────────────────────────────

    def _tab_ship(self, d):
        frame = self.tab_frames["舰船"]
        self._clear_frame(frame)
        ship = d.get("当前舰船")
        location = d.get("当前位置")
        fittings = d.get("舰船装配")

        if ship or location:
            text = tk.Text(frame, height=4, font=("Microsoft YaHei", 10), padx=10, pady=6)
            text.pack(fill=tk.X)
            if ship:
                text.insert(tk.END, f"当前舰船: type_id={ship.get('ship_type_id')}, name={ship.get('ship_name')}\n")
            if location:
                text.insert(tk.END, f"当前位置: solar_system_id={location.get('solar_system_id')}, "
                                    f"station_id={location.get('station_id')}, "
                                    f"structure_id={location.get('structure_id')}\n")
            text.config(state=tk.DISABLED)

        if not fittings:
            ttk.Label(frame, text="装配方案: 无数据", foreground="gray").pack(expand=True)
            return
        tree = self._make_tree(frame, ["装配ID", "名称", "舰船类型ID", "装备数"], [120, 200, 120, 60], height=15)
        for fit in fittings[:50]:
            items = fit.get("items", [])
            tree.insert("", tk.END, values=(
                fit.get("fitting_id"), fit.get("name"), fit.get("ship_type_id"), len(items)))

    # ── Tab 6: 克隆 ────────────────────────────────────────────

    def _tab_clones(self, d):
        frame = self.tab_frames["克隆"]
        self._clear_frame(frame)
        clones = d.get("克隆状态")
        implants = d.get("植入体")

        if clones:
            text = tk.Text(frame, height=6, font=("Microsoft YaHei", 10), padx=10, pady=6)
            text.pack(fill=tk.X)
            text.insert(tk.END, f"home_location_id: {clones.get('home_location', {}).get('location_id')}\n")
            text.insert(tk.END, f"home_location_type: {clones.get('home_location', {}).get('location_type')}\n")
            text.insert(tk.END, f"最后克隆跳跃: {clones.get('last_clone_jump_date', 'N/A')}\n")
            text.insert(tk.END, f"最后空间站变更: {clones.get('last_station_change_date', 'N/A')}\n\n")
            text.insert(tk.END, "跳克隆列表:\n")
            for jc in clones.get("jump_clones", []):
                text.insert(tk.END, f"  location_id={jc.get('location_id')}, "
                                    f"name={jc.get('name', 'N/A')}, "
                                    f"implants={jc.get('implants')}\n")
            text.config(state=tk.DISABLED)

        if implants:
            tree = self._make_tree(frame, ["植入体 type_id"], [150], height=10)
            for imp in implants:
                if isinstance(imp, int):
                    tree.insert("", tk.END, values=(imp,))
                elif isinstance(imp, dict):
                    tree.insert("", tk.END, values=(imp.get("type_id", imp),))
            tree.pack(expand=True, fill=tk.BOTH)

        if not clones and not implants:
            self._show_nodata(frame)

    # ── Tab 7: 邮件/通知 ────────────────────────────────────────

    def _tab_mail(self, d):
        frame = self.tab_frames["邮件/通知"]
        self._clear_frame(frame)
        mail = d.get("邮件")
        notifications = d.get("通知")

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
        orders = d.get("市场订单")
        jobs = d.get("工业任务")
        mining = d.get("采矿")

        paned = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        paned.pack(expand=True, fill=tk.BOTH)

        f1 = ttk.LabelFrame(paned, text="市场订单")
        paned.add(f1, weight=1)
        if orders:
            tree = self._make_tree(f1, ["订单ID", "类型ID", "数量", "单价", "剩余", "买入?", "位置ID"], [100, 100, 50, 100, 50, 50, 100], height=6)
            for o in orders[:50]:
                tree.insert("", tk.END, values=(
                    o.get("order_id"), o.get("type_id"), o.get("volume_total"),
                    f"{o.get('price', 0):,.2f}", o.get("volume_remain"),
                    "买入" if o.get("is_buy_order") else "卖出", o.get("location_id")))
        else:
            ttk.Label(f1, text="无数据", foreground="gray").pack(expand=True)

        f2 = ttk.LabelFrame(paned, text="工业任务")
        paned.add(f2, weight=1)
        if jobs:
            tree = self._make_tree(f2, ["任务ID", "蓝图ID", "活动", "状态", "开始", "结束"], [100, 100, 70, 70, 130, 130], height=6)
            for j in jobs[:50]:
                tree.insert("", tk.END, values=(
                    j.get("job_id"), j.get("blueprint_id"), j.get("activity_type"),
                    j.get("status"), j.get("start_date"), j.get("end_date")))
        else:
            ttk.Label(f2, text="无数据", foreground="gray").pack(expand=True)

        f3 = ttk.LabelFrame(paned, text="采矿记录")
        paned.add(f3, weight=1)
        if mining:
            tree = self._make_tree(f3, ["日期", "太阳系ID", "类型ID", "数量"], [130, 100, 100, 60], height=6)
            for m in mining[:50]:
                tree.insert("", tk.END, values=(m.get("date"), m.get("solar_system_id"),
                                                 m.get("type_id"), m.get("quantity")))
        else:
            ttk.Label(f3, text="无数据", foreground="gray").pack(expand=True)

    # ── Tab 9: 合同/蓝图 ────────────────────────────────────────

    def _tab_contracts(self, d):
        frame = self.tab_frames["合同/蓝图"]
        self._clear_frame(frame)
        contracts = d.get("合同")
        blueprints = d.get("蓝图")

        paned = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        paned.pack(expand=True, fill=tk.BOTH)

        f1 = ttk.LabelFrame(paned, text="合同")
        paned.add(f1, weight=1)
        if contracts:
            tree = self._make_tree(f1, ["合同ID", "类型", "状态", "发出者", "接受者", "价格", "位置ID"],
                                   [100, 70, 70, 70, 70, 100, 100], height=8)
            for c in contracts[:50]:
                tree.insert("", tk.END, values=(
                    c.get("contract_id"), c.get("type"), c.get("status"),
                    "是" if c.get("issuer_corporation_id") else "否",
                    "是" if c.get("acceptor_id") else "",
                    f"{c.get('price', 0):,.2f}", c.get("start_location_id")))
        else:
            ttk.Label(f1, text="无数据", foreground="gray").pack(expand=True)

        f2 = ttk.LabelFrame(paned, text="蓝图")
        paned.add(f2, weight=1)
        if blueprints:
            tree = self._make_tree(f2, ["物品ID", "类型ID", "位置ID", "材料效率", "时间效率", "流程数"],
                                   [100, 100, 100, 80, 80, 60], height=8)
            for b in blueprints[:50]:
                tree.insert("", tk.END, values=(
                    b.get("item_id"), b.get("type_id"), b.get("location_id"),
                    b.get("material_efficiency"), b.get("time_efficiency"), b.get("runs")))
        else:
            ttk.Label(f2, text="无数据", foreground="gray").pack(expand=True)

    # ── Tab 10: 击杀记录 ────────────────────────────────────────

    def _tab_killmails(self, d):
        frame = self.tab_frames["击杀记录"]
        self._clear_frame(frame)
        kms = d.get("击杀记录")
        if not kms:
            self._show_nodata(frame)
            return
        tree = self._make_tree(frame, ["击杀ID", "击杀船ID", "击杀船名称", "总价值"], [120, 120, 120, 100], height=20)
        for km in kms[:50]:
            tree.insert("", tk.END, values=(
                km.get("killmail_id"), km.get("victim", {}).get("ship_type_id"),
                km.get("victim", {}).get("ship_name", ""),
                f"{km.get('zkb', {}).get('totalValue', 0):,.2f}"))

    # ── Tab 11: 联系人 ─────────────────────────────────────────

    def _tab_contacts(self, d):
        frame = self.tab_frames["联系人"]
        self._clear_frame(frame)
        contacts = d.get("联系人")
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
        titles = d.get("头衔")
        roles = d.get("军团角色")
        medals = d.get("勋章")
        planets = d.get("行星开发")
        calendar = d.get("日历")

        paned = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        paned.pack(expand=True, fill=tk.BOTH)

        f1 = ttk.LabelFrame(paned, text="军团头衔")
        paned.add(f1, weight=1)
        if titles:
            tree = self._make_tree(f1, ["头衔ID", "名称"], [150, 200], height=4)
            for t in titles:
                tree.insert("", tk.END, values=(t.get("title_id"), t.get("name")))
        else:
            ttk.Label(f1, text="无数据", foreground="gray").pack(expand=True)

        f2 = ttk.LabelFrame(paned, text="军团角色")
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
            tree = self._make_tree(f4, ["行星ID", "太阳系ID", "类型ID", "升级等级", "安装数量"],
                                   [100, 100, 100, 80, 80], height=4)
            for p in planets[:20]:
                tree.insert("", tk.END, values=(
                    p.get("planet_id"), p.get("solar_system_id"), p.get("planet_type"),
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