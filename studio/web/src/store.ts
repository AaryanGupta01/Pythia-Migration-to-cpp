import { create } from 'zustand'
import { api, errMsg, IS_MOCK, query } from './api'
import { Player } from './player'
import { initialState, reduceAll, topHotspot, type JobState } from './reducer'
import type { Decision, EnvInfo, FunctionRecord, JobInfo, JobInput, JobOptions, RecentWorkspace, Settings, StageName, StudioEvent } from './types'

export type TabKind = 'welcome' | 'file' | 'function' | 'stage' | 'playground' | 'report' | 'settings'
export interface Tab {
  id: string
  kind: TabKind
  title: string
  ref?: string
  line?: number
}
export type FnView = 'diff' | 'three' | 'journey'
export type BottomTab = 'terminal' | 'problems' | 'fidelity' | 'benchmarks'
export type SideView = 'explorer' | 'hotspots'
export type Speed = 0.5 | 1 | 2 | 4 | 0 // 0 = as fast as possible

export interface Toast {
  id: number
  text: string
  kind: 'info' | 'ok' | 'error'
}

const LS = {
  get<T>(k: string, d: T): T {
    try {
      const v = localStorage.getItem('pythia:' + k)
      return v == null ? d : (JSON.parse(v) as T)
    } catch {
      return d
    }
  },
  set(k: string, v: unknown) {
    try {
      localStorage.setItem('pythia:' + k, JSON.stringify(v))
    } catch {
      /* private mode */
    }
  },
}

interface UIState {
  theme: 'dark' | 'light'
  sideView: SideView
  sideOpen: boolean
  agentOpen: boolean
  bottomOpen: boolean
  bottomTab: BottomTab
  sizes: { side: number; agent: number; bottom: number }
  tabs: Tab[]
  activeTab: string
  paletteOpen: boolean
  quickOpen: boolean
  presenter: boolean
  speed: Speed
  fnViews: Record<string, FnView>
  toasts: Toast[]
  dragging: boolean

  env: EnvInfo | null
  envError: string | null
  settings: Settings | null
  recent: RecentWorkspace[]
  jobs: JobInfo[]

  js: JobState
  starting: boolean
  startError: string | null
  replaying: boolean
  playerInfo: { paused: boolean; pending: number; mode: 'instant' | 'paced' }
  /** bumped whenever decisions or accepted state change so views refetch */
  rev: number
  records: Record<string, FunctionRecord>
}

interface Actions {
  set: (p: Partial<UIState>) => void
  setTheme: (t: 'dark' | 'light') => void
  openTab: (t: Tab, opts?: { activate?: boolean }) => void
  closeTab: (id: string) => void
  setActive: (id: string) => void
  openFunction: (id: string, view?: FnView) => void
  openFile: (path: string, line?: number) => void
  openStage: (s: StageName) => void
  openSpecial: (k: 'playground' | 'report' | 'settings' | 'welcome') => void
  toast: (text: string, kind?: Toast['kind']) => void
  loadEnv: () => Promise<void>
  loadRecent: () => Promise<void>
  startJob: (input: JobInput, options?: Partial<JobOptions>) => Promise<void>
  openJob: (id: string, o?: { replay?: boolean }) => Promise<void>
  replayCurrent: () => Promise<void>
  setPresenter: (v: boolean) => void
  setSpeed: (s: Speed) => void
  togglePause: () => void
  stepBeat: () => void
  decide: (id: string, d: Decision) => Promise<void>
  fetchRecord: (id: string, force?: boolean) => Promise<FunctionRecord | null>
  closeJob: () => void
}

let unsub: (() => void) | null = null
let player: Player
let lastRun: { input: JobInput; options?: Partial<JobOptions> } | null = null
export const getLastRun = () => lastRun

