// Types mirror SPEC.md (binding contract). Fields marked optional are defensive.
export type Kind = "Entity" | "Officer" | "Intermediary" | "Address" | "Other" | "Sanction";

export interface SgNode {
  id: string;
  kind: Kind | string;
  name: string;
  jurisdiction?: string;
  sanctioned?: boolean;
}
export interface SgLink {
  source: string;
  target: string;
  type: string;
  link?: string;
}
export interface Subgraph {
  nodes: SgNode[];
  links: SgLink[];
}
export interface Highlight {
  nodes: string[];
  links: { source: string; target: string }[];
}

export type EventType =
  | "status" | "thought" | "tool_call" | "tool_result" | "skeptic"
  | "recall" | "verdict" | "memo" | "done" | "error";
export type AgentName = "investigator" | "skeptic" | "gatekeeper" | "memory";

export interface AgentEvent {
  type: EventType;
  agent?: AgentName | string;
  text?: string;
  tool?: string;
  args?: Record<string, unknown>;
  cypher?: string | string[];
  params?: Record<string, unknown>;
  result?: any;
  highlight?: Highlight;
  subgraph?: Subgraph;
  ts?: number | string;
}

export interface Candidate {
  id: string;
  kind: string;
  name: string;
  jurisdiction?: string;
  countries?: string;
}

export interface Verdict {
  verdict: "APPROVE" | "EDD" | "REJECT" | string;
  reasons: string[];
  rule_ids: string[];
}

export interface Chokepoint {
  id: string;
  name: string;
  kind: string;
  paths_through: number;
  betweenness?: number;
}

export interface CaseRecord {
  id: string;
  created_at?: string;
  subject_id?: string;
  subject_name?: string;
  verdict?: string;
  summary?: string;
  memo?: string;
  [k: string]: unknown;
}

export interface PathRec {
  hops: number;
  weight?: number;
  sanction?: Record<string, unknown>;
  match?: { score?: number; method?: string };
  nodes: string[];
  edges: SgLink[];
  weakened?: boolean;
}

export interface CounterfactualResult {
  still_exposed: boolean;
  paths: PathRec[];
  cypher?: string | string[];
  params?: Record<string, unknown>;
}
