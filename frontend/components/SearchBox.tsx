"use client";
import { useEffect, useRef, useState } from "react";
import { search } from "@/lib/api";
import type { Candidate } from "@/lib/types";

export function SearchBox({ onPick, autoFocus = false }: { onPick: (c: Candidate) => void; autoFocus?: boolean }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Candidate[]>([]);
  const [active, setActive] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const seq = useRef(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const s = q.trim();
    if (s.length < 2) { setItems([]); setErr(null); setLoading(false); return; }
    const my = ++seq.current;
    setLoading(true);
    const t = setTimeout(() => {
      search(s)
        .then((r) => { if (my === seq.current) { setItems(r); setActive(0); setErr(null); } })
        .catch((e) => { if (my === seq.current) { setItems([]); setErr(`Search is unavailable: ${e.message}`); } })
        .finally(() => { if (my === seq.current) setLoading(false); });
    }, 160);
    return () => clearTimeout(t);
  }, [q]);

  const pick = () => (items[active] ? onPick(items[active]) : input.current?.focus());
  const empty = !loading && !err && q.trim().length >= 2 && items.length === 0;

  return (
    <div className="relative w-full text-left">
      <div className="cmdbox flex items-center gap-3 bg-surface rounded-[14px] p-2 pl-[18px]">
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden className="shrink-0 text-ink-3">
          <circle cx="7" cy="7" r="5.2" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="m11 11 3.5 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
        <input
          ref={input}
          autoFocus={autoFocus}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
            if (e.key === "Enter") pick();
            if (e.key === "Escape") setQ("");
          }}
          placeholder="Company or person"
          aria-label="Search the leak data"
          role="combobox"
          aria-expanded={items.length > 0}
          aria-controls="search-results"
          className="flex-1 min-w-0 bg-transparent outline-none text-[17px] tracking-[-.01em] py-[11px] placeholder:text-ink-3"
        />
        <span className="hidden sm:flex items-center gap-1 text-[12px] text-ink-3 shrink-0">
          {loading ? "Searching…" : <><kbd>↑</kbd><kbd>↓</kbd><kbd>↵</kbd></>}
        </span>
        <button onClick={pick} className="btn-primary btn rounded-[10px] px-[18px] py-[11px] text-[14px]">Investigate</button>
      </div>

      {items.length > 0 && (
        <ul id="search-results" role="listbox" className="absolute inset-x-0 top-[calc(100%+8px)] z-30 card shadow-lift p-1.5 max-h-[360px] overflow-auto scroll-thin rise">
          <li className="eyebrow px-2.5 pt-2 pb-1.5" aria-hidden>Matches in the leak data</li>
          {items.map((c, i) => (
            <li key={c.id} role="option" aria-selected={i === active}>
              <button onMouseEnter={() => setActive(i)} onClick={() => onPick(c)}
                className={`w-full flex items-center gap-3 text-left px-2.5 py-2 rounded-lg ${i === active ? "bg-ink/[.045]" : ""}`}>
                <span className="w-[100px] shrink-0"><span className="pill" data-tone={c.kind === "Sanction" ? "oxblood" : c.kind === "Entity" ? "green" : undefined}>{c.kind}</span></span>
                <span className="flex-1 min-w-0 truncate text-[14.5px]">{c.name}</span>
                {c.jurisdiction && <span className="text-[12px] text-ink-3 shrink-0">{c.jurisdiction}</span>}
                <span className="font-mono text-[11.5px] text-ink-3 shrink-0 hidden sm:inline">{c.id}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {err && <p className="mt-3 text-[13px] text-oxblood">{err}</p>}
      {empty && <p className="mt-3 text-[13px] text-ink-2">No match for “{q.trim()}” in the offshore leak records. Shell Game searches companies, officers and intermediaries that appear in the ICIJ Offshore Leaks data, so most ordinary onshore companies won’t be listed. Try a shorter name, drop the suffix (Ltd, Inc), or pick an example below.</p>}
    </div>
  );
}
