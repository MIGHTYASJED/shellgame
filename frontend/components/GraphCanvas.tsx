"use client";
// Loaded only on the client via next/dynamic (ssr:false) from EvidenceGraph.
import ForceGraph2D from "react-force-graph-2d";
import { useEffect, useMemo, useRef, useState } from "react";
import type { SgLink, SgNode, Highlight } from "@/lib/types";
import { linkKey } from "@/lib/investigation";

const WEAK = new Set(["SIMILAR", "SAME_NAME_AS", "PROBABLY_SAME_OFFICER_AS", "PROBABLY_SAME_AS", "SIMILAR_COMPANY_AS"]);
const isWeakType = (t: string) => WEAK.has(t) || t.startsWith("PROBABLY_SAME");

// Palette mirrors the CSS tokens in globals.css (canvas can't read CSS variables cheaply).
const C = { ink: "#15201B", ink2: "#4F5651", ink3: "#878C85", green: "#2D6A4F", ox: "#7B2531", brass: "#A88A4E", white: "#FFFFFF" };
const KIND_COLOR: Record<string, string> = { Entity: C.ink2, Officer: C.green, Intermediary: C.ink2, Address: C.ink3, Other: C.ink3, Sanction: C.ox };
const MONO = '"Geist Mono Variable", ui-monospace, monospace';
const reduceMotion = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

type GNode = SgNode & { x?: number; y?: number; fx?: number; fy?: number };
type GLink = { source: any; target: any; type: string; link?: string; key: string };

export interface GraphCanvasProps {
  nodes: Map<string, SgNode>;
  links: Map<string, SgLink & { key: string }>;
  graphVersion: number;
  highlight: Highlight | null;
  highlightVersion: number;
  subjectId: string | null;
  weakLinks: Set<string>;
  severed: Set<string>;
  chokepointIds: Set<string>;
  selectedId: string | null;
  onNodeClick: (n: SgNode) => void;
  width: number;
  height: number;
}

const endId = (x: any): string => (x && typeof x === "object" ? x.id : String(x));
const short = (s: string, n = 26) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

