# Data layer

## Sources
- **ICIJ Offshore Leaks** (`full-oldb.LATEST.zip`): `nodes-entities/officers/intermediaries/addresses/others.csv` and `relationships.csv`, read straight out of the zip, columns looked up by header name.
- **OpenSanctions** `targets.simple.csv`: only `Person`, `Company`, `Organization`, `LegalEntity` and `PublicBody` records are used. Each name and each `;`-separated alias is a name variant.
- `data/sample/` holds the same files with synthetic, fictional content. `python scripts/make_sample.py` rebuilds them deterministically.

## Ingest
```
python -m shellgame.ingest --icij data/sample --sanctions data/sample/targets.simple.csv --reset
FALKORDB_LITE_PATH=.data/real.db python -m shellgame.ingest --icij ../data/raw/full-oldb.LATEST.zip \
    --sanctions ../data/raw/targets.simple.csv --focus-hops 3 --max-nodes 250000 --reset
```
1. **Name matching.** Both sides are normalized: casefolded, accents and punctuation removed, leading honorifics and trailing corporate suffixes and jr/sr dropped. A trailing "sheikh" is kept because it is usually a surname. A name must have at least 2 tokens and 8 characters, and placeholders like "bearer" are skipped.
   - `exact`: the name equals a sanctions primary name. Score 1.0.
   - `alias`: the name equals a sanctions alias. Score 0.97.
   - `token`: token-set match. Every token of the shorter name must match a distinct token of the longer one. Initials count only when the sanctions record is a person (`dmitri a volkov` ~ `dmitri alexandrovich volkov`). Score = 0.9 × credit / tokens, and a match is kept only if it scores at least 0.85. In practice that leaves two cases: the same words in a different order, or a person's name with an initial. Candidates are looked up through each name's rarest token.
   - `Person` records only match Officers and Intermediaries. For every record type, when both sides list countries, at least one must be shared (ICIJ ISO3 is mapped to OpenSanctions ISO2).
   - If a name matches more than 5 ICIJ nodes ("zhang wei"), it is dropped as a likely collision.
2. **Focus mode** (`--focus-hops N`): starts from the matched ICIJ nodes and runs an undirected BFS by streaming `relationships.csv` once per hop. Nearest nodes are kept first, up to `--max-nodes`. Hubs are nodes with more than `--hub-degree` (1000) relationships, such as a law firm's thousands of client companies. They are kept but not expanded, so they do not use up the node budget.
   - `--background N` (40000) also keeps a deterministic random sample of N entities plus their non-hub neighbours. Edges from these background-only nodes to hubs are not loaded. This means ordinary companies exist in the graph and can come back APPROVE.
3. **Load**: batched `UNWIND` writes (5k rows per batch), then indexes, then a printed summary. Only matched sanctions records are loaded as nodes.

## Graph model (`shellgame`)
```
(:Node:Entity|Officer|Intermediary|Address|Other {id, name, name_norm, jurisdiction, countries, source, ...})
(:Node)-[:OFFICER_OF|INTERMEDIARY_OF|REGISTERED_ADDRESS|SIMILAR|SAME_AS|SAME_NAME_AS|CONNECTED_TO|UNDERLYING|PROBABLY_SAME_OFFICER_AS|... {link, start_date, end_date, w}]->(:Node)
(:Node)-[:MATCHES {score, method, w}]->(:Sanction {id:'san:<os id>', name, schema, aliases, programs, countries, datasets, sanctions})
```
- **Edge weight `w`**:
  - 1: `OFFICER_OF`, `INTERMEDIARY_OF`, `REGISTERED_ADDRESS`, `SAME_AS` (also `SAME_COMPANY_AS`, `SAME_ID_AS`).
  - 3: `SIMILAR*`, `SAME_NAME_AS`, `SAME_INTERMEDIARY_AS`, `PROBABLY_SAME_*`.
  - 2: anything else (`CONNECTED_TO`, `UNDERLYING`).
  - `MATCHES`: 1 if the score is at least 0.95, otherwise 3.
- **Indexes**:
  - Range indexes on `Node.id`, `Sanction.id` and `Node.name_norm`.
  - Full-text indexes on `Node.name` and `Sanction.name`.

## Tool queries (`shellgame/tools.py`)
All reads go through `ro_query`. `{n}`, `{hops}` and `{label}` are integers or a fixed label that the code fills in; everything else is a parameter.

