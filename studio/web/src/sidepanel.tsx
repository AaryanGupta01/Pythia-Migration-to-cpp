import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Check, ChevronDown, ChevronRight, Copy, Flame, GitCompare, Route, Search, X } from 'lucide-react'
import { api } from './api'
import { useStudio } from './store'
import type { FunctionSummary, Status, TreeNode } from './types'
import { STATUS, basename, cn, fmtPct } from './lib/format'
import { Empty, PanelTitle, Skeleton, StatusChip } from './ui'
import { CountUp } from './motion'
import { FileIcon, FolderIcon } from './fileicons'

export function SidePanel() {
  const view = useStudio((s) => s.sideView)
  return (
    <aside aria-label={view === 'explorer' ? 'Explorer' : 'Hotspots'} className="no-print flex h-full min-h-0 w-full flex-col bg-panel">
      {view === 'explorer' ? <Explorer /> : <Hotspots />}
    </aside>
  )
}

// ------------------------------------------------------------------ explorer
function Explorer() {
  const js = useStudio((s) => s.js)
  const rev = useStudio((s) => s.rev)
  const [tree, setTree] = useState<TreeNode[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const ready = !!js.workspaceId && (js.ingest.done || js.state !== 'running')
  const marker = `${js.splice ? 1 : 0}${js.state}${rev}${js.scan ? 1 : 0}`
  useEffect(() => {
    if (!js.workspaceId || !ready) {
      setTree(null)
      return
    }
    let dead = false
    api.tree(js.workspaceId).then((t) => !dead && (setTree(t), setErr(null))).catch((e) => !dead && setErr(String(e.message ?? e)))
    return () => {
      dead = true
    }
  }, [js.workspaceId, ready, marker])

  const byFile = useMemo(() => {
    const m: Record<string, FunctionSummary[]> = {}
    for (const f of Object.values(js.functions)) (m[f.file] ??= []).push(f)
    for (const k of Object.keys(m)) m[k].sort((a, b) => a.line - b.line)
    return m
  }, [js.functions])

  return (
    <>
      <PanelTitle>{js.name ? `Explorer · ${js.name}` : 'Explorer'}</PanelTitle>
      <div className="min-h-0 flex-1 overflow-auto py-1.5">
        {!js.workspaceId ? (
          <Empty title="No folder open">Open a project from the Welcome tab to browse its files.</Empty>
        ) : err ? (
          <Empty title="Could not load files">{err}</Empty>
        ) : !tree ? (
          <div className="space-y-2 p-3" aria-busy>
            {[60, 80, 50, 70, 45, 65].map((w, i) => (
              <Skeleton key={i} className="h-4" />
            ))}
          </div>
        ) : (
          tree.map((n) => <TreeRow key={n.path} node={n} depth={0} byFile={byFile} />)
        )}
      </div>
    </>
  )
}

function TreeRow({ node, depth, byFile }: { node: TreeNode; depth: number; byFile: Record<string, FunctionSummary[]> }) {
  const s = useStudio()
  const [open, setOpen] = useState(depth < 2)
  const [fnOpen, setFnOpen] = useState(false)
  const isDir = node.type === 'dir'
  const active = s.activeTab === `file:${node.path}`
  const fns = byFile[node.path] ?? []
  const pad = 10 + depth * 14
  const guides = Array.from({ length: depth }, (_, i) => <span key={i} aria-hidden className="absolute top-0 h-full w-px bg-line" style={{ left: 16 + i * 14 }} />)
  return (
    <div>
      <div
        role="treeitem"
        tabIndex={0}
        aria-expanded={isDir ? open : undefined}
        onClick={() => (isDir ? setOpen(!open) : s.openFile(node.path))}
        onDoubleClick={() => !isDir && s.pinTab(`file:${node.path}`)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') isDir ? setOpen(!open) : s.openFile(node.path)
          if (e.key === 'ArrowRight' && isDir) setOpen(true)
          if (e.key === 'ArrowLeft' && isDir) setOpen(false)
        }}
        className={cn('group relative flex h-[26px] cursor-pointer items-center gap-1.5 pr-2.5 text-[13px] transition-colors hover:bg-hover/60', active && 'bg-hover text-fg')}
        style={{ paddingLeft: pad }}
      >
        {guides}
        {isDir ? (
          <>
            {open ? <ChevronDown size={13} className="flex-none text-fg3" /> : <ChevronRight size={13} className="flex-none text-fg3" />}
            <FolderIcon open={open} />
          </>
        ) : (
          <>
            <span
              role="button"
              aria-label={fnOpen ? 'Collapse functions' : 'Expand functions'}
              onClick={(e) => {
                e.stopPropagation()
                setFnOpen(!fnOpen)
              }}
              className={cn('flex h-4 w-[13px] flex-none items-center justify-center text-fg3 hover:text-fg', !fns.length && 'invisible')}
            >
              {fnOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            </span>
            <FileIcon name={node.name} />
          </>
        )}
        <span className={cn('min-w-0 flex-1 truncate', !isDir && !active && 'text-fg2')}>{node.name}</span>
        <Badges n={node} />
      </div>
      {isDir && open && node.children?.map((c) => <TreeRow key={c.path} node={c} depth={depth + 1} byFile={byFile} />)}
      {!isDir && fnOpen &&
        fns.map((f) => (
          <div
            key={f.id}
            role="treeitem"
            tabIndex={0}
            onClick={() => s.openFunction(f.id)}
            onContextMenu={(e) => {
              e.preventDefault()
              s.set({ contextMenu: { x: e.clientX, y: e.clientY, id: f.id } })
            }}
            onKeyDown={(e) => e.key === 'Enter' && s.openFunction(f.id)}
            className={cn('relative flex h-[24px] cursor-pointer items-center gap-2 pr-2.5 text-xs text-fg2 hover:bg-hover/60', s.activeTab === `fn:${f.id}` && 'bg-hover text-fg')}
            style={{ paddingLeft: pad + 30 }}
          >
            {guides}
            <span aria-hidden className="absolute top-0 h-full w-px bg-line" style={{ left: 16 + depth * 14 }} />
            <span className={cn('h-1.5 w-1.5 flex-none rounded-full', STATUS[f.status].dot)} />
            <span className="mono min-w-0 flex-1 truncate">{f.name}</span>
            {f.speedup ? <span className="tnum text-ok">{f.speedup.toFixed(1)}×</span> : null}
          </div>
        ))}
    </div>
  )
}

function Badges({ n }: { n: TreeNode }) {
  const b = n.badges
  if (!b || (!b.hotspots && !b.accelerated)) return null
  return (
    <span className="tnum flex flex-none items-center gap-1.5 text-2xs">
      {b.hotspots > 0 && (
        <span className="flex items-center gap-0.5 text-fg3" data-tip={`${b.hotspots} hotspots`}>
          <Flame size={10} />
          {b.hotspots}
        </span>
      )}
      {b.accelerated > 0 && (
        <span className="rounded-full bg-ok/15 px-1.5 text-ok" data-tip={`${b.accelerated} accelerated`}>
          {b.accelerated}
        </span>
      )}
    </span>
  )
}

// ------------------------------------------------------------------ hotspots
type Filter = 'all' | 'accelerated' | 'fixable' | 'stopped'
const FILTERS: { v: Filter; l: string; test: (s: Status) => boolean }[] = [
  { v: 'all', l: 'All', test: () => true },
  { v: 'accelerated', l: 'Accelerated', test: (s) => s === 'verified' || s === 'guarded' },
  { v: 'fixable', l: 'Fixable', test: (s) => s === 'fixable' || s === 'pending' },
  { v: 'stopped', l: 'Stopped', test: (s) => s === 'not_eligible' || s === 'declined' || s === 'failed' },
]

function Hotspots() {
  const js = useStudio((s) => s.js)
  const openFunction = useStudio((s) => s.openFunction)
  const pinTab = useStudio((s) => s.pinTab)
  const set = useStudio((s) => s.set)
  const activeTab = useStudio((s) => s.activeTab)
  const [filter, setFilter] = useState<Filter>('all')
  const [q, setQ] = useState('')
  const [limit, setLimit] = useState(200)
  const list = useMemo(() => {
    const t = FILTERS.find((f) => f.v === filter)!.test
    const needle = q.trim().toLowerCase()
    return js.order.map((id) => js.functions[id]).filter((f) => f && t(f.status) && (!needle || f.name.toLowerCase().includes(needle) || f.file.toLowerCase().includes(needle)))
  }, [js.order, js.functions, filter, q])
  const maxShare = useMemo(() => Math.max(0.01, ...Object.values(js.functions).map((f) => f.share ?? 0)), [js.functions])
  const ranked = !!js.ranking
  const animate = list.length <= 120

  return (
    <>
      <PanelTitle right={<span className="tnum rounded-full bg-hover px-1.5 text-xs text-fg2">{list.length}</span>}>{ranked ? 'Hotspots · ranked' : 'Hotspots'}</PanelTitle>
      <div className="flex flex-none flex-col gap-2 border-b border-line p-2">
        <label className="flex h-7 items-center gap-1.5 rounded-lg border border-line2 bg-bg px-2 text-fg3 transition-colors focus-within:border-accent">
          <Search size={12} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter functions" aria-label="Filter functions" className="min-w-0 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-fg3" />
          {q && <button aria-label="Clear filter" onClick={() => setQ('')}><X size={11} /></button>}
        </label>
        <div className="flex gap-0.5 rounded-lg bg-bg p-0.5">
          {FILTERS.map((f) => (
            <button key={f.v} onClick={() => setFilter(f.v)} aria-pressed={filter === f.v} className={cn('relative flex-1 rounded-md px-1.5 py-0.5 text-xs transition-colors', filter === f.v ? 'text-fg' : 'text-fg3 hover:text-fg2')}>
              {filter === f.v && <motion.span layoutId="filter-pill" className="absolute inset-0 rounded-md bg-hover" transition={{ duration: 0.16 }} />}
              <span className="relative">{f.l}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {!js.jobId ? (
          <Empty title="No hotspots yet" icon={<Flame size={20} />}>
            Open a project and PYTHIA ranks its functions by real time spent and by how well they compile.
          </Empty>
        ) : !list.length && js.state === 'running' && !js.order.length ? (
          <div className="space-y-3 p-3" aria-busy>
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="space-y-1.5">
                <Skeleton className="h-3.5 w-2/3" />
                <Skeleton className="h-2.5 w-full" />
              </div>
            ))}
          </div>
        ) : !list.length ? (
          <Empty title="Nothing matches">Clear the filter to see all {js.order.length} functions.</Empty>
        ) : (
          <ul>
            {list.slice(0, limit).map((f, i) => {
              const rank = js.order.indexOf(f.id) + 1
              const Row = animate ? motion.li : 'li'
              const anim = animate ? { layout: 'position' as const, initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.2, delay: Math.min(i, 12) * 0.012 } } : {}
              return (
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                <Row key={f.id} {...(anim as any)}>
                  <button
                    onClick={() => openFunction(f.id)}
                    onDoubleClick={() => pinTab(`fn:${f.id}`)}
                    onContextMenu={(e) => {
                      e.preventDefault()
                      set({ contextMenu: { x: e.clientX, y: e.clientY, id: f.id } })
                    }}
                    className={cn('relative block w-full border-b border-line/60 px-3 py-2.5 text-left transition-colors hover:bg-hover/50', activeTab === `fn:${f.id}` && 'bg-hover/80')}
                  >
                    {activeTab === `fn:${f.id}` && <span className="absolute inset-y-1 left-0 w-[2px] rounded-r bg-accent" />}
                    <div className="flex items-baseline gap-2">
                      {ranked && <span className="tnum w-5 flex-none text-right text-2xs text-fg3">{rank}</span>}
                      <span className="mono min-w-0 flex-1 truncate text-[12.5px] text-fg">{f.name}</span>
                      {f.speedup ? <CountUp value={f.speedup} decimals={1} suffix="×" className="flex-none text-sm font-semibold text-ok" /> : f.probe_speedup ? <span className="tnum flex-none text-xs text-fg3">{f.probe_speedup.toFixed(2)}× probe</span> : null}
                    </div>
                    <div className={cn('mt-0.5 flex items-center gap-2 text-xs text-fg3', ranked && 'pl-7')}>
                      <span className="min-w-0 flex-1 truncate">{basename(f.file)}</span>
                      <span className="tnum flex-none">{fmtPct(f.share, f.share != null && f.share < 0.1 ? 1 : 0)}</span>
                    </div>
                    <div className={cn('mt-1.5 flex items-center gap-2', ranked && 'pl-7')}>
                      <span className="h-[4px] flex-1 overflow-hidden rounded-full bg-hover">
                        <span className={cn('block h-full rounded-full transition-[width] duration-700 ease-out', f.status === 'not_eligible' ? 'bg-line2' : 'accent-grad')} style={{ width: `${Math.max(1.5, ((f.share ?? 0) / maxShare) * 100)}%` }} />
                      </span>
                      <StatusChip status={f.status} dense />
                    </div>
                  </button>
                  {i === limit - 1 && list.length > limit && (
                    <button onClick={() => setLimit(limit + 200)} className="w-full py-2 text-xs text-accent hover:underline">
                      Show {Math.min(200, list.length - limit)} more
                    </button>
                  )}
                </Row>
              )
            })}
          </ul>
        )}
      </div>
    </>
  )
}

