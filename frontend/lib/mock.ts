// Mock mode fixtures (NEXT_PUBLIC_MOCK=1). Fictional data mirroring the SPEC demo scenario.
// Events follow the SPEC event format exactly so the UI code path is identical to real mode.
import type { AgentEvent, Candidate, CaseRecord, CounterfactualResult, PathRec, SgLink, SgNode, Subgraph } from "./types";

const N = {
  aurora: "10000001",
  coral: "12000101",
  seaview: "10000002",
  addr: "14000301",
  vtrust: "10000003",
  dav: "12000202",
  dav2: "12000203",
  san: "san:NK-7f3c2a91",
  halcyon: "10000044",
  meridian: "10000051",
  meridianSim: "10000052",
  trident: "14000900",
};

const nodes: Record<string, SgNode> = {
  [N.aurora]: { id: N.aurora, kind: "Entity", name: "Aurora Maritime Holdings Ltd", jurisdiction: "BVI", sanctioned: false },
  [N.coral]: { id: N.coral, kind: "Officer", name: "Coral Nominees Ltd", sanctioned: false },
  [N.seaview]: { id: N.seaview, kind: "Entity", name: "Seaview Ventures Inc", jurisdiction: "PAN", sanctioned: false },
  [N.addr]: { id: N.addr, kind: "Address", name: "Suite 4, Harbour Chambers, Road Town, Tortola, BVI", sanctioned: false },
  [N.vtrust]: { id: N.vtrust, kind: "Entity", name: "Volkov Trust Holdings", jurisdiction: "CYP", sanctioned: false },
  [N.dav]: { id: N.dav, kind: "Officer", name: "Dmitri A. Volkov", sanctioned: false },
  [N.dav2]: { id: N.dav2, kind: "Officer", name: "D. Volkov", sanctioned: false },
  [N.san]: { id: N.san, kind: "Sanction", name: "Dmitri Alexandrovich Volkov", sanctioned: true },
  [N.halcyon]: { id: N.halcyon, kind: "Entity", name: "Halcyon Logistics Ltd", jurisdiction: "SGP", sanctioned: false },
  [N.meridian]: { id: N.meridian, kind: "Entity", name: "Meridian Star Trading Ltd", jurisdiction: "SEY", sanctioned: false },
  [N.meridianSim]: { id: N.meridianSim, kind: "Entity", name: "Meridian Star Trading Limited", jurisdiction: "SEY", sanctioned: false },
  [N.trident]: { id: N.trident, kind: "Address", name: "Trident Chambers, Wickhams Cay, Road Town, BVI", sanctioned: false },
};

// Background noise so the canvas looks like a real slice of the leak data.
const bgNames = [
  ["Entity", "Pelican Bay Investments Ltd", "BVI"], ["Entity", "Northgate Shipping SA", "PAN"],
  ["Officer", "Elena Markides"], ["Officer", "Harbour Secretaries Ltd"], ["Entity", "Bluewater Capital Corp", "BVI"],
  ["Intermediary", "Mossbank Corporate Services"], ["Entity", "Kestrel Bulk Carriers Ltd", "MHL"],
  ["Officer", "J. Ferreira"], ["Entity", "Lantern Holdings Inc", "BVI"], ["Officer", "Coral Secretaries Ltd"],
  ["Address", "PO Box 3152, Road Town, Tortola"], ["Entity", "Opal Reef Trading Ltd", "SEY"],
  ["Officer", "Andreas Charalambous"], ["Entity", "Saltmarsh Ventures Ltd", "CYP"], ["Intermediary", "Limassol Fiduciary Ltd"],
  ["Entity", "Greyfriars Commodities Ltd", "BVI"], ["Officer", "Bearer 1"], ["Entity", "Morrow Point Ltd", "BVI"],
  ["Officer", "Nadia Petrenko"], ["Entity", "Cobalt Line Holdings SA", "PAN"], ["Address", "12 Agias Fylaxeos, Limassol"],
  ["Entity", "Westerly Assets Ltd", "BVI"], ["Officer", "Island Directors Ltd"], ["Entity", "Tamarind Holdings Ltd", "MUS"],
] as const;
const bg: SgNode[] = bgNames.map((b, i) => ({
  id: String(20000100 + i), kind: b[0], name: b[1], jurisdiction: (b as any)[2], sanctioned: false,
}));
const bgAnchors = [N.aurora, N.coral, N.aurora, N.coral, N.aurora, N.coral, N.aurora, N.coral];
const bgLinks: SgLink[] = bg.map((b, i) => {
  const anchor = i < 8 ? bgAnchors[i] : bg[(i * 7) % 8].id;
  const type = b.kind === "Officer" ? "OFFICER_OF" : b.kind === "Intermediary" ? "INTERMEDIARY_OF" : b.kind === "Address" ? "REGISTERED_ADDRESS" : "OFFICER_OF";
  return { source: b.id, target: anchor, type, link: type === "OFFICER_OF" ? (i % 3 ? "director" : "shareholder") : type === "INTERMEDIARY_OF" ? "intermediary" : "registered address" };
});