export const useStudio = create<UIState & Actions>((set, get) => {
  player = new Player(
    (batch: StudioEvent[]) => set((s) => ({ js: reduceAll(batch, s.js) })),
    () => set({ playerInfo: { paused: player.paused, pending: player.pending, mode: player.mode } }),
  )
  const presenter0 = query.get('presenter') === '1'
  const theme0 = LS.get<'dark' | 'light'>('theme', 'dark')
  document.documentElement.dataset.theme = theme0
  return {
    theme: theme0,
    sideView: 'explorer',
    sideOpen: false,
    agentOpen: false,
    bottomOpen: false,
    bottomTab: 'terminal',
    sizes: LS.get('sizes', { side: 252, agent: 316, bottom: 210 }),
    tabs: [{ id: 'welcome', kind: 'welcome', title: 'Welcome' }],
    activeTab: 'welcome',
    paletteOpen: false,
    quickOpen: false,
    presenter: presenter0,
    speed: LS.get<Speed>('speed', 1),
    fnViews: {},
    toasts: [],
    dragging: false,
    env: null,
    envError: null,
    settings: null,
    recent: [],
    jobs: [],
    js: initialState(),
    starting: false,
    startError: null,
    replaying: false,
    playerInfo: { paused: false, pending: 0, mode: 'instant' },
    rev: 0,
    records: {},

    set: (p) => {
      set(p)
      if (p.sizes) LS.set('sizes', p.sizes)
      if (p.agentOpen !== undefined) LS.set('agentOpen', p.agentOpen)
    },
    setTheme: (t) => {
      document.documentElement.dataset.theme = t
      LS.set('theme', t)
      set({ theme: t })
    },
    openTab: (t, o) => {
      set((s) => ({
        tabs: s.tabs.some((x) => x.id === t.id) ? s.tabs.map((x) => (x.id === t.id ? { ...x, ...t } : x)) : [...s.tabs, t],
        activeTab: o?.activate === false ? s.activeTab : t.id,
      }))
    },
    closeTab: (id) => {
      set((s) => {
        const i = s.tabs.findIndex((x) => x.id === id)
        let tabs = s.tabs.filter((x) => x.id !== id)
        if (!tabs.length) tabs = [{ id: 'welcome', kind: 'welcome', title: 'Welcome' }]
        const activeTab = s.activeTab === id ? tabs[Math.min(i, tabs.length - 1)].id : s.activeTab
        return { tabs, activeTab }
      })
    },
    setActive: (id) => set({ activeTab: id }),
    openFunction: (id, view) => {
      const s = get()
      const f = s.js.functions[id]
      const title = f ? f.name : id.split('::').pop() ?? id
      if (view) set((st) => ({ fnViews: { ...st.fnViews, [id]: view } }))
      s.openTab({ id: `fn:${id}`, kind: 'function', title, ref: id })
    },
    openFile: (path, line) => get().openTab({ id: `file:${path}`, kind: 'file', title: path.split('/').pop() ?? path, ref: path, line }),
    openStage: (st) => get().openTab({ id: `stage:${st}`, kind: 'stage', title: st[0].toUpperCase() + st.slice(1), ref: st }),
    openSpecial: (k) => {
      const titles = { playground: 'Playground', report: 'Report', settings: 'Settings', welcome: 'Welcome' }
      get().openTab({ id: k, kind: k, title: titles[k] })
    },
    toast: (text, kind = 'info') => {
      const id = Date.now() + Math.random()
      set((s) => ({ toasts: [...s.toasts.slice(-3), { id, text, kind }] }))
      setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), kind === 'error' ? 6500 : 3200)
    },
    loadEnv: async () => {
      try {
        const [env, settings] = await Promise.all([api.env(), api.getSettings().catch(() => null)])
        set({ env, settings, envError: null })
      } catch (e) {
        set({ envError: errMsg(e) })
      }
    },
    loadRecent: async () => {
      try {
        const [recent, jobs] = await Promise.all([api.recent().catch(() => []), api.jobs().catch(() => [])])
        set({ recent, jobs })
      } catch {
        /* optional */
      }
    },

    startJob: async (input, options = {}) => {
      const s = get()
      lastRun = { input, options }
      set({ starting: true, startError: null })
      try {
        const opts: Partial<JobOptions> = { offline: s.env?.offline ?? s.settings?.offline ?? false, llm: true, ...options }
        if (s.presenter || IS_MOCK) opts.pace_ms = opts.pace_ms ?? 0
        const r = await api.startJob(input, opts)
        attach(r.job_id, get, set, { live: true })
        set({ starting: false })
        get().loadRecent()
      } catch (e) {
        set({ starting: false, startError: errMsg(e) })
        get().toast(errMsg(e), 'error')
      }
    },
    openJob: async (id, o) => {
      try {
        const info = await api.job(id)
        if (info.state === 'running') attach(id, get, set, { live: true })
        else await attachSaved(id, get, set, !!o?.replay)
      } catch (e) {
        get().toast(errMsg(e), 'error')
      }
    },
    replayCurrent: async () => {
      const id = get().js.jobId
      if (id) await attachSaved(id, get, set, true)
    },
    setPresenter: (v) => {
      set({ presenter: v })
      player.configure({ presenter: v, mode: v || IS_MOCK || get().replaying ? 'paced' : 'instant' })
      if (!v) player.setPaused(false)
    },
    setSpeed: (sp) => {
      LS.set('speed', sp)
      set({ speed: sp })
      applySpeed(get)
    },
    togglePause: () => player.setPaused(!player.paused),
    stepBeat: () => player.stepBeat(),

    decide: async (id, d) => {
      const jobId = get().js.jobId
      if (!jobId) return
      try {
        const r = await api.decide(jobId, id, d)
        set((s) => {
          const fns = { ...s.js.functions }
          for (const f of r.functions) if (f.id in fns) fns[f.id] = { ...fns[f.id], ...f }
          return { js: { ...s.js, functions: fns }, rev: s.rev + 1 }
        })
        get().toast(id === 'all' ? (d === 'accepted' ? 'Accepted every verified function' : d === 'rejected' ? 'Rejected every function' : 'Reset decisions') : `${id.split('::').pop()}: ${d}`, 'ok')
      } catch (e) {
        get().toast(errMsg(e), 'error')
      }
    },
    fetchRecord: async (id, force) => {
      const s = get()
      if (!s.js.jobId) return null
      if (!force && s.records[id]) return s.records[id]
      try {
        const rec = await api.fn(s.js.jobId, id, true)
        set((st) => ({ records: { ...st.records, [id]: rec } }))
        return rec
      } catch (e) {
        get().toast(errMsg(e), 'error')
        return null
      }
    },
    closeJob: () => {
      unsub?.()
      unsub = null
      player.clear()
      set({ js: initialState(), records: {}, replaying: false, tabs: [{ id: 'welcome', kind: 'welcome', title: 'Welcome' }], activeTab: 'welcome' })
    },
  }
})

