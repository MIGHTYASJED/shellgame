# Shell Game — build contract (all agents read this first)

Hackathon: Graph Hacks (WeMakeDevs x FalkorDB). Deadline Sun Oct 18 2026, 11:59 PM IST.
Track 1 primary (Agents That Act on Connected Data), Track 2 secondary (memory/coordination).

## Product in one line
Give the agent a company/person name. It traces shared officers, intermediaries and registered
addresses through ICIJ Offshore Leaks data to OpenSanctions-listed parties, and returns a
deterministic verdict APPROVE / EDD (enhanced due diligence) / REJECT with the graph path as proof,
a skeptic review of the weakest link, a counterfactual ("cut this node and the link breaks"),
and a due-diligence memo. Every investigation is saved as a Case in per-tenant memory graphs and
recalled as precedent in later sessions.

Language: always "possible link" / "exposure", never "guilty". No accusations.

## Hard rules (from hackathon)
- FalkorDB is the primary DB and does the real work. No other DB.
- The LLM NEVER writes Cypher. It only chooses among fixed, human-written tools with typed args.
  All tool queries are parameterized; read tools use `ro_query`.
- Every tool result includes the exact Cypher string + params it ran (shown in UI = explainability).
- "No path found within N hops" is a first-class result (proof of no exposure in this data).

## Layout
```
shellgame/
  SPEC.md
  data/sample/          synthetic data in EXACT real-file formats (dev + tests + offline demo)
  data/raw/             real downloads (gitignored)
  backend/
    pyproject.toml / requirements.txt
    shellgame/
      db.py        (Agent A)  connection: FALKORDB_URL env -> falkordb client; else falkordblite file
      schema.py    (Agent A)  indexes, constants
      ingest.py    (Agent A)  CLI: load ICIJ + OpenSanctions CSVs, name matching, subgraph filter
      tools.py     (Agent A)  graph tools (contract below)
      memory.py    (Agent B)  case memory graphs per tenant
      gate.py      (Agent B)  deterministic verdict
      llm.py       (Agent B)  provider abstraction + scripted fallback (no API key needed)
      agents.py    (Agent B)  Investigator, Skeptic, Gatekeeper orchestration -> event stream
      api.py       (Agent B)  FastAPI app
    tests/
  frontend/        (Agent C)  Next.js
```

## Database
Python package `falkordb` for server mode; `falkordblite` (import `from redislite.falkordb_client import FalkorDB`)
for embedded local dev/tests — it is real FalkorDB (algo.* procedures work). Both are installed.
`db.get_db()` returns a FalkorDB handle. Main graph name: `shellgame`. Memory graphs: `cases_<tenant>`.

## Graph model (main graph `shellgame`)
All ICIJ nodes carry label `:Node` plus one kind label. Properties are strings unless noted.
- `(:Node:Entity {id, name, name_norm, jurisdiction, jurisdiction_description, incorporation_date, status, countries, source})`
- `(:Node:Officer {id, name, name_norm, countries, source})`
- `(:Node:Intermediary {id, name, name_norm, countries, source})`
- `(:Node:Address {id, name, countries, source})`   (name = the address text)
- `(:Node:Other {id, name, name_norm, countries, source})`
- `(:Sanction {id, name, schema, aliases, programs, countries, datasets, sanctions})` from OpenSanctions targets.simple.csv
Edges (ICIJ rel_type uppercased, non-alnum -> `_`):
- `OFFICER_OF {link, start_date, end_date}` (Officer->Entity; link = role e.g. "director", "shareholder", "nominee director")
- `INTERMEDIARY_OF {link}` (Intermediary->Entity)
- `REGISTERED_ADDRESS {link}` (any->Address)
- `SIMILAR`, `SAME_AS`, `SAME_NAME_AS`, `CONNECTED_TO`, `UNDERLYING`, `PROBABLY_SAME_OFFICER_AS` etc. kept as-is
- `(:Node)-[:MATCHES {score: float, method: 'exact'|'alias'|'token'}]->(:Sanction)`  name-match link created by ingest
Indexes: range index on `Node.id`, `Sanction.id`; full-text index on `Node.name` and `Sanction.name`.

Edge "strength" (used by Skeptic + path weight): OFFICER_OF/INTERMEDIARY_OF/REGISTERED_ADDRESS = strong (weight 1);
SAME_AS = 1; SIMILAR / SAME_NAME_AS / PROBABLY_SAME_* = weak (weight 3); MATCHES weight = 1 if score>=0.95 else 3.

## tools.py contract (Agent A implements, Agent B calls)
Every function: `fn(g, **args) -> dict` with keys `cypher` (str or list[str]), `params` (dict), plus payload.
Subgraph payload format everywhere: `{"nodes":[{"id","kind","name","jurisdiction"?,"sanctioned":bool}], "links":[{"source","target","type","link"?}]}`
(`kind` in Entity|Officer|Intermediary|Address|Other|Sanction; Sanction node ids are prefixed `san:`.)
1. `search(g, q, limit=10)` -> `{"candidates":[{"id","kind","name","jurisdiction","countries"}]}` (full-text)
2. `sanction_paths(g, node_id, max_hops=6, k=3)` -> `{"paths":[{"hops":int,"weight":float,"sanction":{...},"match":{score,method},"nodes":[ids in order],"edges":[{"source","target","type","link"}]}], "subgraph":{...}, "found":bool}`
   Shortest (weighted) paths from node to any `:Sanction` (via MATCHES as final hop), undirected over ICIJ edges.
   Use FalkorDB algos (`algo.SPpaths`/`algo.SSpaths`/`algo.bfs`) where they help; must be fast (<2s) on the demo subgraph.