const L = {
  auroraCoral: { source: N.coral, target: N.aurora, type: "OFFICER_OF", link: "nominee director" },
  coralSeaview: { source: N.coral, target: N.seaview, type: "OFFICER_OF", link: "director" },
  seaviewAddr: { source: N.seaview, target: N.addr, type: "REGISTERED_ADDRESS", link: "registered address" },
  vtrustAddr: { source: N.vtrust, target: N.addr, type: "REGISTERED_ADDRESS", link: "registered address" },
  davVtrust: { source: N.dav, target: N.vtrust, type: "OFFICER_OF", link: "beneficial owner" },
  davSan: { source: N.dav, target: N.san, type: "MATCHES", link: "name match 0.97 (alias)" },
  dav2Seaview: { source: N.dav2, target: N.seaview, type: "OFFICER_OF", link: "shareholder" },
  dav2San: { source: N.dav2, target: N.san, type: "MATCHES", link: "name match 0.82 (token)" },
  meridianSim: { source: N.meridian, target: N.meridianSim, type: "SIMILAR", link: "similar name" },
  meridianSimDav: { source: N.dav2, target: N.meridianSim, type: "OFFICER_OF", link: "director" },
} satisfies Record<string, SgLink>;

function sg(ids: string[], links: SgLink[]): Subgraph {
  return { nodes: ids.map((i) => nodes[i] ?? bg.find((b) => b.id === i)!).filter(Boolean), links };
}

export const mockCandidates: Candidate[] = [
  { id: N.aurora, kind: "Entity", name: "Aurora Maritime Holdings Ltd", jurisdiction: "BVI", countries: "British Virgin Islands" },
  { id: N.vtrust, kind: "Entity", name: "Volkov Trust Holdings", jurisdiction: "CYP", countries: "Cyprus" },
  { id: N.meridian, kind: "Entity", name: "Meridian Star Trading Ltd", jurisdiction: "SEY", countries: "Seychelles" },
  { id: N.halcyon, kind: "Entity", name: "Halcyon Logistics Ltd", jurisdiction: "SGP", countries: "Singapore" },
  { id: N.coral, kind: "Officer", name: "Coral Nominees Ltd", countries: "British Virgin Islands" },
  ...bg.filter((b) => b.kind === "Entity").map((b) => ({ id: b.id, kind: b.kind, name: b.name, jurisdiction: b.jurisdiction, countries: "" })),
];

export function mockSearch(q: string): Candidate[] {
  const s = q.trim().toLowerCase();
  if (!s) return [];
  return mockCandidates.filter((c) => c.name.toLowerCase().includes(s)).slice(0, 10);
}

