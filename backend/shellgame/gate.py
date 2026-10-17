"""Deterministic verdict gate. Pure functions, no I/O, no LLM.

The LLM never decides the verdict. The Gatekeeper calls `decide()` with the facts the
Investigator gathered and the Skeptic's review; the same facts always give the same verdict.

Hop counting: `icij_hops` = number of ICIJ edges on the path (the final MATCHES edge to the
sanctions record is a name-match, not a corporate hop, so it is not counted). The demo chain
Aurora -> Coral Nominees -> Seaview -> shared address -> Volkov Trust -> Dmitri A. Volkov is 5
ICIJ hops (6 edges incl. MATCHES).

Rules (listed verbatim in README):
  R1  REJECT  A path to a sanctioned party exists with <= REJECT_MAX_HOPS ICIJ hops, no weak edge on it
              (weak = SIMILAR* / SAME_NAME_AS / SAME_INTERMEDIARY_AS / PROBABLY_SAME_*), the sanctions
              name-match score is >= MATCH_STRONG (0.95), and the Skeptic did not weaken it.
  R2  EDD     A path exists within max_hops but it was weakened: it contains a weak edge
              (SIMILAR / SAME_NAME_AS / PROBABLY_SAME_*), a name match below 0.95, or a token-only match.
  R3  EDD     A strong path exists but it is longer than REJECT_MAX_HOPS (still within max_hops).
  R4  EDD     The subject sits in a mass-registration cluster (>= CLUSTER_MIN entities sharing its
              registered address or intermediary).
  R5  APPROVE No path to any sanctioned party within max_hops and no cluster signal.
              "No path found within N hops" = no exposure in this dataset.
"""
from __future__ import annotations

from typing import Any, Iterable

REJECT_MAX_HOPS = 5
MATCH_STRONG = 0.95
CLUSTER_MIN = 25
DEFAULT_MAX_HOPS = 6

try:  # single source of truth for edge strength (Agent A's schema.py)
    from .schema import WEAK_TYPES as _SCHEMA_WEAK
except Exception:  # pragma: no cover
    _SCHEMA_WEAK = set()
WEAK_TYPES = {"SIMILAR", "SAME_NAME_AS", *_SCHEMA_WEAK}  # plus any PROBABLY_SAME_* / SIMILAR* (see is_weak_type)

RULES = {
    "R1": "REJECT: path to a sanctioned party with <= {rh} ICIJ hops, no weak edge, name-match score >= {ms}, not weakened by Skeptic.",
    "R2": "EDD: path within {mh} hops but weakened (weak edge SIMILAR/SAME_NAME_AS/PROBABLY_SAME_* etc., match score < {ms}, or token-only match).",
    "R3": "EDD: strong path exists but longer than {rh} ICIJ hops (within {mh}).",
    "R4": "EDD: mass-registration cluster of >= {cm} entities sharing the subject's registered address or intermediary.",
    "R5": "APPROVE: no path to any sanctioned party within {mh} hops and no cluster signal (no exposure in this dataset).",
}


def rules_text(max_hops: int = DEFAULT_MAX_HOPS) -> dict[str, str]:
    return {k: v.format(rh=REJECT_MAX_HOPS, ms=MATCH_STRONG, mh=max_hops, cm=CLUSTER_MIN) for k, v in RULES.items()}


def is_weak_type(rel_type: str | None) -> bool:
    t = (rel_type or "").upper()
    return t in WEAK_TYPES or t.startswith("PROBABLY_SAME") or t.startswith("SIMILAR")


def icij_hops(path: dict) -> int:
    edges = path.get("edges")
    if edges:
        return sum(1 for e in edges if (e.get("type") or "").upper() != "MATCHES")
    # Fallback: trust the tool's count minus the MATCHES edge.
    return max(0, int(path.get("hops", 0)) - 1)


