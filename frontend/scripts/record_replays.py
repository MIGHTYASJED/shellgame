"""Record real investigation streams from a running backend into public/replays/ (offline fallback).

Usage: python scripts/record_replays.py [http://localhost:8000]
The frontend replays these only when the live backend is unreachable, and labels them as recordings.
"""
import json
import sys
import urllib.request
from pathlib import Path

API = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
OUT = Path(__file__).resolve().parent.parent / "public" / "replays"
SUBJECTS = ["10150253", "10161731", "20141145", "20126388"]  # Creatum, USM Finance, Iris Rose, Bison


def get(path):
    with urllib.request.urlopen(API + path) as r:
        return json.load(r)


def stream(node_id):
    with urllib.request.urlopen(f"{API}/api/investigate?node_id={node_id}&tenant=recorded") as r:
        return [json.loads(line[6:]) for line in (l.decode().strip() for l in r) if line.startswith("data: ")]


OUT.mkdir(parents=True, exist_ok=True)
index = {"stats": get("/api/stats"), "subjects": []}
for nid in SUBJECTS:
    node = get(f"/api/node/{nid}")
    node = node.get("node", node)
    index["subjects"].append({k: node.get(k, "") for k in ("id", "name", "kind", "jurisdiction", "countries")})
    events = stream(nid)
    (OUT / f"{nid}.json").write_text(json.dumps({"node": node, "events": events}))
    verdict = next((e.get("result", {}).get("verdict") for e in events if e["type"] == "verdict"), None)
    print(nid, node.get("name"), len(events), "events", verdict)
(OUT / "index.json").write_text(json.dumps(index))