export const mockStats = {
  labels: { Entity: 1184, Officer: 902, Intermediary: 61, Address: 433, Sanction: 312 },
  relationships: { OFFICER_OF: 1830, REGISTERED_ADDRESS: 1121, INTERMEDIARY_OF: 402, SIMILAR: 48, SAME_NAME_AS: 22, MATCHES: 19 },
};

export const mockTenants = ["default", "acme-bank-kyc", "northwind-compliance"];

const CY = {
  search: "CALL db.idx.fulltext.queryNodes('Node', $q) YIELD node, score\nRETURN node.id AS id, labels(node) AS labels, node.name AS name,\n       node.jurisdiction AS jurisdiction, node.countries AS countries\nORDER BY score DESC LIMIT $limit",
  recall: "MATCH (c:Case)-[r:EXAMINED|CLEARED|FLAGGED]->(ref:Ref)\nWHERE ref.id IN $node_ids\nRETURN c.id, c.created_at, c.subject_name, c.verdict, type(r) AS rel, r.reason, ref.name\nORDER BY c.created_at DESC",
  paths: "MATCH (src:Node {id: $node_id})\nMATCH (s:Sanction)<-[m:MATCHES]-(:Node)\nWITH src, s\nCALL algo.SPpaths({sourceNode: src, targetNode: s,\n  relTypes: $rel_types, weightProp: 'w', maxLen: $max_hops,\n  pathCount: $k}) YIELD path, pathWeight\nRETURN path, pathWeight ORDER BY pathWeight ASC LIMIT $k",
  cluster: "MATCH (e:Entity {id: $node_id})-[:REGISTERED_ADDRESS|INTERMEDIARY_OF]-(hub)\nMATCH (hub)-[:REGISTERED_ADDRESS|INTERMEDIARY_OF]-(peer:Entity)\nRETURN hub.id AS hub, labels(hub)[1] AS kind, count(DISTINCT peer) AS size",
  choke: "UNWIND $path_node_ids AS pid\nMATCH (n:Node {id: pid})\nWITH n, count(*) AS paths_through\nCALL algo.betweenness({nodeLabels: ['Node'], relationshipTypes: $rel_types})\nYIELD node, score WHERE node = n\nRETURN n.id, n.name, labels(n)[1], paths_through, score ORDER BY paths_through DESC",
  counter: "MATCH (src:Node {id: $node_id}), (s:Sanction)\nCALL algo.SPpaths({sourceNode: src, targetNode: s, maxLen: $max_hops,\n  pathCount: 3, weightProp: 'w'}) YIELD path, pathWeight\nWHERE NONE(x IN nodes(path) WHERE x.id = $remove_id)\nRETURN path, pathWeight ORDER BY pathWeight LIMIT 3",
  detail: "MATCH (n {id: $node_id}) RETURN n, labels(n)",
};

const path1: PathRec = {
  hops: 6, weight: 6, match: { score: 0.97, method: "alias" },
  sanction: { id: N.san, name: "Dmitri Alexandrovich Volkov", schema: "Person", programs: "EU-UKR-2014; OFAC-RUSSIA-EO14024", datasets: "eu_fsf; us_ofac_sdn" },
  nodes: [N.aurora, N.coral, N.seaview, N.addr, N.vtrust, N.dav, N.san],
  edges: [L.auroraCoral, L.coralSeaview, L.seaviewAddr, L.vtrustAddr, L.davVtrust, L.davSan],
};
const path2: PathRec = {
  hops: 4, weight: 6, match: { score: 0.82, method: "token" },
  sanction: path1.sanction,
  nodes: [N.aurora, N.coral, N.seaview, N.dav2, N.san],
  edges: [L.auroraCoral, L.coralSeaview, L.dav2Seaview, L.dav2San],
};

const hl = (p: PathRec) => ({ nodes: p.nodes, links: p.edges.map((e) => ({ source: e.source, target: e.target })) });

type Step = { delay: number; ev: AgentEvent };

