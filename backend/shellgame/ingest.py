"""Load ICIJ Offshore Leaks + OpenSanctions CSVs into the `shellgame` graph.

    python -m shellgame.ingest --icij DIR_OR_ZIP --sanctions targets.simple.csv [--focus-hops 3] [--max-nodes 250000]
        [--hub-degree 1000] [--background 40000] [--reset]

Streams the files (reads straight from the ICIJ zip), matches ICIJ names against sanctions names, and with
--focus-hops keeps only ICIJ nodes within N hops of a matched node (BFS by streaming relationships.csv once per hop).
Target DB: FALKORDB_URL, else the falkordblite file at FALKORDB_LITE_PATH (default backend/.data/shellgame.db).
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from . import db, schema

BATCH = 5000
csv.field_size_limit(sys.maxsize)

SANCTION_SCHEMAS = {"Person", "Company", "Organization", "LegalEntity", "PublicBody"}
EXACT, ALIAS = 1.0, 0.97
_ISO = ("ABWAW AFGAF AGOAO AIAAI ALAAX ALBAL ANDAD AREAE ARGAR ARMAM ASMAS ATAAQ ATFTF ATGAG AUSAU AUTAT AZEAZ BDIBI "
        "BELBE BENBJ BESBQ BFABF BGDBD BGRBG BHRBH BHSBS BIHBA BLMBL BLRBY BLZBZ BMUBM BOLBO BRABR BRBBB BRNBN BTNBT "
        "BVTBV BWABW CAFCF CANCA CCKCC CHECH CHLCL CHNCN CIVCI CMRCM CODCD COGCG COKCK COLCO COMKM CPVCV CRICR CUBCU "
        "CUWCW CXRCX CYMKY CYPCY CZECZ DEUDE DJIDJ DMADM DNKDK DOMDO DZADZ ECUEC EGYEG ERIER ESHEH ESPES ESTEE ETHET "
        "FINFI FJIFJ FLKFK FRAFR FROFO FSMFM GABGA GBRGB GEOGE GGYGG GHAGH GIBGI GINGN GLPGP GMBGM GNBGW GNQGQ GRCGR "
        "GRDGD GRLGL GTMGT GUFGF GUMGU GUYGY HKGHK HMDHM HNDHN HRVHR HTIHT HUNHU IDNID IMNIM INDIN IOTIO IRLIE IRNIR "
        "IRQIQ ISLIS ISRIL ITAIT JAMJM JEYJE JORJO JPNJP KAZKZ KENKE KGZKG KHMKH KIRKI KNAKN KORKR KWTKW LAOLA LBNLB "
        "LBRLR LBYLY LCALC LIELI LKALK LSOLS LTULT LUXLU LVALV MACMO MAFMF MARMA MCOMC MDAMD MDGMG MDVMV MEXMX MHLMH "
        "MKDMK MLIML MLTMT MMRMM MNEME MNGMN MNPMP MOZMZ MRTMR MSRMS MTQMQ MUSMU MWIMW MYSMY MYTYT NAMNA NCLNC NERNE "
        "NFKNF NGANG NICNI NIUNU NLDNL NORNO NPLNP NRUNR NZLNZ OMNOM PAKPK PANPA PCNPN PERPE PHLPH PLWPW PNGPG POLPL "
        "PRIPR PRKKP PRTPT PRYPY PSEPS PYFPF QATQA REURE ROURO RUSRU RWARW SAUSA SDNSD SENSN SGPSG SGSGS SHNSH SJMSJ "
        "SLBSB SLESL SLVSV SMRSM SOMSO SPMPM SRBRS SSDSS STPST SURSR SVKSK SVNSI SWESE SWZSZ SXMSX SYCSC SYRSY TCATC "
        "TCDTD TGOTG THATH TJKTJ TKLTK TKMTM TLSTL TONTO TTOTT TUNTN TURTR TUVTV TWNTW TZATZ UGAUG UKRUA UMIUM URYUY "
        "USAUS UZBUZ VATVA VCTVC VENVE VGBVG VIRVI VNMVN VUTVU WLFWF WSMWS YEMYE ZAFZA ZMBZM ZWEZW")
ISO3_TO_ISO2 = {c[:3]: c[3:].lower() for c in _ISO.split()}


# ------------------------------------------------------------------ reading
def open_csv(src: Path, name: str):
    """DictReader over `name` inside a directory or a zip (any subfolder). Returns None if absent."""
    if src.is_dir():
        hits = list(src.rglob(name))
        return csv.DictReader(open(hits[0], newline="", encoding="utf-8")) if hits else None
    zf = zipfile.ZipFile(src)
    member = next((m for m in zf.namelist() if m.rsplit("/", 1)[-1] == name), None)
    return csv.DictReader(io.TextIOWrapper(zf.open(member), encoding="utf-8", newline="")) if member else None


def node_files(src: Path):
    for file, kind in schema.ICIJ_FILES.items():
        rows = open_csv(src, file)
        if rows is not None:
            yield kind, rows


def relationships(src: Path):
    rows = open_csv(src, schema.RELATIONSHIPS_FILE)
    for r in rows or ():
        yield r.get("node_id_start", ""), r.get("node_id_end", ""), r


# ------------------------------------------------------------------ name matching
def usable(norm: str) -> bool:
    """Credibility filter: >= 2 tokens, >= 8 chars, not a placeholder name."""
    return len(norm) >= 8 and " " in norm and norm not in schema.JUNK_NAMES


TOKEN_MIN = 0.85


def token_score(a: list[str], b: list[str], initials: bool) -> float:
    """Token-set match: every token of the shorter name matches a distinct token of the longer one
    (full token = 1; an initial = 0.9, persons only). Score = 0.9 * credit / len(longer), kept if >= TOKEN_MIN,
    so in practice: same tokens in another order, or a person's name with an initial."""
    short, long_ = sorted((a, b), key=len)
    pool, credit = list(long_), 0.0
    for t in short:
        if t in pool:
            pool.remove(t)
            credit += 1
            continue
        hit = initials and next((u for u in pool if (len(t) == 1 and u[0] == t) or (len(u) == 1 and t[0] == u)), None)
        if not hit:
            return 0.0
        pool.remove(hit)
        credit += 0.9
    score = round(0.9 * credit / len(long_), 2)
    return score if score >= TOKEN_MIN else 0.0