export default function GraphCanvas(p: GraphCanvasProps) {
  const fg = useRef<any>(null);
  const store = useRef<{ nodes: Map<string, GNode>; links: Map<string, GLink> }>({ nodes: new Map(), links: new Map() });
  const [data, setData] = useState<{ nodes: GNode[]; links: GLink[] }>({ nodes: [], links: [] });
  const [hover, setHover] = useState<string | null>(null);
  const t0 = useRef(performance.now());
  const still = useMemo(reduceMotion, []);

  // Incremental merge that keeps existing node objects (and their positions).
  useEffect(() => {
    const st = store.current;
    if (p.nodes.size === 0) { st.nodes.clear(); st.links.clear(); setData({ nodes: [], links: [] }); return; }
    let added = false;
    p.nodes.forEach((n, id) => {
      const cur = st.nodes.get(id);
      if (!cur) {
        // spawn near a linked neighbour so the graph grows outward instead of exploding from the origin
        let x: number | undefined, y: number | undefined;
        for (const l of Array.from(p.links.values())) {
          const other = l.source === id ? l.target : l.target === id ? l.source : null;
          const o = other ? st.nodes.get(other) : undefined;
          if (o && o.x !== undefined) { x = o.x + (Math.random() - 0.5) * 40; y = (o.y ?? 0) + (Math.random() - 0.5) * 40; break; }
        }
        st.nodes.set(id, { ...n, x, y });
        added = true;
      } else if (n.sanctioned) cur.sanctioned = true;
    });
    p.links.forEach((l, k) => {
      if (!st.links.has(k)) { st.links.set(k, { source: l.source, target: l.target, type: l.type, link: l.link, key: linkKey(l.source, l.target) }); added = true; }
    });
    if (added) setData({ nodes: Array.from(st.nodes.values()), links: Array.from(st.links.values()) });
  }, [p.graphVersion, p.nodes, p.links]);

  // Pin the subject to the centre so the story reads left-to-right outward from it.
  useEffect(() => {
    if (!p.subjectId) return;
    const n = store.current.nodes.get(p.subjectId);
    if (n && n.fx === undefined) { n.fx = 0; n.fy = 0; }
  }, [data, p.subjectId]);

  useEffect(() => {
    const g = fg.current; if (!g) return;
    g.d3Force("charge")?.strength(-160);
    g.d3Force("link")?.distance((l: GLink) => (l.type === "MATCHES" ? 60 : isWeakType(l.type) ? 90 : 55));
  }, [data]);

  const hlNodes = useMemo(() => new Set(p.highlight?.nodes ?? []), [p.highlight]);
  const hlLinks = useMemo(() => new Set((p.highlight?.links ?? []).map((l) => linkKey(endId(l.source), endId(l.target)))), [p.highlight]);
  const hasHl = hlNodes.size > 0;

  // Auto-fit to the highlighted path whenever a new highlight arrives.
  useEffect(() => {
    if (!hasHl) return;
    const t = setTimeout(() => {
      const g = fg.current; if (!g) return;
      const ids = hlNodes;
      const pts = data.nodes.filter((x) => ids.has(x.id) && Number.isFinite(x.x));
      const spread = pts.length >= 2 ? Math.max(...pts.map((a) => Math.hypot((a.x ?? 0) - (pts[0].x ?? 0), (a.y ?? 0) - (pts[0].y ?? 0)))) : 0;
      if (pts.length >= 2 && spread > 40) g.zoomToFit(800, 110, (x: GNode) => ids.has(x.id));
      else g.zoomToFit(800, 140);
    }, 1100);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.highlightVersion]);

  const touchesSevered = (l: GLink) => p.severed.has(endId(l.source)) || p.severed.has(endId(l.target));

  return (
    <ForceGraph2D
      ref={fg}
      width={p.width}
      height={p.height}
      graphData={data}
      backgroundColor="rgba(0,0,0,0)"
      cooldownTicks={140}
      maxZoom={3.2}
      minZoom={0.3}
      d3VelocityDecay={0.32}
      onEngineStop={() => {
        const g = fg.current; if (!g) return;
        if (hasHl && hlNodes.size >= 2) g.zoomToFit(600, 90, (x: GNode) => hlNodes.has(x.id));
        else g.zoomToFit(500, 80);
      }}
      nodeId="id"
      nodeRelSize={4}
      nodeLabel={() => ""}
      onNodeHover={(n: any) => setHover(n ? n.id : null)}
      onNodeClick={(n: any) => p.onNodeClick(n)}
      onBackgroundClick={() => {}}
      linkColor={(l: any) => {
        if (touchesSevered(l)) return "rgba(123,37,49,0.35)";
        const k = linkKey(endId(l.source), endId(l.target));
        if (hlLinks.has(k)) return p.weakLinks.has(k) ? "rgba(168,138,78,0.55)" : C.brass;
        if (isWeakType(l.type)) return "rgba(135,140,133,0.7)";
        return hasHl ? "rgba(21,32,27,0.08)" : "rgba(21,32,27,0.2)";
      }}
      linkWidth={(l: any) => (hlLinks.has(linkKey(endId(l.source), endId(l.target))) ? 2 : 0.7)}
      linkLineDash={(l: any) => {
        if (touchesSevered(l)) return [2, 5];
        const k = linkKey(endId(l.source), endId(l.target));
        if (isWeakType(l.type) || p.weakLinks.has(k)) return [5, 4];
        if (l.type === "MATCHES") return [1.5, 3];
        return null;
      }}
      linkDirectionalParticles={(l: any) => (!still && !touchesSevered(l) && hlLinks.has(linkKey(endId(l.source), endId(l.target))) ? 3 : 0)}
      linkDirectionalParticleWidth={2.6}
      linkDirectionalParticleSpeed={0.008}
      linkDirectionalParticleColor={() => "#C9A96A"}
      linkCanvasObjectMode={() => "after"}
      linkCanvasObject={(l: any, ctx: CanvasRenderingContext2D, scale: number) => {
        const s = l.source, t = l.target;
        if (typeof s !== "object" || !Number.isFinite(s.x) || !Number.isFinite(t?.x)) return;
        const k = linkKey(s.id, t.id);
        const onPath = hlLinks.has(k);
        if (touchesSevered(l)) {
          // a cut mark across the middle of each severed edge
          const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2;
          const ang = Math.atan2(t.y - s.y, t.x - s.x) + Math.PI / 2;
          const r = 5;
          ctx.strokeStyle = C.ox; ctx.lineWidth = 1.6 / Math.max(scale, 0.6);
          ctx.beginPath(); ctx.moveTo(mx - Math.cos(ang) * r, my - Math.sin(ang) * r); ctx.lineTo(mx + Math.cos(ang) * r, my + Math.sin(ang) * r); ctx.stroke();
          return;
        }
        if (!onPath && scale < 2.2) return;
        const label = (l.link || l.type || "").toString().replace(/_/g, " ").toLowerCase();
        if (!label) return;
        const fs = Math.max(9 / scale, 2.4);
        ctx.font = `400 ${fs}px ${MONO}`;
        const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2;
        let ang = Math.atan2(t.y - s.y, t.x - s.x);
        if (ang > Math.PI / 2) ang -= Math.PI; if (ang < -Math.PI / 2) ang += Math.PI;
        ctx.save(); ctx.translate(mx, my); ctx.rotate(ang);
        const w = ctx.measureText(label).width;
        ctx.fillStyle = "rgba(255,255,255,0.92)"; ctx.fillRect(-w / 2 - 2, -fs * 0.7, w + 4, fs * 1.4);
        ctx.fillStyle = onPath ? "#8A6D33" : C.ink3;
        ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(label, 0, 0.5);
        ctx.restore();
      }}
      nodeCanvasObject={(n: any, ctx: CanvasRenderingContext2D, scale: number) => {
        if (!Number.isFinite(n.x) || !Number.isFinite(n.y)) return;
        const id = n.id as string;
        const onPath = hlNodes.has(id);
        const sev = p.severed.has(id);
        const isSubject = id === p.subjectId;
        const sanctioned = !!n.sanctioned || n.kind === "Sanction";
        const choke = p.chokepointIds.has(id);
        const dim = hasHl && !onPath && !isSubject && !sanctioned;
        const r = isSubject ? 7 : sanctioned ? 6.5 : onPath ? 5.5 : 3.6;
        const base = KIND_COLOR[n.kind] ?? C.ink3;
        const fill = onPath && !sanctioned ? C.brass : base;
        ctx.globalAlpha = sev ? 0.4 : dim ? 0.25 : 1;

        if (onPath && !sev) {
          const pulse = still ? 0.5 : 0.5 + 0.5 * Math.sin((performance.now() - t0.current) / 520);
          const g = ctx.createRadialGradient(n.x, n.y, r * 0.6, n.x, n.y, r * (2.8 + pulse * 0.6));
          g.addColorStop(0, sanctioned ? "rgba(123,37,49,0.32)" : "rgba(168,138,78,0.38)");
          g.addColorStop(1, "rgba(168,138,78,0)");
          ctx.fillStyle = g; ctx.beginPath(); ctx.arc(n.x, n.y, r * 3.4, 0, Math.PI * 2); ctx.fill();
        }

        ctx.lineWidth = 1.4 / Math.max(scale, 0.7);
        if (sanctioned) {
          // listed party: square seal with a cross
          ctx.fillStyle = C.ox;
          ctx.fillRect(n.x - r, n.y - r, r * 2, r * 2);
          ctx.strokeStyle = C.white; ctx.lineWidth = 1.6 / Math.max(scale, 0.7);
          ctx.beginPath(); ctx.moveTo(n.x - r * 0.55, n.y - r * 0.55); ctx.lineTo(n.x + r * 0.55, n.y + r * 0.55);
          ctx.moveTo(n.x + r * 0.55, n.y - r * 0.55); ctx.lineTo(n.x - r * 0.55, n.y + r * 0.55); ctx.stroke();
        } else if (n.kind === "Address") {
          ctx.fillStyle = fill;
          ctx.beginPath(); ctx.moveTo(n.x, n.y - r); ctx.lineTo(n.x + r, n.y); ctx.lineTo(n.x, n.y + r); ctx.lineTo(n.x - r, n.y); ctx.closePath(); ctx.fill();
        } else if (n.kind === "Entity") {
          ctx.fillStyle = fill;
          ctx.fillRect(n.x - r * 0.9, n.y - r * 0.9, r * 1.8, r * 1.8);
        } else if (n.kind === "Intermediary" && !onPath) {
          ctx.fillStyle = C.white; ctx.strokeStyle = base;
          ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        } else {
          ctx.fillStyle = fill;
          ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, Math.PI * 2); ctx.fill();
        }
        if (isSubject) {
          ctx.strokeStyle = C.ink; ctx.lineWidth = 1.2 / Math.max(scale, 0.7);
          ctx.beginPath(); ctx.arc(n.x, n.y, r + 4, 0, Math.PI * 2); ctx.stroke();
        }
        if (choke && !sev) {
          ctx.strokeStyle = C.brass; ctx.setLineDash([2, 2]); ctx.lineWidth = 1.2 / Math.max(scale, 0.7);
          ctx.beginPath(); ctx.arc(n.x, n.y, r + 7, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
        }
        if (id === p.selectedId) {
          ctx.strokeStyle = C.green; ctx.lineWidth = 1.2 / Math.max(scale, 0.7);
          ctx.strokeRect(n.x - r - 5, n.y - r - 5, (r + 5) * 2, (r + 5) * 2);
        }
        if (sev) {
          ctx.strokeStyle = C.ox; ctx.lineWidth = 2 / Math.max(scale, 0.7);
          ctx.beginPath(); ctx.moveTo(n.x - r - 4, n.y - r - 4); ctx.lineTo(n.x + r + 4, n.y + r + 4);
          ctx.moveTo(n.x + r + 4, n.y - r - 4); ctx.lineTo(n.x - r - 4, n.y + r + 4); ctx.stroke();
        }

        const showLabel = onPath || isSubject || sanctioned || choke || id === hover || id === p.selectedId || scale > 2.6;
        if (showLabel) {
          const fs = Math.max((onPath || isSubject || sanctioned ? 10.5 : 9.5) / scale, 2.4);
          ctx.font = `${onPath || isSubject ? 500 : 400} ${fs}px ${MONO}`;
          ctx.textAlign = "center"; ctx.textBaseline = "top";
          const txt = short(n.name ?? id, isSubject || onPath ? 34 : 24);
          const w = ctx.measureText(txt).width;
          ctx.fillStyle = "rgba(255,255,255,0.88)"; ctx.fillRect(n.x - w / 2 - 2, n.y + r + 3, w + 4, fs * 1.3);
          ctx.fillStyle = sanctioned ? C.ox : onPath || isSubject ? C.ink : C.ink2;
          ctx.fillText(txt, n.x, n.y + r + 3.5);
        }
        ctx.globalAlpha = 1;
      }}
      nodePointerAreaPaint={(n: any, color: string, ctx: CanvasRenderingContext2D) => {
        if (!Number.isFinite(n.x)) return;
        ctx.fillStyle = color; ctx.beginPath(); ctx.arc(n.x, n.y, 9, 0, Math.PI * 2); ctx.fill();
      }}
      autoPauseRedraw={still}
    />
  );
}