// ------------------------------------------------------------------ context menu (right click on a function)
export function ContextMenu() {
  const m = useStudio((s) => s.contextMenu)
  const s = useStudio()
  useEffect(() => {
    if (!m) return
    const close = () => useStudio.getState().set({ contextMenu: null })
    const k = (e: KeyboardEvent) => e.key === 'Escape' && close()
    window.addEventListener('click', close)
    window.addEventListener('blur', close)
    window.addEventListener('keydown', k)
    window.addEventListener('scroll', close, true)
    return () => {
      window.removeEventListener('click', close)
      window.removeEventListener('blur', close)
      window.removeEventListener('keydown', k)
      window.removeEventListener('scroll', close, true)
    }
  }, [m])
  if (!m) return null
  const f = s.js.functions[m.id]
  if (!f) return null
  const acc = f.status === 'verified' || f.status === 'guarded'
  const item = (label: string, icon: JSX.Element, run: () => void, disabled?: boolean) => (
    <button key={label} disabled={disabled} onClick={() => { run(); useStudio.getState().set({ contextMenu: null }) }} className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-sm text-fg2 transition-colors hover:bg-accent/15 hover:text-fg disabled:pointer-events-none disabled:opacity-40">
      <span className="text-fg3">{icon}</span>
      {label}
    </button>
  )
  const x = Math.min(m.x, window.innerWidth - 220)
  const y = Math.min(m.y, window.innerHeight - 200)
  return (
    <div role="menu" className="surface-2 fixed z-[75] w-[208px] animate-fadeIn rounded-xl p-1" style={{ left: x, top: y }} onClick={(e) => e.stopPropagation()}>
      <div className="mono truncate px-2.5 py-1 text-xs text-fg3">{f.name}</div>
      {item('Open journey', <Route size={14} />, () => s.openFunction(m.id, 'journey'))}
      {item('Open diff', <GitCompare size={14} />, () => s.openFunction(m.id, 'diff'), !acc)}
      <div className="my-1 h-px bg-line" />
      {item(f.decision === 'accepted' ? 'Accepted' : 'Accept', <Check size={14} />, () => s.decide(m.id, 'accepted'), !acc)}
      {item('Reject', <X size={14} />, () => s.decide(m.id, 'rejected'), !acc)}
      <div className="my-1 h-px bg-line" />
      {item('Copy function id', <Copy size={14} />, () => { navigator.clipboard?.writeText(m.id); s.toast('Copied function id', 'ok') })}
    </div>
  )
}
