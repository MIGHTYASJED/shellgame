"use client";
import type { InvState } from "@/lib/investigation";
import { Memo } from "./Memo";

const V: Record<string, { word: string; title: string; sub: string; tone: string; ink: string }> = {
  APPROVE: { word: "Approve", title: "No exposure found", sub: "No path to a listed party in this data.", tone: "green", ink: "#1F4A37" },
  EDD: { word: "EDD", title: "Enhanced due diligence", sub: "A possible link worth reviewing before you proceed.", tone: "brass", ink: "#8A6D33" },
  REJECT: { word: "Reject", title: "Close possible link", sub: "A short, strong path to a listed party.", tone: "oxblood", ink: "#7B2531" },
};

const fmtDate = (s?: string) => {
  const d = s ? new Date(s) : null;
  return d && !isNaN(+d) ? d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : s ?? "";
};

/** An embossed, engraved seal: subtle, paper-like, not a rubber stamp. */
function VerdictSeal({ word, ink, ring }: { word: string; ink: string; ring: string }) {
  return (
    <svg viewBox="0 0 120 120" className="seal-in w-[104px] h-[104px] shrink-0" role="img" aria-label={`Verdict: ${word}`}>
      <defs>
        <path id="seal-arc" d="M60 60 m-44 0 a44 44 0 1 1 88 0 a44 44 0 1 1 -88 0" />
        <filter id="emboss" x="-10%" y="-10%" width="120%" height="120%" colorInterpolationFilters="sRGB">
          <feGaussianBlur in="SourceAlpha" stdDeviation="1.1" result="bump" />
          <feSpecularLighting in="bump" surfaceScale="2.4" specularConstant=".9" specularExponent="22" lightingColor="#FFFFFF" result="spec"><feDistantLight azimuth="225" elevation="48" /></feSpecularLighting>
          <feComposite in="spec" in2="SourceAlpha" operator="in" result="gloss" />
          <feOffset in="bump" dx="1.1" dy="1.5" result="drop" />
          <feComposite in="drop" in2="SourceAlpha" operator="out" result="rim" />
          <feColorMatrix in="rim" values="0 0 0 0 .08  0 0 0 0 .2  0 0 0 0 .14  0 0 0 .32 0" result="shade" />
          <feComposite in="gloss" in2="SourceGraphic" operator="arithmetic" k2=".5" k3="1" result="lit" />
          <feMerge><feMergeNode in="shade" /><feMergeNode in="lit" /></feMerge>
        </filter>
      </defs>
      <g filter="url(#emboss)">
        <circle cx="60" cy="60" r="57" fill="#FFFFFF" stroke={ink} strokeOpacity=".55" strokeWidth="1" />
        <circle cx="60" cy="60" r="52.5" fill="none" stroke="#A88A4E" strokeWidth=".7" strokeDasharray="1 1.6" />
        <circle cx="60" cy="60" r="35" fill="none" stroke={ink} strokeOpacity=".35" strokeWidth=".7" />
        <text fontFamily="Geist Mono Variable,monospace" fontSize="7.2" letterSpacing="2.1" fill={ink} fillOpacity=".75">
          <textPath href="#seal-arc">{ring}</textPath>
        </text>
        <text x="60" y="66" textAnchor="middle" fontFamily="Newsreader Variable,Georgia,serif" fontStyle="italic" fontSize={word.length > 4 ? 19 : 23} fill={ink}>{word}</text>
      </g>
    </svg>
  );
}

