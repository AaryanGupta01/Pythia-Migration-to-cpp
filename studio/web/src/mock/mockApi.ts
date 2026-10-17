// In-browser implementation of the Api interface (?mock=1). Same shapes as the real server.
import type { Api } from '../api'
import type {
  Decision, EnvInfo, FunctionRecord, JobInfo, JobSummary, PlaygroundRun, RecentWorkspace, Settings, StudioEvent,
} from '../types'
import { buildProject, summaryOf, treeOf, workFile, type MockProject } from './project'
import { MOCK_JOB_ID, MOCK_WS_ID, buildScript } from './script'
import { compileForPlayground, dumpStages, interpret } from './minipy'

const wait = <T,>(v: T, ms = 60) => new Promise<T>((r) => setTimeout(() => r(v), ms))
const q = new URLSearchParams(window.location.search)

let proj: MockProject | null = null
let script: StudioEvent[] | null = null
const P = () => (proj ??= buildProject())
const S = () => (script ??= buildScript(P()))
const decisions: Record<string, Decision> = {}
const settings: Settings = { offline: true, model: 'claude-sonnet-5-5', provider: 'offline', api_key_set: false }

const jobInfo = (): JobInfo => {
  const done = S()[S().length - 1] as Extract<StudioEvent, { type: 'job.done' }>
  return { job_id: MOCK_JOB_ID, workspace_id: MOCK_WS_ID, name: 'textlab', state: 'done', options: (S()[0] as Extract<StudioEvent, { type: 'job.start' }>).data.options, started: 1000, finished: 1030, summary: done.data.summary }
}

const lcsDiff = (a: string, b: string) => ({ original: a, modified: b })

