"""Graph tools: fixed, human-written, parameterized Cypher. The LLM only picks a tool and its typed args.

Every tool is `fn(g, **args) -> dict` with `cypher` + `params` (exactly what ran) plus its payload.
All reads go through `ro_query`.
"""
from __future__ import annotations

import bisect
import re
import threading

from .schema import KINDS, SANCTION_PREFIX

PATH_LIMIT = 50  # shortest paths read back per BFS pass before ranking


# ------------------------------------------------------------------ helpers
def _label(node_id: str) -> str:
    return "Sanction" if str(node_id).startswith(SANCTION_PREFIX) else "Node"


def _kind(node) -> str:
    return "Sanction" if "Sanction" in node.labels else next((l for l in node.labels if l in KINDS), "Node")


def _brief(node) -> dict:
    p = node.properties
    d = {"id": p.get("id"), "kind": _kind(node), "name": p.get("name"), "sanctioned": "Sanction" in node.labels}
    if p.get("jurisdiction"):
        d["jurisdiction"] = p["jurisdiction"]
    return d


def _edge(e, ids: dict) -> dict:
    """ids: internal node id -> public id."""
    d = {"source": ids[e.src_node], "target": ids[e.dest_node], "type": e.relation}
    if e.properties.get("link"):
        d["link"] = e.properties["link"]
    return d


def _path(nodes: list, edges: list) -> dict:
    """Ordered falkordb nodes/edges (subject ... sanction) -> SPEC path dict."""
    ids = {n.id: n.properties["id"] for n in nodes}
    match = edges[-1].properties
    return {"hops": len(edges), "weight": float(sum(e.properties.get("w", 1) for e in edges)),
            "sanction": dict(nodes[-1].properties),
            "match": {"score": match.get("score"), "method": match.get("method")},
            "nodes": [n.properties["id"] for n in nodes], "edges": [_edge(e, ids) for e in edges],
            "_raw": (nodes, edges)}


def _subgraph(paths: list) -> dict:
    nodes, links = {}, {}
    for p in paths:
        pn, pe = p["_raw"]
        for n in pn:
            nodes[n.properties["id"]] = _brief(n)
        for e in p["edges"]:
            links[(e["source"], e["target"], e["type"])] = e
    return {"nodes": list(nodes.values()), "links": list(links.values())}


def _public(paths: list) -> list:
    return [{k: v for k, v in p.items() if k != "_raw"} for p in paths]


# ------------------------------------------------------------------ 1. search
SEARCH = ("CALL db.idx.fulltext.queryNodes('Node', $q) YIELD node, score "
          "RETURN node, score ORDER BY score DESC LIMIT $limit")


def search(g, q: str, limit: int = 10) -> dict:
    """Full-text search over ICIJ node names (prefix match on every word)."""
    words = re.findall(r"\w+", q or "")
    params = {"q": " ".join(f"{w}*" if len(w) > 2 else w for w in words), "limit": int(limit)}
    rows = g.ro_query(SEARCH, params).result_set if words else []
    cands = [{**_brief(n), "jurisdiction": n.properties.get("jurisdiction", ""),
              "countries": n.properties.get("countries", "")} for n, _ in rows]
    for c in cands:
        c.pop("sanctioned", None)
    return {"cypher": SEARCH, "params": params, "candidates": cands}


# ------------------------------------------------------------------ 2. sanction paths
# Exact layered BFS inside FalkorDB (one LAYER query per hop) from the subject until the first hop that reaches a
# :Sanction, then shortest paths are read back along BFS parent links (no dead-end enumeration) and their edges
# fetched in one STEPS query. A second strong-only pass (r.w <= 1: officer/intermediary/address/same-as edges and
# >= 0.95 name matches) runs when the best path has a weak edge, so a weak shortcut never hides a strong route.
# (Measured on the 225k-node real graph: allShortestPaths / algo.SPpaths enumerate dead ends through hubs and can
# take > 60 s; this BFS stays ~0.02-1.5 s.)
START = "MATCH (s:Node {id: $id}) RETURN ID(s)"
LAYER = ("UNWIND $frontier AS i MATCH (n) WHERE ID(n) = i WITH n, i MATCH (n)-[r]-(m) "
         "WHERE r.w <= $max_w AND m.id <> $remove_id RETURN i, ID(m), m:Sanction")
STEPS = ("UNWIND $pairs AS p WITH p[0] AS x, p[1] AS y MATCH (a) WHERE ID(a) = x WITH a, x, y "
         "MATCH (b) WHERE ID(b) = y WITH a, b, x, y MATCH (a)-[r]-(b) RETURN x, y, a, r, b ORDER BY r.w")
ANY, STRONG = 99.0, 1.0


