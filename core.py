#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

import requests
import yaml


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
        raise InternalError(f"请求失败：{e}")
    if not r.ok or not r.text.strip():
        raise InternalError(f"HTTP 状态异常：{r.status_code}")
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
                "name": "MANUAL",
                "type": "select",
                "proxies": names,
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

    cfg = build_clash_config(nodes, default_port, True)
    yaml_text = yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False)
    return len(nodes), cfg, yaml_text


def generate_from_url_to_path(url: str, output_path: "Path") -> int:
    from pathlib import Path

    nodes, _cfg, yaml_text = generate_from_url(url)
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write(yaml_text)

    print(f"已保存：{out}（节点数={nodes}）")
    return nodes