function auroraScript(): Step[] {
  const neighborhoodSg = sg(
    [N.aurora, N.coral, ...bg.slice(0, 8).map((b) => b.id), ...bg.slice(8).map((b) => b.id)],
    [L.auroraCoral, ...bgLinks]
  );
  const pathSg = sg([N.aurora, N.coral, N.seaview, N.addr, N.vtrust, N.dav, N.dav2, N.san],
    [L.auroraCoral, L.coralSeaview, L.seaviewAddr, L.vtrustAddr, L.davVtrust, L.davSan, L.dav2Seaview, L.dav2San]);
  return [
    { delay: 300, ev: { type: "status", agent: "investigator", text: "Opening file on Aurora Maritime Holdings Ltd (BVI)." } },
    { delay: 700, ev: { type: "tool_call", agent: "memory", tool: "recall", args: { tenant: "default", node_ids: [N.aurora, N.coral] }, cypher: CY.recall, params: { node_ids: [N.aurora, N.coral] } } },
    { delay: 900, ev: { type: "recall", agent: "memory", text: "Desk memory: Coral Nominees Ltd was flagged as a chokepoint in case #C-0007 (Seaview Ventures Inc) on 12 Oct 2026.", result: { cases: [{ id: "C-0007", created_at: "2026-10-12T15:42:00Z", subject_name: "Seaview Ventures Inc", verdict: "EDD", rel: "FLAGGED", ref_name: "Coral Nominees Ltd", ref_id: N.coral }] }, highlight: { nodes: [N.coral], links: [] } } },
    { delay: 800, ev: { type: "thought", agent: "investigator", text: "The subject itself has no direct list match. A prior case touched its nominee director, so I'll trace weighted paths to any listed party within 6 hops." } },
    { delay: 600, ev: { type: "tool_call", agent: "investigator", tool: "neighborhood", args: { node_id: N.aurora, hops: 1 }, cypher: "MATCH (n:Node {id: $node_id})-[r]-(m)\nRETURN n, r, m LIMIT $limit", params: { node_id: N.aurora, hops: 1, limit: 150 } } },
    { delay: 700, ev: { type: "tool_result", agent: "investigator", tool: "neighborhood", text: `${neighborhoodSg.nodes.length} nodes in the immediate neighbourhood.`, result: { subgraph: { nodes: neighborhoodSg.nodes.length, links: neighborhoodSg.links.length } }, subgraph: neighborhoodSg, highlight: { nodes: [N.aurora], links: [] } } },
    { delay: 700, ev: { type: "tool_call", agent: "investigator", tool: "sanction_paths", args: { node_id: N.aurora, max_hops: 6, k: 3 }, cypher: CY.paths, params: { node_id: N.aurora, max_hops: 6, k: 3, rel_types: ["OFFICER_OF", "INTERMEDIARY_OF", "REGISTERED_ADDRESS", "SAME_AS", "SIMILAR", "SAME_NAME_AS", "MATCHES"] } } },
    { delay: 1300, ev: { type: "tool_result", agent: "investigator", tool: "sanction_paths", text: "2 possible links to an OpenSanctions-listed party: 6 hops via a shared registered address (match 0.97), 4 hops via a token name match (0.82).", result: { found: true, paths: [path1, path2] }, subgraph: pathSg, highlight: hl(path1) } },
    { delay: 900, ev: { type: "tool_call", agent: "investigator", tool: "shell_cluster", args: { node_id: N.aurora }, cypher: CY.cluster, params: { node_id: N.aurora } } },
    { delay: 800, ev: { type: "tool_result", agent: "investigator", tool: "shell_cluster", text: "Small cluster: 6 entities share Aurora's intermediary; no mass-registration signal (threshold 25).", result: { size: 6, shared_addresses: 1, shared_intermediaries: 1, members_sample: ["Pelican Bay Investments Ltd", "Lantern Holdings Inc"] } } },
    { delay: 700, ev: { type: "tool_call", agent: "investigator", tool: "chokepoints", args: { paths: "[2 paths]" }, cypher: CY.choke, params: { path_node_ids: [...path1.nodes, ...path2.nodes] } } },
    { delay: 800, ev: { type: "tool_result", agent: "investigator", tool: "chokepoints", text: "Coral Nominees Ltd sits on every path found.", result: { chokepoints: [ { id: N.coral, name: "Coral Nominees Ltd", kind: "Officer", paths_through: 2, betweenness: 0.71, pagerank_top_pct: 3.2 }, { id: N.seaview, name: "Seaview Ventures Inc", kind: "Entity", paths_through: 2, betweenness: 0.64 } ] }, highlight: { nodes: [N.coral, N.seaview], links: [] } } },
    { delay: 900, ev: { type: "skeptic", agent: "skeptic", text: "Path 2 relies on a token-only match \"D. Volkov\" -> \"Dmitri Alexandrovich Volkov\" at 0.82. Initials alone are not enough; marking it weakened.", result: { path_index: 1, weakened: true, weak_edges: [{ source: N.dav2, target: N.san, type: "MATCHES", reason: "token match score 0.82 < 0.95" }] }, highlight: hl(path2) } },
    { delay: 900, ev: { type: "skeptic", agent: "skeptic", text: "Path 1 holds: every edge is a registry link (director, registered address, beneficial owner) and the list match is an alias hit at 0.97. Its weakness is length, at 6 hops.", result: { path_index: 0, weakened: false }, highlight: hl(path1) } },
    { delay: 700, ev: { type: "tool_call", agent: "investigator", tool: "counterfactual", args: { node_id: N.aurora, remove_id: N.coral }, cypher: CY.counter, params: { node_id: N.aurora, remove_id: N.coral, max_hops: 6 } } },
    { delay: 900, ev: { type: "tool_result", agent: "investigator", tool: "counterfactual", text: "With Coral Nominees Ltd removed, no path remains within 6 hops. The exposure runs entirely through the nominee.", result: { still_exposed: false, paths: [], remove_id: N.coral }, highlight: { nodes: [N.coral], links: [] } } },
    { delay: 900, ev: { type: "verdict", agent: "gatekeeper", text: "Enhanced due diligence", result: { verdict: "EDD", rule_ids: ["EDD-1"], reasons: [ "EDD-1: a possible link to a listed party exists within 6 hops (best surviving path: 6 hops, match 0.97, no weak edges).", "REJECT-1 not met: best surviving path is longer than 3 hops.", "Cluster signal not met: shell cluster size 6 < 25." ] } } },
    { delay: 1100, ev: { type: "memo", agent: "gatekeeper", text: memoAurora() } },
    { delay: 500, ev: { type: "status", agent: "memory", text: "Saved as case #C-0012 on desk \"default\". Coral Nominees Ltd flagged; D. Volkov token match cleared as weak.", result: { case_id: "C-0012" } } },
    { delay: 300, ev: { type: "done", agent: "gatekeeper", text: "Investigation complete." } },
  ];
}

