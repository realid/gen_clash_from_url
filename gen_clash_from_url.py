#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import date
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

import requests
import yaml
from tkinter import Tk, StringVar, Text, Label, ttk
from tkinter import filedialog


class InternalError(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)
        self.message = msg


def b64decode_any(s: str) -> bytes:
    """兼容标准/urlsafe base64，自动补 padding。"""
    s = (s or "").strip()
    if not s:
        return b""
    pad = "=" * ((4 - len(s) % 4) % 4)
    s2 = s + pad
    try:
        return base64.urlsafe_b64decode(s2.encode("utf-8"))
    except Exception:
        return base64.b64decode(s2.encode("utf-8"))


@dataclass
class Node:
    name: str
    data: Dict[str, Any]


def fetch_text(url: str, timeout: int = 15) -> str:
    s = requests.Session()
    s.trust_env = False  # 不读系统代理环境变量
    try:
        r = s.get(url, headers={"User-Agent": "curl/8.5.0"}, timeout=timeout)
    except Exception as e:
        raise InternalError(f"requests.get failed: {e}")
    if not r.ok or not r.text.strip():
        raise InternalError(f"HTTP not ok: {r.status_code}")
    return r.text.strip()


def split_subscription_lines(body_b64: str) -> List[str]:
    raw = b64decode_any(body_b64)
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", "ignore")
    lines = [ln.strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln and "://" in ln]


def parse_ss(uri: str) -> Optional[Node]:
    # ss://... 可能带 #tag 和 ?plugin
    rest = uri[len("ss://"):].strip()

    tag = ""
    if "#" in rest:
        rest, tag = rest.split("#", 1)
        tag = unquote(tag.strip())

    # 去掉 query（plugin 等先忽略）
    if "?" in rest:
        rest, _ = rest.split("?", 1)

    rest = rest.strip()

    # 形式 1: ss://BASE64(method:pass@host:port)
    # 形式 2: ss://method:pass@host:port
    if "@" not in rest or (":" not in rest.split("@", 1)[0]):
        decoded = b64decode_any(rest).decode("utf-8", "ignore").strip()
        rest2 = decoded
    else:
        rest2 = unquote(rest)

    if "@" not in rest2:
        return None

    auth, hostport = rest2.split("@", 1)
    if ":" not in auth:
        return None
    method, password = auth.split(":", 1)

    # host:port 可能是 IPv6 [::1]:443
    hp = hostport.strip()
    if hp.startswith("[") and "]" in hp:
        i = hp.find("]")
        host = hp[1:i]
        tail = hp[i + 1:]
        if not tail.startswith(":"):
            return None
        port = int(tail[1:])
    else:
        if ":" not in hp:
            return None
        host, p = hp.rsplit(":", 1)
        port = int(p)

    name = tag or f"ss@{host}:{port}"
    data = {
        "name": name,
        "type": "ss",
        "server": host,
        "port": port,
        "cipher": method,
        "password": password,
        "udp": True,
    }
    return Node(name=name, data=data)


def parse_vmess(uri: str) -> Optional[Node]:
    rest = uri[len("vmess://"):].strip()
    if not rest:
        return None

    try:
        decoded = b64decode_any(rest).decode("utf-8", "strict")
    except Exception:
        decoded = b64decode_any(rest).decode("utf-8", "ignore")

    try:
        conf = json.loads(decoded)
    except Exception:
        return None

    name = conf.get("ps") or conf.get("remark") or "vmess"
    server = conf.get("add") or conf.get("host") or ""
    port = int(conf.get("port") or 0)
    uuid = conf.get("id") or ""
    aid = int(conf.get("aid") or 0)

    net = conf.get("net") or "tcp"
    tls = (conf.get("tls") or "").lower() == "tls"
    sni = conf.get("sni") or conf.get("servername") or conf.get("host") or ""

    if not server or not port or not uuid:
        return None

    data: Dict[str, Any] = {
        "name": name,
        "type": "vmess",
        "server": server,
        "port": port,
        "uuid": uuid,
        "alterId": aid,
        "cipher": conf.get("scy") or "auto",
        "network": net,
        "udp": True,
    }

    if tls:
        data["tls"] = True
        data["skip-cert-verify"] = True
        if sni:
            data["servername"] = sni

    # ws
    if net == "ws":
        path = conf.get("path") or "/"
        host_hdr = conf.get("host") or sni or ""
        data["ws-opts"] = {"path": path}
        if host_hdr:
            data["ws-opts"]["headers"] = {"Host": host_hdr}

    # grpc
    if net == "grpc":
        svc = conf.get("path") or conf.get("serviceName") or ""
        if svc:
            data["grpc-opts"] = {"grpc-service-name": svc}

    return Node(name=name, data=data)


def parse_node(line: str) -> Optional[Node]:
    line = line.strip()
    if line.startswith("ss://"):
        return parse_ss(line)
    if line.startswith("vmess://"):
        return parse_vmess(line)
    return None


def build_clash_config(nodes: List[Node], port: int, allow_lan: bool) -> Dict[str, Any]:
    proxies: List[Dict[str, Any]] = []
    proxies.extend([n.data for n in nodes])

    names = [n.name for n in nodes]

    cfg: Dict[str, Any] = {
        "port": port,
        "socks-port": port + 1,
        "allow-lan": bool(allow_lan),
        "mode": "rule",
        "log-level": "warning",
        "external-controller": "127.0.0.1:9090",
        "proxies": proxies,
        "proxy-groups": [
            {
                "name": "AUTO",
                "type": "url-test",
                "proxies": names,
                "url": "https://cp.cloudflare.com/generate_204",
                "interval": 300,
            },
            {
                "name": "MANUAL",
                "type": "select",
                "proxies": ["AUTO", "DIRECT"] + names,
            },
        ],
        "rules": [
            "GEOIP,LAN,DIRECT,no-resolve",
            "GEOIP,CN,DIRECT",
            "MATCH,MANUAL",
        ],
    }

    if allow_lan:
        cfg["bind-address"] = "*"

    return cfg


