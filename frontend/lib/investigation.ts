"use client";
import { useCallback, useEffect, useReducer, useRef } from "react";
import { investigate } from "./api";
import type { AgentEvent, Chokepoint, Highlight, SgLink, SgNode, Verdict } from "./types";

export const linkKey = (s: string, t: string) => (s < t ? `${s}~${t}` : `${t}~${s}`);
const endId = (x: any): string => (x && typeof x === "object" ? x.id : String(x));

export interface RecallItem { text?: string; cases: any[] }
export interface AgentCounterfactual { remove_id?: string; still_exposed: boolean; text?: string }

export interface InvState {
  status: "idle" | "running" | "done" | "error";
  error?: string;
  events: AgentEvent[];
  nodes: Map<string, SgNode>;
  links: Map<string, SgLink & { key: string }>;
  graphVersion: number;
  highlight: Highlight | null;
  highlightVersion: number;
  evidence: Set<string>; // nodes ever on a highlighted path
  weakLinks: Set<string>; // link keys the skeptic flagged
  verdict: Verdict | null;
  memo: string | null;
  chokepoints: Chokepoint[];
  recall: RecallItem[];
  agentCf: AgentCounterfactual | null;
  noPath: boolean;
  caseId?: string;
  paths: { nodes: string[]; links: { source: string; target: string }[]; weakened: boolean }[];
  pending: (SgLink)[]; // links that arrived before both endpoints
}

const init = (): InvState => ({
  status: "idle", events: [], nodes: new Map(), links: new Map(), graphVersion: 0,
  highlight: null, highlightVersion: 0, evidence: new Set(), weakLinks: new Set(), verdict: null, memo: null,
  chokepoints: [], recall: [], agentCf: null, noPath: false, paths: [], pending: [],
});

type Action = { t: "reset" } | { t: "event"; e: AgentEvent } | { t: "error"; msg: string } | { t: "focus"; h: Highlight };

function mergeSubgraph(s: InvState, sg: any): boolean {
  if (!sg || typeof sg !== "object") return false;
  let changed = false;
  for (const n of Array.isArray(sg.nodes) ? sg.nodes : []) {
    if (!n?.id) continue;
    const prev = s.nodes.get(n.id);
    if (!prev) { s.nodes.set(n.id, { ...n }); changed = true; }
    else if (n.sanctioned && !prev.sanctioned) { prev.sanctioned = true; changed = true; }
  }
  const incoming = [...s.pending, ...(Array.isArray(sg.links) ? sg.links : [])];
  const still: SgLink[] = [];
  for (const l of incoming) {
    const src = endId(l.source), tgt = endId(l.target);
    if (!s.nodes.has(src) || !s.nodes.has(tgt)) { still.push({ source: src, target: tgt, type: l.type, link: l.link }); continue; }
    const key = `${linkKey(src, tgt)}~${l.type}`;
    if (!s.links.has(key)) { s.links.set(key, { source: src, target: tgt, type: l.type, link: l.link, key }); changed = true; }
  }
  s.pending = still.slice(-500);
  return changed;
}

