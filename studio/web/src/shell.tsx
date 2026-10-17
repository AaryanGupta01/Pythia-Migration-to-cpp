import { useMemo } from 'react'
import {
  Braces, Check, Cpu, FileCode2, FileText, Files, Flame, Moon, PanelBottom, PanelRight, Pause, Play, Presentation, RotateCcw, Search, Settings as SettingsIcon, SkipForward, Sparkles, Sun, X, Zap, Gauge, Layers, Workflow,
} from 'lucide-react'
import { useStudio, getPlayer, type Speed } from './store'
import { countStatus, totalSpeedup } from './reducer'
import { STAGES, type StageName } from './types'
import { STATUS, cn, fmtX } from './lib/format'
import { Dot, IconBtn, Kbd, MOD } from './ui'
import { IS_MOCK } from './api'

export function Logo({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="8" fill="rgb(var(--raised))" stroke="rgb(var(--line2))" />
      <path d="M10 24V8h7.5a5 5 0 010 10H13" fill="none" stroke="rgb(var(--accent))" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// ------------------------------------------------------------------ title bar
export function TitleBar() {
  const s = useStudio()
  const running = s.js.state === 'running'
  const live = running || s.replaying || s.playerInfo.pending > 0
  const showTransport = s.presenter && live
  return (
    <header className="no-print relative flex h-[34px] flex-none items-center border-b border-line bg-panel px-2">
      <div className="flex items-center gap-2 pr-3">
        <Logo />
        <span className="text-sm font-semibold tracking-tight">PYTHIA Studio</span>
        {s.js.name && <span className="hidden truncate text-sm text-fg3 md:inline">/ {s.js.name}</span>}
      </div>
      <button
        onClick={() => s.set({ paletteOpen: true })}
        className="absolute left-1/2 top-1/2 flex h-6 w-[min(34vw,420px)] -translate-x-1/2 -translate-y-1/2 items-center gap-2 rounded-md border border-line2 bg-bg px-2 text-sm text-fg3 transition-colors hover:border-fg3 hover:text-fg2"
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
          title="Presenter mode: play the run stage by stage"
          aria-pressed={s.presenter}
          className={cn(
            'flex h-6 items-center gap-1.5 rounded-md border px-2 text-sm transition-colors',
            s.presenter ? 'border-accent/50 bg-accent/10 text-accent' : 'border-transparent text-fg2 hover:bg-hover hover:text-fg',
          )}
        >
          <Presentation size={14} />
          <span className="hidden lg:inline">Presenter</span>
        </button>
        <IconBtn title={s.agentOpen ? 'Hide agent panel' : 'Show agent panel'} active={s.agentOpen} onClick={() => s.set({ agentOpen: !s.agentOpen })}>
          <PanelRight size={15} />
        </IconBtn>
        <IconBtn title={s.bottomOpen ? 'Hide bottom panel' : 'Show bottom panel'} active={s.bottomOpen} onClick={() => s.set({ bottomOpen: !s.bottomOpen })}>
          <PanelBottom size={15} />
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
      <select
        aria-label="Playback speed"
        value={speed}
        onChange={(e) => setSpeed(Number(e.target.value) as Speed)}
        className="h-5 cursor-pointer rounded border border-line2 bg-bg px-1 text-xs text-fg2"
      >
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
    <div className="mr-1 flex items-center gap-1 rounded-md border border-line2 bg-bg px-1">
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
    { key: 'explorer', icon: <Files size={19} />, title: 'Explorer', on: s.sideOpen && s.sideView === 'explorer', click: () => toggleSide('explorer') },
    { key: 'hotspots', icon: <Flame size={19} />, title: 'Hotspots', on: s.sideOpen && s.sideView === 'hotspots', click: () => toggleSide('hotspots') },
    { key: 'playground', icon: <Braces size={19} />, title: 'Playground', on: active === 'playground', click: () => s.openSpecial('playground') },
    { key: 'report', icon: <FileText size={19} />, title: 'Report', on: active === 'report', click: () => s.openSpecial('report') },
  ]
  function toggleSide(v: 'explorer' | 'hotspots') {
    if (s.sideOpen && s.sideView === v) s.set({ sideOpen: false })
    else s.set({ sideOpen: true, sideView: v })
  }
  return (
    <nav aria-label="Activity bar" className="no-print flex w-12 flex-none flex-col items-center justify-between border-r border-line bg-panel py-2">
      <div className="flex flex-col items-center gap-1">
        {items.map((i) => (
          <ActBtn key={i.key} icon={i.icon} title={i.title} on={i.on} click={i.click} />
        ))}
      </div>
      <ActBtn key="settings" icon={<SettingsIcon size={19} />} title="Settings" on={active === 'settings'} click={() => s.openSpecial('settings')} />
    </nav>
  )
}
function ActBtn({ icon, title, on, click }: { icon: JSX.Element; title: string; on: boolean; click: () => void }) {
  return (
    <button
      onClick={click}
      title={title}
      aria-label={title}
      aria-pressed={on}
      className={cn('relative flex h-10 w-10 items-center justify-center rounded-lg transition-colors', on ? 'text-fg' : 'text-fg3 hover:text-fg2')}
    >
      {on && <span className="absolute -left-1 top-2 h-6 w-[2px] rounded-full bg-accent" />}
      <span className={cn('flex h-9 w-9 items-center justify-center rounded-lg', on ? 'bg-hover' : 'hover:bg-hover/60')}>{icon}</span>
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
export function Stepper() {
  const stages = useStudio((s) => s.js.stages)
  const activeTab = useStudio((s) => s.activeTab)
  const openStage = useStudio((s) => s.openStage)
  const idle = useStudio((s) => s.js.state === 'idle')
  return (
    <nav aria-label="Pipeline" className="no-print flex h-[46px] flex-none items-stretch border-b border-line bg-panel">
      {STAGES.map((st, i) => {
        const x = stages[st]
        const sel = activeTab === `stage:${st}`
        return (
          <button
            key={st}
            onClick={() => openStage(st)}
            aria-label={`${LABEL[st]} stage: ${x.state}${x.summary ? ', ' + x.summary : ''}`}
            className={cn(
              'group relative flex min-w-0 flex-1 flex-col justify-center gap-0.5 border-r border-line px-2.5 text-left transition-colors last:border-r-0 hover:bg-hover/60',
              sel && 'bg-hover/80',
            )}
          >
            <span className="flex items-center gap-1.5">
              {x.state === 'done' ? (
                <Check size={12} className="flex-none text-ok" />
              ) : x.state === 'failed' ? (
                <X size={12} className="flex-none text-bad" />
              ) : x.state === 'running' ? (
                <span className="flex-none text-accent">{STAGE_ICON[st]}</span>
              ) : (
                <span className="flex-none text-fg3">{STAGE_ICON[st]}</span>
              )}
              <span className={cn('truncate text-xs font-medium', x.state === 'idle' || x.state === 'skipped' ? 'text-fg3' : x.state === 'running' ? 'text-fg' : 'text-fg2')}>
                {LABEL[st]}
              </span>
            </span>
            <span className={cn('tnum truncate text-2xs', x.state === 'running' ? 'text-accent' : x.state === 'failed' ? 'text-bad' : 'text-fg3')}>
              {x.summary ?? (x.state === 'running' ? 'running' : x.state === 'skipped' ? 'skipped' : idle ? '—' : 'waiting')}
            </span>
            {x.state === 'running' && (
              <span className="absolute inset-x-0 bottom-0 h-[2px] overflow-hidden bg-accent/15">
                {x.progress != null && x.progress > 0 ? (
                  <span className="block h-full bg-accent transition-all duration-300" style={{ width: `${x.progress * 100}%` }} />
                ) : (
                  <span className="block h-full w-1/3 animate-slide bg-accent" />
                )}
              </span>
            )}
            {sel && <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />}
          </button>
        )
      })}
    </nav>
  )
}

// ------------------------------------------------------------------ tabs
export function TabsBar() {
  const s = useStudio()
  const fns = s.js.functions
  return (
    <div role="tablist" aria-label="Open editors" className="no-print flex h-8 flex-none items-stretch overflow-x-auto border-b border-line bg-panel">
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
            onAuxClick={(e) => e.button === 1 && s.closeTab(t.id)}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && s.setActive(t.id)}
            className={cn(
              'group relative flex max-w-[220px] flex-none cursor-pointer items-center gap-1.5 border-r border-line px-3 text-sm transition-colors',
              on ? 'bg-bg text-fg' : 'text-fg3 hover:bg-hover/50 hover:text-fg2',
            )}
          >
            {on && <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />}
            {f ? <span className={cn('h-1.5 w-1.5 flex-none rounded-full', STATUS[f.status].dot)} /> : <TabIcon kind={t.kind} />}
            <span className="truncate">{t.title}</span>
            {t.kind === 'function' && f?.speedup ? <span className="tnum text-2xs text-ok">{fmtX(f.speedup)}</span> : null}
            {t.id !== 'welcome' || s.tabs.length > 1 ? (
              <button
                aria-label={`Close ${t.title}`}
                onClick={(e) => {
                  e.stopPropagation()
                  s.closeTab(t.id)
                }}
                className="ml-0.5 flex h-4 w-4 items-center justify-center rounded text-fg3 opacity-0 hover:bg-hover hover:text-fg group-hover:opacity-100 focus-visible:opacity-100"
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
function TabIcon({ kind }: { kind: string }) {
  const p = { size: 13, className: 'flex-none text-fg3' }
  switch (kind) {
    case 'file': return <FileCode2 {...p} />
    case 'stage': return <Workflow {...p} />
    case 'playground': return <Braces {...p} />
    case 'report': return <FileText {...p} />
    case 'settings': return <SettingsIcon {...p} />
    default: return <Logo size={13} />
  }
}

// ------------------------------------------------------------------ status bar
export function StatusBar() {
  const s = useStudio()
  const env = s.env
  const c = useMemo(() => countStatus(s.js), [s.js.functions])
  const sp = totalSpeedup(s.js)
  const st = s.js.state
  const label = s.replaying && (st === 'running' || s.playerInfo.pending > 0) ? 'Replaying' : st === 'running' ? 'Running' : st === 'done' ? 'Done' : st === 'failed' ? 'Failed' : st === 'cancelled' ? 'Cancelled' : 'Idle'
  return (
    <footer className="no-print flex h-[22px] flex-none items-center gap-4 border-t border-line bg-panel px-3 text-xs text-fg3">
      <span className="flex items-center gap-1.5 text-fg2">
        <Logo size={11} />
        {s.js.name ?? 'No workspace'}
      </span>
      {env && (
        <span className={cn('flex items-center gap-1.5', env.compiler.found ? '' : 'text-bad')} title={env.compiler.hint ?? undefined}>
          <Cpu size={12} />
          {env.compiler.found ? `${env.compiler.name} ${env.compiler.version?.split('.')[0] ?? ''}` : 'No C++ compiler'}
        </span>
      )}
      {env && (
        <span className="flex items-center gap-1.5" title={env.llm.hint ?? undefined}>
          <Sparkles size={12} className={env.llm.enabled ? 'text-accent' : ''} />
          LLM {env.llm.enabled ? (env.offline ? 'on · offline cache' : 'on') : 'off'}
        </span>
      )}
      {IS_MOCK && <span className="rounded border border-line2 px-1 text-2xs">mock data</span>}
      <span className="ml-auto flex items-center gap-4">
        {s.js.state !== 'idle' && (
          <span className="tnum hidden gap-3 md:flex">
            <span style={{ color: 'rgb(var(--ok))' }}>{c.verified + c.guarded} accelerated</span>
            {c.declined + c.failed > 0 && <span>{c.declined + c.failed} stopped</span>}
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <Dot state={st === 'running' ? 'running' : st === 'done' ? 'done' : st === 'failed' ? 'failed' : 'idle'} />
          {label}
        </span>
        <span className="tnum min-w-[88px] text-right text-fg2">{sp ? <>Total <b className="text-ok">{fmtX(sp)}</b></> : 'Total —'}</span>
        <button onClick={() => s.set({ paletteOpen: true })} className="hidden items-center gap-1 hover:text-fg2 lg:flex" aria-label="Command palette">
          <RotateCcw size={0} />
          <Kbd>{MOD}K</Kbd>
        </button>
      </span>
    </footer>
  )
}
