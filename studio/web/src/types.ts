// Mirrors studio/CONTRACTS.md exactly (snake_case, JSON-shaped). Do not rename fields.

export type Status =
  | 'pending'
  | 'verified'
  | 'guarded'
  | 'fixable'
  | 'not_eligible'
  | 'failed'
  | 'declined'
export type Eligibility = 'verifiable' | 'fixable' | 'not_eligible'
export type Decision = 'pending' | 'accepted' | 'rejected'
export type Severity = 'exact' | 'guarded' | 'divergent'

export const STAGES = [
  'ingest',
  'scan',
  'trace',
  'rank',
  'fix',
  'compile',
  'verify',
  'benchmark',
  'splice',
  'export',
] as const
export type StageName = (typeof STAGES)[number]
export type StageState = 'idle' | 'running' | 'done' | 'failed' | 'skipped'

export const JOURNEY_KEYS = [
  'original',
  'observed_types',
  'eligibility',
  'rewrites',
  'pysub',
  'tokens',
  'ast',
  'typed_ast',
  'pir',
  'cpp',
  'wrapper',
  'build',
  'replay',
  'benchmark',
  'splice',
  'status',
] as const
export type JourneyKey = (typeof JOURNEY_KEYS)[number]

export interface Score {
  total: number
  trace_share: number | null
  static_heuristic: number | null
  eligibility_factor: number | null
  expected_benefit: number | null
  boundary_penalty: number | null
  basis: 'trace' | 'static'
  notes: string[]
}

export interface FunctionSummary {
  id: string
  file: string
  name: string
  qualname: string
  line: number
  end_line: number
  col: number
  status: Status
  eligibility: Eligibility
  reason: string | null
  decision: Decision
  score: Score
  share: number | null
  calls: number | null
  speedup: number | null
  probe_speedup?: number | null
}

export interface FnMetrics {
  size_lines: number
  loop_depth: number
  arith_density: number
  calls: string[]
  imports: string[]
  uses_globals: string[]
}

export interface FnTrace {
  calls: number
  cum_s: number
  self_s: number
  share: number
  arg_types: string[]
  ret_type: string
  samples: number
  avg_arg_elems: number
  avg_ret_elems: number
}

export interface Rewrite {
  attempt: number
  source: 'api' | 'cache'
  pysub: string
  error: string | null
  ok: boolean
}

export interface Diagnostic {
  line: number
  col: number
  kind: string
  msg: string
  phase?: 'eligibility' | 'fix' | 'compile'
}

export interface FidelityNote {
  line: number
  col: number
  cls: string
  detail: string
  mitigation: string
  severity: Severity
}

export interface BuildInfo {
  ok: boolean
  module: string
  so: string
  cached: boolean
  compile_s: number
  log: string
}

export interface Mismatch {
  args: string
  python: string
  cpp: string
  kind: 'value' | 'exception' | 'mutation'
}

export interface ReplayInfo {
  total: number
  matched: number
  exc_matches: number
  first_mismatch: Mismatch | null
}

export interface BenchInfo {
  py_ms: number
  cpp_ms: number
  speedup: number
  calls_timed: number
  repeats: number
}

export interface JourneyNode {
  key: JourneyKey
  title: string
  state: 'done' | 'failed' | 'skipped' | 'pending'
  summary: string
  reason: string | null
}

export interface TreeNodeT {
  t: string
  line: number
  col: number
  ty: string | null
  attrs?: Record<string, unknown>
  kids?: Record<string, TreeNodeT | TreeNodeT[]>
}
export interface Token {
  kind: string
  value: string
  line: number
  col: number
}
export interface StageDump {
  ok: boolean
  diagnostics: Diagnostic[]
  tokens: Token[]
  ast: TreeNodeT | null
  typed_ast: TreeNodeT | null
  pir: TreeNodeT | null
  cpp: string
  fidelity: FidelityNote[]
  guard_elision?: { elided: number; kept: number }
}

export interface FunctionRecord extends FunctionSummary {
  metrics: FnMetrics
  trace: FnTrace | null
  sources: {
    original: string
    annotated: string | null
    pysub: string | null
    cpp: string | null
    wrapper_cpp: string | null
  }
  line_map_ok: boolean
  cpp_line_map: Record<string, number[]>
  rewrites: Rewrite[]
  diagnostics: Diagnostic[]
  fidelity: FidelityNote[]
  build: BuildInfo | null
  replay: ReplayInfo | null
  bench: BenchInfo | null
  splice: { applied: boolean; diff: string } | null
  journey: JourneyNode[]
  stages?: StageDump
}

// ---------- Events (§4) ----------
export interface EventEnvelope<T = string, D = Record<string, unknown>> {
  seq: number
  ts: number
  type: T
  stage: StageName | null
  caption: string | null
  data: D
}

export interface FileDigest {
  path: string
  functions: string[]
}

export interface RankRow {
  id: string
  rank: number
  score: Score
  status: Status
  reason: string | null
}

export interface ProfileRow {
  id: string
  calls: number
  cum_s: number
  share: number
}

export interface JobSummary {
  functions: number
  verified: number
  guarded: number
  fixable: number
  not_eligible: number
  failed: number
  declined: number
  e2e_speedup: number | null
  geomean_speedup: number | null
}