function reducer(state: InvState, a: Action): InvState {
  if (a.t === "reset") return { ...init(), status: "running" };
  if (a.t === "error") return { ...state, status: "error", error: a.msg };
  if (a.t === "focus") return { ...state, highlight: a.h, highlightVersion: state.highlightVersion + 1 };

  const e = a.e;
  const s: InvState = { ...state, events: [...state.events, e], pending: state.pending };
  const r = e.result;

  // graph merge: event.subgraph, result.subgraph, and edges carried on result.paths
  let changed = false;
  s.nodes = new Map(state.nodes); s.links = new Map(state.links);
  changed = mergeSubgraph(s, e.subgraph) || changed;
  if (r && typeof r === "object") {
    changed = mergeSubgraph(s, r.subgraph) || changed;
    if (Array.isArray(r.paths)) for (const p of r.paths) changed = mergeSubgraph(s, { nodes: [], links: p.edges ?? [] }) || changed;
  }
  if (changed) s.graphVersion = state.graphVersion + 1;
  else { s.nodes = state.nodes; s.links = state.links; }

  if (e.highlight && (e.highlight.nodes?.length || e.highlight.links?.length)) {
    s.highlight = { nodes: e.highlight.nodes ?? [], links: e.highlight.links ?? [] };
    s.highlightVersion = state.highlightVersion + 1;
    if (e.type !== "skeptic") { s.evidence = new Set(state.evidence); e.highlight.nodes?.forEach((n) => s.evidence.add(n)); }
  }

  if (e.type === "skeptic" && r && r.weakened === true && typeof r.path_index === "number" && s.paths[r.path_index]) {
    s.paths = s.paths.map((p, i) => (i === r.path_index ? { ...p, weakened: true } : p));
  }
  if (e.type === "skeptic" && r) {
    const weak: any[] = r.weak_edges ?? r.weak_links ?? [];
    if (weak.length || r.weakened) {
      s.weakLinks = new Set(state.weakLinks);
      if (weak.length) weak.forEach((w) => s.weakLinks.add(linkKey(endId(w.source), endId(w.target))));
    }
  }

  if (e.type === "recall") {
    const cases = Array.isArray(r) ? r : r?.cases ?? r?.precedents ?? [];
    s.recall = [...state.recall, { text: e.text, cases }];
  }

  if (e.type === "tool_result" && r) {
    if (e.tool === "chokepoints" && Array.isArray(r.chokepoints)) s.chokepoints = r.chokepoints;
    if (e.tool === "counterfactual" && typeof r.still_exposed === "boolean")
      s.agentCf = { still_exposed: r.still_exposed, remove_id: r.remove_id ?? (e.args?.remove_id as string), text: e.text };
    if (e.tool === "sanction_paths" && r.found === false) s.noPath = true;
    if (e.tool === "sanction_paths" && Array.isArray(r.paths)) {
      s.paths = r.paths.map((p: any) => ({
        nodes: (p.nodes ?? []).map(endId),
        links: (p.edges ?? []).map((x: any) => ({ source: endId(x.source), target: endId(x.target) })),
        weakened: !!p.weakened,
      }));
    }
    if (e.tool === "recall" && (r.cases?.length || (Array.isArray(r) && r.length))) {
      s.recall = [...state.recall, { text: e.text, cases: Array.isArray(r) ? r : r.cases }];
    }
  }

  if (e.type === "verdict" && !e.highlight?.nodes?.length && s.paths.length) {
    // bring the camera back to the path that drives the verdict
    const best = s.paths.find((p) => !p.weakened) ?? s.paths[0];
    s.highlight = { nodes: best.nodes, links: best.links };
    s.highlightVersion = s.highlightVersion + 1;
  }
  if (e.type === "verdict") {
    const v = (r && typeof r === "object" ? r : e) as any;
    s.verdict = { verdict: String(v.verdict ?? e.text ?? "").toUpperCase(), reasons: v.reasons ?? [], rule_ids: v.rule_ids ?? [] };
  }
  if (e.type === "memo") {
    s.memo = typeof e.text === "string" && e.text ? e.text : typeof r === "string" ? r : r?.memo ?? r?.markdown ?? null;
  }
  if (r && typeof r === "object" && (r.case_id || r.case?.id)) s.caseId = r.case_id ?? r.case.id;
  if (e.type === "done") s.status = "done";
  if (e.type === "error") { s.status = "error"; s.error = e.text ?? "The investigation stopped with an error."; }
  return s;
}

export function useInvestigation(nodeId: string | null, tenant: string) {
  const [state, dispatch] = useReducer(reducer, undefined, init);
  const stopRef = useRef<() => void>(() => {});

  const start = useCallback(() => {
    if (!nodeId) return;
    stopRef.current();
    dispatch({ t: "reset" });
    stopRef.current = investigate(nodeId, tenant, (e) => dispatch({ t: "event", e }), (msg) => dispatch({ t: "error", msg }));
  }, [nodeId, tenant]);

  useEffect(() => { start(); return () => stopRef.current(); }, [start]);

  const stop = useCallback(() => { stopRef.current(); }, []);
  const focus = useCallback((h: Highlight) => dispatch({ t: "focus", h }), []);
  return { state, restart: start, stop, focus };
}