def _bfs(g, node_id: str, max_len: int, remove_id: str, max_w: float):
    """-> (sanction hits, parents) for the first BFS layer that reaches a :Sanction (internal ids)."""
    start = g.ro_query(START, {"id": node_id}).result_set
    if not start:
        return [], {}
    depth, parents, frontier = {start[0][0]: 0}, {}, [start[0][0]]
    for d in range(1, max_len + 1):
        nxt, hits = [], []
        params = {"frontier": frontier, "max_w": max_w, "remove_id": remove_id}
        for i, m, is_sanction in g.ro_query(LAYER, params).result_set:
            if m not in depth:
                depth[m] = d
                (hits if is_sanction else nxt).append(m)
            if depth[m] == d:
                parents.setdefault(m, []).append(i)
        if hits or not nxt:
            return hits, parents
        frontier = nxt
    return [], parents


def _chains(hits: list, parents: dict, limit: int) -> list[list[int]]:
    """Walk parent links back from each hit -> up to `limit` shortest node-id chains (subject first)."""
    out = []

    def walk(chain):
        if len(out) < limit:
            if chain[-1] not in parents:
                out.append(chain[::-1])
            for p in parents.get(chain[-1], ()):
                walk(chain + [p])

    for h in hits:
        walk([h])
    return out


def _paths_from_chains(g, chains: list) -> list:
    pairs = sorted({(c[i], c[i + 1]) for c in chains for i in range(len(c) - 1)})
    step = {}
    for x, y, a, r, b in (g.ro_query(STEPS, {"pairs": [list(p) for p in pairs]}).result_set if pairs else []):
        step.setdefault((x, y), (a, r, b))  # strongest edge per step
    return [_path([step[(c[0], c[1])][0]] + [step[(c[i], c[i + 1])][2] for i in range(len(c) - 1)],
                  [step[(c[i], c[i + 1])][1] for i in range(len(c) - 1)]) for c in chains]


def _find(g, node_id: str, max_hops: int, remove_id: str = ""):
    """Ranked, de-duplicated shortest paths (<= max_hops ICIJ edges + the MATCHES edge)."""
    found = {}
    for max_w in (ANY, STRONG):
        hits, parents = _bfs(g, node_id, int(max_hops) + 1, remove_id, max_w)
        for p in _paths_from_chains(g, _chains(hits, parents, PATH_LIMIT)):
            found.setdefault(tuple(p["nodes"]), p)
        best = min(found.values(), key=lambda p: p["weight"], default=None)
        if best is None or best["weight"] == best["hops"]:  # nothing found, or already all-strong
            break
    paths = sorted(found.values(), key=lambda p: (p["weight"], p["hops"]))
    return [START, LAYER, STEPS], {"id": node_id, "max_hops": max_hops, "remove_id": remove_id}, paths


def sanction_paths(g, node_id: str, max_hops: int = 6, k: int = 3) -> dict:
    cyphers, params, paths = _find(g, node_id, max_hops)
    paths = paths[:k]
    return {"cypher": cyphers, "params": params, "paths": _public(paths), "subgraph": _subgraph(paths),
            "found": bool(paths)}


# ------------------------------------------------------------------ 3. neighborhood
NEIGHBORHOOD = ("MATCH (s:{label} {{id: $id}})-[*0..{hops}]-(n) WITH DISTINCT n LIMIT $limit WITH collect(n) AS ns "
                "UNWIND ns AS a OPTIONAL MATCH (a)-[r]->(b) WHERE b IN ns "
                "RETURN a, collect({{source: a.id, target: b.id, type: type(r), link: r.link}})")


def neighborhood(g, node_id: str, hops: int = 1, limit: int = 150) -> dict:
    cy = NEIGHBORHOOD.format(label=_label(node_id), hops=int(hops))
    params = {"id": node_id, "limit": int(limit)}
    nodes, links = [], []
    for a, rels in g.ro_query(cy, params).result_set:
        nodes.append(_brief(a))
        links += [{k: v for k, v in r.items() if v is not None} for r in rels if r["target"] is not None]
    return {"cypher": cy, "params": params, "subgraph": {"nodes": nodes, "links": links}}


# ------------------------------------------------------------------ 4. chokepoints
NODES_BY_ID = "UNWIND $ids AS i MATCH (n:Node {id: i}) RETURN n"
# FalkorDB's built-in PageRank over the whole leak graph: how central a candidate is in the wider offshore
# network, not just on our paths. Reported as "top X%". The graph is read-only, so scores are computed once
# per process (~1 s) and cached; repeated whole-graph runs under load would only waste database memory.
PAGERANK = "CALL algo.pageRank('Node', NULL) YIELD node, score RETURN node.id, score"
_PR: dict | None = None
_PR_SORTED: list | None = None
_PR_LOCK = threading.Lock()


