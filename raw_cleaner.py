import os
import sys
import queue
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


RAW_EXTENSIONS = {
    ".arw", ".sr2", ".srf", ".raw", ".nef", ".nrw", ".cr2", ".cr3", ".crw",
    ".dng", ".raf", ".orf", ".rw2", ".rwl", ".pef", ".ptx", ".srw", ".x3f",
    ".gpr", ".3fr", ".fff", ".iiq", ".kdc", ".mdc", ".mef", ".mos", ".mrw",
    ".ori", ".rwz",
}

JPG_EXTENSIONS = {".jpg", ".jpeg"}

MOVE_FOLDER_NAME = "待删除RAW"

# ---- palette -------------------------------------------------------------
BG = "#eef1f7"
CARD = "#ffffff"
TEXT = "#2b3040"
SUBTLE = "#8a92a6"
BLUE = "#3b82f6"
BLUE_DARK = "#2563eb"
RED = "#ef4444"
RED_DARK = "#c02626"
GREEN = "#10b981"
SHADOW = "#d5dae6"


def iter_files(folder, recursive):
    if recursive:
        for root, _dirs, files in os.walk(folder):
            for name in files:
                yield os.path.join(root, name)
    else:
        try:
            with os.scandir(folder) as it:
                for entry in it:
                    if entry.is_file():
                        yield entry.path
        except OSError:
            pass


def scan(folder, recursive):
    """Return (orphans, raw_total). orphans = RAW files with no same-stem jpg."""
    raw_by_dir = {}
    jpg_stems = {}
    for path in iter_files(folder, recursive):
        d = os.path.dirname(path)
        ext = os.path.splitext(path)[1].lower()
        stem = os.path.splitext(os.path.basename(path))[0].lower()
        if ext in RAW_EXTENSIONS:
            raw_by_dir.setdefault(d, []).append((stem, path))
        elif ext in JPG_EXTENSIONS:
            jpg_stems.setdefault(d, set()).add(stem)

    orphans = []
    raw_total = 0
    for d, items in raw_by_dir.items():
        present = jpg_stems.get(d, set())
        for stem, path in items:
            raw_total += 1
            if stem not in present:
                orphans.append(path)
    return orphans, raw_total


def recycle_delete(paths, use_recycle):
    """Delete a list of files. If use_recycle, send to Recycle Bin via shell API."""
    deleted, errors = 0, []
    if use_recycle and sys.platform.startswith("win"):
        ok = _shell_delete(paths)
        if ok is True:
            return len(paths), []
        if ok is False:
            errors.append("回收站操作失败，已改为直接删除")
    for p in paths:
        try:
            os.remove(p)
            deleted += 1
        except OSError as e:
            errors.append(f"{os.path.basename(p)}: {e.strerror}")
    return deleted, errors


def _shell_delete(paths):
    try:
        import ctypes
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("wFunc", ctypes.c_uint),
                ("pFrom", ctypes.c_wchar_p),
                ("pTo", ctypes.c_wchar_p),
                ("fFlags", ctypes.c_uint16),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", ctypes.c_wchar_p),
            ]

        FO_DELETE = 3
        FOF_ALLOWUNDO = 0x40
        FOF_NOCONFIRMATION = 0x10
        FOF_SILENT = 0x4
        buf = "\0".join(paths) + "\0\0"
        op = SHFILEOPSTRUCTW(
            None, FO_DELETE, buf, None,
            FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT,
            False, None, None,
        )
        res = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        return res == 0 and not op.fAnyOperationsAborted
    except Exception:
        return None


def move_to_trash_folder(orphans, folder):
    """Create MOVE_FOLDER_NAME in folder and move orphan RAW files into it.
    Files are grouped by their own directory's subfolder so recursion stays tidy."""
    target_root = os.path.join(folder, MOVE_FOLDER_NAME)
    moved, errors = 0, []
    for src in orphans:
        try:
            rel = os.path.relpath(os.path.dirname(src), folder)
            dest_dir = target_root if rel == "." else os.path.join(target_root, rel)
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, os.path.basename(src))
            if os.path.exists(dest):
                base, ext = os.path.splitext(os.path.basename(src))
                i = 1
                while os.path.exists(dest):
                    dest = os.path.join(dest_dir, f"{base}_{i}{ext}")
                    i += 1
            shutil.move(src, dest)
            moved += 1
        except (OSError, ValueError) as e:
            errors.append(f"{os.path.basename(src)}: {e}")
    return moved, errors


