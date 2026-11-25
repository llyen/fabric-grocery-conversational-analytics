"""Workspace, lakehouse, upload parquet do OneLake i zaladowanie tabel Delta."""
import json
import time

import requests

from common import (API, CAPACITY_ID, LAKEHOUSE, ROOT, WORKSPACE_NAME, find_item, h, load_state, save_state,
                    token, wait)

DATA = ROOT / "data"
ONELAKE = "https://onelake.dfs.fabric.microsoft.com"


def ensure_workspace() -> str:
    r = requests.get(f"{API}/workspaces", headers=h())
    r.raise_for_status()
    ws = next((w["id"] for w in r.json()["value"] if w["displayName"] == WORKSPACE_NAME), None)
    if not ws:
        if not CAPACITY_ID:
            raise SystemExit("Ustaw zmienna FABRIC_CAPACITY_ID (id pojemnosci Fabric) albo utworz workspace recznie.")
        r = requests.post(f"{API}/workspaces", headers=h(),
                          json={"displayName": WORKSPACE_NAME, "capacityId": CAPACITY_ID,
                                "description": "Demo analityki konwersacyjnej Northwind Traders. Dane syntetyczne."})
        r.raise_for_status()
        ws = r.json()["id"]
    return ws


def ensure_lakehouse(ws: str) -> str:
    lh = find_item(ws, LAKEHOUSE, "Lakehouse")
    if not lh:
        res = wait(requests.post(f"{API}/workspaces/{ws}/lakehouses", headers=h(),
                                 json={"displayName": LAKEHOUSE}), "lakehouse")
        lh = (res or {}).get("id") or find_item(ws, LAKEHOUSE, "Lakehouse")
    return lh


def upload(ws: str, lh: str, path) -> None:
    st = {"Authorization": f"Bearer {token('https://storage.azure.com')}"}
    url = f"{ONELAKE}/{ws}/{lh}/Files/raw/{path.name}"
    data = path.read_bytes()
    requests.put(f"{url}?resource=file", headers=st).raise_for_status()
    chunk = 32 * 1024 * 1024
    for off in range(0, len(data), chunk):
        requests.patch(f"{url}?action=append&position={off}", headers=st,
                       data=data[off:off + chunk]).raise_for_status()
    requests.patch(f"{url}?action=flush&position={len(data)}", headers=st).raise_for_status()


def main() -> None:
    ws = ensure_workspace()
    lh = ensure_lakehouse(ws)
    print("workspace", ws, "lakehouse", lh)
    files = sorted(p for p in DATA.glob("*.parquet"))
    for p in files:
        upload(ws, lh, p)
        print("upload", p.name)
    for p in files:
        name = p.stem
        for attempt in range(5):
            r = requests.post(f"{API}/workspaces/{ws}/lakehouses/{lh}/tables/{name}/load", headers=h(),
                              json={"relativePath": f"Files/raw/{p.name}", "pathType": "File",
                                    "mode": "Overwrite", "formatOptions": {"format": "Parquet"}})
            if r.status_code == 429:
                time.sleep(20)
                continue
            wait(r, f"load {name}")
            break
        print("tabela", name)
    r = requests.get(f"{API}/workspaces/{ws}/lakehouses/{lh}/tables", headers=h())
    names = sorted(t["name"] for t in r.json()["data"])
    print(len(names), names)
    lhd = requests.get(f"{API}/workspaces/{ws}/lakehouses/{lh}", headers=h()).json()
    s = load_state()
    s.update({"workspace_id": ws, "lakehouse_id": lh,
              "sql_endpoint": lhd["properties"]["sqlEndpointProperties"].get("connectionString"),
              "sql_endpoint_id": lhd["properties"]["sqlEndpointProperties"].get("id")})
    save_state(s)
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
