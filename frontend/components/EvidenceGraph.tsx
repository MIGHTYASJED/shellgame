"use client";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import type { GraphCanvasProps } from "./GraphCanvas";

const GraphCanvas = dynamic(() => import("./GraphCanvas"), {
  ssr: false,
  loading: () => <div className="absolute inset-0 grid place-items-center text-ink-3 text-[13px]">Loading graph…</div>,
});

export function EvidenceGraph(props: Omit<GraphCanvasProps, "width" | "height">) {
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  useEffect(() => {
    const el = box.current; if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: Math.floor(e.contentRect.width), h: Math.floor(e.contentRect.height) }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div ref={box} className="absolute inset-0">
      <GraphCanvas {...props} width={size.w} height={size.h} />
    </div>
  );
}

const LEGEND: [string, string][] = [
  ["company", "w-2 h-2 bg-ink-2"], ["officer", "w-2 h-2 rounded-full bg-green-2"], ["intermediary", "w-2 h-2 rounded-full border border-ink-2"],
  ["address", "w-2 h-2 rotate-45 bg-ink-3"], ["listed party", "w-2 h-2 bg-oxblood"], ["evidence path", "w-4 h-0.5 bg-brass"],
  ["weak link", "w-4 border-t border-dashed border-ink-3"], ["chokepoint", "w-2.5 h-2.5 rounded-full border border-dashed border-brass"],
];

export function GraphLegend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-ink-3">
      {LEGEND.map(([label, cls]) => <li key={label} className="flex items-center gap-1.5"><span className={`inline-block ${cls}`} />{label}</li>)}
    </ul>
  );
}
