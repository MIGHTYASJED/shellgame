"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { tenants as fetchTenants, MOCK } from "@/lib/api";

export function Nav({ desk, setDesk, wide = false, children }: { desk: string; setDesk: (d: string) => void; wide?: boolean; children?: React.ReactNode }) {
  const q = `?tenant=${encodeURIComponent(desk)}`;
  return (
    <header className="nav sticky top-0 z-40 shrink-0">
      <div className={`${wide ? "" : "max-w-[1220px]"} mx-auto h-[52px] px-4 sm:px-6 flex items-center gap-6`}>
        <Link href={`/${q}`} className="flex items-center gap-2.5 shrink-0" aria-label="Shell Game home">
          <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden>
            <circle cx="12" cy="12" r="11" fill="none" stroke="#1F4A37" strokeWidth="1" />
            <circle cx="12" cy="12" r="8.6" fill="none" stroke="#A88A4E" strokeWidth=".6" strokeDasharray="1 1.4" />
            <text x="12" y="16.3" textAnchor="middle" fontFamily="Newsreader Variable,Georgia,serif" fontStyle="italic" fontSize="12" fill="#1F4A37">S</text>
          </svg>
          <b className="font-serif font-medium text-[20px] leading-none tracking-[-.01em]">Shell Game</b>
        </Link>
        <nav className="hidden md:flex gap-5 text-[13px] text-ink-2">
          <Link href={`/${q}`} className="hover:text-ink transition-colors">Investigate</Link>
          <Link href={`/cases${q}`} className="hover:text-ink transition-colors">Case files</Link>
        </nav>
        <div className="flex-1 min-w-0">{children}</div>
        {MOCK && <span className="hidden sm:inline pill" data-tone="brass">Demo data</span>}
        <Link href={`/cases${q}`} className="md:hidden text-[13px] text-ink-2">Cases</Link>
        <DeskSwitcher desk={desk} setDesk={setDesk} />
      </div>
    </header>
  );
}

function DeskSwitcher({ desk, setDesk }: { desk: string; setDesk: (d: string) => void }) {
  const [open, setOpen] = useState(false);
  const [list, setList] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    fetchTenants().then(setList).catch(() => setList([]));
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close); };
  }, [open]);

  const choose = (d: string) => { setDesk(d); setOpen(false); setDraft(""); };
  const all = Array.from(new Set(["default", ...list, desk]));

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="listbox"
        className="flex items-center gap-2 rounded-full border border-rule-2 bg-surface/70 hover:border-ink-3 pl-3 pr-2.5 py-1 text-[12.5px] transition-colors">
        <span className="text-ink-3">Desk</span>
        <span className="font-mono text-ink">{desk}</span>
        <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden className="text-ink-3"><path d="M2 3.5 5 6.5 8 3.5" fill="none" stroke="currentColor" strokeWidth="1.3" /></svg>
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-72 card shadow-lift p-1.5 rise">
          <p className="eyebrow px-2.5 pt-2 pb-1">Desks</p>
          <p className="px-2.5 pb-2 text-[12px] text-ink-3 leading-snug">Each desk keeps its own case memory and cites it as precedent.</p>
          <ul role="listbox" className="max-h-56 overflow-auto scroll-thin">
            {all.map((t) => (
              <li key={t} role="option" aria-selected={t === desk}>
                <button onClick={() => choose(t)}
                  className={`w-full flex items-center gap-2 text-left px-2.5 py-1.5 rounded-md font-mono text-[13px] hover:bg-ink/[.045] ${t === desk ? "text-green" : "text-ink"}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${t === desk ? "bg-green" : "bg-transparent"}`} />{t}
                </button>
              </li>
            ))}
          </ul>
          <form className="flex gap-1.5 mt-1.5 pt-1.5 border-t border-rule" onSubmit={(e) => { e.preventDefault(); if (draft.trim()) choose(draft); }}>
            <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="new-desk" aria-label="New desk name"
              className="flex-1 min-w-0 bg-transparent px-2.5 py-1.5 font-mono text-[13px] outline-none placeholder:text-ink-3" />
            <button className="btn">Open</button>
          </form>
        </div>
      )}
    </div>
  );
}
