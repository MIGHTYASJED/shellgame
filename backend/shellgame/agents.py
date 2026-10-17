"""Agent orchestration -> event stream.

  Memory       recall precedents at start, write Case at end          (memory.py, per-tenant graph)
  Investigator LLM picks among FIXED tools with typed args (never Cypher); scripted fallback
  Skeptic      rule-based weak-link review of every path (+ optional LLM commentary)
  Gatekeeper   deterministic verdict (gate.py) + due-diligence memo citing node ids and Cypher

`investigate(node_id, tenant)` is an async generator of SPEC events:
  {"type", "agent", "text"?, "tool"?, "args"?, "cypher"?, "params"?, "result"?, "highlight"?, "subgraph"?, "ts"}
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, AsyncIterator, Callable

from . import gate, llm, memory
from ._compat import main_graph, tools

log = logging.getLogger("shellgame.agents")

DEFAULT_PACE = 0.4
MAX_STEPS = 6
DEFAULT_MAX_HOPS = gate.DEFAULT_MAX_HOPS


def pace_seconds() -> float:
    try:
        return max(0.0, float(os.environ.get("SHELLGAME_PACE", DEFAULT_PACE)))
    except ValueError:
        return DEFAULT_PACE


# ============================================================ tool registry (LLM-visible)
NODE_ID = {"type": "string", "description": "Exact node id from a previous tool result (never invent ids)."}

TOOL_SPECS: list[dict] = [
    {"name": "sanction_paths",
     "description": "Shortest weighted paths from a node to any OpenSanctions-listed party (final hop is a name MATCH). "
                    "Returns paths with hops, weight, edges and match score. 'found=false' means no exposure within max_hops.",
     "parameters": {"type": "object", "properties": {
         "node_id": NODE_ID,
         "max_hops": {"type": "integer", "minimum": 1, "maximum": 6, "default": 6},
         "k": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3}},
         "required": ["node_id"]}},
    {"name": "shell_cluster",
     "description": "Mass-registration signal: how many entities share this node's registered address / intermediary.",
     "parameters": {"type": "object", "properties": {"node_id": NODE_ID}, "required": ["node_id"]}},
    {"name": "chokepoints",
     "description": "Rank intermediate nodes by how many of the most recent sanction paths pass through them. "
                    "Uses the paths from the last sanction_paths call; takes no arguments.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "counterfactual",
     "description": "Recompute sanction paths for the subject with one node removed. still_exposed=false means "
                    "removing that node breaks every link.",
     "parameters": {"type": "object", "properties": {"remove_id": NODE_ID}, "required": ["remove_id"]}},
    {"name": "node_detail",
     "description": "All stored properties of one node.",
     "parameters": {"type": "object", "properties": {"node_id": NODE_ID}, "required": ["node_id"]}},
    {"name": "neighborhood",
     "description": "Nodes and edges within N hops of a node.",
     "parameters": {"type": "object", "properties": {
         "node_id": NODE_ID, "hops": {"type": "integer", "minimum": 1, "maximum": 2, "default": 1}},
         "required": ["node_id"]}},
    {"name": "recall",
     "description": "Look up prior Cases in this tenant's memory that touched any of the given node ids.",
     "parameters": {"type": "object", "properties": {
         "node_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 50}},
         "required": ["node_ids"]}},
    {"name": "finish",
     "description": "Call when you have enough evidence for the Gatekeeper. Give a one-paragraph rationale.",
     "parameters": {"type": "object", "properties": {"rationale": {"type": "string"}}, "required": ["rationale"]}},
]
TOOL_NAMES = {t["name"] for t in TOOL_SPECS}

INVESTIGATOR_SYSTEM = """You are the Investigator agent in a sanctions-exposure due-diligence system over a FalkorDB graph
of ICIJ Offshore Leaks data linked to OpenSanctions records.
You can ONLY act through the provided tools. You never write database queries. Use node ids exactly as returned.
Goal: determine whether the subject has a possible link to a sanctions-listed party, how strong it is, which
intermediary is the chokepoint, and whether removing it breaks the link. Typical plan:
sanction_paths(subject) -> shell_cluster(subject) -> chokepoints -> counterfactual(top chokepoint) -> finish.
If sanction_paths finds nothing, "no path within N hops" is a valid, important result: check shell_cluster and finish.
Keep each thought to one or two sentences. Use neutral language: "possible link", "exposure", never "guilty".
You have at most {max_steps} tool calls."""


class ToolError(ValueError):
    pass


# ============================================================ helpers
def _now() -> float:
    return round(time.time(), 3)


def _hl(nodes=(), links=()) -> dict:
    seen, ls = set(), []
    for l in links:
        key = (l.get("source"), l.get("target"))
        if key not in seen and None not in key:
            seen.add(key)
            ls.append({"source": key[0], "target": key[1]})
    return {"nodes": list(dict.fromkeys(n for n in nodes if n)), "links": ls}


def _path_highlight(paths: list[dict]) -> dict:
    nodes, links = [], []
    for p in paths:
        nodes += p.get("nodes") or []
        links += p.get("edges") or []
    return _hl(nodes, links)


def _strip(res: dict, *drop: str) -> dict:
    return {k: v for k, v in res.items() if k not in {"cypher", "params", "subgraph", *drop}}


def _cy_list(cy) -> list[str]:
    if not cy:
        return []
    return list(cy) if isinstance(cy, (list, tuple)) else [cy]


class Ctx:
    """Mutable investigation state shared by the agents."""

    def __init__(self, node_id: str, tenant: str, max_hops: int):
        self.run_id = uuid.uuid4().hex[:8]
        self.subject_id = node_id
        self.tenant = memory.sanitize_tenant(tenant)
        self.max_hops = max_hops
        self.subject: dict = {}
        self.nodes: dict[str, dict] = {}       # id -> subgraph node (for names/kinds/subgraphs)
        self.valid_ids: set[str] = set()
        self.paths: list[dict] = []
        self.paths_found: bool | None = None
        self.cluster: dict | None = None
        self.chokepoints: list[dict] = []
        self.counterfactuals: dict[str, dict] = {}
        self.queries: list[dict] = []          # {"tool","cypher","params"} for the memo
        self.precedents: dict[str, dict] = {}  # case id -> case
        self.reviews: list[dict] = []
        self.rationale = ""

    def absorb_subgraph(self, sg: dict | None):
        for n in (sg or {}).get("nodes") or []:
            if n.get("id"):
                self.nodes.setdefault(n["id"], n)
                self.valid_ids.add(n["id"])

    def name(self, nid: str) -> str:
        return (self.nodes.get(nid) or {}).get("name") or nid

    def subgraph_for(self, paths: list[dict]) -> dict:
        ids = list(dict.fromkeys(i for p in paths for i in p.get("nodes") or []))
        nodes = [self.nodes.get(i) or {"id": i, "kind": "Sanction" if str(i).startswith("san:") else "Other",
                                         "name": i, "sanctioned": str(i).startswith("san:")} for i in ids]
        links, seen = [], set()
        for p in paths:
            for e in p.get("edges") or []:
                k = (e.get("source"), e.get("target"), e.get("type"))
                if k not in seen:
                    seen.add(k)
                    links.append({kk: e.get(kk) for kk in ("source", "target", "type", "link") if e.get(kk) is not None})
        return {"nodes": nodes, "links": links}


# ============================================================ tool execution (validated)
async def _run(fn: Callable, *a, **kw):
    return await asyncio.to_thread(fn, *a, **kw)


async def _node_exists(ctx: Ctx, g, nid: Any) -> bool:
    if not isinstance(nid, str) or not nid or len(nid) > 200:
        return False
    if nid in ctx.valid_ids:
        return True
    try:
        det = await _run(tools.node_detail, g, node_id=nid)
    except Exception:
        return False
    if det.get("node"):
        ctx.valid_ids.add(nid)
        node = det["node"]
        ctx.nodes.setdefault(nid, {"id": nid, "kind": node.get("kind"), "name": node.get("name"),
                                   "sanctioned": node.get("kind") == "Sanction"})
        return True
    return False


def _int_arg(args: dict, key: str, default: int, lo: int, hi: int) -> int:
    v = args.get(key, default)
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise ToolError(f"{key} must be an integer")
    try:
        v = int(v)
    except ValueError:
        raise ToolError(f"{key} must be an integer") from None
    return max(lo, min(hi, v))


async def execute_tool(ctx: Ctx, g, name: str, args: dict) -> tuple[dict, dict]:
    """Validate + run one tool. Returns (raw_result, event_fields). Raises ToolError on bad input."""
    if name not in TOOL_NAMES or name == "finish":
        raise ToolError(f"unknown tool '{name}'")
    if not isinstance(args, dict):
        raise ToolError("args must be an object")
    allowed = set(next(t for t in TOOL_SPECS if t["name"] == name)["parameters"]["properties"])
    extra = set(args) - allowed
    if extra:
        raise ToolError(f"unexpected argument(s) {sorted(extra)} for {name}")
    for key in ("node_id", "remove_id"):
        if key in allowed and key in args and not await _node_exists(ctx, g, args[key]):
            raise ToolError(f"unknown node id {args[key]!r}")
    if "node_id" in allowed and "node_id" in (next(t for t in TOOL_SPECS if t["name"] == name)["parameters"].get("required") or []):
        if "node_id" not in args:
            raise ToolError("node_id is required")

    ev: dict[str, Any] = {}
    if name == "sanction_paths":
        mh = _int_arg(args, "max_hops", ctx.max_hops, 1, ctx.max_hops)
        k = _int_arg(args, "k", 3, 1, 5)
        res = await _run(tools.sanction_paths, g, node_id=args["node_id"], max_hops=mh, k=k)
        ctx.absorb_subgraph(res.get("subgraph"))
        for p in res.get("paths") or []:
            ctx.valid_ids.update(p.get("nodes") or [])
        if args["node_id"] == ctx.subject_id:
            ctx.paths = list(res.get("paths") or [])
            ctx.paths_found = bool(res.get("found", bool(ctx.paths)))
        ev["highlight"] = _path_highlight(res.get("paths") or []) if res.get("paths") else _hl([args["node_id"]])
        ev["subgraph"] = res.get("subgraph") or ctx.subgraph_for(res.get("paths") or [])
        ev["result"] = {"found": bool(res.get("found", res.get("paths"))),
                        "paths": [{"hops": p.get("hops"), "icij_hops": gate.icij_hops(p), "weight": p.get("weight"),
                                   "sanction": {"id": (p.get("sanction") or {}).get("id"),
                                                "name": (p.get("sanction") or {}).get("name"),
                                                "programs": (p.get("sanction") or {}).get("programs")},
                                   "match": p.get("match"), "nodes": p.get("nodes"), "edges": p.get("edges")}
                                  for p in res.get("paths") or []]}
    elif name == "shell_cluster":
        res = await _run(tools.shell_cluster, g, node_id=args["node_id"])
        if args["node_id"] == ctx.subject_id:
            ctx.cluster = res
        ev["highlight"] = _hl([args["node_id"]])
        ev["result"] = _strip(res)
        if res.get("subgraph"):
            ev["subgraph"] = res["subgraph"]
    elif name == "chokepoints":
        if not ctx.paths:
            raise ToolError("chokepoints needs sanction paths for the subject; run sanction_paths first")
        res = await _run(tools.chokepoints, g, paths=ctx.paths)
        cps = [c for c in res.get("chokepoints") or [] if c.get("id") not in (ctx.subject_id,)
               and not str(c.get("id", "")).startswith("san:")]
        ctx.chokepoints = cps
        ev["highlight"] = _hl([c["id"] for c in cps[:3]])
        ev["result"] = {"chokepoints": cps}
    elif name == "counterfactual":
        rid = args["remove_id"]
        if rid == ctx.subject_id:
            raise ToolError("cannot remove the subject itself")
        res = await _run(tools.counterfactual, g, node_id=ctx.subject_id, remove_id=rid, max_hops=ctx.max_hops)
        ctx.counterfactuals[rid] = res
        alt = res.get("paths") or []
        ctx.absorb_subgraph(res.get("subgraph"))
        hl = _path_highlight(alt) if alt else _hl([])
        hl["removed"] = [rid]
        ev["highlight"] = hl
        ev["subgraph"] = res.get("subgraph") or ctx.subgraph_for(alt)
        ev["result"] = {"removed": rid, "removed_name": ctx.name(rid), "still_exposed": bool(res.get("still_exposed")),
                        "paths": [{"hops": p.get("hops"), "nodes": p.get("nodes"), "edges": p.get("edges"),
                                   "match": p.get("match")} for p in alt]}
        args = {"node_id": ctx.subject_id, "remove_id": rid, "max_hops": ctx.max_hops}
    elif name == "node_detail":
        res = await _run(tools.node_detail, g, node_id=args["node_id"])
        ev["highlight"] = _hl([args["node_id"]])
        ev["result"] = _strip(res)
    elif name == "neighborhood":
        hops = _int_arg(args, "hops", 1, 1, 2)
        res = await _run(tools.neighborhood, g, node_id=args["node_id"], hops=hops)
        ctx.absorb_subgraph(res.get("subgraph"))
        ev["subgraph"] = res.get("subgraph")
        sg = res.get("subgraph") or {}
        ev["highlight"] = _hl([args["node_id"]])
        ev["result"] = {"nodes": len(sg.get("nodes") or []), "links": len(sg.get("links") or [])}
    elif name == "recall":
        ids = args.get("node_ids")
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise ToolError("node_ids must be a list of strings")
        res = await _run(memory.recall, ctx.tenant, ids[:50])
        for c in res["cases"]:
            ctx.precedents.setdefault(c["id"], c)
        ev["highlight"] = _hl([h["id"] for c in res["cases"] for h in c.get("hits") or []])
        ev["result"] = {"cases": res["cases"]}
    else:  # pragma: no cover
        raise ToolError(name)

    ctx.queries.append({"tool": name, "cypher": res.get("cypher"), "params": res.get("params")})
    ev.update({"cypher": res.get("cypher"), "params": res.get("params"), "args": args})
    return res, ev


# ============================================================ orchestration
class Emitter:
    def __init__(self, run_id: str, pace: float):
        self.run_id, self.pace, self.seq = run_id, pace, 0

    def ev(self, type_: str, agent: str, **kw) -> dict:
        self.seq += 1
        e = {"type": type_, "agent": agent, "ts": _now(), "seq": self.seq, "run_id": self.run_id}
        e.update({k: v for k, v in kw.items() if v is not None})
        return e


def _tool_call_text(name: str, args: dict, ctx: Ctx) -> str:
    if name == "sanction_paths":
        return f"Tracing shortest paths from {ctx.name(args.get('node_id'))} to any sanctions-listed party (<= {args.get('max_hops', ctx.max_hops)} hops)."
    if name == "shell_cluster":
        return f"Checking whether {ctx.name(args.get('node_id'))} shares a registered address or agent with many other entities."
    if name == "chokepoints":
        return "Ranking intermediaries by how many exposure paths run through them."
    if name == "counterfactual":
        return f"Counterfactual: remove {ctx.name(args.get('remove_id'))} and recompute every path."
    if name == "recall":
        return "Checking this tenant's case memory for precedents."
    if name == "neighborhood":
        return f"Expanding the neighborhood of {ctx.name(args.get('node_id'))}."
    return f"Looking up {ctx.name(args.get('node_id', ''))}."


def _tool_result_text(name: str, res: dict, ctx: Ctx) -> str:
    if name == "sanction_paths":
        ps = res.get("paths") or []
        if not ps:
            return f"No path found within {ctx.max_hops} hops: no sanctions exposure in this dataset."
        p = ps[0]
        chain = " -> ".join(ctx.name(n) for n in p.get("nodes") or [])
        return (f"{len(ps)} possible link(s). Shortest: {gate.icij_hops(p)} corporate hops + name match "
                f"(score {gate.match_score(p):.2f}): {chain}")
    if name == "shell_cluster":
        s = int(res.get("size") or 0)
        flag = " -> mass-registration signal" if s >= gate.CLUSTER_MIN else " (below mass-registration threshold)"
        return f"{s} entities share the subject's registered address/intermediary{flag}."
    if name == "chokepoints":
        cps = ctx.chokepoints
        if not cps:
            return "No intermediate chokepoint."
        c = cps[0]
        return f"Chokepoint: {c.get('name')} ({c.get('kind')}) sits on {c.get('paths_through')} of {len(ctx.paths)} path(s)."
    if name == "counterfactual":
        rid = (res.get("_removed") or "")
        if res.get("still_exposed"):
            return f"Still exposed without {ctx.name(rid)}: {len(res.get('paths') or [])} alternative path(s) remain."
        return f"Removing {ctx.name(rid)} breaks every link: it is the single point of exposure."
    if name == "recall":
        n = len(res.get("cases") or [])
        return f"{n} prior case(s) touch these nodes." if n else "No prior cases."
    if name == "neighborhood":
        sg = res.get("subgraph") or {}
        return f"{len(sg.get('nodes') or [])} nodes / {len(sg.get('links') or [])} edges in view."
    if name == "node_detail":
        n = res.get("node") or {}
        return f"{n.get('name')} ({n.get('kind')}, {n.get('jurisdiction') or n.get('countries') or 'n/a'})."
    return "done"


async def _tool_step(ctx: Ctx, g, em: Emitter, name: str, args: dict, agent: str = "investigator"):
    """Yield tool_call + tool_result (or error) events; returns via ctx."""
    yield em.ev("tool_call", agent, tool=name, args=args, text=_tool_call_text(name, args, ctx))
    try:
        res, fields = await execute_tool(ctx, g, name, args)
    except ToolError as e:
        yield em.ev("error", agent, tool=name, args=args, text=f"Rejected tool call: {e}", recoverable=True)
        return
    if name == "counterfactual":
        res = {**res, "_removed": args.get("remove_id")}
    yield em.ev("tool_result", agent, tool=name, text=_tool_result_text(name, res, ctx), **fields)


async def _recall_step(ctx: Ctx, em: Emitter, ids: list[str], reason: str):
    try:
        res = await _run(memory.recall, ctx.tenant, ids)
    except Exception as e:  # memory must never break an investigation
        log.warning("recall failed: %s", e)
        return
    ctx.queries.append({"tool": "recall", "cypher": res["cypher"], "params": res["params"]})
    new = [c for c in res["cases"] if c["id"] not in ctx.precedents]
    for c in new:
        ctx.precedents[c["id"]] = c
    if not new:
        return
    lines = []
    for c in new:
        hits = ", ".join(sorted({h.get("name") or h["id"] for h in c.get("hits") or []})[:4])
        lines.append(f"Case {c['id']} ({c.get('created_at')}) on {c.get('subject_name')} -> {c.get('verdict')}; overlaps on {hits}")
    yield em.ev("recall", "memory", text=f"Precedent found ({reason}): " + " | ".join(lines),
                cypher=res["cypher"], params=res["params"], result={"cases": new, "graph": res["graph"]},
                highlight=_hl([h["id"] for c in new for h in c.get("hits") or []]))


# ---------------------------------------------------------------- investigator
async def _scripted_investigator(ctx: Ctx, g, em: Emitter):
    yield em.ev("thought", "investigator",
                text=f"Plan: trace {ctx.subject.get('name')} to sanctions-listed parties, test for a mass-registration "
                     f"cluster, find the chokepoint, then cut it and re-check.")
    async for e in _tool_step(ctx, g, em, "sanction_paths", {"node_id": ctx.subject_id, "max_hops": ctx.max_hops, "k": 3}):
        yield e
    async for e in _recall_step(ctx, em, [i for p in ctx.paths for i in p.get("nodes") or []], "path overlap"):
        yield e
    async for e in _tool_step(ctx, g, em, "shell_cluster", {"node_id": ctx.subject_id}):
        yield e
    if not ctx.paths:
        yield em.ev("thought", "investigator",
                    text=f"No path within {ctx.max_hops} hops. That is a first-class result: no exposure in this dataset.")
        return
    async for e in _tool_step(ctx, g, em, "chokepoints", {}):
        yield e
    if ctx.chokepoints:
        top = ctx.chokepoints[0]
        yield em.ev("thought", "investigator",
                    text=f"{top.get('name')} carries the most exposure. If it is the only bridge, cutting it should break the link.")
        async for e in _tool_step(ctx, g, em, "counterfactual", {"remove_id": top["id"]}):
            yield e


async def _llm_investigator(ctx: Ctx, g, em: Emitter):
    system = INVESTIGATOR_SYSTEM.format(max_steps=MAX_STEPS)
    s = ctx.subject
    messages: list[dict] = [{"role": "user", "content": (
        f"Subject: {s.get('name')} (id={ctx.subject_id}, kind={s.get('kind')}, jurisdiction={s.get('jurisdiction') or 'n/a'}).\n"
        f"Tenant memory precedents already found: {len(ctx.precedents)}.\nInvestigate.")}]
    steps = 0
    while steps < MAX_STEPS:
        try:
            resp = await llm.chat_tools(system, messages, TOOL_SPECS)
        except Exception as e:
            log.warning("LLM error: %s", e)
            yield em.ev("thought", "investigator", text=f"LLM unavailable ({type(e).__name__}); continuing with the scripted plan.")
            return
        if resp.get("text"):
            yield em.ev("thought", "investigator", text=resp["text"][:1200])
        calls = resp.get("tool_calls") or []
        messages.append({"role": "assistant", "text": resp.get("text") or "", "tool_calls": calls})
        if not calls:
            return
        finished = False
        for tc in calls:
            name, args = tc.get("name"), tc.get("args") or {}
            if name == "finish":
                ctx.rationale = str(args.get("rationale") or "")[:2000]
                finished = True
                content = "ok"
            else:
                steps += 1
                content = None
                async for e in _tool_step(ctx, g, em, name, args):
                    yield e
                    if e["type"] == "tool_result":
                        content = json.dumps({"text": e.get("text"), "result": e.get("result")}, default=str)[:6000]
                    elif e["type"] == "error":
                        content = json.dumps({"error": e.get("text")})
                if name == "sanction_paths" and args.get("node_id") == ctx.subject_id:
                    async for e in _recall_step(ctx, em, [i for p in ctx.paths for i in p.get("nodes") or []], "path overlap"):
                        yield e
            messages.append({"role": "tool", "tool_call_id": tc.get("id") or uuid.uuid4().hex, "name": name or "",
                             "content": content or "{}"})
        if finished:
            return


async def _complete_evidence(ctx: Ctx, g, em: Emitter):
    """Deterministic floor: whatever the LLM did, the gate always gets paths, cluster, chokepoint, counterfactual."""
    if ctx.paths_found is None:
        async for e in _tool_step(ctx, g, em, "sanction_paths", {"node_id": ctx.subject_id, "max_hops": ctx.max_hops, "k": 3}):
            yield e
    if ctx.cluster is None:
        async for e in _tool_step(ctx, g, em, "shell_cluster", {"node_id": ctx.subject_id}):
            yield e
    if ctx.paths and not ctx.chokepoints:
        async for e in _tool_step(ctx, g, em, "chokepoints", {}):
            yield e
    if ctx.chokepoints and ctx.chokepoints[0]["id"] not in ctx.counterfactuals:
        async for e in _tool_step(ctx, g, em, "counterfactual", {"remove_id": ctx.chokepoints[0]["id"]}):
            yield e


# ---------------------------------------------------------------- skeptic
def review_path(p: dict, ctx: Ctx | None = None) -> dict:
    """Rule-based review of one path. Always runs (LLM optional on top)."""
    name = (lambda i: ctx.name(i)) if ctx else (lambda i: i)
    weak_edges = [e for e in p.get("edges") or [] if gate.is_weak_type(e.get("type"))]
    reasons = gate.path_weak_reasons(p)
    notes = []
    m = p.get("match") or {}
    method = (m.get("method") or "").lower()
    nodes = p.get("nodes") or []
    if len(nodes) >= 2:
        matched, san = nodes[-2], nodes[-1]
        san_name = (p.get("sanction") or {}).get("name") or name(san)
        if method in {"alias", "token"} or name(matched).lower() != str(san_name).lower():
            notes.append(f"Name match is fuzzy ({method or 'n/a'}): '{name(matched)}' vs listed '{san_name}' "
                         f"(score {gate.match_score(p):.2f}); confirm with DOB / nationality before acting.")
    nominee = [e for e in p.get("edges") or [] if "nominee" in str(e.get("link") or "").lower()]
    if nominee:
        notes.append("Path runs through a nominee role; nominees often front for many unrelated clients, "
                     "so treat this as exposure, not proof of control.")
    weakened = bool(reasons)
    return {"weakened": weakened, "reasons": reasons, "notes": notes, "weak_edges": weak_edges,
            "hops": gate.icij_hops(p), "score": gate.match_score(p)}


async def _skeptic(ctx: Ctx, em: Emitter):
    if not ctx.paths:
        yield em.ev("skeptic", "skeptic",
                    text=f"Nothing to challenge: no path within {ctx.max_hops} hops. Caveat: absence is relative to this dataset only.",
                    result={"reviews": []})
        return
    ctx.reviews = []
    for i, p in enumerate(ctx.paths):
        r = review_path(p, ctx)
        ctx.reviews.append(r)
        if r["weakened"]:
            text = f"Path {i + 1} WEAKENED: " + "; ".join(r["reasons"]) + "."
            hl = _hl([x for e in r["weak_edges"] for x in (e["source"], e["target"])] or p.get("nodes")[-2:], r["weak_edges"])
        else:
            text = f"Path {i + 1} holds: {r['hops']} strong corporate hops, match score {r['score']:.2f}."
            hl = _path_highlight([p])
        if r["notes"]:
            text += " " + " ".join(r["notes"])
        yield em.ev("skeptic", "skeptic", text=text, highlight=hl,
                    result={"path_index": i, **{k: v for k, v in r.items()}})
    for rid, cf in ctx.counterfactuals.items():
        if not cf.get("still_exposed"):
            yield em.ev("skeptic", "skeptic",
                        text=f"Counterfactual confirms {ctx.name(rid)} is the single bridge; the exposure is "
                             f"only as strong as that one relationship.",
                        highlight=_hl([rid]), result={"single_point_of_failure": rid})
    if llm.enabled():
        facts = [{"path": [ctx.name(n) for n in p.get("nodes") or []], "edges": [e.get("type") for e in p.get("edges") or []],
                  "match": p.get("match"), "review": {k: r[k] for k in ("weakened", "reasons", "notes")}}
                 for p, r in zip(ctx.paths, ctx.reviews)]
        try:
            txt = await llm.write(
                "As a skeptical compliance reviewer, in at most 3 sentences, name the single weakest link in this "
                "evidence and what document would confirm or refute it. Do not change the weakened flags. "
                "Neutral language only.\n" + json.dumps(facts, default=str))
            if txt:
                yield em.ev("skeptic", "skeptic", text=txt[:1200], result={"llm_commentary": True})
        except Exception as e:
            log.warning("skeptic LLM failed: %s", e)


# ---------------------------------------------------------------- gatekeeper
def _fmt_params(p) -> str:
    return json.dumps(p, default=str) if p else "{}"


def build_memo(ctx: Ctx, decision: dict, prose: str | None = None) -> str:
    s = ctx.subject
    v = decision["verdict"]
    title = {"REJECT": "REJECT — possible sanctions exposure", "EDD": "ENHANCED DUE DILIGENCE required",
             "APPROVE": "APPROVE — no exposure found in this dataset"}[v]
    L = [f"# Due-diligence memo: {s.get('name')}", "",
         f"**Subject:** {s.get('name')} (`{ctx.subject_id}`, {s.get('kind')}, {s.get('jurisdiction') or 'n/a'})  ",
         f"**Verdict:** {title}  ", f"**Rules fired:** {', '.join(decision['rule_ids'])}  ",
         f"**Tenant:** {ctx.tenant}", ""]
    if prose:
        L += ["## Summary", prose.strip(), ""]
    else:
        L += ["## Summary"]
        for r in decision["reasons"]:
            L.append(f"- {r}")
        L.append("")
    if ctx.paths:
        L.append("## Exposure paths")
        for i, (p, r) in enumerate(zip(ctx.paths, ctx.reviews or [{}] * len(ctx.paths))):
            chain = []
            nodes = p.get("nodes") or []
            for j, e in enumerate(p.get("edges") or []):
                if j == 0:
                    chain.append(f"{ctx.name(nodes[0])} (`{nodes[0]}`)")
                lab = e.get("type") + (f" [{e['link']}]" if e.get("link") else "")
                nxt = nodes[j + 1] if j + 1 < len(nodes) else e.get("target")
                chain.append(f"—{lab}→ {ctx.name(nxt)} (`{nxt}`)")
            status = "weakened: " + "; ".join(r.get("reasons") or []) if r.get("weakened") else "holds"
            L.append(f"{i + 1}. {gate.icij_hops(p)} hops, match {gate.match_score(p):.2f} ({status})  ")
            L.append("   " + " ".join(chain))
        L.append("")
    else:
        L += ["## Exposure paths", f"No path to any sanctions-listed party within {ctx.max_hops} hops "
              "(proof of no exposure **in this dataset only**).", ""]
    if ctx.chokepoints:
        c = ctx.chokepoints[0]
        L.append("## Chokepoint & counterfactual")
        L.append(f"- Chokepoint: **{c.get('name')}** (`{c['id']}`, {c.get('kind')}) on {c.get('paths_through')} path(s)"
                 + (f", betweenness {c.get('betweenness'):.2f}" if isinstance(c.get("betweenness"), (int, float)) else ""))
        cf = ctx.counterfactuals.get(c["id"])
        if cf is not None:
            L.append(f"- Without `{c['id']}`: " + ("still exposed via alternative paths."
                     if cf.get("still_exposed") else "**no path remains** — the link runs entirely through this node."))
        L.append("")
    if ctx.cluster is not None:
        L += ["## Shell-cluster signal", f"- {ctx.cluster.get('size', 0)} entities share the subject's registered "
              f"address / intermediary (threshold {gate.CLUSTER_MIN}).", ""]
    if ctx.precedents:
        L.append("## Precedents (tenant memory)")
        for c in ctx.precedents.values():
            L.append(f"- Case `{c['id']}` ({c.get('created_at')}): {c.get('subject_name')} → {c.get('verdict')}")
        L.append("")
    L.append("## Verdict rules")
    rt = gate.rules_text(ctx.max_hops)
    for rid in decision["rule_ids"]:
        L.append(f"- **{rid}**: {rt[rid]}")
    L += ["", "## Evidence: queries executed (FalkorDB, parameterized, read-only)"]
    for i, q in enumerate(ctx.queries, 1):
        for cy in _cy_list(q.get("cypher")):
            L.append(f"{i}. `{q['tool']}` params `{_fmt_params(q.get('params'))}`")
            L.append("```cypher\n" + str(cy).strip() + "\n```")
    L += ["", "_Language note: findings describe possible links / exposure in leaked-records data, not wrongdoing._"]
    return "\n".join(L)


async def _gatekeeper(ctx: Ctx, em: Emitter):
    cluster_size = int((ctx.cluster or {}).get("size") or 0)
    decision = gate.decide(ctx.paths, cluster_size=cluster_size, max_hops=ctx.max_hops, reviews=ctx.reviews)
    bi = decision.get("best_path_index")
    hl = _path_highlight([ctx.paths[bi]]) if bi is not None else _hl([ctx.subject_id])
    yield em.ev("verdict", "gatekeeper", text=f"{decision['verdict']}: " + " ".join(decision["reasons"]),
                result={**decision, "rules": {r: gate.rules_text(ctx.max_hops)[r] for r in decision["rule_ids"]},
                        "chokepoint": ctx.chokepoints[0] if ctx.chokepoints else None,
                        "counterfactual_breaks_link": (not ctx.counterfactuals[ctx.chokepoints[0]["id"]].get("still_exposed"))
                        if ctx.chokepoints and ctx.chokepoints[0]["id"] in ctx.counterfactuals else None},
                highlight=hl)
    prose = None
    if llm.enabled():
        facts = {"subject": ctx.subject.get("name"), "subject_id": ctx.subject_id, "verdict": decision,
                 "paths": [{"chain": [f"{ctx.name(n)} ({n})" for n in p.get("nodes") or []],
                            "edges": [e.get("type") for e in p.get("edges") or []], "match": p.get("match")}
                           for p in ctx.paths],
                 "chokepoints": ctx.chokepoints[:3], "cluster_size": cluster_size,
                 "skeptic": [{k: r[k] for k in ("weakened", "reasons", "notes")} for r in ctx.reviews],
                 "rationale": ctx.rationale}
        try:
            prose = await llm.write(
                "Write the 'Summary' section (one or two short paragraphs, no headings) of a due-diligence memo from "
                "these facts. Cite node ids in backticks. Do NOT change the verdict. Use 'possible link'/'exposure', "
                "never 'guilty'.\n" + json.dumps(facts, default=str))
        except Exception as e:
            log.warning("memo LLM failed: %s", e)
    memo = build_memo(ctx, decision, prose)
    yield em.ev("memo", "gatekeeper", text=memo, result={"format": "markdown", "llm_prose": bool(prose)})
    ctx._decision = decision  # type: ignore[attr-defined]


async def _write_case(ctx: Ctx, em: Emitter):
    d = getattr(ctx, "_decision")
    examined = [{"id": i, "name": ctx.name(i), "kind": (ctx.nodes.get(i) or {}).get("kind")}
                for p in ctx.paths for i in p.get("nodes") or []]
    examined.insert(0, {"id": ctx.subject_id, "name": ctx.subject.get("name"), "kind": ctx.subject.get("kind")})
    flagged = []
    if d["verdict"] != "APPROVE":
        flagged = [{"id": c["id"], "name": c.get("name"), "kind": c.get("kind")} for c in ctx.chokepoints[:2]]
    cleared = []
    for r in ctx.reviews:
        for e in r.get("weak_edges") or []:
            for nid in (e["source"], e["target"]):
                cleared.append({"id": nid, "name": ctx.name(nid), "kind": (ctx.nodes.get(nid) or {}).get("kind"),
                                "reason": f"weak edge {e.get('type')}"})
    if d["verdict"] == "APPROVE":
        cleared.append({"id": ctx.subject_id, "name": ctx.subject.get("name"), "kind": ctx.subject.get("kind"),
                        "reason": f"no path within {ctx.max_hops} hops"})
    summary = d["reasons"][0] if d["reasons"] else d["verdict"]
    try:
        case = await _run(lambda: memory.write_case(
            ctx.tenant, subject_id=ctx.subject_id, subject_name=ctx.subject.get("name") or ctx.subject_id,
            verdict=d["verdict"], summary=summary, rule_ids=d["rule_ids"], examined=examined,
            flagged=flagged, cleared=cleared, precedent_ids=list(ctx.precedents)))
    except Exception as e:
        log.warning("write_case failed: %s", e)
        yield em.ev("error", "memory", text=f"Could not save case: {e}", recoverable=True)
        return
    txt = f"Saved case {case['id']} to graph {case['graph']}"
    if case["precedents"]:
        txt += f"; linked PRECEDENT_FOR from {', '.join(case['precedents'])}"
    yield em.ev("status", "memory", text=txt + ".", result={"case": case})
    ctx._case = case  # type: ignore[attr-defined]


# ---------------------------------------------------------------- entry point
async def investigate(node_id: str, tenant: str = "default", max_hops: int = DEFAULT_MAX_HOPS,
                      pace: float | None = None) -> AsyncIterator[dict]:
    pace = pace_seconds() if pace is None else max(0.0, pace)
    max_hops = max(1, min(int(max_hops or DEFAULT_MAX_HOPS), DEFAULT_MAX_HOPS))
    ctx = Ctx(node_id, tenant, max_hops)
    em = Emitter(ctx.run_id, pace)

    async def paced(gen):
        async for e in gen:
            yield e
            if pace:
                await asyncio.sleep(pace)

    async def run():
        g = main_graph()
        yield em.ev("status", "investigator", text="Investigation started.",
                    result={"node_id": node_id, "tenant": ctx.tenant, "llm": llm.info(), "max_hops": max_hops})
        det = await _run(tools.node_detail, g, node_id=node_id) if isinstance(node_id, str) and node_id else {}
        if not det.get("node"):
            yield em.ev("error", "investigator", text=f"Unknown node id {node_id!r}.")
            return
        ctx.subject = det["node"]
        ctx.valid_ids.add(node_id)
        ctx.nodes[node_id] = {"id": node_id, "kind": ctx.subject.get("kind"), "name": ctx.subject.get("name"),
                              "jurisdiction": ctx.subject.get("jurisdiction"), "sanctioned": False}
        ctx.queries.append({"tool": "node_detail", "cypher": det.get("cypher"), "params": det.get("params")})

        # Entity resolution (shows the full-text index at work)
        async for e in _tool_step_search(ctx, g, em):
            yield e
        # Memory: recall over subject + 1-hop neighborhood
        try:
            nb = await _run(tools.neighborhood, g, node_id=node_id, hops=1)
            ctx.absorb_subgraph(nb.get("subgraph"))
            near = [n["id"] for n in (nb.get("subgraph") or {}).get("nodes") or []]
        except Exception:
            near = []
        async for e in _recall_step(ctx, em, [node_id, *near], "subject neighborhood"):
            yield e

        if llm.enabled():
            async for e in _llm_investigator(ctx, g, em):
                yield e
            async for e in _complete_evidence(ctx, g, em):
                yield e
        else:
            async for e in _scripted_investigator(ctx, g, em):
                yield e
        async for e in _skeptic(ctx, em):
            yield e
        async for e in _gatekeeper(ctx, em):
            yield e
        async for e in _write_case(ctx, em):
            yield e
        case = getattr(ctx, "_case", None)
        d = getattr(ctx, "_decision")
        yield em.ev("done", "gatekeeper", text=f"Done: {d['verdict']}.",
                    result={"verdict": d["verdict"], "rule_ids": d["rule_ids"],
                            "case_id": case["id"] if case else None,
                            "precedents": list(ctx.precedents), "queries": len(ctx.queries)})

    try:
        async for e in paced(run()):
            yield e
    except Exception as e:  # never kill the stream silently
        log.exception("investigation failed")
        yield em.ev("error", "investigator", text=f"Investigation failed: {type(e).__name__}: {e}")
        yield em.ev("done", "gatekeeper", text="Aborted.", result={"verdict": None})


async def _tool_step_search(ctx: Ctx, g, em: Emitter):
    q = ctx.subject.get("name") or ""
    yield em.ev("tool_call", "investigator", tool="search", args={"q": q, "limit": 5},
                text=f"Resolving '{q}' against the full-text index.")
    try:
        res = await _run(tools.search, g, q=q, limit=5)
    except Exception as e:
        yield em.ev("error", "investigator", tool="search", text=f"search failed: {e}", recoverable=True)
        return
    ctx.queries.append({"tool": "search", "cypher": res.get("cypher"), "params": res.get("params")})
    cands = res.get("candidates") or []
    for c in cands:
        ctx.valid_ids.add(c.get("id"))
    yield em.ev("tool_result", "investigator", tool="search", cypher=res.get("cypher"), params=res.get("params"),
                args={"q": q, "limit": 5}, result={"candidates": cands},
                text=f"{len(cands)} candidate(s); investigating {ctx.subject.get('name')} (`{ctx.subject_id}`).",
                highlight=_hl([ctx.subject_id]),
                subgraph={"nodes": [ctx.nodes[ctx.subject_id]], "links": []})
