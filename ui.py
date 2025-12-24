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
    Toplevel,
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
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk
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
    root.title(" ")
    root.resizable(False, False)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    base_font = tkfont.Font(family="SF Pro Text", size=10)
    if base_font.actual("family") != "SF Pro Text":
        base_font = tkfont.Font(family="PingFang SC", size=12)
    small_font = tkfont.Font(family=base_font.actual("family"), size=11)
    title_font = tkfont.Font(family=base_font.actual("family"), size=12, weight="bold")
    logo_font = tkfont.Font(family=base_font.actual("family"), size=13, weight="bold")

    style = ttk.Style()
    if TTKBOOTSTRAP:
        try:
            style.theme_use("clam")
        except Exception:
            pass
    mac_bg = "#f2f2f7"
    mac_border = "#c7c7cc"
    mac_text = "#1c1c1e"
    mac_label = "#6e6e73"
    mac_field_bg = "#ffffff"

    mac_button_bg = "#efeff4"
    mac_button_hover = "#e5e5ea"
    mac_button_active = "#dcdce0"
    style.configure("TLabel", font=base_font, background=mac_bg)
    style.configure("TButton", font=base_font, padding=(6, 2))
    style.configure("TEntry", font=base_font, padding=(6, 2))
    style.configure("TLabelframe", background=mac_bg)
    style.configure("TLabelframe.Label", font=title_font, background=mac_bg)
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
    label_icons: List[object] = []

    def make_icon(kind: str, size: int = 16, color: str = "#3a3a3c") -> Optional[object]:
        if not PIL_AVAILABLE:
            return None
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        stroke = max(1, size // 8)
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
            d.line(pts, fill=color, width=stroke, joint="curve")
        elif kind == "save":
            d.rectangle((inset, inset, size - inset, size - inset), outline=color, width=stroke)
            d.rectangle((inset + 2, inset + 2, size - inset - 2, size * 0.45),
                        outline=color, width=stroke)
        elif kind == "download":
            d.rectangle((inset, size * 0.6, size - inset, size - inset),
                        outline=color, width=stroke)
            d.line((size * 0.5, inset, size * 0.5, size * 0.6),
                   fill=color, width=stroke)
            d.polygon([(size * 0.35, size * 0.45),
                       (size * 0.65, size * 0.45),
                       (size * 0.5, size * 0.62)],
                      outline=color, fill=color)
        elif kind == "cloud":
            d.ellipse((size * 0.15, size * 0.4, size * 0.45, size * 0.7),
                      outline=color, width=stroke)
            d.ellipse((size * 0.35, size * 0.28, size * 0.7, size * 0.72),
                      outline=color, width=stroke)
            d.ellipse((size * 0.6, size * 0.45, size * 0.85, size * 0.7),
                      outline=color, width=stroke)
            d.line((size * 0.2, size * 0.7, size * 0.8, size * 0.7),
                   fill=color, width=stroke)
        elif kind == "play":
            d.polygon([(inset, inset), (size - inset, size * 0.5), (inset, size - inset)],
                      outline=color, fill=color)
        elif kind == "stop":
            d.rectangle((inset + 2, inset + 2, size - inset - 2, size - inset - 2),
                        outline=color, width=stroke)
        elif kind == "copy":
            d.rectangle((inset + 3, inset + 2, size - inset, size - inset - 3),
                        outline=color, width=stroke)
            d.rectangle((inset, inset + 5, size - inset - 3, size - inset),
                        outline=color, width=stroke)
        elif kind == "trash":
            d.rectangle((inset + 2, inset + 5, size - inset - 2, size - inset),
                        outline=color, width=stroke)
            d.line((inset + 2, inset + 4, size - inset - 2, inset + 4),
                   fill=color, width=stroke)
        elif kind == "format":
            d.line((size * 0.35, inset + 2, inset + 2, size * 0.5),
                   fill=color, width=stroke)
            d.line((inset + 2, size * 0.5, size * 0.35, size - inset - 2),
                   fill=color, width=stroke)
            d.line((size * 0.65, inset + 2, size - inset - 2, size * 0.5),
                   fill=color, width=stroke)
            d.line((size - inset - 2, size * 0.5, size * 0.65, size - inset - 2),
                   fill=color, width=stroke)
        elif kind == "link":
            d.ellipse((inset, size * 0.35, size * 0.5, size * 0.85),
                      outline=color, width=stroke)
            d.ellipse((size * 0.5, size * 0.15, size - inset, size * 0.65),
                      outline=color, width=stroke)
            d.line((size * 0.35, size * 0.6, size * 0.65, size * 0.4),
                   fill=color, width=stroke)
        elif kind == "folder":
            d.rectangle((inset, size * 0.35, size - inset, size - inset),
                        outline=color, width=stroke)
            d.rectangle((inset, inset, size * 0.55, size * 0.45),
                        outline=color, width=stroke)
        elif kind == "server":
            d.rectangle((inset, inset, size - inset, size * 0.5),
                        outline=color, width=stroke)
            d.rectangle((inset, size * 0.55, size - inset, size - inset),
                        outline=color, width=stroke)
            d.ellipse((size * 0.75, size * 0.12, size * 0.85, size * 0.22),
                      outline=color, width=stroke)
            d.ellipse((size * 0.75, size * 0.67, size * 0.85, size * 0.77),
                      outline=color, width=stroke)
        elif kind == "port":
            d.ellipse((inset, inset, size - inset, size - inset),
                      outline=color, width=stroke)
            d.ellipse((size * 0.45, size * 0.45, size * 0.55, size * 0.55),
                      outline=color, width=stroke)
        elif kind == "timer":
            d.ellipse((inset, inset, size - inset, size - inset),
                      outline=color, width=stroke)
            d.line((size * 0.5, size * 0.5, size * 0.5, size * 0.25),
                   fill=color, width=stroke)
            d.line((size * 0.5, size * 0.5, size * 0.7, size * 0.55),
                   fill=color, width=stroke)
        else:
            d.rectangle((inset, inset, size - inset, size - inset),
                        outline=color, width=stroke)

        return ImageTk.PhotoImage(img)

    def make_label_with_icon(parent: object, text: str, kind: str, font: object,
                             size: int = 16, color: str = "#3a3a3c") -> Label:
        icon = make_icon(kind, size=size, color=color)
        if icon is not None:
            label_icons.append(icon)
            label = Label(
                parent,
                text=text,
                image=icon,
                compound="left",
                padx=4,
                bg=mac_bg,
                fg=mac_text,
                font=font,
            )
            return label
        return Label(parent, text=text, bg=mac_bg, fg=mac_text, font=font)

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


    class RoundedEntry(Frame):
        def __init__(self, parent: object, textvariable: StringVar, readonly: bool = False):
            super().__init__(parent, bg=mac_bg)
            Frame.configure(self, height=28)
            self.configure(height=28)
            self.grid_propagate(False)
            self.pack_propagate(False)
            self._focused = False
            self._pad = 2
            self._radius = 7
            self._canvas = Canvas(self, highlightthickness=0, bg=mac_bg)
            self._canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.entry = Entry(
                self,
                textvariable=textvariable,
                bd=0,
                relief="flat",
                highlightthickness=0,
                fg=mac_text,
                bg=mac_field_bg,
                insertbackground=mac_text,
                disabledforeground=mac_text,
                font=base_font,
            )
            if readonly:
                self.entry.configure(state="readonly", readonlybackground=mac_field_bg)
            self.entry.place(x=self._pad, y=self._pad, relwidth=1, relheight=1,
                             width=-self._pad * 2, height=-self._pad * 2)
            self._canvas.bind("<Configure>", self._redraw)
            self.entry.bind("<FocusIn>", self._on_focus_in)
            self.entry.bind("<FocusOut>", self._on_focus_out)

        def _on_focus_in(self, _e: object = None) -> None:
            self._focused = True
            self._redraw()

        def _on_focus_out(self, _e: object = None) -> None:
            self._focused = False
            self._redraw()

        def _redraw(self, _e: object = None) -> None:
            w = self._canvas.winfo_width()
            h = self._canvas.winfo_height()
            if w <= 1 or h <= 1:
                return
            self._canvas.delete("all")
            outline = "#0a84ff" if self._focused else mac_border
            _rounded_rect(
                self._canvas,
                1,
                1,
                w - 1,
                h - 1,
                self._radius,
                fill=mac_field_bg,
                outline=outline,
                width=1,
            )

        def bind(self, sequence: Optional[str] = None, func: Optional[object] = None, add: Optional[bool] = None):
            return self.entry.bind(sequence, func, add)

        def focus_set(self) -> None:
            self.entry.focus_set()

        def get(self) -> str:
            return self.entry.get()

        def insert(self, index: int, string: str) -> None:
            self.entry.insert(index, string)

        def delete(self, first: int, last: Optional[int] = None) -> None:
            self.entry.delete(first, last)

        def configure(self, **kwargs: object) -> None:
            if "height" in kwargs:
                Frame.configure(self, height=kwargs.pop("height"))
            if kwargs:
                self.entry.configure(**kwargs)

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
            start_x = max(6, (w - total_w) // 2)
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
            _rounded_rect(self, 1, 1, w - 1, h - 1, r=(h - 2) // 2, fill=track, outline=mac_border, width=1)
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
            "2) 点击 生成 获取 YAML。\n"
            "3) 选择保存路径后点击 保存。\n"
            "4) 本地订阅服务可一键启动，双击地址可复制。\n"
        )
        if not PIL_AVAILABLE:
            messagebox.showinfo("帮助", message, parent=root)
            return
        help_win = Toplevel(root)
        help_win.title("帮助")
        help_win.transient(root)
        help_win.resizable(False, False)
        help_win.configure(background=mac_bg)
        try:
            icon_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets" / "icon.png"
            if icon_path.exists():
                icon_img = Image.open(icon_path).convert("RGBA").resize((64, 64), Image.LANCZOS)
                icon_photo = ImageTk.PhotoImage(icon_img)
                help_win.iconphoto(True, icon_photo)
                help_win._icon = icon_photo
        except Exception:
            pass
        content = Frame(help_win, bg=mac_bg)
        content.grid(row=0, column=0, padx=14, pady=12, sticky="nsew")
        content.columnconfigure(1, weight=1)
        icon_label = Label(content, bg=mac_bg)
        if hasattr(help_win, "_icon"):
            icon_label.configure(image=help_win._icon)
        icon_label.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 10))
        text_label = Label(
            content,
            text=message,
            bg=mac_bg,
            fg=mac_text,
            font=base_font,
            justify="left",
            anchor="w",
        )
        text_label.grid(row=0, column=1, sticky="w")
        close_btn = ttk.Button(content, text="关闭", command=help_win.destroy)
        close_btn.grid(row=1, column=1, sticky="e", pady=(10, 0))
        help_win.grab_set()

    frm = ttk.Frame(root, padding=12)
    frm.grid(sticky="nsew")
    frm.columnconfigure(0, weight=1)
    frm.columnconfigure(1, weight=0)
    frm.rowconfigure(6, weight=1)

    bg = style.lookup("TFrame", "background") or root.cget("background")
    root.configure(background=bg)

    top_wrap = Frame(frm, bg=mac_bg)
    top_wrap.grid(row=0, column=0, columnspan=2, sticky="we", pady=(0, 6))
    top_wrap.columnconfigure(0, weight=1)

    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    logo_path = base_dir / "assets" / "logo.png"
    if PIL_AVAILABLE and logo_path.exists():
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_height = 36
            logo_state = {"photo": None, "width": 0}
            logo_label = Label(top_wrap, bg=mac_bg)
            logo_label.grid(row=0, column=0, sticky="we")

            def update_logo() -> None:
                width = max(
                    frm.winfo_width(),
                    frm.winfo_reqwidth(),
                    root.winfo_width(),
                    root.winfo_reqwidth(),
                    480,
                )
                target_w = max(240, width - 24)
                if target_w == logo_state["width"]:
                    return
                resized = ImageOps.fit(
                    logo_img,
                    (target_w, logo_height),
                    method=Image.LANCZOS,
                    centering=(0.5, 0.5),
                )
                photo = ImageTk.PhotoImage(resized)
                logo_state["photo"] = photo
                logo_state["width"] = target_w
                label_icons.append(photo)
                logo_label.configure(image=photo)

            root.update_idletasks()
            update_logo()
        except Exception:
            pass
    else:
        Label(top_wrap, bg=mac_bg).grid(row=0, column=0, sticky="we")

    def make_group(parent: object, text: str) -> tuple[Frame, Frame]:
        wrapper = Frame(parent, bg=mac_bg)
        wrapper.columnconfigure(0, weight=1)
        title_kind = {
            "JMS 订阅 URL": "link",
            "生成与保存": "save",
            "本地订阅服务": "server",
        }.get(text, "folder")
        title_label = make_label_with_icon(wrapper, text, title_kind, title_font, size=18, color="#1c1c1e")
        title_label.grid(row=0, column=0, sticky="w", padx=2, pady=(0, 4))
        body = Frame(wrapper, bg=mac_bg, highlightthickness=0)
        body.grid(row=1, column=0, columnspan=2, sticky="we")
        body.columnconfigure(0, weight=1)
        return wrapper, body

    url_group_wrap, url_group = make_group(frm, "JMS 订阅 URL")
    url_group_wrap.grid(row=1, column=0, columnspan=2, sticky="we", pady=(0, 10))
    url_group_wrap.columnconfigure(1, weight=0)

    help_canvas = Canvas(
        top_wrap,
        width=20,
        height=20,
        highlightthickness=0,
        borderwidth=0,
        background=mac_bg,
        cursor="hand2",
    )
    help_circle = help_canvas.create_oval(
        2, 2, 18, 18, fill="", outline="#c2c7d0")
    help_text = help_canvas.create_text(
        10, 10, text="?", fill="#6b7280", font=(base_font.actual("family"), 10, "bold"))
    help_canvas.place(relx=1.0, x=-2, y=2, anchor="ne")

    def on_help_enter(_e: object = None) -> None:
        help_canvas.itemconfigure(
        help_circle, fill="#dbeafe", outline="#93c5fd")
        help_canvas.itemconfigure(help_text, fill="#2563eb")

    def on_help_leave(_e: object = None) -> None:
        help_canvas.itemconfigure(
        help_circle, fill="", outline="#c2c7d0")
        help_canvas.itemconfigure(help_text, fill="#6b7280")

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
    output_group_wrap.grid(row=2, column=0, columnspan=2, sticky="we", pady=(0, 10))

    path_row = Frame(output_group, bg=mac_bg)
    path_row.grid(row=1, column=0, sticky="we", padx=8, pady=(4, 8))
    path_row.columnconfigure(0, weight=1)
    path_entry = make_entry(path_row, path_var)
    path_entry.grid(row=0, column=0, sticky="we")
    browse_btn = make_button(path_row, "浏览", choose_path, width=88, icon=None)
    browse_btn.grid(
        row=0, column=1, sticky="e", padx=(6, 0))
    path_row.columnconfigure(1, weight=0)

    btn_row = Frame(output_group, bg=mac_bg)
    btn_row.grid(row=2, column=0, sticky="we", padx=8, pady=(0, 6))
    btn_row.columnconfigure(0, weight=1)
    btn_row_actions = Frame(btn_row, bg=mac_bg)
    btn_row_actions.grid(row=0, column=0, sticky="e")
    gen_btn = make_button(btn_row_actions, "生成", generate, width=88, icon=None)
    gen_btn.grid(
        row=0, column=0, padx=(0, 6))
    save_btn = make_button(btn_row_actions, "保存", save_yaml, width=88, icon=None)
    save_btn.grid(
        row=0, column=1, padx=(0, 0))
    equalize_button_widths([gen_btn, save_btn])

    local_group_wrap, local_group = make_group(frm, "本地订阅服务")
    local_group_wrap.grid(row=3, column=0, columnspan=2, sticky="we", pady=(0, 8))

    serve_row = Frame(local_group, bg=mac_bg)
    serve_row.grid(row=0, column=0, sticky="we", padx=8, pady=(6, 2))
    Label(serve_row, text="监听", bg=mac_bg, fg=mac_label, font=base_font).grid(
        row=0, column=0, sticky="w")
    serve_row.columnconfigure(1, weight=0)
    serve_row.columnconfigure(3, weight=0)
    serve_row.columnconfigure(5, weight=0)
    listen_entry = make_entry(serve_row, serve_listen_var)
    listen_entry.configure(width=22)
    listen_entry.grid(row=0, column=1, sticky="w", padx=(4, 10))
    Label(serve_row, text="端口", bg=mac_bg, fg=mac_label, font=base_font).grid(
        row=0, column=2, sticky="w")
    port_entry = make_entry(serve_row, serve_port_var)
    port_entry.configure(width=6)
    port_entry.grid(row=0, column=3, sticky="w", padx=(4, 10))
    Label(serve_row, text="间隔(秒)", bg=mac_bg, fg=mac_label, font=base_font).grid(
        row=0, column=4, sticky="w")
    interval_entry = make_entry(serve_row, serve_interval_var)
    interval_entry.configure(width=6)
    interval_entry.grid(row=0, column=5, sticky="w", padx=(4, 0))
    serve_row.columnconfigure(6, weight=0)
    serve_row.columnconfigure(7, weight=1)
    toggle_btn = MacToggle(serve_row, serve_enabled_var, toggle_local_server)
    toggle_btn.grid(row=0, column=7, sticky="e", padx=(12, 0))

    serve_status_row = Frame(local_group, bg=mac_bg)
    serve_status_row.grid(row=1, column=0, sticky="we", padx=8, pady=(4, 8))
    serve_status_row.columnconfigure(0, weight=1)
    serve_status_entry = Label(
        serve_status_row,
        textvariable=serve_status_var,
        bg=mac_bg,
        fg=mac_label,
        font=base_font,
        anchor="w",
        cursor="arrow",
    )
    serve_status_entry.grid(row=0, column=0, sticky="we")
    serve_status_entry.bind("<Double-Button-1>", lambda _e: copy_local_url())

    def copy_local_url() -> None:
        text = serve_status_var.get().strip()
        if not text.startswith("http"):
            set_status("错误：本地服务未运行。", "error")
            return
        root.clipboard_clear()
        root.clipboard_append(text)
        set_status("已复制本地订阅地址。", "success")
        try:
            serve_status_entry.configure(fg="#0a84ff")
            root.after(300, lambda: serve_status_entry.configure(fg=mac_label))
        except Exception:
            pass

    serve_status_row.columnconfigure(1, weight=0)

    bottom_row = Frame(frm, bg=mac_bg)
    bottom_row.grid(row=6, column=0, columnspan=2, sticky="we", pady=(4, 0))
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

    tab_wrap = Frame(frm, bg=mac_bg)
    tab_wrap.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(0, 8))
    tab_wrap.columnconfigure(0, weight=1)
    tab_wrap.rowconfigure(1, weight=1)

    tab_bar = Frame(tab_wrap, bg=mac_bg)
    tab_bar.grid(row=0, column=0, sticky="w", padx=4, pady=(0, 4))

    def make_tab_item(title: str) -> tuple[Frame, Label, Frame]:
        item = Frame(tab_bar, bg=mac_bg)
        item.columnconfigure(0, weight=1)
        label = Label(item, text=title, bg=mac_bg, fg=mac_label, font=small_font)
        label.grid(row=0, column=0, sticky="w")
        underline = Frame(item, bg=mac_bg, height=2)
        underline.grid(row=1, column=0, sticky="we", pady=(2, 0))
        return item, label, underline

    tab_yaml, tab_yaml_label, tab_yaml_line = make_tab_item("YAML 输出")
    tab_log, tab_log_label, tab_log_line = make_tab_item("日志")
    tab_yaml.grid(row=0, column=0, sticky="w", padx=(0, 12))
    tab_log.grid(row=0, column=1, sticky="w")

    tab_body = Frame(tab_wrap, bg=mac_bg)
    tab_body.grid(row=1, column=0, sticky="nsew")
    tab_body.rowconfigure(0, weight=1)
    tab_body.columnconfigure(0, weight=1)

    yaml_tab = Frame(tab_body, bg=mac_bg)
    log_tab = Frame(tab_body, bg=mac_bg)
    yaml_tab.grid(row=0, column=0, sticky="nsew")
    log_tab.grid(row=0, column=0, sticky="nsew")
    log_tab.grid_remove()

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
        highlightthickness=0,
        bd=0,
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
        highlightthickness=0,
        bd=0,
    )
    log_text.grid(row=0, column=0, sticky="nsew")
    log_text.configure(state="disabled")

    def select_tab(tab: str) -> None:
        if tab == "yaml":
            yaml_tab.grid()
            log_tab.grid_remove()
            tab_yaml_label.configure(fg=mac_text)
            tab_log_label.configure(fg=mac_label)
            tab_yaml_line.configure(bg=mac_text)
            tab_log_line.configure(bg=mac_bg)
            set_output(latest_yaml.get("text", ""))
        else:
            log_tab.grid()
            yaml_tab.grid_remove()
            tab_yaml_label.configure(fg=mac_label)
            tab_log_label.configure(fg=mac_text)
            tab_yaml_line.configure(bg=mac_bg)
            tab_log_line.configure(bg=mac_text)
            render_log()

    def bind_tab(item: Frame, label: Label, tab: str) -> None:
        item.bind("<Button-1>", lambda _e: select_tab(tab))
        label.bind("<Button-1>", lambda _e: select_tab(tab))

    bind_tab(tab_yaml, tab_yaml_label, "yaml")
    bind_tab(tab_log, tab_log_label, "log")
    select_tab("yaml")

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
    req_w = root.winfo_reqwidth()
    req_h = root.winfo_reqheight()
    root.geometry(f"{req_w}x{req_h}")
    root.minsize(req_w, req_h)
    root.after(200, process_tray_events)
    root.mainloop()
    return 0
