from shellgame import gate


def _path(edges, score=0.97, method="alias"):
    nodes = [edges[0][0]] + [e[1] for e in edges]
    return {"hops": len(edges), "nodes": nodes, "sanction": {"id": nodes[-1], "name": "X"},
            "match": {"score": score, "method": method},
            "edges": [{"source": s, "target": t, "type": ty} for s, t, ty in edges]}


AURORA = _path([("E1", "O1", "OFFICER_OF"), ("O1", "E2", "OFFICER_OF"), ("E2", "A1", "REGISTERED_ADDRESS"),
                ("A1", "E3", "REGISTERED_ADDRESS"), ("E3", "O2", "OFFICER_OF"), ("O2", "san:1", "MATCHES")])


def test_reject_strong_path():
    d = gate.decide([AURORA], cluster_size=3)
    assert d["verdict"] == "REJECT" and d["rule_ids"] == ["R1"] and d["best_path_index"] == 0


def test_weak_edge_downgrades_to_edd():
    p = _path([("E5", "O5", "OFFICER_OF"), ("O5", "O6", "SIMILAR"), ("O6", "san:2", "MATCHES")], score=1.0)
    d = gate.decide([p])
    assert d["verdict"] == "EDD" and "R2" in d["rule_ids"]


def test_probably_same_is_weak():
    assert gate.is_weak_type("PROBABLY_SAME_OFFICER_AS")


def test_low_score_downgrades():
    p = _path([("E1", "O1", "OFFICER_OF"), ("O1", "san:1", "MATCHES")], score=0.9)
    assert gate.decide([p])["verdict"] == "EDD"


def test_skeptic_can_weaken_but_not_strengthen():
    assert gate.decide([AURORA], reviews=[{"weakened": True}])["verdict"] == "EDD"
    weak = _path([("E5", "O5", "OFFICER_OF"), ("O5", "O6", "SIMILAR"), ("O6", "san:2", "MATCHES")], score=1.0)
    assert gate.decide([weak], reviews=[{"weakened": False}])["verdict"] == "EDD"


def test_long_strong_path_is_edd():
    edges = [(f"n{i}", f"n{i+1}", "OFFICER_OF") for i in range(6)] + [("n6", "san:x", "MATCHES")]
    d = gate.decide([_path(edges)])
    assert d["verdict"] == "EDD" and "R3" in d["rule_ids"]


def test_beyond_max_hops_ignored():
    edges = [(f"n{i}", f"n{i+1}", "OFFICER_OF") for i in range(7)] + [("n7", "san:x", "MATCHES")]
    assert gate.decide([_path(edges)], max_hops=6)["verdict"] == "APPROVE"


def test_cluster_signal():
    d = gate.decide([], cluster_size=40)
    assert d["verdict"] == "EDD" and d["rule_ids"] == ["R4"]
    d = gate.decide([AURORA], cluster_size=40)
    assert d["verdict"] == "REJECT" and d["rule_ids"] == ["R1", "R4"]


def test_approve_no_path():
    d = gate.decide([], cluster_size=2)
    assert d["verdict"] == "APPROVE" and d["rule_ids"] == ["R5"]
    assert d["best_path_index"] is None


def test_deterministic_and_pure():
    a = gate.decide([AURORA], cluster_size=1)
    b = gate.decide([AURORA], cluster_size=1)
    assert a == b
    assert AURORA["hops"] == 6  # input not mutated


def test_rules_text_complete():
    assert set(gate.rules_text()) == {"R1", "R2", "R3", "R4", "R5"}