export function VerdictPanel({ st, subjectName, desk, onPickNode }: { st: InvState; subjectName: string; desk: string; onPickNode: (id: string) => void }) {
  const v = st.verdict ? V[st.verdict.verdict] ?? { word: st.verdict.verdict, title: st.verdict.verdict, sub: "", tone: "", ink: "#15201B" } : null;
  const nodeName = (id?: string) => (id ? st.nodes.get(id)?.name ?? id : "");
  const choke = st.chokepoints[0];
  const slug = subjectName.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 40) || "subject";

  return (
    <div className="flex flex-col min-h-0 h-full">
      <div className="h-12 shrink-0 px-5 flex items-center gap-3 border-b border-rule">
        <h2 className="eyebrow">Finding</h2>
        {st.caseId && <span className="num ml-auto text-[11.5px] text-ink-3">Case {st.caseId}</span>}
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto scroll-thin p-5 space-y-5">
        {!v && (
          <div className="rounded-xl border border-dashed border-rule-2 px-5 py-8 text-center text-[13px] text-ink-3">
            {st.status === "error" ? "No verdict: the run stopped early." : "Verdict pending. The Gatekeeper rules after the Skeptic finishes."}
            {st.noPath && <p className="mt-2 text-green">No path to a listed party within the hop limit. That is a result, not a gap.</p>}
          </div>
        )}

        {v && st.verdict && (
          <section className="card p-5 rise">
            <div className="flex items-center gap-5">
              <VerdictSeal word={v.word} ink={v.ink} ring={`SHELL GAME · DESK ${desk.toUpperCase()} · ${st.verdict.rule_ids.join(" ") || "VERDICT"} · `} />
              <div className="min-w-0">
                <p className="eyebrow">Verdict</p>
                <h3 className="mt-1 font-serif font-light text-[26px] leading-[1.1] tracking-[-.015em]">{v.title}</h3>
                <p className="mt-1 text-[13px] text-ink-2">{v.sub}</p>
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {st.verdict.rule_ids.map((r) => <span key={r} className="pill num" data-tone={v.tone}>{r}</span>)}
                </div>
              </div>
            </div>
            {st.verdict.reasons.length > 0 && (
              <ul className="mt-5 pt-4 border-t border-rule space-y-2">
                {st.verdict.reasons.map((r, i) => <li key={i} className="text-[13px] leading-[1.5] text-ink-2 pl-3 border-l-2 border-rule">{r}</li>)}
              </ul>
            )}
          </section>
        )}

        {st.recall.length > 0 && (
          <section className="rounded-xl bg-brass-wash px-5 py-4 shadow-[inset_0_0_0_1px_rgba(168,138,78,.25)]">
            <h3 className="eyebrow text-[#8A6D33]">Desk memory · precedent</h3>
            {st.recall.map((r, i) => (
              <div key={i} className="mt-2 space-y-1.5">
                {r.text && <p className="font-serif text-[15px] leading-[1.5]">{r.text}</p>}
                {r.cases.slice(0, 4).map((c: any, j: number) => (
                  <p key={j} className="text-[12px] text-ink-2">
                    <span className="num text-ink">#{c.id ?? c.case_id}</span> {c.subject_name}
                    {c.verdict ? ` · ${c.verdict}` : ""}{c.created_at ? ` · ${fmtDate(c.created_at)}` : ""}
                    {c.rel ? ` · ${String(c.rel).toLowerCase()}${c.ref_name ? `: ${c.ref_name}` : ""}` : ""}
                  </p>
                ))}
              </div>
            ))}
          </section>
        )}

        {choke && (
          <section className="card p-5">
            <h3 className="eyebrow">Chokepoint</h3>
            <button onClick={() => onPickNode(choke.id)} className="mt-1.5 text-left group">
              <span className="font-serif text-[22px] leading-tight tracking-[-.01em] group-hover:text-green transition-colors">{choke.name}</span>
              <span className="block mt-1 text-[12.5px] text-ink-3">
                {choke.kind} · on {choke.paths_through} of the paths found
                {typeof choke.pagerank_top_pct === "number" ? <> · PageRank top <span className="num">{choke.pagerank_top_pct}%</span> of the leak graph</> : null}
              </span>
            </button>
            {st.agentCf && (
              <p className="mt-3 flex items-start gap-2 text-[13px] text-ink-2">
                <span className="pill shrink-0" data-tone={st.agentCf.still_exposed ? "brass" : "green"}>{st.agentCf.still_exposed ? "Still exposed" : "Link breaks"}</span>
                <span>{st.agentCf.still_exposed
                  ? `Cutting ${nodeName(st.agentCf.remove_id)} leaves other paths.`
                  : `Cut ${nodeName(st.agentCf.remove_id) || "it"} and no path remains.`}</span>
              </p>
            )}
            {st.chokepoints.length > 1 && (
              <p className="mt-3 text-[12px] text-ink-3">Also on the path: {st.chokepoints.slice(1, 4).map((c) => c.name).join(", ")}</p>
            )}
            <p className="mt-3 pt-3 border-t border-rule text-[12px] text-ink-3">Select any node on the graph to test cutting it yourself.</p>
          </section>
        )}

        {st.memo && <Memo md={st.memo} filename={`dd-memo-${slug}.md`} />}
      </div>
    </div>
  );
}
