"use client";
import { useEffect, useState } from "react";
import { counterfactual, nodeDetail } from "@/lib/api";
import type { CounterfactualResult, SgNode } from "@/lib/types";
import { Cypher } from "./Cypher";

const HIDE = new Set(["id", "name", "kind", "sanctioned", "x", "y", "vx", "vy", "fx", "fy", "index", "__indexColor"]);

export function NodeDrawer({ node, subjectId, onClose, onCut, cutResult }: {
  node: SgNode; subjectId: string; onClose: () => void;
  onCut: (id: string, r: CounterfactualResult) => void; cutResult?: CounterfactualResult;
}) {
  const [detail, setDetail] = useState<Record<string, any> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setDetail(null); setErr(null);
    nodeDetail(node.id).then(setDetail).catch((e) => setErr(`Could not load details: ${e.message}`));
  }, [node.id]);

  const listed = node.kind === "Sanction" || node.sanctioned;
  const cut = async () => {
    setBusy(true); setErr(null);
    try { onCut(node.id, await counterfactual(subjectId, node.id)); }
    catch (e: any) { setErr(`Counterfactual failed: ${e.message}`); }
    finally { setBusy(false); }
  };
  const props = detail ? Object.entries(detail).filter(([k, v]) => !HIDE.has(k) && v !== null && v !== undefined && v !== "") : [];

  return (
    <aside className="rise absolute right-3 top-3 bottom-3 w-[340px] max-w-[calc(100%-24px)] card shadow-lift z-20 flex flex-col">
      <div className="px-5 pt-4 pb-4 border-b border-rule">
        <div className="flex items-center gap-2">
          <span className="pill" data-tone={listed ? "oxblood" : undefined}>{listed ? "OpenSanctions record" : node.kind}</span>
          <span className="num text-[11px] text-ink-3 truncate">{node.id}</span>
          <button onClick={onClose} className="ml-auto -mr-1 w-7 h-7 grid place-items-center rounded-md text-ink-3 hover:text-ink hover:bg-ink/[.045]" aria-label="Close">
            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.4" /></svg>
          </button>
        </div>
        <h3 className="mt-2.5 font-serif text-[22px] leading-tight tracking-[-.01em]">{node.name}</h3>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto scroll-thin px-5 py-4">
        {!detail && !err && <p className="text-[13px] text-ink-3">Loading record…</p>}
        <dl className="text-[12.5px] divide-y divide-rule">
          {props.map(([k, v]) => (
            <div key={k} className="grid grid-cols-[112px_1fr] gap-3 py-1.5">
              <dt className="text-ink-3 truncate capitalize">{k.replace(/_/g, " ")}</dt>
              <dd className="break-words">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
            </div>
          ))}
        </dl>
        {cutResult && (
          <div className="mt-5 rounded-lg p-4" style={{ background: cutResult.still_exposed ? "var(--brass-wash)" : "var(--green-wash)" }}>
            <p className={`font-serif text-[20px] ${cutResult.still_exposed ? "text-[#8A6D33]" : "text-green"}`}>
              {cutResult.still_exposed ? "Still exposed" : "Link broken"}
            </p>
            <p className="text-[13px] text-ink-2 mt-1">
              {cutResult.still_exposed
                ? `${cutResult.paths?.length ?? 0} path${cutResult.paths?.length === 1 ? "" : "s"} survive without this node. It is not the only route.`
                : "With this node removed, no path to a listed party remains within the hop limit."}
            </p>
            {cutResult.cypher && <Cypher code={cutResult.cypher} params={cutResult.params} />}
          </div>
        )}
        {err && <p className="mt-3 text-[13px] text-oxblood">{err}</p>}
      </div>
      {node.id !== subjectId && (
        <div className="p-4 border-t border-rule">
          <button onClick={cut} disabled={busy} className="btn btn-danger w-full justify-center py-2.5">
            {busy ? "Re-tracing paths…" : cutResult ? "Cut again" : "Cut this node"}
          </button>
          <p className="mt-2 text-[11.5px] text-ink-3 leading-snug">Re-runs the path search with this node removed. Nothing in the data changes.</p>
        </div>
      )}
    </aside>
  );
}