def generate_from_url(url: str) -> tuple[int, Dict[str, Any], str]:
    default_port = 1082
    default_timeout = 15

    body_b64 = fetch_text(url, timeout=default_timeout)
    lines = split_subscription_lines(body_b64)

    nodes: List[Node] = []
    for ln in lines:
        n = parse_node(ln)
        if n:
            nodes.append(n)

    if not nodes:
        raise InternalError("解析结果为空：订阅可能不是 base64 列表，或不包含 ss/vmess。")

    cfg = build_clash_config(nodes, default_port, False)
    yaml_text = yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False)
    return len(nodes), cfg, yaml_text


def generate_from_url_to_path(url: str, output_path: Path) -> int:
    nodes, _cfg, yaml_text = generate_from_url(url)
    out = output_path.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write(yaml_text)

    print(f"OK: wrote {out} (nodes={nodes})")
    return nodes


def run_gui(default_output: str) -> int:
    root = Tk()
    root.title("Generate Clash YAML")
    root.resizable(False, False)

    url_var = StringVar()
    path_var = StringVar(
        value=str(Path(default_output).expanduser().resolve()))
    status_var = StringVar(value="Ready.")
    latest_yaml: Dict[str, str] = {"text": ""}

    def set_status(msg: str, level: str = "info") -> None:
        status_var.set(msg)
        color = {"info": "#333333", "success": "#0b7a2a",
                 "error": "#b00020"}.get(level, "#333333")
        status_label.configure(foreground=color)

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
            title="Choose output YAML",
            defaultextension=".yaml",
            filetypes=[("YAML", "*.yaml"), ("YML", "*.yml"),
                       ("All Files", "*.*")],
            initialdir=initial_dir,
            initialfile=initial_file,
        )
        if chosen:
            path_var.set(chosen)

    def set_output(text: str) -> None:
        output_text.configure(state="normal")
        output_text.delete("1.0", "end")
        output_text.insert("1.0", text)
        output_text.configure(state="disabled")

    def generate() -> None:
        url = url_var.get().strip()
        if not url:
            set_status("Error: Please enter URL.", "error")
            return
        try:
            nodes, _cfg, yaml_text = generate_from_url(url)
        except InternalError as e:
            set_status(f"Error: {e.message}", "error")
            return
        except Exception as e:
            set_status(f"Error: Unexpected error: {e}", "error")
            return
        latest_yaml["text"] = yaml_text
        set_output(yaml_text)
        set_status(f"Generated YAML (nodes={nodes})", "success")

    def save_yaml() -> None:
        path = path_var.get().strip()
        if not path:
            set_status("Error: Please choose output path.", "error")
            return
        if not latest_yaml["text"]:
            set_status("Error: Please generate YAML first.", "error")
            return
        try:
            out = Path(path).expanduser().resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", encoding="utf-8") as f:
                f.write(latest_yaml["text"])
        except Exception as e:
            set_status(f"Error: Save failed: {e}", "error")
            return
        set_status(f"Wrote {path}", "success")

    frm = ttk.Frame(root, padding=12)
    frm.grid()

    ttk.Label(frm, text="Subscription URL").grid(row=0, column=0, sticky="w")
    url_entry = ttk.Entry(frm, width=60, textvariable=url_var)
    url_entry.grid(row=1, column=0, columnspan=2, sticky="we", pady=(4, 10))

    ttk.Label(frm, text="Output YAML Path").grid(row=2, column=0, sticky="w")
    path_entry = ttk.Entry(frm, width=50, textvariable=path_var)
    path_entry.grid(row=3, column=0, sticky="we", pady=(4, 10))
    ttk.Button(frm, text="Browse...", command=choose_path).grid(
        row=3, column=1, sticky="e", padx=(8, 0))

    ttk.Button(frm, text="Generate", command=generate).grid(
        row=4, column=0, sticky="we")
    ttk.Button(frm, text="Save YAML", command=save_yaml).grid(
        row=4, column=1, sticky="we", padx=(8, 0))

    status_label = Label(frm, textvariable=status_var, anchor="w")
    status_label.grid(row=5, column=0, columnspan=2, sticky="we", pady=(10, 0))

    ttk.Label(frm, text="YAML Output").grid(
        row=6, column=0, sticky="w", pady=(8, 0))
    output_text = Text(frm, width=70, height=18, wrap="none")
    output_text.grid(row=7, column=0, columnspan=2, sticky="we", pady=(4, 0))
    output_text.configure(state="disabled")

    url_entry.focus_set()
    root.mainloop()
    return 0


def main() -> int:
    default_output = f"{date.today().strftime('%Y-%m-%d')}.yaml"
    ap = argparse.ArgumentParser(
        description="Generate Clash YAML from subscription URL (base64 list of ss/vmess)")
    ap.add_argument(
        "url", nargs="?", help="subscription URL (the SUBSCRIPTION_URL you already have)")
    ap.add_argument("-o", "--output", default=default_output,
                    help=f"output yaml path (default: {default_output})")
    args = ap.parse_args()

    if not args.url:
        return run_gui(default_output)

    generate_from_url_to_path(args.url, Path(args.output))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InternalError as e:
        print(f"ERROR: {e.message}", file=sys.stderr)
        raise SystemExit(2)
