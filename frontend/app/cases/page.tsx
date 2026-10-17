"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";
import { Memo } from "@/components/Memo";
import { cases as fetchCases } from "@/lib/api";
import { useDesk } from "@/lib/useDesk";
import type { CaseRecord } from "@/lib/types";

const TONE: Record<string, string> = { APPROVE: "green", EDD: "brass", REJECT: "oxblood" };

function fmt(s?: string) {
  const d = s ? new Date(s) : null;
  if (!d || isNaN(+d)) return s ?? "";
  return d.toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", hour12: true });
}

export default function Cases() {
  const [desk, setDesk] = useDesk();
  const [rows, setRows] = useState<CaseRecord[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<CaseRecord | null>(null);

  useEffect(() => {
    setRows(null); setErr(null); setSel(null);
    fetchCases(desk).then((r) => { setRows(r); setSel(r[0] ?? null); }).catch((e) => setErr(e.message));
  }, [desk]);

  return (
    <>
      <Nav desk={desk} setDesk={setDesk} />
      <main className="flex-1 max-w-[1220px] w-full mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="grid md:grid-cols-2 gap-4 md:gap-12 items-end pb-6 border-b border-rule">
          <div>
            <p className="eyebrow">Desk memory · {desk}</p>
            <h1 className="mt-2.5 font-serif font-light text-[clamp(34px,4.6vw,52px)] leading-[1.04] tracking-[-.02em]">Case <em className="italic text-green">files</em></h1>
          </div>
          <p className="text-[14.5px] text-ink-2 max-w-[54ch]">
            Every investigation on this desk is filed here. Later investigations recall these as precedent when they touch the same people, companies or addresses.
          </p>
        </div>

        {err && <p className="mt-6 text-[14px] text-oxblood">Could not load cases: {err}</p>}
        {!rows && !err && <p className="mt-8 text-ink-3">Loading cases…</p>}
        {rows?.length === 0 && (
          <div className="mt-10 card p-8 max-w-xl">
            <p className="font-serif text-[22px]">No cases on this desk yet.</p>
            <p className="mt-1 text-[14px] text-ink-2">Run an investigation and it is filed here automatically.</p>
            <Link href={`/?tenant=${encodeURIComponent(desk)}`} className="btn btn-primary mt-5">Start an investigation</Link>
          </div>
        )}

        {rows && rows.length > 0 && (
          <div className="mt-8 grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] gap-8 items-start">
            <ul className="card p-1.5">
              {rows.map((c) => (
                <li key={c.id}>
                  <button onClick={() => setSel(c)} aria-current={sel?.id === c.id}
                    className={`w-full text-left rounded-lg px-4 py-3.5 grid grid-cols-[72px_minmax(0,1fr)_auto] gap-3 items-baseline transition-colors ${sel?.id === c.id ? "bg-green-wash" : "hover:bg-ink/[.03]"}`}>
                    <span className="num text-[12px] text-ink-3">{c.id}</span>
                    <span className="min-w-0">
                      <span className="block font-serif text-[18px] leading-snug truncate">{c.subject_name ?? c.subject_id}</span>
                      <span className="block text-[12.5px] text-ink-2 mt-0.5 line-clamp-2">{c.summary}</span>
                      <span className="block text-[11.5px] text-ink-3 mt-1">{fmt(c.created_at)}</span>
                    </span>
                    {c.verdict && <span className="pill num" data-tone={TONE[c.verdict]}>{c.verdict}</span>}
                  </button>
                </li>
              ))}
            </ul>
            {sel && (
              <div className="min-w-0 lg:sticky lg:top-[76px]">
                <div className="flex items-baseline gap-3 mb-4">
                  <h2 className="font-serif text-[28px] leading-tight tracking-[-.012em]">{sel.subject_name}</h2>
                  {sel.subject_id && (
                    <Link href={`/investigate?node_id=${encodeURIComponent(sel.subject_id)}&tenant=${encodeURIComponent(desk)}&name=${encodeURIComponent(sel.subject_name ?? "")}`}
                      className="link ml-auto text-[13px] shrink-0">Re-run →</Link>
                  )}
                </div>
                <Memo md={sel.memo ?? `**Verdict:** ${sel.verdict ?? "n/a"}\n\n${sel.summary ?? "No summary stored for this case."}`} filename={`case-${sel.id}.md`} />
              </div>
            )}
          </div>
        )}
      </main>
      <Footer />
    </>
  );
}