class Matcher:
    def __init__(self, path: Path):
        self.records: list[dict] = []
        self.exact: dict[str, list] = defaultdict(list)          # normalized name/alias -> [(record idx, score)]
        self.variants: list[tuple[int, list[str]]] = []         # (record idx, tokens)
        self.by_token: dict[str, list[int]] = defaultdict(list)  # token -> variant idx
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("schema") in SANCTION_SCHEMAS:
                    self._add(r)

    def _add(self, r: dict):
        i = len(self.records)
        r["_person"] = r["schema"] == "Person"
        r["_countries"] = {c for c in (r.get("countries") or "").split(";") if c}
        self.records.append(r)
        names = [(r.get("name"), EXACT)] + [(a, ALIAS) for a in (r.get("aliases") or "").split(";")]
        seen = set()
        for name, score in names:
            norm = schema.normalize(name)
            if not usable(norm) or norm in seen:
                continue
            seen.add(norm)
            self.exact[norm].append((i, score))
            v = len(self.variants)
            self.variants.append((i, norm.split()))
            for t in set(norm.split()):
                if len(t) >= 3:
                    self.by_token[t].append(v)

    def match(self, kind: str, norm: str, country_codes: str):
        """Best (record idx, score, method) for an ICIJ name, or None."""
        if not usable(norm):
            return None
        iso2 = {ISO3_TO_ISO2.get(c) for c in country_codes.split(";")} - {None}
        best = None
        for i, score in self.exact.get(norm, ()):
            cand = (i, score, "exact" if score == EXACT else "alias")
            if self._compatible(kind, i, iso2) and (best is None or score > best[1]):
                best = cand
        if best:
            return best
        toks = norm.split()
        postings = [self.by_token[t] for t in toks if t in self.by_token]
        if not postings:
            return None
        rarest = min(postings, key=len)
        if len(rarest) > 2000:
            return None
        for v in rarest:
            i, vt = self.variants[v]
            s = token_score(toks, vt, self.records[i]["_person"])
            if s and self._compatible(kind, i, iso2) and (best is None or s > best[1]):
                best = (i, s, "token")
        return best

    def _compatible(self, kind: str, i: int, iso2: set) -> bool:
        """Persons only match people-like ICIJ nodes; when both sides list countries they must overlap."""
        r = self.records[i]
        if r["_person"] and kind not in ("Officer", "Intermediary"):
            return False
        return not (r["_countries"] and iso2 and not r["_countries"] & iso2)


