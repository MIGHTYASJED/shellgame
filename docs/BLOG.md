---
title: "Shell Game: three agents, one graph, and a 3-hop path to a sanctions list"
tags: falkordb, ai, graphs, hackathon
---

*Built for Graph Hacks (WeMakeDevs × FalkorDB). Code: github.com/MIGHTYASJED/shellgame*

## The question nobody can answer with a table

"Is it safe to do business with this company?" Ask that about an offshore company and the honest
answer is rarely in its own record. The record lists a name, a jurisdiction and an incorporation date.
The risk sits two or three relationships away: a nominee shareholder who also holds shares in
another company, whose shareholder appears on a sanctions list.

That is a path, and paths are what graph databases are good at.

## What I built

Shell Game takes a company or person. Three agents investigate it over a FalkorDB graph built from two
public datasets:

- **ICIJ Offshore Leaks**: about 2M entities, officers, intermediaries and addresses from the Panama,
  Paradise and Pandora Papers.
- **OpenSanctions**: consolidated sanctions lists.

It returns **APPROVE**, **EDD** (enhanced due diligence) or **REJECT**, and the graph path is the evidence.

Here is a real run. *Creatum Business Group Ltd* (BVI) → its shareholder *Bridgewater Second Nominees* →
which is also a shareholder of *Sealfate Ltd* → whose shareholder *Gulbakhor Ismailova* exactly matches
a sanctions-listed person. Three hops, found in milliseconds. In the UI you watch the path light up and
can read the Cypher that found it.

## Design decisions that mattered

**1. The LLM never writes Cypher.** The Investigator picks from a small set of human-written,
parameterised, read-only tools: `sanction_paths`, `shell_cluster`, `chokepoints`, `counterfactual` and
`recall`. A node id it invents is rejected. Every tool result carries its Cypher, so the explanation is
the actual query, not a story about one.

**2. A deterministic verdict.** A Skeptic agent attacks each path. It flags "similar name" edges and
token-only name matches. The Gatekeeper then applies five fixed rules: R1 is a short, strong path with a
≥ 0.95 name match, which means REJECT; R5 is no path within 6 hops, which means APPROVE. The LLM can
explain a verdict but cannot change one.

**3. "No path" is an answer.** A graph lets you prove a negative within the data. If a 6-hop search finds
nothing, there is no exposure in this dataset. A vector search can't tell you that.

**4. Counterfactuals.** Cut any node and the paths are recomputed without it. If removing one nominee
breaks every link, you have found the chokepoint, which is exactly what an investigator wants to know.

**5. Memory as a graph, one graph per desk.** Every case is written to `cases_<desk>`, a separate graph in
the same FalkorDB instance. `EXAMINED`, `FLAGGED` and `CLEARED` edges point at the nodes it touched. The
next investigation that reaches those nodes recalls the precedent. FalkorDB's multi-graph support gives
tenant isolation without extra infrastructure.

## What surprised me

**Shortest paths across a real leak graph are hard.** My first version used built-in shortest-path
enumeration. On the real data it sometimes ran past 60 seconds, because law-firm intermediaries connect
to thousands of companies and the search wandered through all of them. The fix was a layered BFS. Each
hop is one indexed Cypher query, it stops at the first hop that reaches a sanctioned party, and it
rebuilds only the shortest paths. Median search time is now 0.03 s. FalkorDB's PageRank still runs
across the whole graph in about 0.6 s, to show where a chokepoint sits in the wider network.

**Name matching is where credibility is won or lost.** A loose match turns "MRH Investment S.A." into a
sanctioned entity, and that is a false accusation. I ended up with strict rules:

- names need at least two tokens;
- countries must overlap when both sides list them;
- a name that matches more than five records is dropped;
- partial matches can never produce a REJECT.

Even so, the product only ever says "possible link."

## Numbers

- 241,847 nodes and 506,015 edges: everything within 3 hops of a match, plus a 40k-company random
  background so ordinary companies exist.
- 1,712 name matches: 503 exact, 602 alias, 607 token.
- Path search: median 0.03 s, p95 2 s.

## Stack

- **Database:** FalkorDB, with Cypher, full-text indexes and `algo.pageRank`.
- **Backend:** FastAPI streaming agent events over SSE.
- **Frontend:** Next.js and react-force-graph.

Built with AI coding assistance, as disclosed in the repository.

*Possible links, not findings of wrongdoing.*