function memoAurora() {
  return `# Due diligence memo: Aurora Maritime Holdings Ltd

| | |
|---|---|
| Subject | Aurora Maritime Holdings Ltd (\`${N.aurora}\`), British Virgin Islands |
| Verdict | EDD (enhanced due diligence), rule \`EDD-1\` |
| Desk / case | default, C-0012 |

## Summary
No direct list match exists for the subject. The data shows a **possible link** to an OpenSanctions-listed person, *Dmitri Alexandrovich Volkov* (\`${N.san}\`), at 6 hops. The link runs through the subject's nominee director, Coral Nominees Ltd. This is an exposure to review, not a finding of wrongdoing.

## Evidence path
1. Aurora Maritime Holdings Ltd (\`${N.aurora}\`) has nominee director **Coral Nominees Ltd** (\`${N.coral}\`)
2. Coral Nominees Ltd is also director of **Seaview Ventures Inc** (\`${N.seaview}\`)
3. Seaview Ventures Inc shares its registered address (\`${N.addr}\`) with **Volkov Trust Holdings** (\`${N.vtrust}\`)
4. Volkov Trust Holdings lists **Dmitri A. Volkov** (\`${N.dav}\`) as beneficial owner
5. *Dmitri A. Volkov* matches *Dmitri Alexandrovich Volkov* by alias, score 0.97

## Skeptic review
A second, shorter path (4 hops) through shareholder "D. Volkov" relies on a token-only name match at 0.82. It was **weakened** and does not drive the verdict.

## Counterfactual
Removing Coral Nominees Ltd leaves **no path within 6 hops**, so the nominee is the single chokepoint. Desk memory shows the same nominee was flagged in case C-0007 (Seaview Ventures Inc, 12 Oct 2026).

## Recommended next steps
- Request the beneficial-ownership register behind Coral Nominees Ltd.
- Confirm whether Seaview Ventures Inc and Volkov Trust Holdings share more than a registered agent address.

## Queries run
\`\`\`cypher
${CY.paths}
\`\`\`

*Source: ICIJ Offshore Leaks Database & OpenSanctions. Possible links, not findings of wrongdoing.*
`;
}