def match_names(src: Path, matcher: Matcher, max_namesakes: int = 5):
    """One pass over the named node files -> [(node_id, record idx, score, method)].
    Names matched on more than `max_namesakes` ICIJ nodes ("zhang wei") are dropped as likely collisions."""
    found = []
    for kind, rows in node_files(src):
        if kind not in schema.NAMED_KINDS:
            continue
        for r in rows:
            norm = schema.normalize(r.get("name"))
            m = matcher.match(kind, norm, r.get("country_codes") or "")
            if m:
                found.append((norm, r["node_id"], *m))
    namesakes = Counter(f[0] for f in found)
    return [f[1:] for f in found if namesakes[f[0]] <= max_namesakes]


# ------------------------------------------------------------------ focus subgraph
def hubs(src: Path, hub_degree: int) -> set[str]:
    """Nodes with more than hub_degree relationships (a formation agent's thousands of client companies)."""
    deg = Counter()
    for a, b, _ in relationships(src):
        deg[a] += 1
        deg[b] += 1
    return {n for n, d in deg.items() if d > hub_degree}


def focus(src: Path, seeds: set[str], hops: int, max_nodes: int, hub_set: set[str]) -> set[str]:
    """Nodes within `hops` of the seeds (undirected), nearest first, capped at max_nodes.
    Hubs are kept but not expanded, so the budget goes to meaningful structure."""
    keep, frontier = set(seeds), set(seeds)
    for h in range(hops):
        nxt = set()
        for a, b, _ in relationships(src):
            if a in frontier and a not in hub_set and b not in keep:
                nxt.add(b)
            if b in frontier and b not in hub_set and a not in keep:
                nxt.add(a)
        room = max_nodes - len(keep)
        if len(nxt) > room:
            nxt = set(sorted(nxt)[:room])
        keep |= nxt
        frontier = nxt
        print(f"  hop {h + 1}: +{len(nxt)} nodes (total {len(keep)})")
        if not frontier or len(keep) >= max_nodes:
            break
    return keep


def background(src: Path, n: int, hub_set: set[str]) -> set[str]:
    """Deterministic random sample of n Entity nodes plus their non-hub neighbours, so ordinary companies
    (that can come back APPROVE) exist next to the focus subgraph."""
    rng, sample = random.Random(0), []
    for k, r in enumerate(open_csv(src, "nodes-entities.csv") or ()):  # reservoir sampling
        if k < n:
            sample.append(r["node_id"])
        elif (j := rng.randrange(k + 1)) < n:
            sample[j] = r["node_id"]
    sample = set(sample)
    keep = set(sample)
    for a, b, _ in relationships(src):
        if a in sample and b not in hub_set:
            keep.add(b)
        elif b in sample and a not in hub_set:
            keep.add(a)
    return keep


# ------------------------------------------------------------------ writing
def flush(g, cypher: str, rows: list):
    if rows:
        g.query(cypher, {"rows": rows})
        rows.clear()


def load_nodes(g, src: Path, keep: set[str] | None) -> Counter:
    counts = Counter()
    for kind, rows in node_files(src):
        cy = f"UNWIND $rows AS r CREATE (n:Node:{kind}) SET n = r"
        props, batch = schema.NODE_PROPS[kind], []
        for r in rows:
            nid = r.get("node_id")
            if not nid or (keep is not None and nid not in keep):
                continue
            node = {p: r[c] for c, p in props.items() if r.get(c)}
            node["id"] = nid
            if kind in schema.NAMED_KINDS:
                node["name_norm"] = schema.normalize(node.get("name"))
            batch.append(node)
            counts[kind] += 1
            if len(batch) >= BATCH:
                flush(g, cy, batch)
        flush(g, cy, batch)
    return counts


