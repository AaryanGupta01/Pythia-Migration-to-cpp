import type {
  DemoInfo,
  EnvInfo,
  FileContent,
  FsList,
  FunctionRecord,
  FunctionSummary,
  JobInfo,
  JobInput,
  JobOptions,
  PlaygroundCompile,
  PlaygroundRun,
  PlaygroundConvert,
  ConvertStatus,
  RecentWorkspace,
  ReportData,
  Settings,
  StageDump,
  StudioEvent,
  TreeNode,
  Decision,
} from './types'

export const query = new URLSearchParams(window.location.search)
export const IS_MOCK = query.get('mock') === '1'

export interface Api {
  env(): Promise<EnvInfo>
  /** optional: not every server has it; callers feature-detect */
  demos?(): Promise<DemoInfo[]>
  getSettings(): Promise<Settings>
  putSettings(patch: Partial<Settings>): Promise<Settings>
  testKey(provider: string, api_key: string): Promise<{ ok: boolean; provider: string; model?: string; error?: string }>
  doctor(): Promise<{ ready: boolean; checks: { id: string; label: string; ok: boolean; required: boolean; detail: string; hint: string | null }[] }>
  startJob(input: JobInput, options: Partial<JobOptions>): Promise<{ job_id: string; workspace_id: string }>
  jobs(): Promise<JobInfo[]>
  job(id: string): Promise<JobInfo>
  events(id: string, after?: number): Promise<{ events: StudioEvent[]; last_seq: number }>
  cancel(id: string): Promise<void>
  functions(id: string): Promise<FunctionSummary[]>
  fn(id: string, fid: string, stages?: boolean): Promise<FunctionRecord>
  decide(id: string, fid: string, decision: Decision): Promise<{ functions: FunctionSummary[] }>
  fileDiff(id: string, path: string): Promise<{ original: string; modified: string }>
  exportProject(id: string, dest?: string, zip?: boolean): Promise<{ path: string }>
  exportZipUrl(id: string): string
  report(id: string): Promise<ReportData>
  recent(): Promise<RecentWorkspace[]>
  tree(ws: string): Promise<TreeNode[]>
  file(ws: string, path: string, version?: 'work' | 'original'): Promise<FileContent>
  fsList(path: string): Promise<FsList>
  pgCompile(source: string): Promise<PlaygroundCompile>
  pgRun(source: string, stdin?: string, reference?: string): Promise<PlaygroundRun>
  pgConvert(source: string): Promise<PlaygroundConvert>
  pgConvertStatus(): Promise<ConvertStatus>
  stages(source: string): Promise<StageDump>
  upload(file: File): Promise<{ job_id: string; workspace_id: string }>
  /** Subscribe to a job's event stream (backlog + live). Returns unsubscribe. */
  subscribe(
    id: string,
    after: number,
    onEvent: (e: StudioEvent) => void,
    onClose: (reason: 'done' | 'error') => void,
  ): () => void
}

class HttpError extends Error {
  status: number
  constructor(status: number, msg: string) {
    super(msg)
    this.status = status
  }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, init)
  } catch {
    throw new HttpError(0, 'Cannot reach the PYTHIA server. Is it running on port 8765?')
  }
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`
    try {
      const j = await res.json()
      if (j?.error) msg = j.error
    } catch {
      /* ignore */
    }
    throw new HttpError(res.status, msg)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})
const q = (o: Record<string, string | number | boolean | undefined>) =>
  Object.entries(o)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join('&')

export const realApi: Api = {
  env: () => http('/env'),
  demos: () => http('/demos'),
  getSettings: () => http('/settings'),
  putSettings: (p) => http('/settings', { ...json(p), method: 'PUT' }),
  testKey: (provider, api_key) => http('/settings/test-key', json({ provider, api_key })),
  doctor: () => http('/doctor'),
  startJob: (input, options) => http('/jobs', json({ input, options })),
  jobs: () => http('/jobs'),
  job: (id) => http(`/jobs/${id}`),
  events: (id, after = 0) => http(`/jobs/${id}/events?after=${after}`),
  cancel: (id) => http(`/jobs/${id}/cancel`, { method: 'POST' }),
  functions: (id) => http(`/jobs/${id}/functions`),
  fn: (id, fid, stages = false) => http(`/jobs/${id}/function?${q({ id: fid, stages: stages ? 1 : 0 })}`),
  decide: (id, fid, decision) => http(`/jobs/${id}/decision`, json({ id: fid, decision })),
  fileDiff: (id, path) => http(`/jobs/${id}/file-diff?${q({ path })}`),
  exportProject: (id, dest, zip) => http(`/jobs/${id}/export`, json({ dest, zip })),
  exportZipUrl: (id) => `/api/jobs/${id}/export.zip`,
  report: (id) => http(`/jobs/${id}/report`),
  recent: () => http('/workspaces/recent'),
  tree: (ws) => http(`/workspaces/${ws}/tree`),
  file: (ws, path, version = 'work') => http(`/workspaces/${ws}/file?${q({ path, version })}`),
  fsList: (path) => http(`/fs/list?${q({ path })}`),
  pgCompile: (source) => http('/playground/compile', json({ source })),
  pgRun: (source, stdin, reference) => http('/playground/run', json({ source, stdin: stdin ?? '', reference: reference ?? null })),
  pgConvert: (source) => http('/playground/convert', json({ source })),
  pgConvertStatus: () => http('/playground/convert/status'),
  stages: (source) => http('/stages', json({ source })),
  upload: async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return http('/upload', { method: 'POST', body: fd })
  },
  subscribe(id, after, onEvent, onClose) {
    let closed = false
    let ws: WebSocket | null = null
    let last = after
    let retries = 0
    const open = () => {
      if (closed) return
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/api/jobs/${id}/ws?after=${last}`)
      ws.onmessage = (m) => {
        try {
          const e = JSON.parse(m.data) as StudioEvent
          if (e.seq <= last && last > 0 && e.seq !== 0) return // dedupe backlog/live overlap
          last = Math.max(last, e.seq)
          retries = 0
          onEvent(e)
        } catch {
          /* ignore malformed */
        }
      }
      ws.onclose = () => {
        if (closed) return
        // Server closes after job.done; if it closed early, resume from `last`.
        if (retries++ < 5) setTimeout(open, 400 * retries)
        else onClose('error')
      }
      ws.onerror = () => ws?.close()
    }
    open()
    return () => {
      closed = true
      ws?.close()
    }
  },
}

// Lazily bound so the mock module is only loaded (and tree-shaken otherwise) in ?mock=1.
let _api: Api = realApi
export const api: Api = new Proxy({} as Api, {
  get: (_t, k: string) => (_api as unknown as Record<string, unknown>)[k],
})
export function useMockApi(m: Api) {
  _api = m
}

export const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e))
