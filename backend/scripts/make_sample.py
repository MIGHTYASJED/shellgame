"""Write deterministic synthetic data in the exact ICIJ Offshore Leaks + OpenSanctions CSV formats.

    python scripts/make_sample.py [OUT_DIR]        (default: <repo>/data/sample)

All names are fictional. Contains the SPEC demo scenario plus ~1.5k background nodes.
"""
from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "data" / "sample"
rng = random.Random(42)

HEADERS = {
    "nodes-entities.csv": "node_id,name,original_name,former_name,jurisdiction,jurisdiction_description,company_type,"
                          "address,internal_id,incorporation_date,inactivation_date,struck_off_date,dorm_date,status,"
                          "service_provider,ibcRUC,country_codes,countries,note,valid_until,sourceID",
    "nodes-officers.csv": "node_id,name,countries,country_codes,valid_until,sourceID,note",
    "nodes-intermediaries.csv": "node_id,name,status,internal_id,address,countries,country_codes,valid_until,sourceID,note",
    "nodes-addresses.csv": "node_id,address,name,countries,country_codes,valid_until,sourceID,note",
    "nodes-others.csv": "node_id,name,type,incorporation_date,struck_off_date,closed_date,jurisdiction,"
                        "jurisdiction_description,countries,country_codes,valid_until,sourceID,note",
    "relationships.csv": "node_id_start,node_id_end,rel_type,link,status,start_date,end_date,sourceID",
}
SANCTIONS_HEADER = ("id,schema,name,aliases,birth_date,countries,addresses,identifiers,sanctions,phones,emails,"
                    "program_ids,dataset,first_seen,last_seen,last_change")
ID_BASE = {"nodes-entities.csv": 10000001, "nodes-officers.csv": 12000001, "nodes-intermediaries.csv": 11000001,
           "nodes-addresses.csv": 14000001, "nodes-others.csv": 85000001}
SOURCES = {"Panama Papers": "The Panama Papers data is current through 2015",
           "Paradise Papers - Appleby": "The Paradise Papers data is current through 2014",
           "Pandora Papers": "The Pandora Papers data is current through 2020"}
JURISDICTIONS = [("BVI", "British Virgin Islands", "VGB"), ("PMA", "Panama", "PAN"), ("SEY", "Seychelles", "SYC"),
                 ("BAH", "Bahamas", "BHS"), ("SAM", "Samoa", "WSM"), ("NIUE", "Niue", "NIU"),
                 ("CYP", "Cyprus", "CYP"), ("HK", "Hong Kong", "HKG")]
COUNTRIES = [("United Kingdom", "GBR"), ("Switzerland", "CHE"), ("Hong Kong", "HKG"), ("Russia", "RUS"),
             ("United Arab Emirates", "ARE"), ("Cyprus", "CYP"), ("Germany", "DEU"), ("Brazil", "BRA"),
             ("Singapore", "SGP"), ("Panama", "PAN"), ("Monaco", "MCO"), ("Luxembourg", "LUX")]
FIRST = ["Adrian", "Beatriz", "Carlos", "Daria", "Elena", "Farid", "Gustav", "Helena", "Igor", "Julia", "Kenji",
         "Lars", "Marta", "Nikos", "Olga", "Pavel", "Rosa", "Stefan", "Tomas", "Ursula", "Viktor", "Wen", "Yusuf", "Zofia"]
LAST = ["Abernathy", "Bellweather", "Castellane", "Dunmore", "Esterhazy", "Falkenrath", "Grimsby", "Halloway",
        "Ivers", "Jandorf", "Kessler", "Lindqvist", "Morrow", "Nightingale", "Oakhart", "Pemberton", "Quillon",
        "Ravensworth", "Stavrakis", "Thornbury", "Underhill", "Vantongeren", "Whitlock", "Yardley", "Zelenko"]
CO_A = ["Amber", "Atlas", "Azure", "Birch", "Cobalt", "Crimson", "Delta", "Ember", "Falcon", "Granite", "Harbor",
        "Indigo", "Jade", "Juniper", "Lighthouse", "Meridian", "Monarch", "Northgate", "Obsidian", "Onyx", "Pinnacle",
        "Quartz", "Redwood", "Sapphire", "Sierra", "Solstice", "Summit", "Tamarind", "Titan", "Vertex", "Willow", "Zenith"]