def load_relationships(g, src: Path, keep: set[str] | None, isolated=frozenset(), hub_set=frozenset()) -> Counter:
    """Edges between kept nodes; background-only nodes are never wired to hubs."""
    counts, batches = Counter(), defaultdict(list)

    def cy(t):
        return f"UNWIND $rows AS r MATCH (a:Node {{id: r.s}}) MATCH (b:Node {{id: r.t}}) CREATE (a)-[e:{t}]->(b) SET e = r.p"

    for a, b, r in relationships(src):
        if keep is not None and (a not in keep or b not in keep):
            continue
        if (a in isolated and b in hub_set) or (b in isolated and a in hub_set):
            continue
        t = schema.rel_type(r.get("rel_type"))
        p = {k: r[k] for k in ("link", "status", "start_date", "end_date") if r.get(k)}
        p["w"] = schema.edge_weight(t)
        batches[t].append({"s": a, "t": b, "p": p})
        counts[t] += 1
        if len(batches[t]) >= BATCH:
            flush(g, cy(t), batches[t])
    for t, rows in batches.items():
        flush(g, cy(t), rows)
    return counts


def load_sanctions(g, matcher: Matcher, matches: list):
    used = sorted({i for _, i, _, _ in matches})
    rows = [{"id": schema.SANCTION_PREFIX + r["id"], "name": r.get("name") or "", "schema": r.get("schema") or "",
             "aliases": r.get("aliases") or "", "programs": r.get("program_ids") or "",
             "countries": r.get("countries") or "", "datasets": r.get("dataset") or "",
             "sanctions": r.get("sanctions") or ""} for r in (matcher.records[i] for i in used)]
    for k in range(0, len(rows), BATCH):
        g.query("UNWIND $rows AS r CREATE (s:Sanction) SET s = r", {"rows": rows[k:k + BATCH]})
    edges = [{"n": nid, "s": schema.SANCTION_PREFIX + matcher.records[i]["id"], "score": score, "method": method,
              "w": schema.match_weight(score)} for nid, i, score, method in matches]
    for k in range(0, len(edges), BATCH):
        g.query("UNWIND $rows AS r MATCH (n:Node {id: r.n}) MATCH (s:Sanction {id: r.s}) "
                "CREATE (n)-[:MATCHES {score: r.score, method: r.method, w: r.w}]->(s)", {"rows": edges[k:k + BATCH]})
    return len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--icij", required=True, type=Path, help="ICIJ directory or full-oldb zip")
    ap.add_argument("--sanctions", required=True, type=Path, help="OpenSanctions targets.simple.csv")
    ap.add_argument("--focus-hops", type=int, default=0, help="keep only nodes within N hops of a match (0 = all)")
    ap.add_argument("--max-nodes", type=int, default=250_000, help="node cap in focus mode")
    ap.add_argument("--hub-degree", type=int, default=1000, help="focus mode: do not expand nodes with more edges")
    ap.add_argument("--background", type=int, default=40_000, help="focus mode: also keep N random entities + neighbours")
    ap.add_argument("--reset", action="store_true", help="drop the graph first")
    a = ap.parse_args(argv)

    t0 = time.time()
    g = db.get_graph()
    if a.reset and schema.MAIN_GRAPH in db.get_db().list_graphs():
        g.delete()
        g = db.get_graph()
    matcher = Matcher(a.sanctions)
    print(f"sanctions: {len(matcher.records)} records, {len(matcher.variants)} name variants")
    matches = match_names(a.icij, matcher)
    print(f"matches: {len(matches)} {dict(Counter(m[3] for m in matches))}  ({time.time() - t0:.0f}s)")
    keep, bg_only, hub_set = None, set(), set()
    if a.focus_hops > 0:
        hub_set = hubs(a.icij, a.hub_degree)
        keep = focus(a.icij, {m[0] for m in matches}, a.focus_hops, a.max_nodes, hub_set)
        bg_only = background(a.icij, a.background, hub_set) - keep if a.background else set()
        keep |= bg_only
        print(f"  background: +{len(bg_only)} nodes; {len(hub_set)} hubs (> {a.hub_degree} edges)")
    schema.create_indexes(g)
    nodes = load_nodes(g, a.icij, keep)
    print(f"nodes: {dict(nodes)}  ({time.time() - t0:.0f}s)")
    rels = load_relationships(g, a.icij, keep, bg_only, hub_set)
    print(f"relationships: {sum(rels.values())} {dict(rels.most_common(8))}  ({time.time() - t0:.0f}s)")
    n_san = load_sanctions(g, matcher, matches)
    print(f"done: {sum(nodes.values())} nodes, {sum(rels.values())} edges, {n_san} sanctions, "
          f"{len(matches)} MATCHES in {time.time() - t0:.0f}s -> graph '{schema.MAIN_GRAPH}'")


if __name__ == "__main__":
    main()
