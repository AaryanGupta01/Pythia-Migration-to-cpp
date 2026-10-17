// Pure (state, event) -> state. Shared by live WS, mock player and saved-job replay.
import {
  STAGES,
  type FunctionSummary,
  type JobOptions,
  type JobSummary,
  type JourneyKey,
  type Mismatch,
  type ProfileRow,
  type RankRow,
  type StageName,
  type StageState,
  type StudioEvent,
  type Status,
  type Diagnostic,
  type FileDigest,
} from './types'

export interface StageInfo {
  state: StageState
  summary: string | null
  progress: number | null
  startSeq: number | null
}
export interface StepItem {
  step_id: string
  fn_id: string | null
  title: string
  state: 'running' | 'done' | 'failed' | 'info'
  detail: string | null
  seq: number
  ts: number
}
export interface LogLine {
  seq: number
  stream: 'build' | 'trace' | 'system'
  level: 'info' | 'warn' | 'error'
  text: string
  stage: StageName | null
}
export interface FixAttemptS {
  attempt: number
  source: 'api' | 'cache'
  ok: boolean
  error: string | null
  pysub: string
  /** wall-clock gap since the previous step for this function (ms), derived from event timestamps */
  latency_ms: number | null
  model: string | null
  provider: string | null
  at: number
}
export interface FixState {
  attempts: FixAttemptS[]
  done: { ok: boolean; reason: string | null } | null
}
export interface CompileS {
  ok: boolean
  cached: boolean
  compile_s: number
  module: string
  error: string | null
  diagnostics: Diagnostic[]
}
export interface VerifyS {
  status: 'verified' | 'guarded' | 'failed'
  total: number
  matched: number
  first_mismatch: Mismatch | null
}
export interface BenchS {
  py_ms: number
  cpp_ms: number
  speedup: number
  calls_timed: number
  probe: boolean
}
export interface E2E {
  cmd: string
  before_s: number
  after_s: number
  speedup: number
  output_match: boolean
  ok: boolean
}
export interface IngestS {
  phase: string
  files: number
  bytes: number
  current: string | null
  message: string
  messages: string[]
  done: { workspace_id: string; name: string; files: number; py_files: number; skipped: { path: string; reason: string }[] } | null
}
export interface TraceS {
  calls: number
  functions_seen: number
  elapsed_s: number
  stdout_tail: string
  history: { t: number; calls: number }[]
  done: { total_s: number; exit_code: number; timed_out: boolean; calls: number; profile: ProfileRow[] } | null
}
export type RunState = 'idle' | 'running' | 'done' | 'failed' | 'cancelled'

export interface JobState {
  jobId: string | null
  workspaceId: string | null
  name: string | null
  inputKind: string | null
  options: JobOptions | null
  state: RunState
  stages: Record<StageName, StageInfo>
  caption: string | null
  captionSeq: number
  activeStage: StageName | null
  activeFn: string | null
  lastSeq: number
  eventCount: number
  ingest: IngestS
  functions: Record<string, FunctionSummary>
  order: string[]
  scan: { functions: number; verifiable: number; fixable: number; not_eligible: number } | null
  trace: TraceS
  ranking: RankRow[] | null
  fix: Record<string, FixState>
  fixStart: Record<string, number>
  compile: Record<string, CompileS>
  verify: Record<string, VerifyS>
  bench: Record<string, BenchS>
  e2e: E2E | null
  splice: { files: FileDigest[]; functions: number } | null
  exported: { path: string; zip: boolean; files: number } | null
  steps: StepItem[]
  logs: LogLine[]
  errors: { where: string; message: string; fatal: boolean; seq: number }[]
  summary: JobSummary | null
  /** per-function change counter so views know when to refetch the full record */
  touched: Record<string, number>
}

const emptyStages = (): Record<StageName, StageInfo> =>
  Object.fromEntries(STAGES.map((s) => [s, { state: 'idle', summary: null, progress: null, startSeq: null }])) as Record<
    StageName,
    StageInfo
  >