export type StudioEvent =
  | EventEnvelope<'job.start', { job_id: string; workspace_id: string; name: string; input_kind: string; options: JobOptions }>
  | EventEnvelope<'stage', { stage: StageName; state: StageState; summary: string | null; progress: number | null }>
  | EventEnvelope<'ingest.progress', { phase: 'copy' | 'clone' | 'index'; files: number; bytes: number; current: string | null; message: string }>
  | EventEnvelope<'ingest.done', { workspace_id: string; name: string; files: number; py_files: number; skipped: { path: string; reason: string }[] }>
  | EventEnvelope<'scan.function', { function: FunctionSummary }>
  | EventEnvelope<'scan.done', { functions: number; verifiable: number; fixable: number; not_eligible: number }>
  | EventEnvelope<'trace.progress', { calls: number; functions_seen: number; elapsed_s: number; stdout_tail: string }>
  | EventEnvelope<'trace.done', { total_s: number; exit_code: number; timed_out: boolean; calls: number; profile: ProfileRow[] }>
  | EventEnvelope<'rank.done', { ranking: RankRow[] }>
  | EventEnvelope<'fix.attempt', { id: string; attempt: number; source: 'api' | 'cache'; ok: boolean; error: string | null; pysub: string }>
  | EventEnvelope<'fix.done', { id: string; ok: boolean; reason: string | null }>
  | EventEnvelope<'compile.done', { id: string; ok: boolean; cached: boolean; compile_s: number; module: string; error: string | null; diagnostics: Diagnostic[] }>
  | EventEnvelope<'verify.result', { id: string; status: 'verified' | 'guarded' | 'failed'; total: number; matched: number; first_mismatch: Mismatch | null }>
  | EventEnvelope<'bench.result', { id: string; py_ms: number; cpp_ms: number; speedup: number; calls_timed: number; probe: boolean }>
  | EventEnvelope<'bench.e2e', { cmd: string; before_s: number; after_s: number; speedup: number; output_match: boolean; ok: boolean }>
  | EventEnvelope<'splice.ready', { files: FileDigest[]; functions: number }>
  | EventEnvelope<'export.done', { path: string; zip: boolean; files: number }>
  | EventEnvelope<'agent.step', { step_id: string; fn_id: string | null; title: string; state: 'running' | 'done' | 'failed' | 'info'; detail: string | null }>
  | EventEnvelope<'log', { stream: 'build' | 'trace' | 'system'; level: 'info' | 'warn' | 'error'; text: string }>
  | EventEnvelope<'error', { where: string; message: string; fatal: boolean }>
  | EventEnvelope<'job.done', { state: 'done' | 'failed' | 'cancelled'; summary: JobSummary }>

export type EventType = StudioEvent['type']

// ---------- REST ----------
export interface JobOptions {
  trace_cmd: string | null
  trace_timeout_s: number
  offline: boolean
  llm: boolean
  model: string
  pace_ms: number
}

export type JobInput =
  | { kind: 'snippet'; code: string; name?: string }
  | { kind: 'file'; filename: string; content_b64: string }
  | { kind: 'folder'; path: string }
  | { kind: 'git'; url: string }
  | { kind: 'demo'; name?: string }

export interface DemoInfo {
  name: string
  title?: string
  files?: number
  lines?: number
  description?: string
  functions?: number
  [k: string]: unknown
}

export interface EnvInfo {
  compiler: { found: boolean; name: string | null; version: string | null; hint: string | null }
  pybind11: boolean
  python: string
  platform: string
  llm: { enabled: boolean; model: string; hint: string | null; provider?: 'groq' | 'anthropic' | 'offline-cache' | null }
  offline_available: boolean
  offline: boolean
  wsl: boolean
}

export interface JobInfo {
  job_id: string
  workspace_id: string
  name: string
  state: 'running' | 'done' | 'failed' | 'cancelled'
  options: JobOptions
  started: number | null
  finished: number | null
  summary: JobSummary | null
  sample?: boolean
}

export interface RecentWorkspace {
  workspace_id: string
  name: string
  path?: string
  job_id?: string | null
  opened?: number | null
  [k: string]: unknown
}

export interface TreeNode {
  path: string
  name: string
  type: 'dir' | 'file'
  children?: TreeNode[]
  badges?: { hotspots: number; accelerated: number }
}

export interface FileContent {
  path: string
  content: string
  language: string
  size: number
}

export interface FsList {
  path: string
  parent: string | null
  entries: { name: string; type: 'dir' | 'file' }[]
}

export interface Settings {
  offline: boolean
  model: string
  provider?: 'auto' | 'groq' | 'anthropic' | 'offline'
  api_key_set?: boolean
  api_key?: string
  [k: string]: unknown
}

export interface PlaygroundCompile {
  ok: boolean
  cpp: string
  diagnostics: Diagnostic[]
  fidelity: FidelityNote[]
  cpp_line_map: Record<string, number[]>
}
export interface RunSide {
  stdout: string
  exception: string | null
  time_ms: number
}
export interface ConvertAttempt {
  attempt: number
  ok: boolean
  source: string | null
  diagnostics: Diagnostic[]
  latency_ms: number
  error?: string | null
}
export interface PlaygroundConvert {
  ok: boolean
  already?: boolean
  source?: string
  attempts: ConvertAttempt[]
  error?: string
  provider?: string | null
  model?: string | null
}
export interface ConvertStatus {
  enabled: boolean
  provider: string | null
  model: string | null
  hint: string | null
}
export interface PlaygroundRun {
  ok: boolean
  python: RunSide
  cpp: RunSide
  same: boolean
  error?: string
}
export interface ReportData {
  markdown: string
  json: Record<string, unknown>
}