def match_score(path: dict) -> float:
    m = path.get("match") or {}
    try:
        return float(m.get("score") if m.get("score") is not None else 0.0)
    except (TypeError, ValueError):
        return 0.0


def path_weak_reasons(path: dict) -> list[str]:
    """Structural weakness of one path, independent of any reviewer."""
    reasons = []
    for e in path.get("edges") or []:
        if is_weak_type(e.get("type")):
            reasons.append(f"weak edge {e.get('type')} {e.get('source')}->{e.get('target')}")
    score = match_score(path)
    if score < MATCH_STRONG:
        reasons.append(f"sanctions name-match score {score:.2f} < {MATCH_STRONG}")
    method = ((path.get("match") or {}).get("method") or "").lower()
    if method == "token":
        reasons.append("token-only name match")
    return reasons


def _san_name(path: dict) -> str:
    s = path.get("sanction") or {}
    return s.get("name") or s.get("id") or "sanctioned party"


def decide(
    paths: Iterable[dict],
    cluster_size: int | None = 0,
    max_hops: int = DEFAULT_MAX_HOPS,
    reviews: Iterable[dict] | None = None,
) -> dict[str, Any]:
    """Return {"verdict", "reasons", "rule_ids", "best_path_index"}.

    paths:   sanction paths (tools.sanction_paths format).
    reviews: optional Skeptic reviews aligned with paths: {"weakened": bool, ...}. A path is weakened
             if the Skeptic says so OR it is structurally weak (gate re-checks; it never trusts
             the reviewer to *strengthen* a path).
    """
    paths = list(paths or [])
    reviews = list(reviews or [])
    cluster_size = int(cluster_size or 0)

    evaluated = []
    for i, p in enumerate(paths):
        h = icij_hops(p)
        if h > max_hops:
            continue
        weak = path_weak_reasons(p)
        rev = reviews[i] if i < len(reviews) else {}
        weakened = bool(weak) or bool(rev.get("weakened"))
        evaluated.append((i, p, h, weakened, weak))

    reasons: list[str] = []
    rule_ids: list[str] = []
    verdict = "APPROVE"
    best = None

    strong_short = [e for e in evaluated if not e[3] and e[2] <= REJECT_MAX_HOPS]
    if strong_short:
        best = min(strong_short, key=lambda e: (e[2], -match_score(e[1])))
        i, p, h, _, _ = best
        verdict = "REJECT"
        rule_ids.append("R1")
        reasons.append(
            f"Possible link: {h}-hop path of strong corporate edges to sanctions-listed "
            f"'{_san_name(p)}' (name-match score {match_score(p):.2f})."
        )
    else:
        weakened = [e for e in evaluated if e[3]]
        strong_long = [e for e in evaluated if not e[3] and e[2] > REJECT_MAX_HOPS]
        if strong_long:
            best = min(strong_long, key=lambda e: e[2])
            verdict = "EDD"
            rule_ids.append("R3")
            reasons.append(f"Strong but distant exposure: {best[2]} ICIJ hops to '{_san_name(best[1])}'.")
        if weakened:
            w = min(weakened, key=lambda e: e[2])
            best = best or w
            verdict = "EDD"
            rule_ids.append("R2")
            reasons.append(
                f"Possible link to '{_san_name(w[1])}' in {w[2]} hops, weakened: " + "; ".join(w[4] or ["Skeptic review"]) + "."
            )

    if cluster_size >= CLUSTER_MIN:
        rule_ids.append("R4")
        reasons.append(f"Mass-registration signal: {cluster_size} entities share the subject's address/intermediary.")
        if verdict == "APPROVE":
            verdict = "EDD"

    if verdict == "APPROVE":
        rule_ids.append("R5")
        reasons.append(f"No path to any sanctioned party within {max_hops} hops; no exposure in this dataset.")

    return {
        "verdict": verdict,
        "reasons": reasons,
        "rule_ids": rule_ids,
        "best_path_index": best[0] if best else None,
    }
