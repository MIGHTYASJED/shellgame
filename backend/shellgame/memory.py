"""Case memory (Track 2). One FalkorDB graph per tenant: `cases_<tenant>` -> full isolation.

(:Case {id, created_at, subject_id, subject_name, verdict, summary, rule_ids})
(:Case)-[:EXAMINED]->(:Ref {id, name, kind})        every node on cited paths (Ref.id = main-graph node id)
(:Case)-[:CLEARED {reason}]->(:Ref)                  nodes judged weak / not exposing
(:Case)-[:FLAGGED]->(:Ref)                           chokepoints
(:Case)-[:PRECEDENT_FOR]->(:Case)                    earlier case -> later case that reused it
Ref nodes are MERGEd, so two cases touching the same company share the Ref -> recall is a 1-hop query.
"""
from __future__ import annotations

import re
import time
import uuid
from typing import Any, Iterable

from ._compat import db

PREFIX = "cases_"

RECALL_CYPHER = (
    "MATCH (c:Case)-[rel:EXAMINED|FLAGGED|CLEARED]->(r:Ref) WHERE r.id IN $ids "
    "RETURN c, collect(DISTINCT {id: r.id, name: r.name, rel: type(rel)}) AS hits "
    "ORDER BY c.created_at DESC LIMIT $limit"
)


def sanitize_tenant(tenant: str | None) -> str:
    t = re.sub(r"[^a-z0-9_]+", "_", (tenant or "default").strip().lower()).strip("_")
    return (t or "default")[:48]


def graph_name(tenant: str | None) -> str:
    return PREFIX + sanitize_tenant(tenant)


def _list_graphs() -> list[str]:
    fn = getattr(db, "list_graphs", None)
    if fn is not None:
        return list(fn())
    return list(db.get_db().list_graphs())


def _graph(tenant: str | None):
    return db.get_db().select_graph(graph_name(tenant))


def _exists(tenant: str | None) -> bool:
    return graph_name(tenant) in _list_graphs()


def _case_dict(node) -> dict:
    p = dict(node.properties)
    if isinstance(p.get("rule_ids"), str):
        p["rule_ids"] = [x for x in p["rule_ids"].split(",") if x]
    return p


def list_tenants() -> list[str]:
    return sorted(g[len(PREFIX):] for g in _list_graphs() if g.startswith(PREFIX))


def list_cases(tenant: str | None, limit: int = 100) -> list[dict]:
    if not _exists(tenant):
        return []
    g = _graph(tenant)
    res = g.ro_query(
        "MATCH (c:Case) OPTIONAL MATCH (c)-[:FLAGGED]->(f:Ref) OPTIONAL MATCH (p:Case)-[:PRECEDENT_FOR]->(c) "
        "RETURN c, collect(DISTINCT f.name), collect(DISTINCT p.id) ORDER BY c.created_at DESC LIMIT $limit",
        {"limit": int(limit)},
    ).result_set
    out = []
    for c, flagged, precedents in res:
        d = _case_dict(c)
        d["flagged"] = [x for x in flagged if x]
        d["precedents"] = [x for x in precedents if x]
        out.append(d)
    return out


def recall(tenant: str | None, node_ids: Iterable[str], limit: int = 5, exclude_subject: bool = False) -> dict:
    """Prior cases in this tenant that touched any of node_ids. Returns tool-style dict incl. cypher."""
    ids = sorted({str(i) for i in node_ids if i})
    params = {"ids": ids, "limit": int(limit)}
    out: dict[str, Any] = {"cypher": RECALL_CYPHER, "params": params, "graph": graph_name(tenant), "cases": []}
    if not ids or not _exists(tenant):
        return out
    for c, hits in _graph(tenant).ro_query(RECALL_CYPHER, params).result_set:
        d = _case_dict(c)
        d["hits"] = hits
        out["cases"].append(d)
    return out


def write_case(
    tenant: str | None,
    *,
    subject_id: str,
    subject_name: str,
    verdict: str,
    summary: str,
    rule_ids: list[str] | None = None,
    examined: Iterable[dict] = (),
    flagged: Iterable[dict] = (),
    cleared: Iterable[dict] = (),
    precedent_ids: Iterable[str] = (),
) -> dict:
    """Persist a Case. examined/flagged/cleared items: {"id","name","kind"[, "reason"]}."""
    g = _graph(tenant)
    case_id = "case_" + uuid.uuid4().hex[:10]
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    g.query(
        "CREATE (:Case {id:$id, created_at:$created, subject_id:$sid, subject_name:$sname, verdict:$verdict, "
        "summary:$summary, rule_ids:$rules})",
        {"id": case_id, "created": created, "sid": subject_id, "sname": subject_name, "verdict": verdict,
         "summary": summary, "rules": ",".join(rule_ids or [])},
    )
    try:
        g.query("CREATE INDEX FOR (r:Ref) ON (r.id)")
    except Exception:
        pass  # already exists

    def _rows(items, with_reason=False):
        rows, seen = [], set()
        for it in items:
            if not it or not it.get("id") or it["id"] in seen:
                continue
            seen.add(it["id"])
            row = {"id": str(it["id"]), "name": it.get("name") or "", "kind": it.get("kind") or ""}
            if with_reason:
                row["reason"] = it.get("reason") or ""
            rows.append(row)
        return rows

    link = ("UNWIND $rows AS row MERGE (r:Ref {id: row.id}) SET r.name = row.name, r.kind = row.kind "
            "WITH r, row MATCH (c:Case {id:$cid}) ")
    ex = _rows(examined)
    if ex:
        g.query(link + "MERGE (c)-[:EXAMINED]->(r)", {"rows": ex, "cid": case_id})
    fl = _rows(flagged)
    if fl:
        g.query(link + "MERGE (c)-[:FLAGGED]->(r)", {"rows": fl, "cid": case_id})
    cl = _rows(cleared, with_reason=True)
    if cl:
        g.query(link + "MERGE (c)-[x:CLEARED]->(r) SET x.reason = row.reason", {"rows": cl, "cid": case_id})
    prec = [p for p in dict.fromkeys(precedent_ids) if p and p != case_id]
    if prec:
        g.query(
            "MATCH (c:Case {id:$cid}) UNWIND $pids AS pid MATCH (p:Case {id:pid}) MERGE (p)-[:PRECEDENT_FOR]->(c)",
            {"cid": case_id, "pids": prec},
        )
    return {"id": case_id, "created_at": created, "graph": graph_name(tenant), "examined": len(ex),
            "flagged": len(fl), "cleared": len(cl), "precedents": prec}


def delete_tenant(tenant: str | None) -> None:
    if _exists(tenant):
        _graph(tenant).delete()
