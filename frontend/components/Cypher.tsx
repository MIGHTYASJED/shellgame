import type { ReactNode } from "react";

const KW = /\b(MATCH|OPTIONAL|WHERE|RETURN|WITH|UNWIND|CALL|YIELD|ORDER|BY|LIMIT|SKIP|AS|AND|OR|NOT|IN|DISTINCT|CREATE|MERGE|SET|DELETE|DETACH|DESC|ASC|NONE|ANY|ALL|CASE|WHEN|THEN|ELSE|END|IS|NULL|UNION|EXISTS|COUNT)\b/i;
const TOKEN = /(\/\/[^\n]*)|('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")|(\$[A-Za-z_][A-Za-z0-9_]*)|(:[A-Z_][A-Za-z0-9_]*)|(\b[a-zA-Z_][\w]*(?:\.[\w]+)+(?=\s*\())|(\b[A-Za-z_]+\b)|(\b\d+(?:\.\d+)?\b)/g;

function tint(src: string) {
  const out: ReactNode[] = [];
  let last = 0, i = 0;
  for (const m of src.matchAll(TOKEN)) {
    const idx = m.index ?? 0;
    if (idx > last) out.push(src.slice(last, idx));
    const [t, cm, str, param, label, fn, word, num] = m;
    let cls = "";
    if (cm) cls = "cy-cm"; else if (str) cls = "cy-str"; else if (param) cls = "cy-param";
    else if (label) cls = "cy-label"; else if (fn) cls = "cy-fn"; else if (word && KW.test(word) && word.length > 1) cls = "cy-kw";
    else if (num) cls = "cy-num";
    out.push(cls ? <span key={i++} className={cls}>{t}</span> : t);
    last = idx + t.length;
  }
  if (last < src.length) out.push(src.slice(last));
  return out;
}

export function Cypher({ code, params }: { code: string | string[]; params?: Record<string, unknown> }) {
  const parts = Array.isArray(code) ? code : [code];
  const ps = params ? Object.entries(params) : [];
  return (
    <div className="cypher mt-2.5 overflow-hidden">
      {parts.map((c, k) => (
        <pre key={k} className="px-3 py-2.5 overflow-x-auto scroll-thin whitespace-pre">{tint(c)}</pre>
      ))}
      {ps.length > 0 && (
        <dl className="px-3 py-2 border-t border-rule text-[11px]">
          {ps.map(([k, v]) => (
            <div key={k} className="flex gap-2 min-w-0">
              <dt className="cy-param shrink-0">${k}</dt>
              <dd className="text-ink-3 truncate" title={JSON.stringify(v)}>{JSON.stringify(v)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