3. `neighborhood(g, node_id, hops=1, limit=150)` -> `{"subgraph":{...}}`
4. `chokepoints(g, paths)` -> `{"chokepoints":[{"id","name","kind","paths_through":int,"betweenness":float}]}` — which intermediate
   nodes appear in the most sanction paths (+ betweenness on the path subgraph via algo.betweenness if practical).
5. `counterfactual(g, node_id, remove_id, max_hops=6)` -> `{"still_exposed":bool,"paths":[...] }` — recompute paths excluding remove_id.
6. `shell_cluster(g, node_id)` -> `{"size":int,"shared_addresses":int,"shared_intermediaries":int,"members_sample":[...],"community_id"?}` —
   entities sharing the same registered address / intermediary (mass-registration signal); may use algo.WCC / algo.labelPropagation.
7. `node_detail(g, node_id)` -> `{"node":{all props, "kind"}}`
8. `stats(g)` -> counts by label and rel type.

## Verdict gate (Agent B, deterministic, gate.py)
Inputs: best surviving path after Skeptic review, cluster signal.
- REJECT: path with hops <= 3 AND match.score >= 0.95 AND no weak edge on it.
- EDD: any path with hops <= 6 (or REJECT conditions weakened by a weak edge / lower score), or shell_cluster size >= 25.
- APPROVE: no path within max_hops ("no path found = no exposure in this dataset") and no cluster signal.
Return `{"verdict","reasons":[str],"rule_ids":[str]}`. Rules are listed verbatim in README.

## Case memory (Track 2) — memory.py, graph `cases_<tenant>`
`(:Case {id, created_at, subject_id, subject_name, verdict, summary})`
`(:Case)-[:EXAMINED]->(:Ref {id, name, kind})`  for every node on cited paths (Ref id = main-graph node id)
`(:Case)-[:CLEARED {reason}]->(:Ref)` for nodes the Skeptic/gate judged weak/not-exposing; `(:Case)-[:FLAGGED]->(:Ref)` for chokepoints.
`(:Case)-[:PRECEDENT_FOR]->(:Case)` when a later case reused an earlier one.
`recall(tenant, node_ids)` returns prior cases touching any of those ids. Tenants are fully isolated graphs (multigraph).

## Agents (agents.py) — event stream
`investigate(node_id, tenant) -> AsyncIterator[event]`. Event JSON:
`{"type": "status"|"thought"|"tool_call"|"tool_result"|"skeptic"|"recall"|"verdict"|"memo"|"done"|"error", "agent": "investigator"|"skeptic"|"gatekeeper"|"memory", "text"?, "tool"?, "args"?, "cypher"?, "params"?, "result"?, "highlight": {"nodes":[ids], "links":[{"source","target"}]}?, "subgraph"?, "ts"}`
- Investigator: LLM tool-calling loop over tools 2–7 + recall (max ~6 steps). Scripted fallback when no LLM key:
  search->recall->sanction_paths->shell_cluster->chokepoints->counterfactual(top chokepoint).
- Skeptic: reviews each path, flags weak edges (SIMILAR/SAME_NAME_AS/low match score) and fuzzy name matches; can mark a path "weakened".
- Gatekeeper: gate.py verdict, then memo (LLM writes prose from facts; scripted template fallback). Memo must cite node ids + the Cypher used.
- Memory: writes Case at end; emits "recall" event at start if precedents exist.
LLM env: `LLM_PROVIDER=anthropic|openai|none`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `LLM_MODEL`.

## API (FastAPI, port 8000, CORS open)
- `GET /api/health`
- `GET /api/stats`
- `GET /api/search?q=`
- `GET /api/node/{id}` ; `GET /api/neighborhood/{id}?hops=1`
- `GET /api/investigate?node_id=&tenant=default` -> Server-Sent Events, one `data: <event json>` per event
- `POST /api/counterfactual {node_id, remove_id}`
- `GET /api/cases?tenant=` ; `GET /api/tenants`

## Demo scenario (must exist in sample data, fictional names)
"Aurora Maritime Holdings Ltd" (BVI) looks clean. Its director is "Coral Nominees Ltd" (nominee).
Coral Nominees is also director of "Seaview Ventures Inc", whose registered address is shared with
"Volkov Trust Holdings", whose officer "Dmitri A. Volkov" MATCHES OpenSanctions-format record "Dmitri Alexandrovich Volkov" (score 0.97).
=> 4–5 hops, chokepoint = Coral Nominees Ltd. Also include: a clearly clean company (APPROVE), one linked only via a
weak SIMILAR edge (EDD after Skeptic), a mass-registration address with 40+ entities (cluster signal), plus ~1–2k
random background nodes/edges so the graph looks real.
