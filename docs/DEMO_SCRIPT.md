# Demo video script (target: 2:30)

Record at 1920×1080 with the browser at 100% zoom. Open with the "aha" moment, then explain how it works.

| Time | Screen | Say |
|---|---|---|
| 0:00 | Landing page, cursor in search | "Before you sign with a supplier, you need to know who is really behind it. That answer is almost never in one record. It's a path." |
| 0:10 | Click the **Creatum Business Group** chip | "Creatum Business Group is a BVI company. On paper it looks completely ordinary." |
| 0:15 | Agent log streams, graph grows, path lights up | "Three agents are working over FalkorDB. The Investigator calls fixed graph tools. Here it finds that Creatum's nominee shareholder, Bridgewater Second Nominees, also holds shares in Sealfate Limited. Sealfate's shareholder matches a sanctioned person exactly. That's three hops through the ICIJ Offshore Leaks data." |
| 0:40 | Click **Show Cypher** on the sanction_paths card | "Every step carries the exact Cypher and parameters that ran. The language model never writes Cypher. It only picks tools." |
| 0:50 | Skeptic cards | "The Skeptic attacks the evidence: similar-name edges, weak name matches. A weakened path can't drive the verdict." |
| 1:00 | Verdict seal: REJECT, rule R1 | "The Gatekeeper is deterministic. A short, strong path with an exact name match is REJECT, rule R1. The memo cites every node id and query." |
| 1:10 | Chokepoint card, PageRank top X% | "This is the chokepoint. FalkorDB's PageRank shows where this node sits in the whole 240,000-node leak graph." |
| 1:20 | Click a node, then **Cut this node** | "And the counterfactual: cut a node, and the paths are recomputed without it. Does the exposure survive?" |
| 1:35 | Back to the landing page, click **Bison Management** | "Now a clean company. No path within six hops. In this dataset, that's a provable negative." Verdict: APPROVE. |
| 1:50 | Click **Iris Rose Holdings**, then the EDD verdict | "Iris Rose has a strong path, but it's six hops long, so it gets enhanced due diligence instead of a rejection." |
| 2:00 | Re-run Creatum and point at the Desk memory card | "Memory. Every case is written to this desk's own FalkorDB graph. Investigate anything that touches those nodes again and the precedent comes back. Switch desks and that memory isn't there. One isolated graph per tenant." |
| 2:15 | Show the Case files page | "Case files persist across sessions." |
| 2:20 | Show the README graph model | "Real data: ICIJ Offshore Leaks and OpenSanctions, 242k nodes, half a million edges, paths in milliseconds. This is Shell Game." |

Tips:
- Run each subject once before recording, so the Creatum re-run shows the precedent.
- Pick a fresh desk name, for example `demo-video`, so earlier test cases don't clutter the Case files page.
- Keep the voice calm. Say "possible link", never "guilty".