export const initialState = (): JobState => ({
  jobId: null,
  workspaceId: null,
  name: null,
  inputKind: null,
  options: null,
  state: 'idle',
  stages: emptyStages(),
  caption: null,
  captionSeq: 0,
  activeStage: null,
  activeFn: null,
  lastSeq: 0,
  eventCount: 0,
  ingest: { phase: '', files: 0, bytes: 0, current: null, message: '', messages: [], done: null },
  functions: {},
  order: [],
  scan: null,
  trace: { calls: 0, functions_seen: 0, elapsed_s: 0, stdout_tail: '', history: [], done: null },
  ranking: null,
  fix: {},
  fixStart: {},
  compile: {},
  verify: {},
  bench: {},
  e2e: null,
  splice: null,
  exported: null,
  steps: [],
  logs: [],
  errors: [],
  summary: null,
  touched: {},
})

const LOG_CAP = 6000

const bump = (t: Record<string, number>, id: string | null | undefined) =>
  id ? { ...t, [id]: (t[id] ?? 0) + 1 } : t

function patchFn(s: JobState, id: string, p: Partial<FunctionSummary>): Record<string, FunctionSummary> {
  const f = s.functions[id]
  if (!f) return s.functions
  return { ...s.functions, [id]: { ...f, ...p } }
}