function applySpeed(get: () => UIState & Actions) {
  const { speed, presenter, replaying } = get()
  const paced = presenter || IS_MOCK || replaying
  if (speed === 0) player.configure({ mode: 'instant', presenter })
  else player.configure({ mode: paced ? 'paced' : 'instant', speed, presenter })
  if (speed === 0 && player.pending) player.flush()
}

type G = () => UIState & Actions
type SetFn = (p: Partial<UIState> | ((s: UIState) => Partial<UIState>)) => void

function resetForJob(set: SetFn, jobId: string) {
  unsub?.()
  unsub = null
  player.clear()
  set({
    js: { ...initialState(), jobId, state: 'running' },
    records: {},
    tabs: [{ id: 'welcome', kind: 'welcome', title: 'Welcome' }],
    activeTab: 'welcome',
    startError: null,
  })
}

function attach(jobId: string, get: G, set: SetFn, o: { live: boolean }) {
  resetForJob(set, jobId)
  set({ replaying: false })
  applySpeed(get)
  player.setPaused(false)
  unsub = api.subscribe(
    jobId,
    0,
    (e) => player.push(e),
    () => {
      /* socket closed after job.done */
    },
  )
  void o
}

async function attachSaved(jobId: string, get: G, set: SetFn, replay: boolean) {
  resetForJob(set, jobId)
  set({ replaying: replay })
  player.setPaused(false)
  try {
    const r = await api.events(jobId, 0)
    if (replay) {
      applySpeed(get)
      player.configure({ mode: 'paced' })
    } else player.configure({ mode: 'instant' })
    player.push(r.events)
    if (!replay) player.flush()
  } catch (e) {
    get().toast(errMsg(e), 'error')
  }
}

export const getPlayer = () => player
;(window as unknown as { __studio: unknown }).__studio = useStudio
export { topHotspot }
