import type { AgentEvent, Candidate, CaseRecord, CounterfactualResult } from "./types";
import { mockCandidates, mockCases, mockCounterfactual, mockNode, mockScript, mockSearch, mockStats, mockTenants } from "./mock";

export const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
export const MOCK = process.env.NEXT_PUBLIC_MOCK === "1" || process.env.NEXT_PUBLIC_MOCK === "true";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} on ${path}`);
  return r.json();
}

// Offline fallback: real investigation streams recorded from the live backend (scripts/record_replays.py),
// used only when the backend can't be reached, and always labelled as a recording.
type Replay = { node: Record<string, any>; events: AgentEvent[] };
const fromStatic = <T,>(path: string): Promise<T> =>
  fetch(`/replays/${path}`).then((r) => { if (!r.ok) throw new Error("no recording"); return r.json(); });
const replayIndex = () => fromStatic<{ stats: any; subjects: Candidate[] }>("index.json");

// Tolerant unwrapping: SPEC defines payloads for tools; API wrappers may return the bare list or {key: list}.
function list<T>(x: any, key: string): T[] {
  if (Array.isArray(x)) return x;
  if (x && Array.isArray(x[key])) return x[key];
  return [];
}

export async function search(q: string): Promise<Candidate[]> {
  if (MOCK) return mockSearch(q);
  try {
    return list<Candidate>(await get(`/api/search?q=${encodeURIComponent(q)}`), "candidates");
  } catch {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    return (await replayIndex()).subjects.filter((c) => words.every((w) => c.name.toLowerCase().includes(w)));
  }
}

export async function stats(): Promise<any> {
  if (MOCK) return mockStats;
  return get(`/api/stats`).catch(async () => (await replayIndex()).stats);
}

export async function tenants(): Promise<string[]> {
  if (MOCK) return mockTenants;
  const t = list<any>(await get(`/api/tenants`).catch(() => []), "tenants");
  return t.map((x) => (typeof x === "string" ? x : x.id ?? x.name ?? String(x)));
}

export async function cases(tenant: string): Promise<CaseRecord[]> {
  if (MOCK) return tenant === "default" ? mockCases : [];
  return list<CaseRecord>(await get(`/api/cases?tenant=${encodeURIComponent(tenant)}`).catch(() => []), "cases");
}

export async function nodeDetail(id: string): Promise<Record<string, any>> {
  if (MOCK) return mockNode(id).node;
  try {
    const r: any = await get(`/api/node/${encodeURIComponent(id)}`);
    return r?.node ?? r;
  } catch (e) {
    const r = await fromStatic<Replay>(`${encodeURIComponent(id)}.json`).catch(() => { throw e; });
    return r.node;
  }
}

export async function counterfactual(nodeId: string, removeId: string): Promise<CounterfactualResult> {
  if (MOCK) {
    await new Promise((r) => setTimeout(r, 600));
    return mockCounterfactual(nodeId, removeId);
  }
  const r = await fetch(`${API}/api/counterfactual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ node_id: nodeId, remove_id: removeId }),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} on /api/counterfactual`);
  return r.json();
}

/** Opens the investigation stream. Returns a stop() function. */
export function investigate(
  nodeId: string,
  tenant: string,
  onEvent: (e: AgentEvent) => void,
  onError: (msg: string) => void
): () => void {
  if (MOCK) {
    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];
    let t = 0;
    for (const step of mockScript(nodeId)) {
      t += step.delay;
      timers.push(setTimeout(() => { if (!cancelled) onEvent({ ...step.ev, ts: Date.now() / 1000 }); }, t));
    }
    return () => { cancelled = true; timers.forEach(clearTimeout); };
  }
  let stopReplay: (() => void) | null = null;
  let received = 0;
  const replay = () =>
    fromStatic<Replay>(`${encodeURIComponent(nodeId)}.json`)
      .then(({ events }) => {
        let cancelled = false;
        const timers = [{ type: "status", agent: "memory",
          text: "Live backend unreachable. Replaying a recorded run of this investigation from the live system." } as AgentEvent, ...events]
          .map((ev, i) => setTimeout(() => { if (!cancelled) onEvent({ ...ev, ts: Date.now() / 1000 }); }, i * 450));
        stopReplay = () => { cancelled = true; timers.forEach(clearTimeout); };
      })
      .catch(() => onError(`Lost connection to ${API}. The live backend may be offline; recorded demos exist for the four example companies.`));
  const es = new EventSource(`${API}/api/investigate?node_id=${encodeURIComponent(nodeId)}&tenant=${encodeURIComponent(tenant)}`);
  let finished = false;
  es.onmessage = (m) => {
    try {
      const ev = JSON.parse(m.data) as AgentEvent;
      received++;
      onEvent(ev);
      if (ev.type === "done" || ev.type === "error") { finished = true; es.close(); }
    } catch {
      /* ignore keepalives / non-JSON lines */
    }
  };
  es.onerror = () => {
    // EventSource auto-reconnects when the server closes; that would replay the investigation. Stop instead.
    es.close();
    if (finished) return;
    if (received === 0) replay();
    else onError(`Lost connection to ${API}. Check the backend is running, then replay.`);
  };
  return () => { finished = true; es.close(); stopReplay?.(); };
}
