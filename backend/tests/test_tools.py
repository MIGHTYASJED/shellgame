"""Graph tools + ingest against the synthetic sample (data/sample), in a throwaway falkordblite file."""
import asyncio
import time
from pathlib import Path

import pytest

from shellgame import db, gate, ingest, tools

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample"


@pytest.fixture(scope="module")
def g(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("FALKORDB_LITE_PATH", str(tmp_path_factory.mktemp("db") / "test.db"))
    mp.setenv("LLM_PROVIDER", "none")
    db.reset_db()
    ingest.main(["--icij", str(SAMPLE), "--sanctions", str(SAMPLE / "targets.simple.csv"), "--reset"])
    yield db.get_graph()
    db.reset_db()
    mp.undo()


def nid(g, name):
    return g.ro_query("MATCH (n:Node {name: $n}) RETURN n.id", {"n": name}).result_set[0][0]


def test_every_tool_reports_its_cypher(g):
    aurora = nid(g, "Aurora Maritime Holdings Ltd")
    for res in [tools.search(g, "aurora"), tools.sanction_paths(g, aurora), tools.neighborhood(g, aurora),
                tools.shell_cluster(g, aurora), tools.node_detail(g, aurora), tools.stats(g)]:
        assert res["cypher"] and isinstance(res["params"], dict)


def test_search_finds_subject(g):
    c = tools.search(g, "Aurora Maritime")["candidates"]
    assert c[0]["name"] == "Aurora Maritime Holdings Ltd" and c[0]["kind"] == "Entity"


def test_ingest_matches_only_intended_names(g):
    rows = g.ro_query("MATCH (n:Node)-[m:MATCHES]->(s:Sanction) RETURN n.name, s.name, m.score, m.method").result_set
    assert sorted(rows) == [["Dmitri A. Volkov", "Dmitri Alexandrovich Volkov", 0.97, "alias"],
                            ["Radu Marinescou", "Radu Marinescou", 1.0, "exact"]]


def test_aurora_reject_path_via_coral(g):
    t = time.time()
    res = tools.sanction_paths(g, nid(g, "Aurora Maritime Holdings Ltd"))
    assert time.time() - t < 2
    assert res["found"]
    best = res["paths"][0]
    assert gate.icij_hops(best) <= 5 and best["match"]["score"] >= 0.95
    assert nid(g, "Coral Nominees Ltd") in best["nodes"]
    assert best["nodes"][-1].startswith("san:") and best["sanction"]["name"] == "Dmitri Alexandrovich Volkov"
    assert {n["id"] for n in res["subgraph"]["nodes"]} == set(best["nodes"])
    assert gate.decide(res["paths"])["verdict"] == "REJECT"


def test_clean_company_has_no_path(g):
    res = tools.sanction_paths(g, nid(g, "Greenleaf Bakery Supplies Ltd"))
    assert res["found"] is False and res["paths"] == []


def test_weak_company_path_has_similar(g):
    res = tools.sanction_paths(g, nid(g, "Kestrel Logistics SA"))
    assert res["found"]
    assert "SIMILAR" in [e["type"] for e in res["paths"][0]["edges"]]
    assert gate.decide(res["paths"])["verdict"] == "EDD"


def test_mass_registration_cluster(g):
    assert tools.shell_cluster(g, nid(g, "Bluefin Capital Ltd"))["size"] >= 40


def test_chokepoint_and_counterfactual(g):
    aurora, coral = nid(g, "Aurora Maritime Holdings Ltd"), nid(g, "Coral Nominees Ltd")
    paths = tools.sanction_paths(g, aurora)["paths"]
    assert tools.chokepoints(g, paths)["chokepoints"][0]["id"] == coral
    t = time.time()
    cf = tools.counterfactual(g, aurora, coral)
    assert time.time() - t < 2
    assert cf["still_exposed"] is False and cf["paths"] == []
    # removing an unrelated node leaves the link intact
    assert tools.counterfactual(g, aurora, nid(g, "Greenleaf Bakery Supplies Ltd"))["still_exposed"] is True


def test_counterfactual_finds_longer_detour(g):
    """Every shortest path from Seaview uses the shared address; cutting it must surface the longer detour."""
    seaview = nid(g, "Seaview Ventures Inc")
    addr = nid(g, "Suite 1702, Kallisti Tower, 45 Makariou Avenue, 3030 Limassol, Cyprus")
    assert all(addr in p["nodes"] for p in tools.sanction_paths(g, seaview)["paths"])
    cf = tools.counterfactual(g, seaview, addr)
    assert cf["still_exposed"] and addr not in cf["paths"][0]["nodes"]
    assert nid(g, "Marina Volkova") in cf["paths"][0]["nodes"] and cf["paths"][0]["edges"][-1]["type"] == "MATCHES"


def test_node_detail_and_neighborhood(g):
    san = tools.node_detail(g, "san:NK-3vQd8kXmT2pLs9WcZr4Hf")["node"]
    assert san["kind"] == "Sanction" and "Dmitri A. Volkov" in san["aliases"]
    sub = tools.neighborhood(g, nid(g, "Coral Nominees Ltd"))["subgraph"]
    assert len(sub["nodes"]) >= 6 and all(l["source"] and l["target"] for l in sub["links"])
    assert tools.node_detail(g, "nope")["node"] is None


def test_stats(g):
    s = tools.stats(g)
    assert s["labels"]["Entity"] > 600 and s["relationships"]["MATCHES"] == 2


def test_investigate_aurora_end_to_end(g):
    from shellgame import agents

    async def run():
        return [e async for e in agents.investigate(nid(g, "Aurora Maritime Holdings Ltd"), "pytest", pace=0)]

    events = asyncio.run(run())
    assert not [e for e in events if e["type"] == "error" and not e.get("recoverable")]
    verdict = next(e for e in events if e["type"] == "verdict")
    assert events[-1]["type"] == "done" and events[-1]["result"]["verdict"] == "REJECT", verdict
