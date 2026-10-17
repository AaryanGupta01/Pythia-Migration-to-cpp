import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Braces, Check, ChevronRight, Cpu, FileCode2, FileText, Files, Flame, Gauge, Keyboard, Layers, Moon, PanelBottom, PanelRight, Pause, Play, Presentation, Search, Settings as SettingsIcon, SkipForward, Sparkles, Sun, Workflow, X, Zap,
} from 'lucide-react'
import { useStudio, getPlayer, type Speed } from './store'
import { countStatus, totalSpeedup } from './reducer'
import { STAGES, type StageName } from './types'
import { STATUS, cn, fmtX, llmLabel, compilerLabel } from './lib/format'
import { IconBtn, Kbd, MOD } from './ui'
import { CountText, CountUp } from './motion'
import { IS_MOCK } from './api'
import { Logo, Wordmark } from './brand'
import { FileIcon } from './fileicons'

export { Logo }

// ------------------------------------------------------------------ title bar
export function TitleBar() {
  const s = useStudio()
  const running = s.js.state === 'running'
  const live = running || s.replaying || s.playerInfo.pending > 0
  const showTransport = s.presenter && live
  return (
    <header className="no-print relative flex h-[38px] flex-none items-center border-b border-line bg-panel px-2.5 hair-top">
      <div className="flex items-center gap-2.5 pr-3">
        <Logo size={20} />
        <Wordmark size="sm" />
        {s.js.name && (
          <span className="hidden items-center gap-1.5 text-sm text-fg3 md:flex">
            <ChevronRight size={12} />
            <span className="max-w-[180px] truncate text-fg2">{s.js.name}</span>
          </span>
        )}
      </div>
      <button
        onClick={() => s.set({ paletteOpen: true })}
        className="absolute left-1/2 top-1/2 flex h-7 w-[min(32vw,440px)] -translate-x-1/2 -translate-y-1/2 items-center gap-2 rounded-lg border border-line2 bg-bg px-2.5 text-sm text-fg3 shadow-[inset_0_1px_0_rgb(var(--hl)/0.03)] transition-colors hover:border-fg3/50 hover:text-fg2"
        aria-label="Open command palette"
      >
        <Search size={13} />
        <span className="flex-1 truncate text-left">Search commands, functions, files</span>
        <Kbd>{MOD}K</Kbd>
      </button>
      <div className="ml-auto flex items-center gap-1">
        {showTransport && <Transport />}
        <button
          onClick={() => s.setPresenter(!s.presenter)}
          data-tip="Presenter mode: plays the run stage by stage"
          aria-pressed={s.presenter}
          className={cn(
            'flex h-7 items-center gap-1.5 rounded-lg border px-2.5 text-sm transition-colors',
            s.presenter ? 'border-accent/50 bg-accent/10 text-accent shadow-[0_0_16px_-4px_rgb(var(--accent)/0.5)]' : 'border-transparent text-fg2 hover:bg-hover hover:text-fg',
          )}
        >
          <Presentation size={14} />
          <span className="hidden lg:inline">Presenter</span>
        </button>
        <span className="mx-1 h-4 w-px bg-line2" />
        <IconBtn title={s.agentOpen ? 'Hide agent panel' : 'Show agent panel'} active={s.agentOpen} onClick={() => s.set({ agentOpen: !s.agentOpen })}>
          <PanelRight size={15} />
        </IconBtn>
        <IconBtn title={s.bottomOpen ? 'Hide bottom panel' : 'Show bottom panel'} active={s.bottomOpen} onClick={() => s.set({ bottomOpen: !s.bottomOpen })}>
          <PanelBottom size={15} />
        </IconBtn>
        <IconBtn title="Keyboard shortcuts (?)" onClick={() => s.set({ shortcutsOpen: true })}>
          <Keyboard size={15} />
        </IconBtn>
        <IconBtn title={s.theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'} onClick={() => s.setTheme(s.theme === 'dark' ? 'light' : 'dark')}>
          {s.theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
        </IconBtn>
      </div>
    </header>
  )
}

const SPEEDS: { v: Speed; l: string }[] = [
  { v: 0.5, l: '0.5×' },
  { v: 1, l: '1×' },
  { v: 2, l: '2×' },
  { v: 4, l: '4×' },
  { v: 0, l: 'Max' },
]
export function SpeedSelect() {
  const speed = useStudio((s) => s.speed)
  const setSpeed = useStudio((s) => s.setSpeed)
  return (
    <label className="flex items-center gap-1 text-xs text-fg3">
      <Gauge size={12} />
      <select aria-label="Playback speed" value={speed} onChange={(e) => setSpeed(Number(e.target.value) as Speed)} className="h-5 cursor-pointer rounded border border-line2 bg-bg px-1 text-xs text-fg2">
        {SPEEDS.map((o) => (
          <option key={o.v} value={o.v}>
            {o.l}
          </option>
        ))}
      </select>
    </label>
  )
}

function Transport() {
  const info = useStudio((s) => s.playerInfo)
  const p = getPlayer()
  return (
    <div className="mr-1 flex items-center gap-1 rounded-lg border border-line2 bg-bg px-1">
      <IconBtn title={info.paused ? 'Resume (Space)' : 'Pause (Space)'} onClick={() => p.setPaused(!p.paused)}>
        {info.paused ? <Play size={13} /> : <Pause size={13} />}
      </IconBtn>
      <IconBtn title="Next step (→)" onClick={() => p.stepBeat()}>
        <SkipForward size={13} />
      </IconBtn>
      <SpeedSelect />
    </div>
  )
}

// ------------------------------------------------------------------ activity bar
export function ActivityBar() {
  const s = useStudio()
  const active = s.tabs.find((t) => t.id === s.activeTab)?.kind
  const items: { key: string; icon: JSX.Element; title: string; on: boolean; click: () => void }[] = [
    { key: 'explorer', icon: <Files size={19} strokeWidth={1.7} />, title: 'Explorer', on: s.sideOpen && s.sideView === 'explorer', click: () => toggleSide('explorer') },
    { key: 'hotspots', icon: <Flame size={19} strokeWidth={1.7} />, title: 'Hotspots', on: s.sideOpen && s.sideView === 'hotspots', click: () => toggleSide('hotspots') },
    { key: 'playground', icon: <Braces size={19} strokeWidth={1.7} />, title: 'Playground', on: active === 'playground', click: () => s.openSpecial('playground') },
    { key: 'report', icon: <FileText size={19} strokeWidth={1.7} />, title: 'Report', on: active === 'report', click: () => s.openSpecial('report') },
  ]
  function toggleSide(v: 'explorer' | 'hotspots') {
    if (s.sideOpen && s.sideView === v) s.set({ sideOpen: false })
    else s.set({ sideOpen: true, sideView: v })
  }
  return (
    <nav aria-label="Activity bar" className="no-print flex w-[50px] flex-none flex-col items-center justify-between border-r border-line bg-panel py-2">
      <div className="flex flex-col items-center gap-1">
        {items.map((i) => (
          <ActBtn key={i.key} icon={i.icon} title={i.title} on={i.on} click={i.click} />
        ))}
      </div>
      <ActBtn icon={<SettingsIcon size={19} strokeWidth={1.7} />} title="Settings" on={active === 'settings'} click={() => s.openSpecial('settings')} />
    </nav>
  )
}
function ActBtn({ icon, title, on, click }: { icon: JSX.Element; title: string; on: boolean; click: () => void }) {
  return (
    <button
      onClick={click}
      data-tip={title}
      data-tip-pos="right"
      aria-label={title}
      aria-pressed={on}
      className={cn('relative flex h-10 w-10 items-center justify-center rounded-lg transition-colors', on ? 'text-fg' : 'text-fg3 hover:text-fg2')}
    >
      {on && <motion.span layoutId="act-indicator" className="absolute -left-[5px] top-2.5 h-5 w-[3px] rounded-full bg-accent shadow-[0_0_10px_rgb(var(--accent)/0.8)]" transition={{ duration: 0.18 }} />}
      <span className={cn('flex h-9 w-9 items-center justify-center rounded-lg transition-colors', on ? 'bg-hover' : 'hover:bg-hover/60')}>{icon}</span>
    </button>
  )
}

// ------------------------------------------------------------------ pipeline stepper
const STAGE_ICON: Record<StageName, JSX.Element> = {
  ingest: <Layers size={12} />, scan: <Search size={12} />, trace: <Workflow size={12} />, rank: <Flame size={12} />, fix: <Sparkles size={12} />,
  compile: <Cpu size={12} />, verify: <Check size={12} />, benchmark: <Gauge size={12} />, splice: <FileCode2 size={12} />, export: <Zap size={12} />,
}
const LABEL: Record<StageName, string> = {
  ingest: 'Ingest', scan: 'Scan', trace: 'Trace', rank: 'Rank', fix: 'Fix', compile: 'Compile', verify: 'Verify', benchmark: 'Benchmark', splice: 'Splice', export: 'Export',
}
const SHORT: Record<StageName, string> = { ...LABEL, compile: 'Build', benchmark: 'Bench' }
export function Stepper() {
  const ref = useRef<HTMLElement>(null)
  const [narrow, setNarrow] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(() => setNarrow(el.clientWidth / STAGES.length < 98))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  const stages = useStudio((s) => s.js.stages)
  const activeTab = useStudio((s) => s.activeTab)
  const openStage = useStudio((s) => s.openStage)
  const idle = useStudio((s) => s.js.state === 'idle')
  const doneN = STAGES.filter((st) => stages[st].state === 'done' || stages[st].state === 'skipped').length
  const runIdx = STAGES.findIndex((st) => stages[st].state === 'running')
  const pct = ((doneN + (runIdx >= 0 ? (stages[STAGES[runIdx]].progress ?? 0.35) : 0)) / STAGES.length) * 100
  return (
    <nav ref={ref} aria-label="Pipeline" className={cn('no-print relative flex h-[50px] flex-none items-stretch border-b border-line bg-panel transition-opacity', idle && 'opacity-60')}>
      {STAGES.map((st) => {
        const x = stages[st]
        const sel = activeTab === `stage:${st}`
        return (
          <button
            key={st}
            onClick={() => openStage(st)}
            aria-label={`${LABEL[st]} stage: ${x.state}${x.summary ? ', ' + x.summary : ''}`}
            className={cn('group relative flex min-w-0 flex-1 flex-col justify-center border-r border-line px-2.5 text-left transition-colors last:border-r-0 hover:bg-hover/50', sel && 'bg-hover/70')}
          >
            <span className="flex min-w-0 items-center gap-1.5">
              <StageGlyph state={x.state} icon={STAGE_ICON[st]} />
              <span className={cn('truncate text-[12px] font-medium leading-4', x.state === 'idle' || x.state === 'skipped' ? 'text-fg3' : x.state === 'running' ? 'text-fg' : 'text-fg2')}>{narrow ? SHORT[st] : LABEL[st]}</span>
            </span>
            <span className={cn('tnum block truncate pl-[18px] text-2xs leading-[14px]', x.state === 'running' ? 'text-accent' : x.state === 'failed' ? 'text-bad' : 'text-fg3')}>
              {x.summary ? <CountText text={x.summary} /> : x.state === 'running' ? 'running' : x.state === 'skipped' ? 'skipped' : idle ? '—' : 'waiting'}
            </span>
            {sel && <motion.span layoutId="stage-sel" className="absolute inset-x-0 top-0 h-[2px] bg-accent" transition={{ duration: 0.16 }} />}
          </button>
        )
      })}
      {/* progress track along the bottom edge; a beam flows through the running stage */}
      <span className="pointer-events-none absolute inset-x-0 bottom-0 h-[2px] bg-line">
        <span className="absolute inset-y-0 left-0 rounded-r bg-gradient-to-r from-ok/60 to-ok transition-[width] duration-500 ease-out" style={{ width: `${pct}%` }} />
        {runIdx >= 0 && (
          <span className="absolute inset-y-0 overflow-hidden" style={{ left: `${(runIdx / STAGES.length) * 100}%`, width: `${100 / STAGES.length}%` }}>
            <span className="beam absolute inset-0" />
          </span>
        )}
      </span>
    </nav>
  )
}

function StageGlyph({ state, icon }: { state: string; icon: JSX.Element }) {
  const base = 'flex h-3 w-3 flex-none items-center justify-center'
  if (state === 'done')
    return (
      <motion.span initial={{ scale: 0.4 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 520, damping: 22 }} className={cn(base, 'text-ok')}>
        <Check size={12} strokeWidth={3} />
      </motion.span>
    )
  if (state === 'failed') return <span className={cn(base, 'text-bad')}><X size={12} strokeWidth={3} /></span>
  if (state === 'running') return <span className={cn(base, 'text-accent')}><span className="absolute h-3 w-3 animate-ping rounded-full bg-accent/40" /><span className="relative">{icon}</span></span>
  return <span className={cn(base, 'text-fg3', state === 'skipped' && 'opacity-50')}>{icon}</span>
}

// ------------------------------------------------------------------ tabs + breadcrumb
export function TabsBar() {
  const s = useStudio()
  const fns = s.js.functions
  return (
    <div role="tablist" aria-label="Open editors" className="no-print flex h-[34px] flex-none items-stretch overflow-x-auto border-b border-line bg-panel">
      {s.tabs.map((t) => {
        const on = t.id === s.activeTab
        const f = t.kind === 'function' && t.ref ? fns[t.ref] : null
        return (
          <div
            key={t.id}
            role="tab"
            aria-selected={on}
            tabIndex={0}
            onClick={() => s.setActive(t.id)}
            onDoubleClick={() => s.pinTab(t.id)}
            onAuxClick={(e) => e.button === 1 && s.closeTab(t.id)}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && s.setActive(t.id)}
            className={cn(
              'group relative flex max-w-[230px] flex-none cursor-pointer items-center gap-2 border-r border-line px-3 text-[12.5px] transition-colors',
              on ? 'bg-bg text-fg' : 'text-fg3 hover:bg-hover/40 hover:text-fg2',
            )}
          >
            {on && <motion.span layoutId="tab-top" className="absolute inset-x-0 top-0 h-[2px] bg-accent" transition={{ duration: 0.16 }} />}
            {f ? <span className={cn('h-1.5 w-1.5 flex-none rounded-full', STATUS[f.status].dot)} /> : <TabIcon kind={t.kind} path={t.ref} />}
            <span className={cn('truncate', t.preview && 'italic')}>{t.title}</span>
            {t.kind === 'function' && f?.speedup ? <span className="tnum text-2xs text-ok">{fmtX(f.speedup)}</span> : null}
            {t.id !== 'welcome' || s.tabs.length > 1 ? (
              <button
                aria-label={`Close ${t.title}`}
                onClick={(e) => {
                  e.stopPropagation()
                  s.closeTab(t.id)
                }}
                className={cn('ml-0.5 flex h-4 w-4 flex-none items-center justify-center rounded text-fg3 hover:bg-hover hover:text-fg focus-visible:opacity-100', on ? 'opacity-70' : 'opacity-0 group-hover:opacity-100')}
              >
                <X size={11} />
              </button>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
function TabIcon({ kind, path }: { kind: string; path?: string }) {
  const p = { size: 13, className: 'flex-none text-fg3' }
  switch (kind) {
    case 'file': return <FileIcon name={path ?? ''} size={13} />
    case 'stage': return <Workflow {...p} />
    case 'playground': return <Braces {...p} />
    case 'report': return <FileText {...p} />
    case 'settings': return <SettingsIcon {...p} />
    default: return <Logo size={13} />
  }
}

export function Breadcrumbs() {
  const s = useStudio()
  const tab = s.tabs.find((t) => t.id === s.activeTab)
  const f = tab?.kind === 'function' && tab.ref ? s.js.functions[tab.ref] : null
  const crumbs: { label: string; click?: () => void; mono?: boolean }[] = []
  if (s.js.name && tab && tab.kind !== 'welcome' && tab.kind !== 'settings' && tab.kind !== 'playground') crumbs.push({ label: s.js.name })
  if (tab?.kind === 'file' && tab.ref) tab.ref.split('/').forEach((p, i, a) => crumbs.push({ label: p, mono: true, click: i === a.length - 1 ? undefined : undefined }))
  if (f) {
    f.file.split('/').forEach((p, i, a) => crumbs.push({ label: p, mono: true, click: i === a.length - 1 ? () => s.openFile(f.file, f.line) : undefined }))
    crumbs.push({ label: f.qualname, mono: true })
  }
  if (tab?.kind === 'stage') crumbs.push({ label: 'Pipeline' }, { label: tab.title })
  if (tab?.kind === 'report') crumbs.push({ label: 'Report' })
  if (tab?.kind === 'playground') crumbs.push({ label: 'Playground' })
  if (tab?.kind === 'settings') crumbs.push({ label: 'Settings' })
  if (!crumbs.length) return null
  return (
    <div aria-label="Breadcrumb" className="no-print flex h-[26px] flex-none items-center gap-1 overflow-hidden border-b border-line bg-bg px-3 text-xs text-fg3">
      {crumbs.map((c, i) => (
        <span key={i} className="flex min-w-0 items-center gap-1">
          {i > 0 && <ChevronRight size={11} className="flex-none opacity-60" />}
          <span onClick={c.click} className={cn('truncate', c.mono && 'mono !text-[11.5px]', c.click && 'cursor-pointer hover:text-fg', i === crumbs.length - 1 && 'text-fg2')}>
            {c.label}
          </span>
        </span>
      ))}
    </div>
  )
}

// ------------------------------------------------------------------ status bar
export function StatusBar() {
  const s = useStudio()
  const env = s.env
  const c = useMemo(() => countStatus(s.js), [s.js.functions])
  const sp = totalSpeedup(s.js)
  const st = s.js.state
  const live = st === 'running' || (s.replaying && s.playerInfo.pending > 0)
  const label = s.replaying && live ? 'Replaying' : st === 'running' ? 'Running' : st === 'done' ? 'Done' : st === 'failed' ? 'Failed' : st === 'cancelled' ? 'Cancelled' : 'Idle'
  return (
    <footer className="no-print flex h-[24px] flex-none items-center gap-4 border-t border-line bg-panel px-3 text-xs text-fg3">
      <span className="flex items-center gap-1.5 text-fg2">
        <Logo size={11} />
        {s.js.name ?? 'No workspace'}
      </span>
      {env && (
        <span className={cn('flex items-center gap-1.5', env.compiler.found ? '' : 'text-bad')} data-tip={env.compiler.hint ?? 'C++ toolchain'} data-tip-pos="top">
          <Cpu size={12} />
          {compilerLabel(env)}
        </span>
      )}
      {env && (
        <span className="flex items-center gap-1.5" data-tip={env.llm.hint || 'LLM fixer'} data-tip-pos="top">
          <Sparkles size={12} className={env.llm.enabled ? 'text-accent' : ''} />
          {llmLabel(env)}
        </span>
      )}
      {IS_MOCK && <span className="rounded border border-line2 px-1 text-2xs">sample data</span>}
      <span className="ml-auto flex items-center gap-4">
        {st !== 'idle' && (
          <span className="tnum hidden gap-3 md:flex">
            <span className="text-ok">{c.verified + c.guarded} accelerated</span>
            {c.declined + c.failed > 0 && <span>{c.declined + c.failed} stopped</span>}
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <span className="relative flex h-2 w-2">
            {live && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />}
            <span className={cn('relative inline-flex h-2 w-2 rounded-full', live ? 'bg-accent' : st === 'done' ? 'bg-ok' : st === 'failed' ? 'bg-bad' : 'bg-line2')} />
          </span>
          {label}
        </span>
        <span className="tnum min-w-[92px] text-right text-fg2">{sp ? <>Total <CountUp value={sp} decimals={1} suffix="×" className="font-semibold text-ok" /></> : 'Total —'}</span>
        <button onClick={() => s.set({ shortcutsOpen: true })} className="hidden items-center gap-1 hover:text-fg2 lg:flex" aria-label="Keyboard shortcuts">
          <Kbd>?</Kbd>
        </button>
      </span>
    </footer>
  )
}