function vtrustScript(): Step[] {
  const p: PathRec = { hops: 2, weight: 2, match: { score: 0.97, method: "alias" }, sanction: path1.sanction, nodes: [N.vtrust, N.dav, N.san], edges: [L.davVtrust, L.davSan] };
  const s = sg([N.vtrust, N.dav, N.san, N.addr, N.seaview], [L.davVtrust, L.davSan, L.vtrustAddr, L.seaviewAddr]);
  return [
    { delay: 300, ev: { type: "status", agent: "investigator", text: "Opening file on Volkov Trust Holdings (CYP)." } },
    { delay: 600, ev: { type: "tool_call", agent: "memory", tool: "recall", args: { node_ids: [N.vtrust] }, cypher: CY.recall, params: { node_ids: [N.vtrust] } } },
    { delay: 500, ev: { type: "tool_result", agent: "memory", tool: "recall", text: "No prior cases on this desk touch the subject.", result: { cases: [] } } },
    { delay: 600, ev: { type: "tool_call", agent: "investigator", tool: "sanction_paths", args: { node_id: N.vtrust, max_hops: 6, k: 3 }, cypher: CY.paths, params: { node_id: N.vtrust, max_hops: 6, k: 3 } } },
    { delay: 1100, ev: { type: "tool_result", agent: "investigator", tool: "sanction_paths", text: "1 possible link at 2 hops: beneficial owner matches a listed person (0.97).", result: { found: true, paths: [p] }, subgraph: s, highlight: hl(p) } },
    { delay: 800, ev: { type: "skeptic", agent: "skeptic", text: "Both edges are strong; the match is an alias hit at 0.97. No grounds to weaken.", result: { weakened: false }, highlight: hl(p) } },
    { delay: 800, ev: { type: "verdict", agent: "gatekeeper", text: "Reject", result: { verdict: "REJECT", rule_ids: ["REJECT-1"], reasons: ["REJECT-1: path of 2 hops (<= 3) with match score 0.97 (>= 0.95) and no weak edge."] } } },
    { delay: 900, ev: { type: "memo", agent: "gatekeeper", text: `# Due diligence memo: Volkov Trust Holdings\n\n**Verdict:** REJECT, rule \`REJECT-1\`\n\nThe beneficial owner, Dmitri A. Volkov (\`${N.dav}\`), matches the OpenSanctions record *Dmitri Alexandrovich Volkov* (\`${N.san}\`) by alias at 0.97. Path length is 2 hops, and every edge is a registry link.\n\nThis is a possible link based on name matching, not a finding of wrongdoing. Confirm identity with date of birth and nationality before you act.\n\n\`\`\`cypher\n${CY.paths}\n\`\`\`\n` } },
    { delay: 400, ev: { type: "done", agent: "gatekeeper", text: "Investigation complete." } },
  ];
}