export function reduce(s: JobState, e: StudioEvent): JobState {
  const base: JobState = {
    ...s,
    lastSeq: Math.max(s.lastSeq, e.seq),
    eventCount: s.eventCount + 1,
    caption: e.caption ?? s.caption,
    captionSeq: e.caption ? e.seq : s.captionSeq,
  }
  switch (e.type) {
    case 'job.start': {
      const d = e.data
      return {
        ...initialState(),
        jobId: d.job_id,
        workspaceId: d.workspace_id,
        name: d.name,
        inputKind: d.input_kind,
        options: d.options,
        state: 'running',
        lastSeq: e.seq,
        eventCount: 1,
        caption: e.caption,
        captionSeq: e.caption ? e.seq : 0,
      }
    }
    case 'stage': {
      const d = e.data
      const prev = s.stages[d.stage]
      const stages = {
        ...s.stages,
        [d.stage]: {
          state: d.state,
          summary: d.summary ?? (d.state === 'running' ? null : prev.summary),
          progress: d.progress,
          startSeq: d.state === 'running' && prev.state !== 'running' ? e.seq : prev.startSeq,
        },
      }
      return { ...base, stages, activeStage: d.state === 'running' ? d.stage : s.activeStage }
    }
    case 'ingest.progress': {
      const d = e.data
      const messages = d.message && s.ingest.messages[s.ingest.messages.length - 1] !== d.message
        ? [...s.ingest.messages.slice(-199), d.message]
        : s.ingest.messages
      return { ...base, ingest: { ...s.ingest, phase: d.phase, files: d.files, bytes: d.bytes, current: d.current, message: d.message, messages } }
    }
    case 'ingest.done':
      return { ...base, workspaceId: e.data.workspace_id, name: e.data.name || s.name, ingest: { ...s.ingest, done: e.data } }
    case 'scan.function': {
      const f = e.data.function
      const known = f.id in s.functions
      return {
        ...base,
        functions: { ...s.functions, [f.id]: known ? { ...s.functions[f.id], ...f } : f },
        order: known ? s.order : [...s.order, f.id],
        touched: bump(s.touched, f.id),
        activeFn: s.activeFn,
      }
    }
    case 'scan.done':
      return { ...base, scan: e.data }
    case 'trace.progress': {
      const d = e.data
      const hist = s.trace.history
      const history =
        hist.length && hist[hist.length - 1].t === d.elapsed_s ? hist : [...hist.slice(-299), { t: d.elapsed_s, calls: d.calls }]
      return { ...base, trace: { ...s.trace, ...d, history } }
    }
    case 'trace.done': {
      const d = e.data
      const functions = { ...s.functions }
      let touched = s.touched
      for (const r of d.profile) {
        const f = functions[r.id]
        if (f) {
          functions[r.id] = { ...f, share: r.share, calls: r.calls }
          touched = bump(touched, r.id)
        }
      }
      return { ...base, functions, touched, trace: { ...s.trace, calls: d.calls, done: d } }
    }
    case 'rank.done': {
      const functions = { ...s.functions }
      let touched = s.touched
      const order = e.data.ranking.map((r) => r.id).filter((id) => id in functions)
      for (const r of e.data.ranking) {
        const f = functions[r.id]
        if (f) {
          functions[r.id] = { ...f, score: r.score, status: r.status, reason: r.reason ?? f.reason }
          touched = bump(touched, r.id)
        }
      }
      const rest = s.order.filter((id) => !order.includes(id))
      return { ...base, functions, touched, ranking: e.data.ranking, order: [...order, ...rest] }
    }
    case 'fix.attempt': {
      const d = e.data
      const cur = s.fix[d.id] ?? { attempts: [], done: null }
      const prev = cur.attempts.length ? cur.attempts[cur.attempts.length - 1] : null
      const t0 = prev ? prev.at : s.fixStart[d.id]
      const x = d as unknown as { model?: string; provider?: string; latency_ms?: number }
      const lat = x.latency_ms ?? (t0 != null && e.ts > t0 ? Math.round((e.ts - t0) * 1000) : null)
      const attempts = [...cur.attempts.filter((a) => a.attempt !== d.attempt), { attempt: d.attempt, source: d.source, ok: d.ok, error: d.error, pysub: d.pysub, latency_ms: lat, model: x.model ?? null, provider: x.provider ?? null, at: e.ts }]
      return { ...base, fix: { ...s.fix, [d.id]: { ...cur, attempts } }, touched: bump(s.touched, d.id), activeFn: d.id }
    }
    case 'fix.done': {
      const d = e.data
      const cur = s.fix[d.id] ?? { attempts: [], done: null }
      const patch: Partial<FunctionSummary> = d.ok ? {} : { status: 'not_eligible', reason: d.reason ?? s.functions[d.id]?.reason ?? null }
      return { ...base, fix: { ...s.fix, [d.id]: { ...cur, done: { ok: d.ok, reason: d.reason } } }, functions: patchFn(s, d.id, patch), touched: bump(s.touched, d.id), activeFn: d.id }
    }
    case 'compile.done': {
      const d = e.data
      return {
        ...base,
        compile: { ...s.compile, [d.id]: { ok: d.ok, cached: d.cached, compile_s: d.compile_s, module: d.module, error: d.error, diagnostics: d.diagnostics } },
        touched: bump(s.touched, d.id),
        activeFn: d.id,
      }
    }
    case 'verify.result': {
      const d = e.data
      const status: Status = d.status
      return {
        ...base,
        verify: { ...s.verify, [d.id]: { status: d.status, total: d.total, matched: d.matched, first_mismatch: d.first_mismatch } },
        functions: patchFn(s, d.id, { status }),
        touched: bump(s.touched, d.id),
        activeFn: d.id,
      }
    }
    case 'bench.result': {
      const d = e.data
      return {
        ...base,
        bench: { ...s.bench, [d.id]: d },
        functions: patchFn(s, d.id, d.probe ? { probe_speedup: d.speedup } : { speedup: d.speedup }),
        touched: bump(s.touched, d.id),
        activeFn: d.id,
      }
    }
    case 'bench.e2e':
      return { ...base, e2e: e.data }
    case 'splice.ready': {
      let touched = s.touched
      for (const f of e.data.files) for (const id of f.functions) touched = bump(touched, id)
      return { ...base, splice: e.data, touched }
    }
    case 'export.done':
      return { ...base, exported: e.data }
    case 'agent.step': {
      const d = e.data
      const item: StepItem = { step_id: d.step_id, fn_id: d.fn_id, title: d.title, state: d.state, detail: d.detail, seq: e.seq, ts: e.ts }
      const fixStart = e.stage === 'fix' && d.fn_id && s.fixStart[d.fn_id] == null ? { ...s.fixStart, [d.fn_id]: e.ts } : s.fixStart
      const idx = s.steps.findIndex((x) => x.step_id === d.step_id)
      const steps = idx >= 0 ? s.steps.map((x, i) => (i === idx ? { ...item, seq: x.seq } : x)) : [...s.steps, item]
      return { ...base, steps, fixStart, activeFn: d.fn_id ?? s.activeFn }
    }
    case 'log': {
      const d = e.data
      const line: LogLine = { seq: e.seq, stream: d.stream, level: d.level, text: d.text, stage: e.stage }
      const logs = s.logs.length >= LOG_CAP ? [...s.logs.slice(-LOG_CAP + 1), line] : [...s.logs, line]
      return { ...base, logs }
    }
    case 'error':
      return { ...base, errors: [...s.errors, { ...e.data, seq: e.seq }], state: e.data.fatal ? 'failed' : s.state }
    case 'job.done': {
      return { ...base, state: e.data.state, summary: e.data.summary, activeFn: null }
    }
    default:
      return base
  }
}

