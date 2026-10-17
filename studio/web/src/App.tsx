import { Component, useCallback, useEffect, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Pause, Upload } from 'lucide-react'
import { api, IS_MOCK, query } from './api'
import { getLastRun, getPlayer, runAuto, useStudio } from './store'
import { topHotspot } from './reducer'
import { ActivityBar, Breadcrumbs, StatusBar, Stepper, TabsBar, TitleBar } from './shell'
import { ShortcutsSheet } from './sheets'
import { ContextMenu, SidePanel } from './sidepanel'
import { AgentPanel } from './agent'
import { BottomPanel } from './bottom'
import { Welcome } from './welcome'
import { FunctionView } from './fnview'
import { StageInspector } from './stages'
import { FileView, Playground, Report, SettingsPage } from './pages'
import { Palette } from './palette'
import { Btn, Splitter, Kbd, isMac } from './ui'
import { fileToB64, cn } from './lib/format'
import type { StageName } from './types'

class Boundary extends Component<{ children: ReactNode; k: string }, { err: Error | null; k: string }> {
  state = { err: null as Error | null, k: this.props.k }
  static getDerivedStateFromError(err: Error) {
    return { err }
  }
  static getDerivedStateFromProps(p: { k: string }, s: { k: string }) {
    return p.k !== s.k ? { err: null, k: p.k } : null
  }
  render() {
    if (!this.state.err) return this.props.children
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
        <div className="text-base">This view hit an error</div>
        <div className="mono max-w-[560px] text-xs text-fg3">{this.state.err.message}</div>
        <Btn onClick={() => this.setState({ err: null })}>Try again</Btn>
      </div>
    )
  }
}

let booted = false

