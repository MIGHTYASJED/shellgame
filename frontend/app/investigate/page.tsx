"use client";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";
import { SearchBox } from "@/components/SearchBox";
import { Timeline } from "@/components/Timeline";
import { EvidenceGraph, GraphLegend } from "@/components/EvidenceGraph";
import { VerdictPanel } from "@/components/VerdictPanel";
import { NodeDrawer } from "@/components/NodeDrawer";
import { useInvestigation } from "@/lib/investigation";
import { useDesk } from "@/lib/useDesk";
import type { CounterfactualResult, SgNode } from "@/lib/types";

const TABS = [["log", "Agent log"], ["graph", "Graph"], ["finding", "Finding"]] as const;
type Tab = (typeof TABS)[number][0];

const href = (id: string, desk: string, name: string) =>
  `/investigate?node_id=${encodeURIComponent(id)}&tenant=${encodeURIComponent(desk)}&name=${encodeURIComponent(name)}`;

function Investigation() {
  const sp = useSearchParams();
  const router = useRouter();
  const nodeId = sp.get("node_id");
  const [desk, setDeskRaw] = useDesk();
  const tenant = sp.get("tenant") || desk;
  const { state: st, restart, stop, focus } = useInvestigation(nodeId, tenant);
  const [selected, setSelected] = useState<SgNode | null>(null);
  const [cuts, setCuts] = useState<Record<string, CounterfactualResult>>({});
  const [tab, setTab] = useState<Tab>("graph");

  useEffect(() => { setCuts({}); setSelected(null); }, [nodeId, tenant]);

  const subjectName = (nodeId && st.nodes.get(nodeId)?.name) || sp.get("name") || nodeId || "";
  const severed = useMemo(() => new Set(Object.keys(cuts)), [cuts]);
  const chokeIds = useMemo(() => new Set(st.chokepoints.map((c) => c.id)), [st.chokepoints]);
  const running = st.status === "running";

  if (!nodeId) {
    return (
      <>
        <Nav desk={desk} setDesk={setDeskRaw} />
        <main className="flex-1 grid place-items-center px-4">
          <div className="w-full max-w-[640px] text-center">
            <p className="eyebrow mb-4">New investigation</p>
            <SearchBox autoFocus onPick={(c) => router.push(href(c.id, desk, c.name))} />
          </div>
        </main>
        <Footer />
      </>
    );
  }

  const setDesk = (d: string) => { setDeskRaw(d); router.replace(href(nodeId, d, subjectName)); };
  const pickNode = (id: string) => { const n = st.nodes.get(id); if (n) { setSelected(n); setTab("graph"); } };
  const col = (t: Tab) => `${tab === t ? "flex" : "hidden"} lg:flex flex-col min-h-0`;

  return (
    <div className="h-dvh flex flex-col">
      <Nav desk={tenant} setDesk={setDesk} wide>
        <div className="hidden lg:flex items-baseline gap-3 min-w-0">
          <span className="text-rule-2">/</span>
          <span className="font-serif text-[17px] truncate">{subjectName}</span>
          <span className="num text-[11px] text-ink-3">{nodeId}</span>
        </div>
      </Nav>

      <div className="lg:hidden px-4 pt-3 pb-1">
        <p className="font-serif text-[20px] leading-tight truncate">{subjectName}</p>
        <div role="tablist" className="mt-3 grid grid-cols-3 p-1 rounded-full bg-paper-2 shadow-[inset_0_0_0_1px_var(--rule)] text-[13px]">
          {TABS.map(([t, label]) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
              className={`py-1.5 rounded-full transition-colors ${tab === t ? "bg-surface shadow-ring text-ink font-medium" : "text-ink-2"}`}>
              {t === "finding" && st.verdict ? st.verdict.verdict : label}
            </button>
          ))}
        </div>
      </div>

      <main className="flex-1 min-h-0 grid grid-rows-[minmax(0,1fr)] grid-cols-[minmax(0,1fr)] lg:grid-cols-[minmax(320px,380px)_minmax(0,1fr)_minmax(380px,440px)]">
        <section className={`${col("log")} lg:border-r border-rule`}>
          <Timeline events={st.events} running={running} onFocus={(h) => { focus(h); setTab("graph"); }} />
          {st.status === "error" && <p className="px-5 py-3 border-t border-rule text-[13px] text-oxblood">{st.error}</p>}
        </section>

        <section className={`${col("graph")} p-3`}>
          <div className="card flex-1 min-h-[420px] flex flex-col overflow-hidden">
            <div className="h-12 shrink-0 px-4 flex items-center gap-3 border-b border-rule">
              <h2 className="eyebrow">Evidence graph</h2>
              <span className="num text-[11.5px] text-ink-3 hidden sm:inline">{st.nodes.size} nodes · {st.links.size} links</span>
              <span className="ml-auto" />
              {running
                ? <button onClick={stop} className="btn py-1 px-3 text-[12px]">Stop</button>
                : <button onClick={() => { setCuts({}); setSelected(null); restart(); }} className="btn py-1 px-3 text-[12px]">↻ Replay</button>}
            </div>
            <div className="relative flex-1 min-h-0">
              <EvidenceGraph
                nodes={st.nodes} links={st.links} graphVersion={st.graphVersion}
                highlight={st.highlight} highlightVersion={st.highlightVersion}
                subjectId={nodeId} weakLinks={st.weakLinks} severed={severed} chokepointIds={chokeIds}
                selectedId={selected?.id ?? null} onNodeClick={(n) => setSelected(st.nodes.get(n.id) ?? n)}
              />
              {st.nodes.size === 0 && (
                <p className="absolute inset-0 grid place-items-center pointer-events-none text-[13px] text-ink-3">
                  {st.status === "error" ? "Nothing to draw." : "Waiting for the first query…"}
                </p>
              )}
              {Object.keys(cuts).length > 0 && (
                <ul className="absolute left-3 top-3 z-10 space-y-1.5 max-w-[60%]">
                  {Object.entries(cuts).map(([id, r]) => (
                    <li key={id} className="rise card shadow-lift pl-3 pr-2 py-1.5 text-[12.5px] flex items-center gap-2.5">
                      <span className="text-ink-3">Cut</span>
                      <span className="truncate font-medium">{st.nodes.get(id)?.name ?? id}</span>
                      <span className="pill shrink-0" data-tone={r.still_exposed ? "brass" : "green"}>{r.still_exposed ? "still exposed" : "link broken"}</span>
                      <button onClick={() => setCuts((c) => { const n = { ...c }; delete n[id]; return n; })} className="link text-[12px]">Restore</button>
                    </li>
                  ))}
                </ul>
              )}
              {selected && (
                <NodeDrawer node={selected} subjectId={nodeId} onClose={() => setSelected(null)}
                  cutResult={cuts[selected.id]} onCut={(id, r) => setCuts((c) => ({ ...c, [id]: r }))} />
              )}
            </div>
            <div className="shrink-0 px-4 py-2.5 border-t border-rule"><GraphLegend /></div>
          </div>
        </section>

        <section className={`${col("finding")} lg:border-l border-rule`}>
          <VerdictPanel st={st} subjectName={subjectName} desk={tenant} onPickNode={pickNode} />
        </section>
      </main>
      <div className="hidden lg:block"><Footer wide /></div>
    </div>
  );
}

export default function Page() {
  return <Suspense fallback={null}><Investigation /></Suspense>;
}
