"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";
import { Seal } from "@/components/Seal";
import { SearchBox } from "@/components/SearchBox";
import { MOCK, search, stats as fetchStats } from "@/lib/api";
import { useDesk } from "@/lib/useDesk";

// Demo subjects as [name, ICIJ node id]. Real mode: two REJECT, one EDD, one APPROVE. Mock mode looks names up.
const EXAMPLES: [string, string?][] = MOCK
  ? [["Aurora Maritime Holdings Ltd"], ["Meridian Star Trading Ltd"], ["Volkov Trust Holdings"], ["Halcyon Logistics Ltd"]]
  : [["Creatum Business Group", "10150253"], ["USM Finance Limited", "10161731"], ["Iris Rose Holdings Corp", "20141145"], ["Bison Management Limited", "20126388"]];

const AGENTS = [
  ["Investigator", "Traces officers, nominees and shared addresses toward listed parties using fixed, parameterised Cypher tools. Every query is on the record."],
  ["Skeptic", "Attacks the weakest link: similar-name edges, token-only name matches. A weakened path never drives the verdict."],
  ["Gatekeeper", "Applies a deterministic rule set, writes the memo, and files the case to desk memory so later work can cite it."],
];

const RULES = [
  ["APPROVE", "green", "No path to a listed party within 6 hops, and no cluster signal."],
  ["EDD", "brass", "A possible link within 6 hops, a weakened short path, or a 25+ entity shell cluster."],
  ["REJECT", "oxblood", "A path of 3 hops or fewer, match score ≥ 0.95, with no weak edge."],
];

// Tolerates the shapes /api/stats may return.
function counts(s: any): Record<string, number> {
  const out: Record<string, number> = {};
  for (const o of [s?.labels ?? s?.nodes ?? s?.by_label, s?.relationships ?? s?.rels ?? s?.by_rel_type, s])
    if (o && typeof o === "object") for (const [k, v] of Object.entries(o)) if (typeof v === "number" && !(k in out)) out[k] = v;
  return out;
}

export default function Home() {
  const router = useRouter();
  const [desk, setDesk] = useDesk();
  const [st, setSt] = useState<Record<string, number> | null>(null);

  useEffect(() => { fetchStats().then((s) => setSt(counts(s))).catch(() => setSt({})); }, []);

  const go = (id: string, name: string) =>
    router.push(`/investigate?node_id=${encodeURIComponent(id)}&tenant=${encodeURIComponent(desk)}&name=${encodeURIComponent(name)}`);
  const tryName = (name: string) => search(name).then((r) => r[0] && go(r[0].id, r[0].name)).catch(() => {});

  const statRow: [string, number | undefined][] = [
    ["entities", st?.Entity], ["officers", st?.Officer], ["addresses", st?.Address], ["listed parties", st?.Sanction], ["name matches", st?.MATCHES],
  ];

  return (
    <>
      <Nav desk={desk} setDesk={setDesk} />
      <main className="flex-1">
        <section className="hero relative overflow-hidden border-b border-rule pt-20 pb-16 sm:pt-28 sm:pb-24">
          <Seal className="absolute opacity-70 left-1/2 top-[62%] w-[min(760px,130vw)] -translate-x-1/2 -translate-y-1/2" />
          <div className="relative z-10 max-w-[1220px] mx-auto px-4 sm:px-6 flex flex-col items-center text-center">
            <p className="eyebrow rise">Graph Hacks · FalkorDB</p>
            <h1 className="rise mt-4 max-w-[15ch] font-serif font-light text-[clamp(40px,6.4vw,72px)] leading-[1.02] tracking-[-.022em]">
              Know who you’re <em className="italic text-green">really</em> doing business with.
            </h1>
            <p className="rise mt-5 mb-9 max-w-[56ch] text-[16px] text-ink-2">
              Name a counterparty. Three agents trace offshore officers, nominees and shared addresses toward sanctioned parties,
              argue over the weakest link, and return a verdict with the graph path as proof.
            </p>
            <div className="w-full max-w-[720px]"><SearchBox autoFocus onPick={(c) => go(c.id, c.name)} /></div>
            <div className="mt-5 flex flex-wrap justify-center items-center gap-2 max-w-[760px]">
              <span className="text-[12.5px] text-ink-3 mr-1">Try</span>
              {EXAMPLES.map(([n, id]) => <button key={n} className="chip" onClick={() => (id ? go(id, n) : tryName(n))}>{n}</button>)}
            </div>
            <p className="mt-10 flex flex-wrap justify-center gap-x-6 gap-y-2 text-[12.5px] text-ink-3">
              {st && Object.keys(st).length === 0 && "Graph stats unavailable. Is the backend running?"}
              {statRow.filter(([, n]) => n !== undefined).map(([k, n]) => (
                <span key={k}><b className="num text-ink font-medium">{n!.toLocaleString()}</b> {k}</span>
              ))}
            </p>
          </div>
        </section>

        <section className="bg-paper-2 border-b border-rule py-16 sm:py-24">
          <div className="max-w-[1220px] mx-auto px-4 sm:px-6">
            <div className="grid md:grid-cols-2 gap-6 md:gap-12 items-end mb-10">
              <div>
                <p className="eyebrow">How a case is built</p>
                <h2 className="mt-2.5 font-serif font-light text-[clamp(30px,4.2vw,46px)] leading-[1.06] tracking-[-.02em]">
                  Three agents. <em className="italic text-green">One</em> graph. Every step shown.
                </h2>
              </div>
              <p className="text-[15px] text-ink-2 max-w-[52ch]">
                The language model never writes Cypher. It chooses among human-written graph tools that run on FalkorDB,
                and each result carries the exact query and parameters behind it. Desk <span className="font-mono text-ink">{desk}</span> remembers
                every case and recalls it as precedent.
              </p>
            </div>
            <ol className="grid md:grid-cols-3 gap-4">
              {AGENTS.map(([name, body], i) => (
                <li key={name} className="card p-6">
                  <span className="num text-[12px] text-oxblood">0{i + 1}</span>
                  <h3 className="mt-2 font-serif text-[22px] leading-tight tracking-[-.01em]">{name}</h3>
                  <p className="mt-2 text-[13.5px] text-ink-2">{body}</p>
                </li>
              ))}
            </ol>
            <ul className="mt-10 grid md:grid-cols-3 gap-x-8 gap-y-4 pt-6 border-t border-rule-2">
              {RULES.map(([v, tone, body]) => (
                <li key={v} className="flex flex-col gap-2 items-start">
                  <span className="pill num" data-tone={tone}>{v}</span>
                  <p className="text-[13px] text-ink-2">{body}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