export default function App() {
  const s = useStudio()
  const { tabs, activeTab } = s
  const [vw, setVw] = useState(window.innerWidth)
  const [vh, setVh] = useState(window.innerHeight)
  useEffect(() => {
    const h = () => {
      setVw(window.innerWidth)
      setVh(window.innerHeight)
    }
    window.addEventListener('resize', h)
    return () => window.removeEventListener('resize', h)
  }, [])
  // narrow windows get slimmer panels so the editor keeps room
  const sizes = { ...(vw < 1240 ? { ...s.sizes, side: Math.min(s.sizes.side, 232), agent: Math.min(s.sizes.agent, 296) } : s.sizes) }
  if (vh < 800) sizes.bottom = Math.min(sizes.bottom, 168)
  const playgroundVisited = tabs.some((t) => t.kind === 'playground')

  // ------- boot
  useEffect(() => {
    s.loadEnv()
    s.loadRecent()
    if (booted) return // StrictMode runs effects twice in dev; start the run once
    booted = true
    const job = query.get('job')
    if (job) s.openJob(job, { replay: query.get('replay') === '1' || query.get('presenter') === '1' })
    else if (query.get('autostart') === '1') s.startJob({ kind: 'demo' })
    const h = location.hash.replace(/^#\/?/, '')
    if (['playground', 'report', 'settings'].includes(h)) s.openSpecial(h as 'playground')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    const t = tabs.find((x) => x.id === activeTab)
    const h = t ? (t.kind === 'function' ? `fn/${encodeURIComponent(t.ref ?? '')}` : t.kind === 'stage' ? `stage/${t.ref}` : t.kind === 'file' ? `file/${t.ref}` : t.kind === 'welcome' ? '' : t.kind) : ''
    history.replaceState(null, '', `${location.pathname}${location.search}${h ? '#/' + h : ''}`)
  }, [activeTab, tabs])

  // ------- follow the run (normal mode and presenter mode)
  const openAuto = useCallback((id: string, open: () => void) => {
    if (useStudio.getState().activeTab === id) return
    runAuto(open)
  }, [])
  const jobId = s.js.jobId
  useEffect(() => {
    if (!jobId) return
    useStudio.getState().closeTab('welcome')
    useStudio.getState().set({ agentOpen: window.innerWidth >= 1180, bottomOpen: false, bottomTab: 'terminal' })
    runAuto(() => useStudio.getState().openStage('ingest'))
  }, [jobId])
  // bottom panel: stays collapsed while empty, opens on the first log line, shows Benchmarks when the run finishes
  const nLogs = s.js.logs.length
  useEffect(() => {
    if (nLogs > 0 && nLogs < 3 && jobId) useStudio.getState().set({ bottomOpen: true, bottomTab: 'terminal' })
  }, [nLogs > 0, jobId])
  const runState = s.js.state
  useEffect(() => {
    if (runState === 'done' && !s.replaying && Object.keys(useStudio.getState().js.bench).length) useStudio.getState().set({ bottomOpen: true, bottomTab: 'benchmarks' })
  }, [runState])
  useEffect(() => {
    document.title = s.js.name ? `PYTHIA Studio — ${s.js.name}` : 'PYTHIA Studio'
  }, [s.js.name])
  useEffect(() => {
    if (s.js.scan) s.set({ sideOpen: true, sideView: 'hotspots' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [!!s.js.scan, jobId])
  const stage = s.js.activeStage
  useEffect(() => {
    if (!stage || !(s.presenter || s.following)) return
    openAuto(`stage:${stage}`, () => useStudio.getState().openStage(stage))
  }, [stage, s.presenter, s.following, openAuto])
  const fn = s.js.activeFn
  const fnTouched = fn ? s.js.touched[fn] ?? 0 : 0
  const interesting = useCallback(
    (id: string) => {
      const js = useStudio.getState().js
      if (id === topHotspot(js)) return true
      if (js.fix[id]) return true
      const rank = js.ranking?.findIndex((r) => r.id === id) ?? -1
      return rank >= 0 && rank < 8 && js.functions[id]?.eligibility !== 'not_eligible'
    },
    [],
  )
  useEffect(() => {
    if (!s.presenter || !fn || !s.js.ranking || s.js.e2e) return
    const idx = ['fix', 'compile', 'verify', 'benchmark'].indexOf(s.js.activeStage ?? '')
    if (idx < 0 || !interesting(fn)) return
    openAuto(`fn:${fn}`, () => useStudio.getState().openFunction(fn, 'journey'))
  }, [fn, fnTouched, s.presenter, s.js.ranking, s.js.e2e, s.js.activeStage, interesting, openAuto])
  useEffect(() => {
    if (s.presenter && s.js.e2e) openAuto('stage:benchmark', () => useStudio.getState().openStage('benchmark' as StageName))
  }, [!!s.js.e2e, s.presenter, openAuto])

  // ------- keyboard
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = isMac ? e.metaKey : e.ctrlKey
      const t = e.target as HTMLElement
      const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable || t.closest?.('.monaco-editor'))
      const st = useStudio.getState()
      if (mod && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        st.set({ paletteOpen: !st.paletteOpen, quickOpen: false })
      } else if (mod && e.key.toLowerCase() === 'p' && !e.shiftKey) {
        e.preventDefault()
        st.set({ quickOpen: !st.quickOpen, paletteOpen: false })
      } else if (mod && e.key === 'Enter') {
        e.preventDefault()
        if (st.activeTab === 'playground') window.dispatchEvent(new Event('pythia:run'))
        else window.dispatchEvent(new Event('pythia:rerun'))
      } else if (mod && e.shiftKey && e.key.toLowerCase() === 'a') {
        e.preventDefault()
        st.decide('all', 'accepted')
      } else if (e.key === '?' && !typing && !mod) {
        e.preventDefault()
        st.set({ shortcutsOpen: !st.shortcutsOpen })
      } else if (st.presenter && !typing && !mod) {
        if (e.key === ' ') {
          e.preventDefault()
          getPlayer().setPaused(!getPlayer().paused)
        } else if (e.key === 'ArrowRight') {
          e.preventDefault()
          getPlayer().stepBeat()
        }
      }
    }
    const rerun = () => {
      const st = useStudio.getState()
      const last = getLastRun()
      if (st.js.state === 'running') return
      st.startJob(last?.input ?? { kind: 'demo' }, last?.options)
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('pythia:rerun', rerun)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('pythia:rerun', rerun)
    }
  }, [])

  // ------- drag and drop anywhere
  useEffect(() => {
    let depth = 0
    const has = (e: DragEvent) => !!e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files')
    const enter = (e: DragEvent) => { if (has(e)) { depth++; e.preventDefault(); useStudio.setState({ dragging: true }) } }
    const over = (e: DragEvent) => { if (has(e)) e.preventDefault() }
    const leave = (e: DragEvent) => { if (has(e) && --depth <= 0) { depth = 0; useStudio.setState({ dragging: false }) } }
    const drop = async (e: DragEvent) => {
      if (!has(e)) return
      e.preventDefault()
      depth = 0
      useStudio.setState({ dragging: false })
      const st = useStudio.getState()
      const items = Array.from(e.dataTransfer!.items ?? [])
      if (items.some((i) => i.webkitGetAsEntry?.()?.isDirectory)) {
        st.toast('Folders cannot be read from the browser. Paste the folder path into Open folder instead.', 'error')
        return
      }
      const f = Array.from(e.dataTransfer!.files).find((x) => x.name.endsWith('.py'))
      if (!f) return st.toast('Drop a .py file to analyse it.', 'error')
      st.startJob({ kind: 'file', filename: f.name, content_b64: await fileToB64(f) })
    }
    window.addEventListener('dragenter', enter)
    window.addEventListener('dragover', over)
    window.addEventListener('dragleave', leave)
    window.addEventListener('drop', drop)
    return () => {
      window.removeEventListener('dragenter', enter)
      window.removeEventListener('dragover', over)
      window.removeEventListener('dragleave', leave)
      window.removeEventListener('drop', drop)
    }
  }, [])

  const setSize = (k: 'side' | 'agent' | 'bottom', d: number, min: number, max: number) =>
    useStudio.setState((st) => ({ sizes: { ...st.sizes, [k]: Math.max(min, Math.min(max, st.sizes[k] + d)) } }))

  const tab = tabs.find((t) => t.id === activeTab) ?? tabs[0]
  const content = (() => {
    switch (tab.kind) {
      case 'welcome': return <Welcome />
      case 'function': return <FunctionView id={tab.ref!} />
      case 'stage': return <StageInspector stage={tab.ref as StageName} />
      case 'file': return <FileView path={tab.ref!} line={tab.line} />
      case 'report': return <Report />
      case 'settings': return <SettingsPage />
      default: return null
    }
  })()

  return (
    <div className="print-flow flex h-full flex-col bg-bg text-fg">
      <TitleBar />
      <div className="print-flow flex min-h-0 flex-1">
        <ActivityBar />
        <AnimatePresence initial={false}>
          {s.sideOpen && (
            <motion.div key="side" className="no-print flex flex-none overflow-hidden" initial={{ width: 0, opacity: 0 }} animate={{ width: sizes.side + 1, opacity: 1 }} exit={{ width: 0, opacity: 0 }} transition={{ duration: s.resizing ? 0 : 0.18, ease: 'easeOut' }}>
              <div className="min-w-0 flex-1" style={{ minWidth: sizes.side }}>
                <SidePanel />
              </div>
              <div className="no-print flex-none border-r border-line">
                <Splitter dir="h" onDrag={(d) => setSize('side', d, 200, 520)} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <main className="print-flow relative flex min-w-0 flex-1 flex-col">
          <Stepper />
          <TabsBar />
          <Breadcrumbs />
          <div className="print-flow relative min-h-0 flex-1 bg-bg">
            <Boundary k={tab.id}>{content}</Boundary>
            {playgroundVisited && (
              <div className={cn('absolute inset-0 bg-bg', tab.kind !== 'playground' && 'hidden')}>
                <Boundary k="pg">
                  <Playground />
                </Boundary>
              </div>
            )}
            <CaptionBar />
          </div>
          <AnimatePresence initial={false}>
            {s.bottomOpen && (
              <motion.div key="bottom" className="no-print flex flex-none flex-col overflow-hidden" initial={{ height: 0, opacity: 0 }} animate={{ height: sizes.bottom + 1, opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: s.resizing ? 0 : 0.18, ease: 'easeOut' }}>
                <Splitter dir="v" onDrag={(d) => setSize('bottom', -d, 120, 560)} />
                <div className="min-h-0 flex-1" style={{ minHeight: sizes.bottom - 4 }}>
                  <BottomPanel />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </main>
        <AnimatePresence initial={false}>
          {s.agentOpen && (
            <motion.div key="agent" className="no-print flex flex-none overflow-hidden" initial={{ width: 0, opacity: 0 }} animate={{ width: sizes.agent + 1, opacity: 1 }} exit={{ width: 0, opacity: 0 }} transition={{ duration: s.resizing ? 0 : 0.18, ease: 'easeOut' }}>
              <div className="no-print flex-none border-l border-line">
                <Splitter dir="h" onDrag={(d) => setSize('agent', -d, 260, 560)} />
              </div>
              <div className="min-w-0 flex-1" style={{ minWidth: sizes.agent }}>
                <AgentPanel />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <StatusBar />
      {(s.paletteOpen || s.quickOpen) && <Palette mode={s.paletteOpen ? 'commands' : 'files'} onClose={() => s.set({ paletteOpen: false, quickOpen: false })} />}
      <Toasts />
      <ContextMenu />
      <ShortcutsSheet />
      {s.dragging && (
        <div className="pointer-events-none fixed inset-0 z-[70] flex items-center justify-center bg-bg/80 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-accent px-16 py-12">
            <Upload size={28} className="text-accent" />
            <div className="text-lg font-medium">Drop a Python file to analyse it</div>
            <div className="text-sm text-fg3">The original stays untouched</div>
          </div>
        </div>
      )}
    </div>
  )
}

function CaptionBar() {
  const presenter = useStudio((s) => s.presenter)
  const caption = useStudio((s) => s.js.caption)
  const seq = useStudio((s) => s.js.captionSeq)
  const paused = useStudio((s) => s.playerInfo.paused)
  const running = useStudio((s) => s.js.state === 'running' || s.playerInfo.pending > 0)
  if (!presenter || !caption) return null
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-4 z-30 flex justify-center px-6 no-print">
      <div key={seq} className="pointer-events-auto flex max-w-[860px] animate-fadeIn items-center gap-3 rounded-xl border border-line2 bg-panel/95 px-5 py-3 shadow-2xl backdrop-blur">
        {paused && <Pause size={16} className="flex-none text-warn" />}
        <p className="text-[16px] leading-6 text-fg">{caption}</p>
        {running && (
          <span className="ml-2 flex flex-none items-center gap-1 text-xs text-fg3">
            <Kbd>Space</Kbd> pause <Kbd>→</Kbd> step
          </span>
        )}
      </div>
    </div>
  )
}

function Toasts() {
  const toasts = useStudio((s) => s.toasts)
  return (
    <div className="no-print pointer-events-none fixed bottom-8 right-4 z-[80] flex w-[340px] flex-col gap-2" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={cn('pointer-events-auto animate-fadeIn rounded-lg border px-3.5 py-2.5 text-sm shadow-xl', t.kind === 'error' ? 'border-bad/40 bg-panel text-fg' : t.kind === 'ok' ? 'border-ok/40 bg-panel text-fg' : 'border-line2 bg-panel text-fg')}>
          <span className={cn('mr-2 inline-block h-2 w-2 rounded-full', t.kind === 'error' ? 'bg-bad' : t.kind === 'ok' ? 'bg-ok' : 'bg-accent')} />
          {t.text}
        </div>
      ))}
    </div>
  )
}

export { api, IS_MOCK }