export const mockApi: Api = {
  env: () => wait<EnvInfo>({
    compiler: q.get('nocompiler') === '1'
      ? { found: false, name: null, version: null, hint: 'Install a C++17 compiler: on Ubuntu or WSL run `sudo apt install g++ python3-dev`; on macOS run `xcode-select --install`.' }
      : { found: true, name: 'g++', version: '15.2.0', hint: null },
    pybind11: true, python: '3.14.0', platform: 'linux', wsl: true,
    llm: { enabled: true, model: settings.offline ? settings.model : 'openai/gpt-oss-120b', provider: settings.offline ? 'offline-cache' : 'groq', hint: settings.offline ? 'Offline: replaying cached LLM responses' : '' },
    offline_available: true, offline: settings.offline,
  }, 30),
  getSettings: () => wait({ ...settings }, 20),
  putSettings: (p) => { Object.assign(settings, p); if (p.api_key) { settings.api_key_set = true; delete settings.api_key } return wait({ ...settings }, 20) },
  startJob: () => wait({ job_id: MOCK_JOB_ID, workspace_id: MOCK_WS_ID }, 120),
  jobs: () => wait([jobInfo()], 20),
  job: () => wait(jobInfo(), 20),
  events: (_id, after = 0) => wait({ events: S().filter((e) => e.seq > after), last_seq: S()[S().length - 1].seq }, 40),
  cancel: () => wait(undefined, 10),
  functions: () => wait(P().fns.map((m) => summaryOf(m.rec)), 30),
  fn: (_id, fid, stages = false) => {
    const m = P().byId[fid]
    if (!m) return Promise.reject(new Error(`Unknown function ${fid}`))
    const rec: FunctionRecord = { ...m.rec, decision: decisions[fid] ?? 'pending' }
    if (stages && P().stagesCache[fid]) rec.stages = P().stagesCache[fid]
    return wait(rec, 45)
  },
  decide: (_id, fid, decision) => {
    const targets = fid === 'all' ? P().fns.filter((m) => m.finalStatus === 'verified' || m.finalStatus === 'guarded').map((m) => m.rec.id) : [fid]
    for (const t of targets) decisions[t] = decision
    return wait({ functions: P().fns.map((m) => summaryOf({ ...m.rec, decision: decisions[m.rec.id] ?? 'pending' })) }, 40)
  },
  fileDiff: (_id, path) => {
    const f = P().files.find((x) => x.path === path)
    if (!f) return Promise.reject(new Error('No such file'))
    return wait(lcsDiff(f.content, workFile(P(), f, decisions)), 40)
  },
  exportProject: () => wait({ path: '/home/vishal/pythia-out/textlab-accelerated' }, 500),
  exportZipUrl: () => '#',
  report: () => {
    const rs = P().fns.map((m) => m.rec)
    const acc = rs.filter((r) => r.status === 'verified' || r.status === 'guarded')
    const md = `# PYTHIA report: textlab\n\nEnd-to-end: 14.8 s -> 2.6 s (5.7x), output identical.\n\n| function | status | speedup |\n|---|---|---|\n` + acc.map((r) => `| ${r.id} | ${r.status} | ${r.speedup}x |`).join('\n')
    return wait({ markdown: md, json: { functions: rs.length } }, 40)
  },
  recent: () => wait<RecentWorkspace[]>([
    { workspace_id: MOCK_WS_ID, name: 'textlab (demo project)', path: 'demo/textlab', job_id: MOCK_JOB_ID, opened: Date.now() / 1000 - 3600 },
    { workspace_id: 'ws000002', name: 'pyrt-playground', path: '~/code/pyrt-playground', job_id: null, opened: Date.now() / 1000 - 86400 * 2 },
  ], 20),
  tree: () => wait(treeOf(P(), decisions), 30),
  file: (_ws, path, version = 'work') => {
    const f = P().files.find((x) => x.path === path)
    if (!f) return Promise.reject(new Error(`No such file: ${path}`))
    const content = version === 'work' ? workFile(P(), f, decisions) : f.content
    return wait({ path, content, language: 'python', size: content.length }, 30)
  },
  fsList: (path) => {
    const root: Record<string, string[]> = {
      '/': ['home', 'mnt', 'tmp'],
      '/home': ['vishal'],
      '/home/vishal': ['code', 'Downloads', 'projects'],
      '/home/vishal/code': ['textlab', 'pyrt-playground', 'notes'],
      '/home/vishal/projects': ['segmenter', 'wordbench'],
    }
    const p = path && path !== '~' ? path.replace(/\/$/, '') || '/' : '/home/vishal'
    const kids = root[p] ?? []
    const parent = p === '/' ? null : p.split('/').slice(0, -1).join('/') || '/'
    return wait({ path: p, parent, entries: [...kids.map((n) => ({ name: n, type: 'dir' as const })), ...(p.endsWith('textlab') ? [{ name: 'main.py', type: 'file' as const }] : [])] }, 40)
  },
  pgCompile: (source) => wait(compileForPlayground(source), 120),
  pgRun: (source) => {
    const r = interpret(source)
    const c = compileForPlayground(source)
    if (!c.ok) return wait<PlaygroundRun>({ ok: false, error: c.diagnostics[0]?.msg ?? 'compile failed', python: { stdout: r.stdout, exception: r.exception, time_ms: 0 }, cpp: { stdout: '', exception: null, time_ms: 0 }, same: false }, 200)
    const py = Math.max(0.05, r.steps * 0.00035)
    return wait<PlaygroundRun>({
      ok: true,
      python: { stdout: r.stdout, exception: r.exception, time_ms: Math.round(py * 100) / 100 },
      cpp: { stdout: r.stdout, exception: r.exception, time_ms: Math.round(Math.max(0.01, py / 31) * 100) / 100 },
      same: true,
    }, 350)
  },
  stages: (source) => wait(dumpStages(source), 80),
  upload: () => wait({ job_id: MOCK_JOB_ID, workspace_id: MOCK_WS_ID }, 200),
  subscribe(_id, after, onEvent, onClose) {
    let cancelled = false
    queueMicrotask(() => {
      for (const e of S()) { if (cancelled) return; if (e.seq > after) onEvent(e) }
      onClose('done')
    })
    return () => { cancelled = true }
  },
}

export type { JobSummary }
