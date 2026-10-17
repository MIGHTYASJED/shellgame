"""Graph model constants, edge weights, index creation and name normalization (shared by ingest + tools)."""
from __future__ import annotations

import re
import unicodedata

MAIN_GRAPH = "shellgame"
SANCTION_PREFIX = "san:"

KINDS = ("Entity", "Officer", "Intermediary", "Address", "Other")
NAMED_KINDS = ("Entity", "Officer", "Intermediary", "Other")  # kinds that get name_norm + matching

# ICIJ file name -> kind label
ICIJ_FILES = {
    "nodes-entities.csv": "Entity",
    "nodes-officers.csv": "Officer",
    "nodes-intermediaries.csv": "Intermediary",
    "nodes-addresses.csv": "Address",
    "nodes-others.csv": "Other",
}
RELATIONSHIPS_FILE = "relationships.csv"

# Properties copied from each ICIJ file (csv column -> graph property). Missing columns are ignored.
NODE_PROPS = {
    "Entity": {"name": "name", "jurisdiction": "jurisdiction", "jurisdiction_description": "jurisdiction_description",
               "incorporation_date": "incorporation_date", "inactivation_date": "inactivation_date",
               "struck_off_date": "struck_off_date", "status": "status", "company_type": "company_type",
               "service_provider": "service_provider", "countries": "countries", "country_codes": "country_codes",
               "address": "address", "original_name": "original_name", "former_name": "former_name",
               "sourceID": "source"},
    "Officer": {"name": "name", "countries": "countries", "country_codes": "country_codes", "sourceID": "source"},
    "Intermediary": {"name": "name", "status": "status", "address": "address", "countries": "countries",
                     "country_codes": "country_codes", "sourceID": "source"},
    "Address": {"address": "name", "countries": "countries", "country_codes": "country_codes", "sourceID": "source"},
    "Other": {"name": "name", "type": "type", "incorporation_date": "incorporation_date",
              "struck_off_date": "struck_off_date", "closed_date": "closed_date", "jurisdiction": "jurisdiction",
              "jurisdiction_description": "jurisdiction_description", "countries": "countries",
              "country_codes": "country_codes", "sourceID": "source"},
}

# ---------------------------------------------------------------- edges
STRONG_TYPES = {"OFFICER_OF", "INTERMEDIARY_OF", "REGISTERED_ADDRESS", "SAME_AS", "SAME_COMPANY_AS", "SAME_ID_AS"}
WEAK_TYPES = {"SIMILAR", "SAME_NAME_AS", "SAME_INTERMEDIARY_AS"}
MATCHES = "MATCHES"


def rel_type(raw: str) -> str:
    """ICIJ rel_type -> edge type: uppercase, non-alnum -> '_' (safe to interpolate into Cypher)."""
    t = re.sub(r"[^A-Z0-9]+", "_", (raw or "").strip().upper()).strip("_") or "RELATED"
    if t[0].isdigit():
        t = "R_" + t
    return t


def is_weak(t: str) -> bool:
    t = (t or "").upper()
    return t in WEAK_TYPES or t.startswith("PROBABLY_SAME") or t.startswith("SIMILAR")


def edge_weight(t: str) -> float:
    """SPEC edge strength: strong = 1, weak (SIMILAR / SAME_NAME_AS / PROBABLY_SAME_*) = 3, other = 2."""
    t = (t or "").upper()
    if t in STRONG_TYPES:
        return 1.0
    if is_weak(t):
        return 3.0
    return 2.0  # CONNECTED_TO, UNDERLYING and any unknown ICIJ type


def match_weight(score: float) -> float:
    return 1.0 if score >= 0.95 else 3.0


# ---------------------------------------------------------------- indexes
INDEX_QUERIES = [
    "CREATE INDEX FOR (n:Node) ON (n.id)",
    "CREATE INDEX FOR (s:Sanction) ON (s.id)",
    "CREATE INDEX FOR (n:Node) ON (n.name_norm)",
    "CALL db.idx.fulltext.createNodeIndex('Node', 'name')",
    "CALL db.idx.fulltext.createNodeIndex('Sanction', 'name')",
]


def create_indexes(g) -> None:
    for q in INDEX_QUERIES:
        try:
            g.query(q)
        except Exception as e:  # already exists
            if "already" not in str(e).lower():
                raise


# ---------------------------------------------------------------- name normalization
CORP_SUFFIXES = {
    "ltd", "limited", "inc", "incorporated", "corp", "corporation", "co", "company", "llc", "lc", "plc", "sa",
    "sas", "sarl", "srl", "spa", "ag", "gmbh", "bv", "nv", "lp", "llp", "pte", "pty", "sl", "ab", "as", "oy",
    "kft", "ooo", "zao", "oao", "pjsc", "jsc", "ojsc", "cjsc", "ltda", "sde", "intl", "international", "the",
}
HONORIFICS = {"mr", "mrs", "ms", "miss", "dr", "sir", "dame", "lord", "lady", "prof", "sheikh", "shaikh", "hon",
              "the", "mme", "mlle", "herr", "frau", "jr", "sr", "ii", "iii"}
GENERATIONAL = {"jr", "sr", "ii", "iii"}
JUNK_NAMES = {"bearer", "the bearer", "unknown", "nominee", "n a", "na", "none", "same", "deceased"}


def normalize(name: str | None) -> str:
    """casefold, strip accents + punctuation, drop trailing corporate suffixes and honorifics, collapse spaces."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    s = s.replace("&", " and ")
    s = re.sub(r"[.'`’]", "", s)          # "S.A." -> "sa", "O'Neil" -> "oneil"
    s = re.sub(r"[^\w]+", " ", s).replace("_", " ")
    toks = s.split()
    while toks and toks[0] in HONORIFICS:
        toks.pop(0)
    while len(toks) > 1 and (toks[-1] in CORP_SUFFIXES or toks[-1] in GENERATIONAL):  # not "sheikh": a surname there
        toks.pop()
    return " ".join(toks)
