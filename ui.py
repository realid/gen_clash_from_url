#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import queue
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

from tkinter import (
    Tk,
    StringVar,
    BooleanVar,
    Text,
    Canvas,
    Entry,
    Frame,
    Label,
    messagebox,
)
from tkinter import filedialog, font as tkfont

from core import InternalError, generate_from_url

try:
    import ttkbootstrap as tb
    from ttkbootstrap import ttk
    TTKBOOTSTRAP = True
except Exception:
    import tkinter.ttk as ttk
    TTKBOOTSTRAP = False

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

try:
    import pystray
    TRAY_AVAILABLE = True
except Exception:
    TRAY_AVAILABLE = False

try:
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory, NSApplicationActivationPolicyRegular
    DOCK_API_AVAILABLE = True
except Exception:
    DOCK_API_AVAILABLE = False


def run_gui(default_output: str) -> int:
    if TTKBOOTSTRAP:
        root = tb.Window(themename="yeti")
    else:
        root = Tk()
    root.title("JMS 订阅管家")
    root.resizable(True, True)
    root.geometry("900x720")
    root.minsize(600, 450)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    base_font = tkfont.Font(family="SF Pro Text", size=10)
    if base_font.actual("family") != "SF Pro Text":
        base_font = tkfont.Font(family="PingFang SC", size=12)
    small_font = tkfont.Font(family=base_font.actual("family"), size=11)
    title_font = tkfont.Font(family=base_font.actual("family"), size=12, weight="bold")

    style = ttk.Style()
    if TTKBOOTSTRAP:
        try:
            style.theme_use("clam")
        except Exception:
            pass
    mac_bg = "#f2f2f7"
    mac_border = "#c7c7cc"
    mac_text = "#1c1c1e"
    mac_field_bg = "#ffffff"
    mac_button_bg = "#efeff4"
    mac_button_hover = "#e5e5ea"
    mac_button_active = "#dcdce0"
    style.configure("TLabel", font=base_font, background=mac_bg)
    style.configure("TButton", font=base_font, padding=(8, 2))
    style.configure("TEntry", font=base_font, padding=(6, 2))
    style.configure("TLabelframe", background=mac_bg)
    style.configure("TLabelframe.Label", font=title_font, background=mac_bg)
    style.configure("TNotebook", background=mac_bg)
    style.configure("TNotebook.Tab", font=small_font, padding=(8, 4))
    if TTKBOOTSTRAP:
        style.configure(
            "Mac.TButton",
            background="#e9e9eb",
            foreground="#1c1c1e",
            bordercolor="#c7c7cc",
            focusthickness=0,
            padding=(8, 2),
        )
        style.map(
            "Mac.TButton",
            background=[("active", "#dedee2"), ("pressed", "#d1d1d6")],
            foreground=[("disabled", "#8e8e93")],
        )

    icon_cache: Dict[str, object] = {}

    def make_icon(kind: str, size: int = 14) -> Optional[object]:
        if not PIL_AVAILABLE:
            return None
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        stroke = max(1, size // 9)
        inset = stroke + 2

        if kind == "generate":
            pts = [
                (size * 0.55, inset),
                (size * 0.25, size * 0.55),
                (size * 0.52, size * 0.55),
                (size * 0.35, size - inset),
                (size * 0.75, size * 0.42),
                (size * 0.5, size * 0.42),
            ]
            d.line(pts, fill="black", width=stroke, joint="curve")
        elif kind == "save":
            d.rectangle((inset, inset, size - inset, size - inset), outline="black", width=stroke)
            d.rectangle((inset + 2, inset + 2, size - inset - 2, size * 0.45),
                        outline="black", width=stroke)
        elif kind == "download":
            d.rectangle((inset, size * 0.6, size - inset, size - inset),
                        outline="black", width=stroke)
            d.line((size * 0.5, inset, size * 0.5, size * 0.6),
                   fill="black", width=stroke)
            d.polygon([(size * 0.35, size * 0.45),
                       (size * 0.65, size * 0.45),
                       (size * 0.5, size * 0.62)],
                      outline="black", fill="black")
        elif kind == "cloud":
            d.ellipse((size * 0.15, size * 0.4, size * 0.45, size * 0.7),
                      outline="black", width=stroke)
            d.ellipse((size * 0.35, size * 0.28, size * 0.7, size * 0.72),
                      outline="black", width=stroke)
            d.ellipse((size * 0.6, size * 0.45, size * 0.85, size * 0.7),
                      outline="black", width=stroke)
            d.line((size * 0.2, size * 0.7, size * 0.8, size * 0.7),
                   fill="black", width=stroke)
        elif kind == "play":
            d.polygon([(inset, inset), (size - inset, size * 0.5), (inset, size - inset)],
                      outline="black", fill="black")
        elif kind == "stop":
            d.rectangle((inset + 2, inset + 2, size - inset - 2, size - inset - 2),
                        outline="black", width=stroke)
        elif kind == "copy":
            d.rectangle((inset + 3, inset + 2, size - inset, size - inset - 3),
                        outline="black", width=stroke)
            d.rectangle((inset, inset + 5, size - inset - 3, size - inset),
                        outline="black", width=stroke)
        elif kind == "trash":
            d.rectangle((inset + 2, inset + 5, size - inset - 2, size - inset),
                        outline="black", width=stroke)
            d.line((inset + 2, inset + 4, size - inset - 2, inset + 4),
                   fill="black", width=stroke)
        elif kind == "format":
            d.line((size * 0.35, inset + 2, inset + 2, size * 0.5),
                   fill="black", width=stroke)
            d.line((inset + 2, size * 0.5, size * 0.35, size - inset - 2),
                   fill="black", width=stroke)
            d.line((size * 0.65, inset + 2, size - inset - 2, size * 0.5),
                   fill="black", width=stroke)
            d.line((size - inset - 2, size * 0.5, size * 0.65, size - inset - 2),
                   fill="black", width=stroke)
        else:
            d.rectangle((inset, inset, size - inset, size - inset),
                        outline="black", width=stroke)

        return ImageTk.PhotoImage(img)

    def _rounded_rect(canvas: Canvas, x1: int, y1: int, x2: int, y2: int, r: int, **kwargs: object) -> int:
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)


    class MacButton(Canvas):
        def __init__(self, parent: object, text: str, command: object, icon: Optional[object] = None):
            super().__init__(parent, height=24, highlightthickness=0, bg=mac_bg)
            self._text = text
            self._command = command
            self._icon = icon
            self._pressed = False
            self.bind("<Configure>", self._redraw)
            self.bind("<Enter>", self._on_enter)
            self.bind("<Leave>", self._on_leave)
            self.bind("<ButtonPress-1>", self._on_press)
            self.bind("<ButtonRelease-1>", self._on_release)
            self._state = "normal"

        def _draw(self, fill: str) -> None:
            self.delete("all")
            w = self.winfo_width()
            h = self.winfo_height()
            if w <= 1 or h <= 1:
                return
            _rounded_rect(
                self,
                1,
                1,
                w - 1,
                h - 1,
                r=7,
                fill=fill,
                outline=mac_border,
                width=1,
            )
            text_w = base_font.measure(self._text)
            icon_w = 14 if self._icon else 0
            gap = 6 if self._icon else 0
            total_w = text_w + icon_w + gap
            start_x = max(8, (w - total_w) // 2)
            x = start_x
            if self._icon:
                self.create_image(x, h // 2, image=self._icon, anchor="w")
                x += icon_w + gap
            self.create_text(
                x,
                h // 2,
                text=self._text,
                fill=mac_text,
                font=base_font,
                anchor="w",
            )

        def _redraw(self, _e: object = None) -> None:
            self._draw(mac_button_bg)

        def _on_enter(self, _e: object = None) -> None:
            if not self._pressed:
                self._draw(mac_button_hover)

        def _on_leave(self, _e: object = None) -> None:
            if not self._pressed:
                self._draw(mac_button_bg)

        def _on_press(self, _e: object = None) -> None:
            self._pressed = True
            self._draw(mac_button_active)

        def _on_release(self, e: object = None) -> None:
            if self._pressed:
                self._pressed = False
                self._draw(mac_button_hover)
                if self._command:
                    self._command()

    class MacToggle(Canvas):
        def __init__(self, parent: object, variable: BooleanVar, command: object):
            super().__init__(parent, width=42, height=22, highlightthickness=0, bg=mac_bg)
            self._var = variable
            self._command = command
            self.bind("<Button-1>", self._toggle)
            self.bind("<Configure>", self._redraw)
            self._redraw()

        def _toggle(self, _e: object = None) -> None:
            self._var.set(not self._var.get())
            self._redraw()
            if self._command:
                self._command()

        def _redraw(self, _e: object = None) -> None:
            self.delete("all")
            w = self.winfo_width()
            h = self.winfo_height()
            if w <= 1 or h <= 1:
                return
            on = bool(self._var.get())
            track = "#0a84ff" if on else "#e5e5ea"
            _rounded_rect(self, 1, 1, w - 1, h - 1, r=h // 2, fill=track, outline=mac_border, width=1)
            knob_r = h - 4
            x = w - knob_r - 2 if on else 2
            self.create_oval(x, 2, x + knob_r, 2 + knob_r, fill="#ffffff", outline="#d1d1d6")


    def make_button(parent: object, text: str, command: object, width: int = 84, icon: Optional[object] = None) -> MacButton:
        btn = MacButton(parent, text, command, icon=icon)
        btn.configure(height=24, width=width)
        return btn

    def equalize_button_widths(buttons: List[MacButton]) -> None:
        return
    def make_entry(parent: object, textvariable: StringVar, readonly: bool = False) -> Entry:
        entry = Entry(
            parent,
            textvariable=textvariable,
            bd=1,
            relief="solid",
            highlightthickness=0,
            fg=mac_text,
            bg=mac_field_bg,
            insertbackground=mac_text,
            disabledforeground=mac_text,
            font=base_font,
        )
        if readonly:
            entry.configure(state="readonly", readonlybackground=mac_field_bg)
        return entry

    def load_last_url() -> str:
        try:
            path = Path.home() / ".config" / "gen_clash_from_url" / "last_url.txt"
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def save_last_url(url: str) -> None:
        try:
            path = Path.home() / ".config" / "gen_clash_from_url" / "last_url.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(url.strip(), encoding="utf-8")
        except Exception:
            pass

    url_var = StringVar(value=load_last_url())
    path_var = StringVar(
        value=str(Path(default_output).expanduser().resolve()))
    status_var = StringVar(value="就绪。")
    serve_status_var = StringVar(value="未启动")
    serve_listen_var = StringVar(value="127.0.0.1")
    serve_port_var = StringVar(value="9095")
    serve_interval_var = StringVar(value="300")
    serve_enabled_var = BooleanVar(value=False)
    latest_yaml: Dict[str, str] = {"text": ""}
    log_buffer: List[str] = []
    serve_state: Dict[str, Any] = {
        "httpd": None,
        "stop_event": None,
        "latest": None,
        "lock": None,
    }
    tray_state: Dict[str, Any] = {"icon": None}
    tray_events: "queue.Queue[str]" = queue.Queue()

    def set_status(msg: str, level: str = "info") -> None:
        status_var.set(msg)
        color = {
            "info": "#6e6e73",
            "success": "#0a7a3f",
            "error": "#b00020",
        }.get(level, "#6e6e73")
        status_label.configure(foreground=color)

    def create_tray_image(size: int = 32) -> "Image.Image":
        base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        tray_path = base_dir / "assets" / "tray" / "tray.png"
        if tray_path.exists():
            try:
                img = Image.open(tray_path).convert("RGBA")
                if img.size != (size, size):
                    img = img.resize((size, size), Image.LANCZOS)
                pixels = img.load()
                w, h = img.size
                visited = bytearray(w * h)

                def is_bg(r: int, g: int, b: int, a: int) -> bool:
                    return a > 0 and r >= 245 and g >= 245 and b >= 245

                stack = []
                for x in range(w):
                    for y in (0, h - 1):
                        r, g, b, a = pixels[x, y]
                        if is_bg(r, g, b, a):
                            stack.append((x, y))
                for y in range(h):
                    for x in (0, w - 1):
                        r, g, b, a = pixels[x, y]
                        if is_bg(r, g, b, a):
                            stack.append((x, y))
                while stack:
                    x, y = stack.pop()
                    idx = y * w + x
                    if visited[idx]:
                        continue
                    visited[idx] = 1
                    r, g, b, a = pixels[x, y]
                    if not is_bg(r, g, b, a):
                        continue
                    pixels[x, y] = (r, g, b, 0)
                    if x > 0:
                        stack.append((x - 1, y))
                    if x + 1 < w:
                        stack.append((x + 1, y))
                    if y > 0:
                        stack.append((x, y - 1))
                    if y + 1 < h:
                        stack.append((x, y + 1))
                return img
            except Exception:
                pass
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        text = "JMS"
        font_size = int(size * 0.5)
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf", font_size
            )
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (size - tw) // 2
        y = (size - th) // 2 - int(size * 0.03)
        draw.text((x, y), text, fill="black", font=font)
        return image

    def show_window() -> None:
        set_dock_visibility(True)
        root.deiconify()
        root.lift()
        try:
            root.focus_force()
        except Exception:
            pass

    def ensure_tray() -> bool:
        if not TRAY_AVAILABLE:
            return False
        if tray_state["icon"] is not None:
            return True

        def on_show(_icon: object = None, _item: object = None) -> None:
            tray_events.put("show")

        def on_quit(_icon: object = None, _item: object = None) -> None:
            tray_events.put("quit")

        menu = pystray.Menu(
            pystray.MenuItem("显示", on_show),
            pystray.MenuItem("退出", on_quit),
        )
        icon = pystray.Icon(
            "JMS订阅管家",
            create_tray_image(),
            "JMS 订阅管家",
            menu,
        )
        icon.run_detached()
        tray_state["icon"] = icon
        return True

    def process_tray_events() -> None:
        while True:
            try:
                action = tray_events.get_nowait()
            except queue.Empty:
                break
            if action == "show":
                try:
                    show_window()
                    log_message("托盘操作：显示窗口。")
                except Exception as e:
                    log_message(f"托盘显示失败：{e}")
            elif action == "quit":
                try:
                    log_message("托盘操作：退出程序。")
                    quit_app()
                except Exception as e:
                    log_message(f"托盘退出失败：{e}")
        root.after(200, process_tray_events)

    def quit_app() -> None:
        stop_local_server()
        icon = tray_state.get("icon")
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
            tray_state["icon"] = None
        root.destroy()

    def set_dock_visibility(show: bool) -> None:
        if not DOCK_API_AVAILABLE:
            return
        try:
            app = NSApplication.sharedApplication()
            if show:
                app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
            else:
                app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except Exception:
            return

    def choose_path() -> None:
        initial = Path(path_var.get() or default_output).expanduser()
        if initial.is_dir():
            initial_dir = str(initial)
            initial_file = ""
        else:
            initial_dir = str(initial.parent)
            initial_file = initial.name
        chosen = filedialog.asksaveasfilename(
            parent=root,
            title="选择输出 YAML",
            defaultextension=".yaml",
            filetypes=[("YAML", "*.yaml"), ("YML", "*.yml"),
                       ("All Files", "*.*")],
            initialdir=initial_dir,
            initialfile=initial_file,
        )
        if chosen:
            path_var.set(chosen)

    def set_output(text: str) -> None:
        output_text.delete("1.0", "end")
        output_text.insert("1.0", text)

    def current_yaml_text() -> str:
        return output_text.get("1.0", "end-1c")

    def render_log() -> None:
        log_text.configure(state="normal")
        log_text.delete("1.0", "end")
        if log_buffer:
            log_text.insert("end", "\n".join(log_buffer) + "\n")
        log_text.see("end")
        log_text.configure(state="disabled")

    def append_log(message: str) -> None:
        line = message.rstrip()
        log_buffer.append(line)
        log_text.configure(state="normal")
        log_text.insert("end", line + "\n")
        log_text.see("end")
        log_text.configure(state="disabled")

    def log_message(message: str) -> None:
        root.after(0, lambda m=message: append_log(m))

    def generate() -> None:
        url = url_var.get().strip()
        if not url:
            set_status("错误：请输入 URL。", "error")
            return
        try:
            nodes, _cfg, yaml_text = generate_from_url(url)
        except InternalError as e:
            set_status(f"错误：{e.message}", "error")
            log_message(f"生成失败：{e.message}")
            return
        except Exception as e:
            set_status(f"错误：未知错误：{e}", "error")
            log_message(f"生成异常：{e}")
            return
        latest_yaml["text"] = yaml_text
        set_output(yaml_text)
        save_last_url(url)
        set_status(f"已生成 YAML（节点数={nodes}）", "success")
        log_message(f"生成成功：节点数={nodes}")

    def save_yaml() -> None:
        path = path_var.get().strip()
        if not path:
            set_status("错误：请选择输出路径。", "error")
            return
        yaml_text = current_yaml_text()
        if not yaml_text.strip():
            set_status("错误：请先生成 YAML。", "error")
            return
        try:
            out = Path(path).expanduser().resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", encoding="utf-8") as f:
                f.write(yaml_text)
        except Exception as e:
            set_status(f"错误：保存失败：{e}", "error")
            log_message(f"保存失败：{e}")
            return
        latest_yaml["text"] = yaml_text
        set_status(f"已保存：{path}", "success")
        log_message(f"已保存：{path}")

    def show_help() -> None:
        message = (
            "使用说明：\n"
            "1) 输入 JMS 订阅 URL。\n"
            "2) 点击 生成 生成 YAML。\n"
            "3) 可选择保存路径并点击 保存。\n"
        )
        messagebox.showinfo("帮助", message, parent=root)

    frm = ttk.Frame(root, padding=12)
    frm.grid(sticky="nsew")
    frm.columnconfigure(0, weight=1)
    frm.columnconfigure(1, weight=0)
    frm.rowconfigure(5, weight=1)

    def make_group(parent: object, text: str) -> tuple[Frame, Frame]:
        wrapper = Frame(parent, bg=mac_bg)
        wrapper.columnconfigure(0, weight=1)
        Label(wrapper, text=text, bg=mac_bg, fg=mac_text, font=title_font).grid(
            row=0, column=0, sticky="w", padx=2, pady=(0, 4))
        body = Frame(wrapper, bg=mac_bg, highlightbackground=mac_border, highlightthickness=1)
        body.grid(row=1, column=0, sticky="we")
        body.columnconfigure(0, weight=1)
        return wrapper, body

    url_group_wrap, url_group = make_group(frm, "JMS 订阅 URL")
    url_group_wrap.grid(row=0, column=0, columnspan=2, sticky="we", pady=(0, 10))
    url_group_wrap.columnconfigure(1, weight=0)

    bg = style.lookup("TFrame", "background") or root.cget("background")
    root.configure(background=bg)
    help_canvas = Canvas(
        url_group_wrap,
        width=20,
        height=20,
        highlightthickness=0,
        background=bg,
        cursor="hand2",
    )
    help_circle = help_canvas.create_oval(
        2, 2, 18, 18, fill="#f5f5f7", outline="#d1d1d6")
    help_text = help_canvas.create_text(
        10, 10, text="?", fill="#5c5c5c", font=(base_font.actual("family"), 10, "bold"))
    help_canvas.grid(row=0, column=1, sticky="e", padx=(8, 0))

    def on_help_enter(_e: object = None) -> None:
        help_canvas.itemconfigure(
            help_circle, fill="#e8f0fe", outline="#8ab4f8")
        help_canvas.itemconfigure(help_text, fill="#1a73e8")

    def on_help_leave(_e: object = None) -> None:
        help_canvas.itemconfigure(
            help_circle, fill="#f5f5f7", outline="#d1d1d6")
        help_canvas.itemconfigure(help_text, fill="#5c5c5c")

    help_canvas.bind("<Button-1>", lambda _e: show_help())
    help_canvas.bind("<Enter>", on_help_enter)
    help_canvas.bind("<Leave>", on_help_leave)

    url_entry = make_entry(url_group, url_var)
    url_entry.grid(row=0, column=0, sticky="we", padx=8, pady=8)

    def persist_url(_e: object = None) -> None:
        save_last_url(url_var.get())

    url_entry.bind("<FocusOut>", persist_url)
    url_entry.bind("<KeyRelease>", persist_url)

    def start_local_server() -> None:
        if serve_state["httpd"] is not None:
            set_status("错误：本地服务已在运行。", "error")
            log_message("本地订阅服务已在运行。")
            serve_enabled_var.set(True)
            return
        url = url_var.get().strip()
        if not url:
            set_status("错误：请输入 URL。", "error")
            serve_enabled_var.set(False)
            return
        listen = serve_listen_var.get().strip() or "127.0.0.1"
        try:
            port = int(serve_port_var.get().strip() or "9095")
        except ValueError:
            set_status("错误：端口无效。", "error")
            serve_enabled_var.set(False)
            return
        try:
            interval = int(serve_interval_var.get().strip() or "300")
        except ValueError:
            set_status("错误：间隔无效。", "error")
            serve_enabled_var.set(False)
            return
        if interval < 10:
            interval = 10
            serve_interval_var.set("10")

        latest: Dict[str, Any] = {"text": "", "error": "", "nodes": 0}
        lock = threading.Lock()
        stop_event = threading.Event()

        def update_output_from_yaml(text: str) -> None:
            set_output(text)
            latest_yaml["text"] = text

        def refresh_once() -> None:
            try:
                nodes, _cfg, yaml_text = generate_from_url(url)
            except Exception as e:
                with lock:
                    latest["error"] = str(e)
                log_message(f"订阅刷新失败：{e}")
                return
            with lock:
                latest["text"] = yaml_text
                latest["error"] = ""
                latest["nodes"] = nodes
            root.after(0, lambda t=yaml_text: update_output_from_yaml(t))
            log_message(f"订阅刷新成功：节点数={nodes}")

        def refresh_loop() -> None:
            refresh_once()
            while not stop_event.wait(max(10, interval)):
                refresh_once()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path not in ("/", "/clash.yaml", "/config.yaml", "/config"):
                    self.send_response(404)
                    self.end_headers()
                    return
                with lock:
                    text = latest["text"]
                    err = latest["error"]
                if err or not text.strip():
                    self.send_response(503)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write((err or "未就绪").encode("utf-8"))
                    return
                body = text.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/yaml; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        try:
            httpd = ThreadingHTTPServer((listen, port), Handler)
        except Exception as e:
            set_status(f"错误：启动服务失败：{e}", "error")
            log_message(f"启动服务失败：{e}")
            serve_enabled_var.set(False)
            return

        threading.Thread(target=refresh_loop, daemon=True).start()
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        serve_state["httpd"] = httpd
        serve_state["stop_event"] = stop_event
        serve_state["latest"] = latest
        serve_state["lock"] = lock
        serve_status_var.set(f"http://{listen}:{port}/clash.yaml")
        set_status("本地订阅服务已启动。", "success")
        log_message(f"本地服务已启动：http://{listen}:{port}/clash.yaml")
        serve_enabled_var.set(True)

    def stop_local_server() -> None:
        httpd = serve_state.get("httpd")
        stop_event = serve_state.get("stop_event")
        if httpd is None:
            return
        try:
            if stop_event:
                stop_event.set()
            httpd.shutdown()
            httpd.server_close()
        finally:
            serve_state["httpd"] = None
            serve_state["stop_event"] = None
            serve_state["latest"] = None
            serve_state["lock"] = None
            serve_status_var.set("未启动")
            log_message("本地服务已停止。")
        serve_enabled_var.set(False)
        set_status("本地订阅服务已停止。", "info")

    def toggle_local_server() -> None:
        if serve_enabled_var.get():
            start_local_server()
        else:
            stop_local_server()

    def on_close() -> None:
        persist_url()
        if ensure_tray():
            root.withdraw()
            set_dock_visibility(False)
            set_status("已最小化到托盘。", "info")
            return
        quit_app()

    root.protocol("WM_DELETE_WINDOW", on_close)

    output_group_wrap, output_group = make_group(frm, "生成与保存")
    output_group_wrap.grid(row=1, column=0, columnspan=2, sticky="we", pady=(0, 10))

    Label(output_group, text="输出 YAML 路径", bg=mac_bg, fg=mac_text, font=base_font).grid(
        row=0, column=0, sticky="w")
    path_row = Frame(output_group, bg=mac_bg)
    path_row.grid(row=1, column=0, sticky="we", padx=8, pady=(4, 8))
    path_row.columnconfigure(0, weight=1)
    path_entry = make_entry(path_row, path_var)
    path_entry.grid(row=0, column=0, sticky="we")
    icon_cache["browse"] = make_icon("download")
    browse_btn = make_button(path_row, "浏览", choose_path, width=80, icon=icon_cache["browse"])
    browse_btn.grid(
        row=0, column=1, sticky="w", padx=(6, 0))
    path_row.columnconfigure(1, weight=0)

    btn_row = Frame(output_group, bg=mac_bg)
    btn_row.grid(row=2, column=0, sticky="we", padx=8, pady=(0, 6))
    btn_row.columnconfigure(0, weight=1)
    btn_row_actions = Frame(btn_row, bg=mac_bg)
    btn_row_actions.grid(row=0, column=0, sticky="e")
    icon_cache["generate"] = make_icon("generate")
    gen_btn = make_button(btn_row_actions, "生成", generate, width=88, icon=icon_cache["generate"])
    gen_btn.grid(
        row=0, column=0, padx=(0, 6))
    icon_cache["save"] = make_icon("save")
    save_btn = make_button(btn_row_actions, "保存", save_yaml, width=88, icon=icon_cache["save"])
    save_btn.grid(
        row=0, column=1, padx=(0, 6))
    equalize_button_widths([gen_btn, save_btn])

    local_group_wrap, local_group = make_group(frm, "本地订阅服务")
    local_group_wrap.grid(row=2, column=0, columnspan=2, sticky="we", pady=(0, 8))

    serve_row = Frame(local_group, bg=mac_bg)
    serve_row.grid(row=0, column=0, sticky="we", padx=8, pady=(6, 2))
    serve_row.columnconfigure(1, weight=1)
    serve_row.columnconfigure(3, weight=1)
    serve_row.columnconfigure(5, weight=1)
    Label(serve_row, text="监听", bg=mac_bg, fg=mac_text, font=base_font).grid(
        row=0, column=0, sticky="w")
    listen_entry = make_entry(serve_row, serve_listen_var)
    listen_entry.grid(row=0, column=1, sticky="we", padx=(4, 10))
    Label(serve_row, text="端口", bg=mac_bg, fg=mac_text, font=base_font).grid(
        row=0, column=2, sticky="w")
    port_entry = make_entry(serve_row, serve_port_var)
    port_entry.grid(row=0, column=3, sticky="we", padx=(4, 10))
    Label(serve_row, text="间隔(秒)", bg=mac_bg, fg=mac_text, font=base_font).grid(
        row=0, column=4, sticky="w")
    interval_entry = make_entry(serve_row, serve_interval_var)
    interval_entry.grid(row=0, column=5, sticky="we", padx=(4, 0))

    toggle_row = Frame(local_group, bg=mac_bg)
    toggle_row.grid(row=1, column=0, sticky="we", padx=8, pady=(4, 0))
    toggle_row.columnconfigure(0, weight=1)
    toggle_row.columnconfigure(1, weight=0)
    Label(toggle_row, text="启用本地服务", bg=mac_bg, fg=mac_text, font=base_font).grid(
        row=0, column=0, sticky="w")
    toggle_btn = MacToggle(toggle_row, serve_enabled_var, toggle_local_server)
    toggle_btn.grid(row=0, column=1, sticky="e")

    serve_status_row = Frame(local_group, bg=mac_bg)
    serve_status_row.grid(row=2, column=0, sticky="we", padx=8, pady=(4, 8))
    serve_status_row.columnconfigure(0, weight=1)
    serve_status_entry = make_entry(serve_status_row, serve_status_var, readonly=True)
    serve_status_entry.grid(row=0, column=0, sticky="we")

    def copy_local_url() -> None:
        text = serve_status_var.get().strip()
        if not text.startswith("http"):
            set_status("错误：本地服务未运行。", "error")
            return
        root.clipboard_clear()
        root.clipboard_append(text)
        set_status("已复制本地订阅地址。", "success")

    icon_cache["copy"] = make_icon("copy")
    copy_btn = make_button(serve_status_row, "复制", copy_local_url, width=80, icon=icon_cache["copy"])
    copy_btn.grid(row=0, column=1, padx=(6, 0))
    serve_status_row.columnconfigure(1, weight=0)

    bottom_row = Frame(frm, bg=mac_bg)
    bottom_row.grid(row=5, column=0, columnspan=2, sticky="we", pady=(4, 0))
    bottom_row.columnconfigure(0, weight=1)
    status_label = Label(
        bottom_row,
        textvariable=status_var,
        anchor="w",
        bg=mac_bg,
        fg=mac_text,
        font=small_font,
    )
    status_label.grid(row=0, column=0, sticky="w", padx=8, pady=2)

    notebook = ttk.Notebook(frm)
    notebook.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(0, 8))
    yaml_tab = ttk.Frame(notebook)
    log_tab = ttk.Frame(notebook)
    notebook.add(yaml_tab, text="YAML 输出")
    notebook.add(log_tab, text="日志")

    yaml_tab.rowconfigure(0, weight=1)
    yaml_tab.columnconfigure(0, weight=1)
    log_tab.rowconfigure(0, weight=1)
    log_tab.columnconfigure(0, weight=1)

    output_text = Text(
        yaml_tab,
        width=70,
        height=18,
        wrap="none",
        font=base_font,
        bg=mac_field_bg,
        fg=mac_text,
        insertbackground=mac_text,
    )
    output_text.grid(row=0, column=0, sticky="nsew")

    log_text = Text(
        log_tab,
        width=70,
        height=18,
        wrap="word",
        font=base_font,
        bg=mac_field_bg,
        fg=mac_text,
        insertbackground=mac_text,
    )
    log_text.grid(row=0, column=0, sticky="nsew")
    log_text.configure(state="disabled")

    def on_tab_changed(_e: object = None) -> None:
        current = notebook.select()
        if current == str(yaml_tab):
            set_output(latest_yaml.get("text", ""))
        else:
            render_log()

    notebook.bind("<<NotebookTabChanged>>", on_tab_changed)

    copyright_label = Label(
        bottom_row,
        text="© 李丹 2025 · 由 ChatGPT 驱动",
        anchor="e",
        fg="#8e8e93",
        bg=mac_bg,
        font=small_font,
    )
    copyright_label.grid(row=0, column=1, sticky="e", padx=8, pady=2)

    url_entry.focus_set()
    root.update_idletasks()
    root.minsize(root.winfo_reqwidth(), root.winfo_reqheight())
    root.after(200, process_tray_events)
    root.mainloop()
    return 0
