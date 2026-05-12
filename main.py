import tkinter as tk
from tkinter import ttk, messagebox
import threading

import eve_auth

# 请在 https://developers.eveonline.com 注册应用后填入你的 Client ID
EVE_CLIENT_ID = "9905be5356d7420caf87bdd8b639f6f4"


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Python_AI")
        self.root.geometry("400x250")
        self.root.resizable(False, False)

        self.frame = ttk.Frame(root, padding=20)
        self.frame.pack(expand=True, fill=tk.BOTH)

        self.char_info = None
        self._build_ui()

    def _build_ui(self):
        for widget in self.frame.winfo_children():
            widget.destroy()

        if self.char_info:
            ttk.Label(
                self.frame,
                text=f"欢迎，{self.char_info['character_name']}！",
                font=("Microsoft YaHei", 14, "bold"),
            ).pack(pady=(0, 10))

            ttk.Label(
                self.frame,
                text=f"Character ID: {self.char_info['character_id']}",
                font=("Microsoft YaHei", 10),
            ).pack()

            ttk.Button(self.frame, text="退出登录", command=self._logout).pack(pady=20)
        else:
            ttk.Label(
                self.frame,
                text="Python_AI",
                font=("Microsoft YaHei", 16, "bold"),
            ).pack(pady=(0, 10))

            ttk.Label(
                self.frame,
                text="请登录以继续",
                font=("Microsoft YaHei", 12),
            ).pack()

            ttk.Button(
                self.frame,
                text="使用 EVE Online 登录",
                command=self._start_login,
            ).pack(pady=20)

            self.status_label = ttk.Label(self.frame, text="", foreground="gray")
            self.status_label.pack()

    def _start_login(self):
        if not EVE_CLIENT_ID:
            messagebox.showerror(
                "未配置 Client ID",
                "请先在 main.py 中设置 EVE_CLIENT_ID\n"
                "获取地址: https://developers.eveonline.com",
            )
            return

        self.status_label.config(text="正在打开浏览器，请完成授权...")
        thread = threading.Thread(target=self._do_login, daemon=True)
        thread.start()

    def _do_login(self):
        try:
            self.char_info = eve_auth.login(EVE_CLIENT_ID)
            self.root.after(0, self._build_ui)
        except Exception as e:
            import traceback
            with open("login_error.log", "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            self.root.after(0, lambda: self._show_error(f"登录失败: {type(e).__name__}: {e}"))

    def _show_error(self, msg):
        self.status_label.config(text=msg, foreground="red")

    def _logout(self):
        self.char_info = None
        self._build_ui()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
