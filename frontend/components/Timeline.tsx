"use client";
import { useEffect, useRef, useState } from "react";
import type { AgentEvent, Highlight } from "@/lib/types";
import { Cypher } from "./Cypher";

const TONE: Record<string, string | undefined> = { investigator: "green", skeptic: "oxblood", memory: "brass" };
const VERB: Record<string, string> = {
  status: "note", thought: "reasoning", tool_call: "ran", tool_result: "found", skeptic: "challenge",
  recall: "recalled", verdict: "verdict", done: "closed", error: "error",
};

const secs = (ts: AgentEvent["ts"]) => (typeof ts === "number" ? ts : ts ? Date.parse(ts) / 1000 : NaN);

function Event({ e, t0, onFocus }: { e: AgentEvent; t0: number; onFocus: (h: Highlight) => void }) {
  const [open, setOpen] = useState(false);
  const hasCy = Array.isArray(e.cypher) ? e.cypher.length > 0 : !!e.cypher;
  const hl = e.highlight?.nodes?.length ? e.highlight : null;
  const dt = secs(e.ts) - t0;
  const agent = e.agent ?? "agent";
  const textCls = e.type === "skeptic" ? "font-serif italic text-[15.5px] text-ink"
    : e.type === "thought" ? "font-serif text-[15.5px] text-ink"
    : e.type === "error" ? "text-oxblood" : "text-ink-2";

  return (
    <li className="rise relative pl-6 pb-5">
      <span className={`absolute left-[3px] top-[6px] w-[9px] h-[9px] rounded-full ring-4 ring-paper ${
        e.type === "tool_call" ? "bg-surface border border-green" : e.type === "skeptic" || e.type === "error" ? "bg-oxblood" : e.type === "verdict" ? "bg-ink" : "bg-rule-2"}`} />
      <div className="flex items-center gap-2 text-[12px]">
        <span className="pill capitalize" data-tone={TONE[agent]}>{agent}</span>
        <span className="text-ink-3">{VERB[e.type] ?? e.type}</span>
        {e.tool && <span className="font-mono text-ink">{e.tool}</span>}
        {dt >= 0 && <span className="num ml-auto text-[11px] text-ink-3">+{dt.toFixed(1)}s</span>}
      </div>
      {e.text && <p className={`mt-1.5 leading-[1.5] text-[13.5px] ${textCls}`}>{e.text}</p>}
      {(hasCy || hl) && (
        <div className="mt-1.5 flex gap-4 text-[12px]">
          {hasCy && <button onClick={() => setOpen(!open)} aria-expanded={open} className="link">{open ? "Hide Cypher" : "Show Cypher"}</button>}
          {hl && <button onClick={() => onFocus(hl)} className="link text-ink-2">Show on graph</button>}
        </div>
      )}
      {open && hasCy && <Cypher code={e.cypher!} params={e.params ?? e.args} />}
    </li>
  );
}

export function Timeline({ events, running, onFocus }: { events: AgentEvent[]; running: boolean; onFocus: (h: Highlight) => void }) {
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  useEffect(() => {
    const el = scroller.current;
    if (stick.current && el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [events.length]);
  const shown = events.filter((e) => e.type !== "memo");
  const t0 = secs(events[0]?.ts);
  const queries = events.filter((e) => e.cypher).length;

  return (
    <div className="flex flex-col min-h-0 h-full">
      <div className="h-12 shrink-0 px-5 flex items-center gap-3 border-b border-rule">
        <h2 className="eyebrow">Agent log</h2>
        <span className="num text-[11.5px] text-ink-3">{shown.length} events · {queries} queries</span>
        {running && <span className="live ml-auto flex gap-1" aria-label="Live"><i className="w-[5px] h-[5px] rounded-full bg-green" /><i className="w-[5px] h-[5px] rounded-full bg-green" /><i className="w-[5px] h-[5px] rounded-full bg-green" /></span>}
      </div>
      <div ref={scroller} onScroll={(ev) => { const el = ev.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; }}
        className="flex-1 min-h-0 overflow-y-auto scroll-thin px-5 pt-5">
        <ol className="relative before:absolute before:left-[7px] before:top-2 before:bottom-6 before:w-px before:bg-rule">
          {shown.map((e, i) => <Event key={i} e={e} t0={t0} onFocus={onFocus} />)}
        </ol>
        {events.length === 0 && running && <p className="text-[13px] text-ink-3">Connecting to the investigation…</p>}
      </div>
    </div>
  );
}
