"""Wspolne funkcje wdrozenia demo Northwind Traders do Microsoft Fabric (REST API)."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".fabric" / "deployment.json"
API = "https://api.fabric.microsoft.com/v1"
CAPACITY_ID = os.environ.get("FABRIC_CAPACITY_ID", "")
WORKSPACE_NAME = os.environ.get("FABRIC_WORKSPACE_NAME", "Northwind Traders demo")
LAKEHOUSE = "lh_northwind_demo"
MODEL = "sm_northwind_operacje"
REPORT = "rpt_northwind_operacje"
AGENT = "agent_operacje_northwind"

_tokens: dict[str, tuple[str, float]] = {}


def token(resource: str = "https://api.fabric.microsoft.com") -> str:
    t = _tokens.get(resource)
    if t and t[1] > time.time() + 300:
        return t[0]
    out = subprocess.run(f'az account get-access-token --resource {resource} -o json',
                         shell=True, capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    _tokens[resource] = (d["accessToken"], float(d.get("expires_on") or time.time() + 3000))
    return d["accessToken"]


def h(resource: str = "https://api.fabric.microsoft.com") -> dict:
    return {"Authorization": f"Bearer {token(resource)}", "Content-Type": "application/json"}


def wait(resp: requests.Response, what: str = "operacja") -> dict | None:
    if resp.status_code in (200, 201):
        return resp.json() if resp.content else None
    if resp.status_code != 202:
        raise RuntimeError(f"{what}: {resp.status_code} {resp.text}")
    op = resp.headers.get("x-ms-operation-id")
    loc = resp.headers.get("Location")
    for _ in range(180):
        time.sleep(int(resp.headers.get("Retry-After", 3)))
        r = requests.get(f"{API}/operations/{op}", headers=h())
        st = r.json().get("status")
        if st == "Succeeded":
            res = requests.get(f"{API}/operations/{op}/result", headers=h())
            return res.json() if res.status_code == 200 and res.content else None
        if st in ("Failed", "Cancelled"):
            raise RuntimeError(f"{what}: {r.text}")
    raise TimeoutError(f"{what}: {loc}")


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save_state(s: dict) -> None:
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2), encoding="utf-8")


def find_item(ws: str, name: str, typ: str) -> str | None:
    r = requests.get(f"{API}/workspaces/{ws}/items?type={typ}", headers=h())
    r.raise_for_status()
    return next((i["id"] for i in r.json()["value"] if i["displayName"] == name), None)


def part(path: str, content) -> dict:
    raw = content if isinstance(content, bytes) else (
        content if isinstance(content, str) else json.dumps(content, indent=2, ensure_ascii=False)).encode("utf-8")
    return {"path": path, "payload": base64.b64encode(raw).decode(), "payloadType": "InlineBase64"}


def upsert_item(ws: str, name: str, typ: str, parts: list[dict]) -> str:
    iid = find_item(ws, name, typ)
    body = {"definition": {"parts": parts}}
    if iid:
        wait(requests.post(f"{API}/workspaces/{ws}/items/{iid}/updateDefinition?updateMetadata=true",
                           headers=h(), json=body), f"update {name}")
    else:
        res = wait(requests.post(f"{API}/workspaces/{ws}/items", headers=h(),
                                 json={"displayName": name, "type": typ, **body}), f"create {name}")
        iid = (res or {}).get("id") or find_item(ws, name, typ)
    return iid


def get_definition(ws: str, iid: str) -> dict[str, str]:
    res = wait(requests.post(f"{API}/workspaces/{ws}/items/{iid}/getDefinition", headers=h()), "getDefinition")
    return {p["path"]: base64.b64decode(p["payload"]).decode("utf-8", "replace")
            for p in res["definition"]["parts"]}
