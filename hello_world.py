import tkinter as tk
from tkinter import ttk


def main():
    root = tk.Tk()
    root.title("Python_AI")
    root.geometry("400x200")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=20)
    frame.pack(expand=True, fill=tk.BOTH)

    ttk.Label(
        frame,
        text="Hello world!",
        font=("Microsoft YaHei", 16, "bold")
    ).pack(pady=(0, 10))

    ttk.Label(
        frame,
        text="欢迎使用 Python_AI 项目！",
        font=("Microsoft YaHei", 12)
    ).pack()

    ttk.Button(frame, text="确定", command=root.destroy).pack(pady=20)

    root.mainloop()


if __name__ == "__main__":
    main()
