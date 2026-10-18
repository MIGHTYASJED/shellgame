"""FastAPI app. Run from backend/:  uvicorn shellgame.api:app --port 8000"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import agents, gate, llm, memory
from ._compat import main_graph, tools

log = logging.getLogger("shellgame.api")

app = FastAPI(title="Shell Game", version="0.1.0",
              description="Sanctions-exposure tracing agents over FalkorDB (ICIJ Offshore Leaks x OpenSanctions).")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


async def _call(fn, *a, **kw):
    return await asyncio.to_thread(fn, *a, **kw)


def _g():
    return main_graph()


@app.on_event("startup")
async def warm_up():
    """Load the graph and cache PageRank before the first visitor (keeps the first investigation fast)."""
    asyncio.create_task(_call(tools.chokepoints, _g(), [{"nodes": ["", "", ""]}]))


@app.get("/api/health")
async def health():
    try:
        await _call(lambda: _g().ro_query("RETURN 1"))
        db_ok = True
    except Exception as e:  # pragma: no cover
        log.warning("health db error: %s", e)
        db_ok = False
    return {"ok": db_ok, "db": db_ok, "llm": llm.info(),
            "rules": gate.rules_text(), "pace": agents.pace_seconds()}


@app.get("/api/stats")
async def stats():
    return await _call(tools.stats, _g())


@app.get("/api/search")
async def search(q: str = Query(..., min_length=1, max_length=200), limit: int = Query(10, ge=1, le=50)):
    return await _call(tools.search, _g(), q=q, limit=limit)


@app.get("/api/node/{node_id}")
async def node(node_id: str):
    res = await _call(tools.node_detail, _g(), node_id=node_id)
    if not res.get("node"):
        raise HTTPException(404, f"node {node_id!r} not found")
    return res


@app.get("/api/neighborhood/{node_id}")
async def neighborhood(node_id: str, hops: int = Query(1, ge=1, le=3), limit: int = Query(150, ge=1, le=1000)):
    return await _call(tools.neighborhood, _g(), node_id=node_id, hops=hops, limit=limit)


@app.get("/api/investigate")
async def investigate(node_id: str = Query(..., min_length=1), tenant: str = Query("default"),
                      max_hops: int = Query(gate.DEFAULT_MAX_HOPS, ge=1, le=gate.DEFAULT_MAX_HOPS),
                      pace: float | None = Query(None, ge=0, le=5)):
    async def stream():
        async for ev in agents.investigate(node_id, tenant, max_hops=max_hops, pace=pace):
            yield f"data: {json.dumps(ev, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


@app.post("/api/counterfactual")
async def counterfactual(payload: dict = Body(...)):
    node_id, remove_id = payload.get("node_id"), payload.get("remove_id")
    if not isinstance(node_id, str) or not isinstance(remove_id, str) or not node_id or not remove_id:
        raise HTTPException(422, "node_id and remove_id (strings) are required")
    max_hops = int(payload.get("max_hops") or gate.DEFAULT_MAX_HOPS)
    g = _g()
    before = await _call(tools.sanction_paths, g, node_id=node_id, max_hops=max_hops, k=3)
    after = await _call(tools.counterfactual, g, node_id=node_id, remove_id=remove_id, max_hops=max_hops)
    return {**after, "removed": remove_id, "was_exposed": bool(before.get("paths")),
            "breaks_link": bool(before.get("paths")) and not after.get("still_exposed"),
            "before": {"paths": before.get("paths"), "cypher": before.get("cypher"), "params": before.get("params")}}


@app.get("/api/cases")
async def cases(tenant: str = Query("default"), limit: int = Query(100, ge=1, le=500)):
    return {"tenant": memory.sanitize_tenant(tenant), "graph": memory.graph_name(tenant),
            "cases": await _call(memory.list_cases, tenant, limit)}


@app.get("/api/tenants")
async def tenants():
    return {"tenants": await _call(memory.list_tenants)}