class QButton(tk.Canvas):
    """Bouncy rounded button with press/hover visual feedback."""

    def __init__(self, master, text, sub="", color=BLUE, color_dark=BLUE_DARK,
                 command=None, width=230, height=96):
        super().__init__(master, width=width, height=height, bg=BG,
                         highlightthickness=0, bd=0)
        self.command = command
        self.color = color
        self.color_dark = color_dark
        self.text = text
        self.sub = sub
        self.w, self.h = width, height
        self.state = "normal"  # normal | hover | press | disabled
        self._radius = 20
        self.bind("<Enter>", lambda e: self._set("hover"))
        self.bind("<Leave>", lambda e: self._set("normal"))
        self.bind("<ButtonPress-1>", lambda e: self._set("press"))
        self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def _set(self, s):
        if self.state == "disabled":
            return
        self.state = s
        self._draw()

    def configure_state(self, enabled):
        self.state = "normal" if enabled else "disabled"
        self._draw()

    def _release(self, event):
        inside = (0 <= event.x <= self.w) and (0 <= event.y <= self.h)
        self._set("hover" if inside else "normal")
        if inside and self.state != "disabled" and self.command:
            self.command()

    def _fill(self):
        if self.state == "disabled":
            return "#cfd4df"
        if self.state == "press":
            return self.color_dark
        if self.state == "hover":
            return self._lighten(self.color)
        return self.color

    @staticmethod
    def _lighten(hexcolor):
        r, g, b = (int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))
        r, g, b = (min(255, int(c + (255 - c) * 0.15)) for c in (r, g, b))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self):
        self.delete("all")
        pressed = self.state == "press"
        off = 3 if pressed else 0
        shadow_y = self.h - 6
        if not pressed and self.state != "disabled":
            self._round_rect(6, 8, self.w - 6, shadow_y + 4, self._radius,
                             fill=SHADOW, outline="")
        top = 4 + off
        bottom = self.h - 8 + off
        self._round_rect(6, top, self.w - 6, bottom, self._radius,
                         fill=self._fill(), outline="")
        fg = "#ffffff" if self.state != "disabled" else "#9aa0ae"
        ty = self.h / 2 - (10 if self.sub else 0) + off
        weight = "bold" if self.state != "disabled" else "normal"
        self.create_text(self.w / 2, ty, text=self.text, fill=fg,
                         font=("Microsoft YaHei UI", 15, weight))
        if self.sub:
            self.create_text(self.w / 2, ty + 24, text=self.sub,
                             fill="#e8edff" if self.state != "disabled" else "#b4b9c4",
                             font=("Microsoft YaHei UI", 9))