export function reduceAll(events: StudioEvent[], from: JobState = initialState()): JobState {
  let st = from
  for (const e of events) st = reduce(st, e)
  return st
}

// ---------- derived helpers ----------
const finished = (st: StageInfo) => st.state === 'done' || st.state === 'failed' || st.state === 'skipped'

/** Has the run progressed far enough that artifact `key` of function `id` exists "now"? */
export function nodeSeen(js: JobState, id: string, key: JourneyKey): boolean {
  if (js.state === 'done' || js.state === 'failed' || js.state === 'cancelled') return true
  const S = js.stages
  switch (key) {
    case 'original':
    case 'eligibility':
      return id in js.functions
    case 'observed_types':
      return finished(S.trace) || finished(S.rank)
    case 'rewrites':
    case 'pysub':
      return finished(S.fix) || !!js.fix[id]?.done || (key === 'rewrites' && (js.fix[id]?.attempts.length ?? 0) > 0)
    case 'tokens':
    case 'ast':
    case 'typed_ast':
    case 'pir':
    case 'cpp':
    case 'wrapper':
    case 'build':
      return !!js.compile[id] || finished(S.compile)
    case 'replay':
      return !!js.verify[id] || finished(S.verify)
    case 'benchmark':
      return !!js.bench[id] || finished(S.benchmark)
    case 'splice':
      return !!js.splice || finished(S.splice)
    case 'status':
      return finished(S.splice) || finished(S.benchmark)
  }
}

export function topHotspot(js: JobState): string | null {
  const r = js.ranking
  if (!r) return null
  const hit = r.find((x) => x.status !== 'not_eligible' && x.status !== 'declined')
  return (hit ?? r[0])?.id ?? null
}

export function totalSpeedup(js: JobState): number | null {
  if (js.e2e?.ok) return js.e2e.speedup
  if (js.summary?.e2e_speedup) return js.summary.e2e_speedup
  if (js.summary?.geomean_speedup) return js.summary.geomean_speedup
  const sp = Object.values(js.functions)
    .filter((f) => (f.status === 'verified' || f.status === 'guarded') && f.speedup && f.speedup > 0)
    .map((f) => f.speedup as number)
  if (!sp.length) return null
  return Math.exp(sp.reduce((a, b) => a + Math.log(b), 0) / sp.length)
}

export function countStatus(js: JobState) {
  const c: Record<Status, number> = { pending: 0, verified: 0, guarded: 0, fixable: 0, not_eligible: 0, failed: 0, declined: 0 }
  for (const f of Object.values(js.functions)) c[f.status]++
  return c
}