function meridianScript(): Step[] {
  const p: PathRec = { hops: 3, weight: 5, match: { score: 0.82, method: "token" }, sanction: path1.sanction, nodes: [N.meridian, N.meridianSim, N.dav2, N.san], edges: [L.meridianSim, L.meridianSimDav, L.dav2San] };
  const s = sg([N.meridian, N.meridianSim, N.dav2, N.san], [L.meridianSim, L.meridianSimDav, L.dav2San]);
  return [
    { delay: 300, ev: { type: "status", agent: "investigator", text: "Opening file on Meridian Star Trading Ltd (SEY)." } },
    { delay: 700, ev: { type: "tool_call", agent: "investigator", tool: "sanction_paths", args: { node_id: N.meridian, max_hops: 6, k: 3 }, cypher: CY.paths, params: { node_id: N.meridian, max_hops: 6, k: 3 } } },
    { delay: 1100, ev: { type: "tool_result", agent: "investigator", tool: "sanction_paths", text: "1 possible link at 3 hops, through a SIMILAR-name edge.", result: { found: true, paths: [p] }, subgraph: s, highlight: hl(p) } },
    { delay: 900, ev: { type: "skeptic", agent: "skeptic", text: "The first hop is a SIMILAR edge between two differently-registered companies, and the list match is token-only (0.82). Weakened: this reads as a naming coincidence until proven otherwise.", result: { weakened: true }, highlight: { nodes: [N.meridian, N.meridianSim], links: [{ source: N.meridian, target: N.meridianSim }] } } },
    { delay: 800, ev: { type: "verdict", agent: "gatekeeper", text: "Enhanced due diligence", result: { verdict: "EDD", rule_ids: ["EDD-2"], reasons: ["EDD-2: REJECT conditions weakened by a weak edge (SIMILAR) and match score 0.82 < 0.95."] } } },
    { delay: 900, ev: { type: "memo", agent: "gatekeeper", text: `# Due diligence memo: Meridian Star Trading Ltd\n\n**Verdict:** EDD, rule \`EDD-2\`\n\nThe only path depends on a SIMILAR-name edge to *Meridian Star Trading Limited* (\`${N.meridianSim}\`) and a token-only name match. The Skeptic weakened it. Ask the counterparty to confirm it is not related to the similarly named entity.\n` } },
    { delay: 400, ev: { type: "done", agent: "gatekeeper", text: "Investigation complete." } },
  ];
}

function cleanScript(id: string): Step[] {
  const n = nodes[id] ?? bg.find((b) => b.id === id) ?? { id, kind: "Entity", name: "Subject", sanctioned: false };
  return [
    { delay: 300, ev: { type: "status", agent: "investigator", text: `Opening file on ${n.name}.` } },
    { delay: 700, ev: { type: "tool_call", agent: "investigator", tool: "sanction_paths", args: { node_id: id, max_hops: 6, k: 3 }, cypher: CY.paths, params: { node_id: id, max_hops: 6, k: 3 } } },
    { delay: 1000, ev: { type: "tool_result", agent: "investigator", tool: "sanction_paths", text: "No path found within 6 hops.", result: { found: false, paths: [] }, subgraph: { nodes: [n], links: [] }, highlight: { nodes: [id], links: [] } } },
    { delay: 700, ev: { type: "tool_call", agent: "investigator", tool: "shell_cluster", args: { node_id: id }, cypher: CY.cluster, params: { node_id: id } } },
    { delay: 700, ev: { type: "tool_result", agent: "investigator", tool: "shell_cluster", text: "Cluster size 1; no shared-address signal.", result: { size: 1, shared_addresses: 0, shared_intermediaries: 0, members_sample: [] } } },
    { delay: 700, ev: { type: "verdict", agent: "gatekeeper", text: "Approve", result: { verdict: "APPROVE", rule_ids: ["APPROVE-1"], reasons: ["APPROVE-1: no path to a listed party within 6 hops, and no cluster signal."] } } },
    { delay: 700, ev: { type: "memo", agent: "gatekeeper", text: `# Due diligence memo: ${n.name}\n\n**Verdict:** APPROVE, rule \`APPROVE-1\`\n\nNo path to an OpenSanctions-listed party was found within 6 hops in this dataset. That means no exposure in this data, not a clean bill of health elsewhere.\n` } },
    { delay: 300, ev: { type: "done", agent: "gatekeeper", text: "Investigation complete." } },
  ];
}