CO_B = ["Holdings", "Ventures", "Capital", "Trading", "Investments", "Resources", "Shipping", "Properties",
        "Enterprises", "Group", "Partners", "Assets"]
CO_SUFFIX = ["Ltd", "Limited", "Inc.", "Corp.", "S.A.", "Ltd."]
LINKS = ["director of", "shareholder of", "beneficiary of", "secretary of", "director of", "shareholder of"]
STREETS = ["Wickhams Cay", "Main Street", "Bay Street", "Calle 50", "Queen's Road Central", "Avenue Princesse Grace",
           "Victoria Street", "Marina Boulevard", "Rue du Rhone", "Sheikh Zayed Road"]


def date(y0=1998, y1=2015) -> str:
    return f"{rng.randint(1, 28):02d}-{rng.choice(['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'])}-{rng.randint(y0, y1)}"


class Sample:
    def __init__(self):
        self.rows = {f: [] for f in HEADERS}
        self.next_id = dict(ID_BASE)
        self.sanctions = []

    def node(self, file: str, **fields) -> str:
        nid = str(self.next_id[file])
        self.next_id[file] += 1
        source = fields.pop("source", rng.choice(list(SOURCES)))
        self.rows[file].append({"node_id": nid, "sourceID": source, "valid_until": SOURCES[source], **fields})
        return nid

    def entity(self, name, jur=None, **kw):
        code, desc, cc = jur or rng.choice(JURISDICTIONS)
        return self.node("nodes-entities.csv", name=name, original_name=name, jurisdiction=code,
                         jurisdiction_description=desc, incorporation_date=date(), status=kw.pop("status", "Active"),
                         service_provider=kw.pop("service_provider", "Tidewater Trust Co."), internal_id=str(rng.randint(10000, 999999)),
                         countries=desc, country_codes=cc, **kw)

    def officer(self, name, country=None):
        c, cc = country or rng.choice(COUNTRIES)
        return self.node("nodes-officers.csv", name=name, countries=c, country_codes=cc)

    def intermediary(self, name, country=None):
        c, cc = country or rng.choice(COUNTRIES)
        return self.node("nodes-intermediaries.csv", name=name, status="ACTIVE", countries=c, country_codes=cc,
                         internal_id=str(rng.randint(1000, 99999)))

    def address(self, text, country=None):
        c, cc = country or rng.choice(COUNTRIES)
        return self.node("nodes-addresses.csv", address=text, countries=c, country_codes=cc)

    def other(self, name):
        code, desc, cc = rng.choice(JURISDICTIONS)
        return self.node("nodes-others.csv", name=name, type="LIMITED LIABILITY COMPANY", incorporation_date=date(),
                         jurisdiction=code, jurisdiction_description=desc, countries=desc, country_codes=cc)

    def rel(self, start, end, rel_type, link):
        self.rows["relationships.csv"].append({"node_id_start": start, "node_id_end": end, "rel_type": rel_type,
                                               "link": link, "start_date": date() if rel_type == "officer_of" else "",
                                               "sourceID": "Panama Papers"})

    def sanction(self, sid, schema, name, aliases="", countries="", program="", birth_date=""):
        self.sanctions.append({"id": sid, "schema": schema, "name": name, "aliases": aliases, "birth_date": birth_date,
                               "countries": countries, "sanctions": program, "program_ids": program.split(" - ")[0],
                               "dataset": "Shell Game synthetic sample", "first_seen": "2022-03-01T00:00:00",
                               "last_seen": "2026-10-01T00:00:00", "last_change": "2024-06-12T00:00:00"})

    def write(self, out: Path):
        out.mkdir(parents=True, exist_ok=True)
        for file, header in HEADERS.items():
            with open(out / file, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=header.split(","))
                w.writeheader()
                w.writerows(self.rows[file])
        with open(out / "targets.simple.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=SANCTIONS_HEADER.split(","))
            w.writeheader()
            w.writerows(self.sanctions)


def background(s: Sample):
    """Random but realistic-looking offshore web; contains no sanctioned names."""
    people = rng.sample([f"{f} {l}" for f in FIRST for l in LAST], 480)
    ents = [s.entity(f"{rng.choice(CO_A)} {rng.choice(CO_B)} {rng.choice(CO_SUFFIX)}") for _ in range(600)]
    offs = [s.officer(n) for n in people]
    offs += [s.officer(f"{a} Nominees Limited", ("Seychelles", "SYC")) for a in CO_A[:8]]  # corporate directors
    inters = [s.intermediary(f"{a} {rng.choice(['Corporate Services', 'Trust Company', 'Law Chambers', 'Fiduciaries'])} Ltd")
              for a in rng.sample(CO_A, 30)]
    addrs = [s.address(f"{rng.randint(1, 400)} {rng.choice(STREETS)}, Suite {rng.randint(100, 999)}") for _ in range(280)]
    others = [s.other(f"{rng.choice(CO_A)} {rng.choice(['Foundation', 'Trust', 'Stiftung'])}") for _ in range(40)]
    hot = offs[-8:]  # corporate nominees serve many companies
    for e in ents:
        for o in rng.sample(offs, rng.randint(1, 2)) + ([rng.choice(hot)] if rng.random() < 0.3 else []):
            s.rel(o, e, "officer_of", rng.choice(LINKS) if o not in hot else "nominee director of")
        s.rel(rng.choice(inters), e, "intermediary_of", "intermediary of")
        if rng.random() < 0.8:
            s.rel(e, rng.choice(addrs), "registered_address", "registered address")
    for o in rng.sample(offs, 120):
        s.rel(o, rng.choice(addrs), "registered_address", "registered address")
    for o in others:
        s.rel(o, rng.choice(ents), rng.choice(["connected_to", "underlying"]), "connected to")
    for _ in range(12):
        a, b = rng.sample(offs, 2)
        s.rel(a, b, rng.choice(["similar", "same_name_as", "probably_same_officer_as", "same_as"]),
              "similar name and address as")
    # sanctions records that match nobody in ICIJ (fictional)
    sf = ["Anatoly", "Bogdan", "Gennady", "Ruslan", "Timur", "Vadim", "Yaroslav", "Zakhar", "Arkady", "Leonid"]
    sl = ["Orlovsky", "Baranikov", "Chernyshev", "Durnovo", "Kalganov", "Lebedinsky", "Mirskov", "Pashutin",
          "Rozhdestvin", "Tarkhanov", "Velichko", "Zhdanovich"]
    for i, (f, l) in enumerate(rng.sample([(f, l) for f in sf for l in sl], 110)):
        s.sanction(f"NK-bg{i:04d}person", "Person", f"{f} {l}", f"{f[0]}. {l}", "ru",
                   "EU Financial Sanctions - Annex I", f"19{rng.randint(50, 89)}-0{rng.randint(1, 9)}-1{rng.randint(0, 9)}")
    for i, l in enumerate(sl):
        s.sanction(f"NK-bg{i:04d}company", "Company", f"{l} Industrial Group JSC", "", "ru", "OFAC SDN - RUSSIA-EO14024")
    return ents, offs, inters


def scenario(s: Sample, ents, offs, inters):
    bvi, cyp, pma = JURISDICTIONS[0], JURISDICTIONS[6], JURISDICTIONS[1]
    # Demo: Aurora -> Coral Nominees -> Seaview -> shared address -> Volkov Trust -> Dmitri A. Volkov ~ sanctioned
    aurora = s.entity("Aurora Maritime Holdings Ltd", bvi, source="Pandora Papers")
    coral = s.officer("Coral Nominees Ltd", ("Seychelles", "SYC"))
    seaview = s.entity("Seaview Ventures Inc", JURISDICTIONS[2])
    shared = s.address("Suite 1702, Kallisti Tower, 45 Makariou Avenue, 3030 Limassol, Cyprus", ("Cyprus", "CYP"))
    trust = s.entity("Volkov Trust Holdings", cyp)
    dmitri = s.officer("Dmitri A. Volkov", ("Russia", "RUS"))
    s.rel(coral, aurora, "officer_of", "nominee director of")
    s.rel(rng.choice(offs[:480]), aurora, "officer_of", "shareholder of")
    s.rel(inters[0], aurora, "intermediary_of", "intermediary of")
    s.rel(aurora, s.address("Unit 4B, Pelican Court, 9 Marina Drive, Road Town, Tortola, BVI", ("British Virgin Islands", "VGB")),
          "registered_address", "registered address")
    s.rel(coral, seaview, "officer_of", "nominee director of")
    for e in rng.sample(ents, 3):
        s.rel(coral, e, "officer_of", "nominee director of")
    s.rel(seaview, shared, "registered_address", "registered address")
    s.rel(trust, shared, "registered_address", "registered address")
    s.rel(dmitri, trust, "officer_of", "beneficial owner of")
    marina = s.officer("Marina Volkova", ("Cyprus", "CYP"))
    s.rel(marina, trust, "officer_of", "secretary of")
    # longer detour (Seaview -> agent -> Limassol Bay -> Marina -> trust): cutting the shared address alone is not enough
    kallisti = s.intermediary("Kallisti Corporate Services Ltd", ("Cyprus", "CYP"))
    bay = s.entity("Limassol Bay Trading Ltd", cyp)
    s.rel(kallisti, seaview, "intermediary_of", "intermediary of")
    s.rel(kallisti, bay, "intermediary_of", "intermediary of")
    s.rel(marina, bay, "officer_of", "director of")
    s.sanction("NK-3vQd8kXmT2pLs9WcZr4Hf", "Person", "Dmitri Alexandrovich Volkov",
               "Dmitry Aleksandrovich Volkov;Dmitri A. Volkov;Дмитрий Александрович Волков", "ru",
               "EU Financial Sanctions - Annex I;OFAC SDN - RUSSIA-EO14024", "1968-04-11")

    # Weak link (EDD): Kestrel's director is only SIMILAR to a sanctioned namesake.
    kestrel = s.entity("Kestrel Logistics SA", pma)
    radu = s.officer("Radu Marinescu", ("Romania", "ROU"))
    radu2 = s.officer("Radu Marinescou", ("Moldova", "MDA"))
    s.rel(radu, kestrel, "officer_of", "director of")
    s.rel(radu, radu2, "similar", "similar name and address as")
    s.rel(radu2, s.entity("Danube Freight Holdings Ltd", bvi), "officer_of", "director of")
    s.rel(kestrel, s.address("Torre Global, Piso 12, Calle 50, Panama City", ("Panama", "PAN")), "registered_address",
          "registered address")
    s.sanction("NK-9pXe2RmQw7KdTb4Lc1Vz", "Person", "Radu Marinescou", "Radu Marinesku", "md",
               "UK Sanctions List - Russia")

    # Clean (APPROVE): isolated, ordinary company.
    fernhill = s.intermediary("Fernhill Accountancy LLP", ("United Kingdom", "GBR"))
    for name, people in [("Greenleaf Bakery Supplies Ltd", ["Margaret Holloway", "Peter Lindgren"]),
                         ("Brookside Garden Tools Ltd", ["Alan Pritchard"]), ("Millbrook Stationers Ltd", ["Susan Okafor"])]:
        e = s.entity(name, JURISDICTIONS[3], service_provider="Fernhill Accountancy")
        s.rel(fernhill, e, "intermediary_of", "intermediary of")
        for p in people:
            s.rel(s.officer(p, ("United Kingdom", "GBR")), e, "officer_of", "director of")
        s.rel(e, s.address(f"{rng.randint(2, 90)} High Street, Bath, United Kingdom", ("United Kingdom", "GBR")),
              "registered_address", "registered address")

    # Mass registration: 45 shells at one PO box, formed by one agent.
    pobox = s.address("PO Box 3340, Road Town, Tortola, British Virgin Islands", ("British Virgin Islands", "VGB"))
    agent = s.intermediary("Sterling Formation Agents Ltd", ("British Virgin Islands", "VGB"))
    shells = ["Bluefin Capital Ltd"] + [f"{a} {b} {n} Ltd" for a, b, n in
                                        zip(rng.sample(CO_A, 32) * 2, rng.choices(CO_B, k=44), range(101, 145))]
    for name in shells:
        e = s.entity(name, bvi, status="Defaulted")
        s.rel(e, pobox, "registered_address", "registered address")
        s.rel(agent, e, "intermediary_of", "intermediary of")
        s.rel(rng.choice(offs[-8:]), e, "officer_of", "nominee director of")


def main():
    s = Sample()
    scenario(s, *background(s))
    s.write(OUT)
    n = sum(len(v) for k, v in s.rows.items() if k != "relationships.csv")
    print(f"wrote {n} nodes, {len(s.rows['relationships.csv'])} relationships, {len(s.sanctions)} sanctions -> {OUT}")


if __name__ == "__main__":
    main()