| Tool | Cypher |
|---|---|
| search | `CALL db.idx.fulltext.queryNodes('Node', $q) YIELD node, score RETURN node, score ORDER BY score DESC LIMIT $limit` |
| sanction_paths, counterfactual | `MATCH (s:Node {id: $id}) RETURN ID(s)`; once per hop: `UNWIND $frontier AS i MATCH (n) WHERE ID(n) = i WITH n, i MATCH (n)-[r]-(m) WHERE r.w <= $max_w AND m.id <> $remove_id RETURN i, ID(m), m:Sanction`; read-back: `UNWIND $pairs AS p WITH p[0] AS x, p[1] AS y MATCH (a) WHERE ID(a) = x WITH a, x, y MATCH (b) WHERE ID(b) = y WITH a, b, x, y MATCH (a)-[r]-(b) RETURN x, y, a, r, b ORDER BY r.w` |
| neighborhood | `MATCH (s:{label} {id: $id})-[*0..{hops}]-(n) WITH DISTINCT n LIMIT $limit WITH collect(n) AS ns UNWIND ns AS a OPTIONAL MATCH (a)-[r]->(b) WHERE b IN ns RETURN a, collect({source: a.id, target: b.id, type: type(r), link: r.link})` |
| chokepoints | `UNWIND $ids AS i MATCH (n:Node {id: i}) RETURN n`; network centrality: `CALL algo.pageRank('Node', NULL) YIELD node, score WITH collect({id: node.id, s: score}) AS all UNWIND [x IN all WHERE x.id IN $ids] AS c RETURN c.id, size([y IN all WHERE y.s > c.s]) * 100.0 / size(all)` |
| shell_cluster | `MATCH (s:Node {id: $id}) OPTIONAL MATCH (s)-[:REGISTERED_ADDRESS*0..1]-(a:Address)-[:REGISTERED_ADDRESS]-(m:Entity) WITH s, count(DISTINCT a) AS addrs, collect(DISTINCT m) AS by_addr OPTIONAL MATCH (s)-[:INTERMEDIARY_OF*0..1]-(i:Intermediary)-[:INTERMEDIARY_OF]-(m2:Entity) RETURN addrs, size(by_addr), [x IN by_addr[..8] \| x.name], count(DISTINCT i), count(DISTINCT m2)` |
| node_detail | `MATCH (n:{label} {id: $id}) RETURN n` |
| stats | `CALL db.labels()`, `CALL db.relationshipTypes()`, then `MATCH (n:L) RETURN count(n)` and `MATCH ()-[r:T]->() RETURN count(r)` |

### How the tools work
- **sanction_paths**: an exact, layered BFS that runs inside FalkorDB.
  - Each hop is one query, and each query plan is an `NodeByIdSeek` followed by an expand.
  - The search stops at the first hop that reaches a `:Sanction`, which is always via `MATCHES`. It goes at most `max_hops` ICIJ edges plus that one match.
  - Up to 50 shortest paths are rebuilt by following BFS parent links backwards, so no dead ends are explored. Their edges are fetched in one read-back query that picks the strongest edge for each step.
  - If the best path contains a weak edge, a second pass runs with `max_w = 1`. It allows only strong edges and matches with a score of at least 0.95, so a short weak path cannot hide a strong path that is slightly longer.
  - Paths are ranked by total `w`, then by hops. `hops` counts every edge up to and including `MATCHES`. The verdict gate counts ICIJ hops only, which is `hops` − 1.
  - Why not built-in procedures: on the 225k-node real graph, `allShortestPaths` and `algo.SPpaths` enumerate dead ends through hub nodes and sometimes ran longer than 60 s.
- **counterfactual**: the same BFS with `$remove_id` skipped. It is exact: `still_exposed=false` means no path within `max_hops` avoids that node.
- **chokepoints**: ranks nodes by how many sanction paths pass through them, with ties going to the node closest to the subject, then by FalkorDB `algo.pageRank` over the whole graph (~0.6 s). `betweenness` is the share of paths that pass through the node; `pagerank_top_pct` places the node in the wider offshore network ("top 3%").
- **shell_cluster**: `size` counts the entities that share the subject's registered address, including the subject. The mass-registration rule R4 uses this number. Sharing an intermediary is reported separately, because large formation agents serve thousands of companies.

## Real-data run (2026-10-17, ICIJ full-oldb + OpenSanctions `targets.simple.csv`)
- **Ingest** with `--focus-hops 3 --max-nodes 250000 --background 40000`: 246 s in total, about 160 s of which is name matching.
- **Matches**: 1,712 in total.

  | Method | Matches |
  |---|---|
  | exact | 503 |
  | alias | 602 |
  | token | 607 |

- **Graph kept**: 241,847 nodes, 506,015 edges and 1,118 sanctions nodes. 147k nodes come from the focus subgraph and 94k from the background sample; 146 nodes counted as hubs.
- **`sanction_paths` speed** on 155 random entities: median 0.03 s, p95 2.0 s, max 3.4 s.