export function mockScript(nodeId: string): Step[] {
  if (nodeId === N.aurora) return auroraScript();
  if (nodeId === N.vtrust) return vtrustScript();
  if (nodeId === N.meridian) return meridianScript();
  return cleanScript(nodeId);
}

export function mockNode(id: string) {
  const n = nodes[id] ?? bg.find((b) => b.id === id);
  if (!n) return { node: { id, kind: "Other", name: id } };
  const extra: Record<string, unknown> = n.kind === "Sanction"
    ? { schema: "Person", aliases: "Dmitri A. Volkov; Dmitriy Volkov", programs: "EU-UKR-2014; OFAC-RUSSIA-EO14024", countries: "ru", datasets: "eu_fsf; us_ofac_sdn" }
    : { name_norm: n.name.toLowerCase(), countries: n.jurisdiction ?? "", source: "Panama Papers (synthetic)", incorporation_date: n.kind === "Entity" ? "14-MAR-2011" : undefined, status: n.kind === "Entity" ? "Active" : undefined, jurisdiction_description: n.jurisdiction };
  return { node: { ...n, ...extra } };
}

export function mockCounterfactual(nodeId: string, removeId: string): CounterfactualResult {
  const params = { node_id: nodeId, remove_id: removeId, max_hops: 6 };
  if (nodeId !== N.aurora) {
    const still = nodeId === N.vtrust ? ![N.dav, N.san].includes(removeId) : nodeId === N.meridian ? ![N.meridianSim, N.dav2, N.san].includes(removeId) : false;
    return { still_exposed: still, paths: [], cypher: CY.counter, params };
  }
  const p1 = path1.nodes.includes(removeId), p2 = path2.nodes.includes(removeId);
  const remaining = [!p1 && path1, !p2 && path2].filter(Boolean) as PathRec[];
  return { still_exposed: remaining.length > 0, paths: remaining, cypher: CY.counter, params };
}

export const mockCases: CaseRecord[] = [
  { id: "C-0007", created_at: "2026-10-12T15:42:00Z", subject_id: N.seaview, subject_name: "Seaview Ventures Inc", verdict: "EDD", summary: "Shares registered address with Volkov Trust Holdings; Coral Nominees Ltd flagged as chokepoint.",
    memo: `# Due diligence memo: Seaview Ventures Inc\n\n**Verdict:** EDD, rule \`EDD-1\`\n\nSeaview Ventures Inc (\`${N.seaview}\`) shares its registered address (\`${N.addr}\`) with Volkov Trust Holdings (\`${N.vtrust}\`), whose beneficial owner matches the OpenSanctions record *Dmitri Alexandrovich Volkov* (alias, 0.97). Path length: 4 hops.\n\n## Chokepoint\nDirector **Coral Nominees Ltd** (\`${N.coral}\`) also directs other BVI entities. Flagged for future cases on this desk.\n\n*Possible link, not a finding of wrongdoing.*\n` },
  { id: "C-0005", created_at: "2026-10-10T09:15:00Z", subject_id: N.halcyon, subject_name: "Halcyon Logistics Ltd", verdict: "APPROVE", summary: "No path to a listed party within 6 hops." },
  { id: "C-0003", created_at: "2026-10-08T11:03:00Z", subject_id: N.vtrust, subject_name: "Volkov Trust Holdings", verdict: "REJECT", summary: "Beneficial owner matches listed person (alias, 0.97) at 2 hops." },
];