def _pagerank_top_pct(g, ids: list) -> dict:
    global _PR, _PR_SORTED
    with _PR_LOCK:
        if _PR is None:
            _PR = dict(g.ro_query(PAGERANK).result_set)
            _PR_SORTED = sorted(_PR.values())
    n = len(_PR_SORTED)
    return {i: round(100.0 * (n - bisect.bisect_right(_PR_SORTED, _PR[i])) / n, 1) for i in ids if i in _PR}


def chokepoints(g, paths: list) -> dict:
    """Intermediate nodes ranked by how many sanction paths run through them, then closest to the subject, then by network PageRank.
    betweenness = share of our paths through the node; pagerank_top_pct = FalkorDB algo.pageRank percentile."""
    count, first_pos = {}, {}
    for p in paths:
        for pos, nid in enumerate(p["nodes"][1:-1], 1):
            count[nid] = count.get(nid, 0) + 1
            first_pos[nid] = min(first_pos.get(nid, pos), pos)
    params = {"ids": list(count)}
    cypher = [NODES_BY_ID, PAGERANK]
    if not count:
        return {"cypher": cypher, "params": params, "chokepoints": []}
    top = _pagerank_top_pct(g, params["ids"])
    out = [{"id": (i := n.properties["id"]), "name": n.properties.get("name"), "kind": _kind(n),
            "paths_through": count[i], "betweenness": round(count[i] / len(paths), 3),
            "pagerank_top_pct": round(top.get(i, 100.0), 1)}
           for (n,) in g.ro_query(NODES_BY_ID, params).result_set]
    out.sort(key=lambda c: (-c["paths_through"], first_pos[c["id"]], c["pagerank_top_pct"]))
    return {"cypher": cypher, "params": params, "chokepoints": out}


# ------------------------------------------------------------------ 5. counterfactual
def counterfactual(g, node_id: str, remove_id: str, max_hops: int = 6) -> dict:
    """Same exact BFS as sanction_paths with `remove_id` skipped: no path left = the link runs through it."""
    cyphers, params, paths = _find(g, node_id, max_hops, remove_id)
    paths = paths[:3]
    return {"cypher": cyphers, "params": params, "still_exposed": bool(paths), "paths": _public(paths),
            "subgraph": _subgraph(paths)}


# ------------------------------------------------------------------ 6. shell cluster
CLUSTER = ("MATCH (s:Node {id: $id}) "
           "OPTIONAL MATCH (s)-[:REGISTERED_ADDRESS*0..1]-(a:Address)-[:REGISTERED_ADDRESS]-(m:Entity) "
           "WITH s, count(DISTINCT a) AS addrs, collect(DISTINCT m) AS by_addr "
           "OPTIONAL MATCH (s)-[:INTERMEDIARY_OF*0..1]-(i:Intermediary)-[:INTERMEDIARY_OF]-(m2:Entity) "
           "RETURN addrs, size(by_addr), [x IN by_addr[..8] | x.name], count(DISTINCT i), count(DISTINCT m2)")


def shell_cluster(g, node_id: str) -> dict:
    """Mass-registration signal. `size` = entities sharing the subject's registered address(es) (incl. itself);
    intermediary sharing is reported separately (big agents serve thousands of companies, so it is not a signal alone)."""
    params = {"id": node_id}
    rows = g.ro_query(CLUSTER, params).result_set
    addrs, size, sample, inters, by_inter = rows[0] if rows else (0, 0, [], 0, 0)
    return {"cypher": CLUSTER, "params": params, "size": size, "shared_addresses": addrs,
            "shared_intermediaries": inters, "entities_via_intermediary": by_inter, "members_sample": sample}


# ------------------------------------------------------------------ 7. node detail
DETAIL = "MATCH (n:{label} {{id: $id}}) RETURN n"


def node_detail(g, node_id: str) -> dict:
    cy, params = DETAIL.format(label=_label(node_id)), {"id": node_id}
    rows = g.ro_query(cy, params).result_set
    node = {**rows[0][0].properties, "kind": _kind(rows[0][0])} if rows else None
    return {"cypher": cy, "params": params, "node": node}


# ------------------------------------------------------------------ 8. stats
LABELS = "CALL db.labels() YIELD label RETURN label"
TYPES = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
COUNT_LABEL = "MATCH (n:{0}) RETURN count(n)"
COUNT_TYPE = "MATCH ()-[r:{0}]->() RETURN count(r)"


def stats(g) -> dict:
    labels = {l: g.ro_query(COUNT_LABEL.format(l)).result_set[0][0] for (l,) in g.ro_query(LABELS).result_set}
    rels = {t: g.ro_query(COUNT_TYPE.format(t)).result_set[0][0] for (t,) in g.ro_query(TYPES).result_set}
    return {"cypher": [LABELS, TYPES, COUNT_LABEL, COUNT_TYPE], "params": {}, "labels": labels, "relationships": rels}
