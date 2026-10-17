"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useState } from "react";

export function Memo({ md, filename }: { md: string; filename: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(md); setCopied(true); setTimeout(() => setCopied(false), 1600); } catch {}
  };
  const download = () => {
    const url = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
    const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <div className="card">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-rule">
        <h3 className="eyebrow">Due diligence memo</h3>
        <button onClick={copy} className="btn ml-auto py-1 px-2.5 text-[12px]">{copied ? "Copied" : "Copy"}</button>
        <button onClick={download} className="btn py-1 px-2.5 text-[12px]">Download .md</button>
      </div>
      <article className="memo px-5 py-5"><ReactMarkdown remarkPlugins={[remarkGfm]}>{md}</ReactMarkdown></article>
    </div>
  );
}