class App:
    def __init__(self, root):
        self.root = root
        self.folder = tk.StringVar(value="")
        self.recursive = tk.BooleanVar(value=False)
        self.use_recycle = tk.BooleanVar(value=True)
        self.busy = False
        self.q = queue.Queue()
        self._build()
        root.after(80, self._poll)

    def _build(self):
        r = self.root
        r.title("RAW 废片清理工具")
        r.configure(bg=BG)
        r.geometry("620x520")
        r.minsize(560, 480)

        head = tk.Frame(r, bg=BG)
        head.pack(fill="x", padx=26, pady=(22, 6))
        tk.Label(head, text="RAW 废片清理工具", bg=BG, fg=TEXT,
                 font=("Microsoft YaHei UI", 20, "bold")).pack(anchor="w")
        tk.Label(head, text="用 JPG 选完片后，一键清理对应的 RAW 废片",
                 bg=BG, fg=SUBTLE, font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(2, 0))

        card = tk.Frame(r, bg=CARD, highlightbackground=SHADOW, highlightthickness=1)
        card.pack(fill="x", padx=26, pady=14)

        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=16, pady=(16, 8))
        self._flat_button(row, "选择文件夹…", BLUE, self._choose_folder).pack(side="left")
        self.path_label = tk.Label(row, text="尚未选择文件夹", bg=CARD, fg=SUBTLE,
                                   font=("Microsoft YaHei UI", 10), anchor="w")
        self.path_label.pack(side="left", fill="x", expand=True, padx=(12, 0))

        opt = tk.Frame(card, bg=CARD)
        opt.pack(fill="x", padx=16, pady=(4, 14))
        self._check(opt, "包含子文件夹（递归处理）", self.recursive).pack(side="left")
        self._check(opt, "剔除时移入回收站", self.use_recycle).pack(side="left", padx=(24, 0))

        btns = tk.Frame(r, bg=BG)
        btns.pack(fill="x", padx=26, pady=6)
        self.btn_select = QButton(btns, "选出 RAW", "新建“待删除RAW”并移入",
                                  GREEN, "#059669", command=lambda: self._start("select"),
                                  width=280, height=96)
        self.btn_select.pack(side="left", expand=True, fill="x", padx=(0, 10))
        self.btn_purge = QButton(btns, "剔除 RAW", "直接删除无对应 JPG 的 RAW",
                                 RED, RED_DARK, command=lambda: self._start("purge"),
                                 width=280, height=96)
        self.btn_purge.pack(side="left", expand=True, fill="x", padx=(10, 0))

        self.progress = ttk.Progressbar(r, mode="determinate", length=560)
        self.progress.pack(padx=26, pady=(14, 4), fill="x")

        self.status = tk.Label(r, text="就绪：请先选择文件夹", bg=BG, fg=TEXT,
                               font=("Microsoft YaHei UI", 10), anchor="w", justify="left")
        self.status.pack(fill="x", padx=28, pady=(2, 16))

        self._style_progress()

    def _style_progress(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("green.Horizontal.TProgressbar", troughcolor=SHADOW,
                        background=GREEN, thickness=10, bordercolor=SHADOW, lightcolor=GREEN,
                        darkcolor=GREEN)
        self.progress.configure(style="green.Horizontal.TProgressbar")

    def _flat_button(self, parent, text, color, command):
        b = tk.Button(parent, text=text, command=command, bg=color, fg="white",
                      activebackground=self._dark(color), relief="flat", bd=0,
                      font=("Microsoft YaHei UI", 10, "bold"), padx=16, pady=7, cursor="hand2")
        return b

    @staticmethod
    def _dark(hexcolor):
        r, g, b = (int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))
        return f"#{max(0, r - 30):02x}{max(0, g - 30):02x}{max(0, b - 30):02x}"

    def _check(self, parent, text, var):
        return tk.Checkbutton(parent, text=text, variable=var, bg=CARD, fg=TEXT,
                              selectcolor="white", activebackground=CARD,
                              font=("Microsoft YaHei UI", 10))

    def _choose_folder(self):
        path = filedialog.askdirectory(title="选择要处理的文件夹")
        if path:
            self.folder.set(path)
            self.path_label.config(text=path, fg=TEXT)
            self._set_status("文件夹已选择，可以开始处理")

    def _set_status(self, msg):
        self.status.config(text=msg)

    def _set_buttons(self, enabled):
        self.btn_select.configure_state(enabled)
        self.btn_purge.configure_state(enabled)

    def _start(self, mode):
        if self.busy:
            return
        folder = self.folder.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("提示", "请先选择一个有效的文件夹")
            return
        orphans, raw_total = scan(folder, self.recursive.get())
        if raw_total == 0:
            messagebox.showinfo("结果", "该文件夹中没有找到任何 RAW 文件")
            return
        if not orphans:
            messagebox.showinfo("结果", f"共扫描 {raw_total} 个 RAW 文件，全部都有对应 JPG，无需处理 🎉")
            return
        if mode == "purge":
            verb = "移入回收站" if self.use_recycle.get() else "永久删除"
            msg = (f"将{verb} {len(orphans)} 个没有对应 JPG 的 RAW 文件。\n\n"
                   f"（共扫描 {raw_total} 个 RAW）\n\n确定继续吗？")
            if not messagebox.askyesno("确认剔除", msg, icon="warning"):
                return
        else:
            confirm = (f"将把 {len(orphans)} 个没有对应 JPG 的 RAW 文件\n"
                       f"移入新建文件夹「{MOVE_FOLDER_NAME}」。\n\n"
                       f"（共扫描 {raw_total} 个 RAW）\n\n确定继续吗？")
            if not messagebox.askyesno("确认选出", confirm):
                return

        self.busy = True
        self._set_buttons(False)
        self.progress.config(maximum=max(1, len(orphans)), value=0)
        self._set_status("处理中…")
        t = threading.Thread(target=self._worker, args=(mode, folder, orphans, raw_total), daemon=True)
        t.start()

    def _worker(self, mode, folder, orphans, raw_total):
        try:
            if mode == "select":
                done, errors = move_to_trash_folder(orphans, folder)
                detail = f"已移动 {done} 个 RAW 到「{MOVE_FOLDER_NAME}」"
            else:
                done, errors = recycle_delete(orphans, self.use_recycle.get())
                detail = f"已删除 {done} 个 RAW 文件"
            self.q.put(("finish", detail, errors, raw_total))
        except Exception as e:
            self.q.put(("error", str(e)))

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "progress":
                    self.progress.config(value=msg[1])
                elif msg[0] == "finish":
                    _kind, detail, errors, raw_total = msg
                    self.progress.config(value=self.progress["maximum"])
                    self._set_status(
                        f"完成：{detail}｜共 {raw_total} 个 RAW" +
                        (f"｜{len(errors)} 个出错" if errors else "")
                    )
                    self.busy = False
                    self._set_buttons(True)
                    if errors:
                        messagebox.showwarning("部分完成",
                                               detail + "\n\n以下文件处理失败：\n" +
                                               "\n".join(errors[:12]))
                    else:
                        messagebox.showinfo("完成", detail)
                elif msg[0] == "error":
                    self._set_status("出错：" + msg[1])
                    self.busy = False
                    self._set_buttons(True)
                    messagebox.showerror("错误", msg[1])
        except queue.Empty:
            pass
        self.root.after(80, self._poll)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
