import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, FileCode2, Flame, Folder, FolderOpen, Search } from 'lucide-react'
import { api } from './api'
import { useStudio } from './store'
import type { FunctionSummary, Status, TreeNode } from './types'
import { STATUS, basename, cn, fmtPct, fmtX } from './lib/format'
import { Bar, Empty, PanelTitle, Skeleton, StatusChip } from './ui'

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
      <div className="min-h-0 flex-1 overflow-auto py-1">
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
  const pad = 8 + depth * 12
  return (
    <div>
      <div
        role="treeitem"
        tabIndex={0}
        aria-expanded={isDir ? open : undefined}
        onClick={() => (isDir ? setOpen(!open) : s.openFile(node.path))}
        onKeyDown={(e) => {
          if (e.key === 'Enter') isDir ? setOpen(!open) : s.openFile(node.path)
          if (e.key === 'ArrowRight' && isDir) setOpen(true)
          if (e.key === 'ArrowLeft' && isDir) setOpen(false)
        }}
        className={cn('group flex h-[24px] cursor-pointer items-center gap-1 pr-2 text-sm hover:bg-hover/60', active && 'bg-hover text-fg')}
        style={{ paddingLeft: pad }}
      >
        {isDir ? (
          <>
            {open ? <ChevronDown size={13} className="flex-none text-fg3" /> : <ChevronRight size={13} className="flex-none text-fg3" />}
            {open ? <FolderOpen size={14} className="flex-none text-fg3" /> : <Folder size={14} className="flex-none text-fg3" />}
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
            <FileCode2 size={14} className="flex-none text-fg3" />
          </>
        )}
        <span className="min-w-0 flex-1 truncate">{node.name}</span>
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
            onKeyDown={(e) => e.key === 'Enter' && s.openFunction(f.id)}
            className={cn('flex h-[22px] cursor-pointer items-center gap-2 pr-2 text-xs text-fg2 hover:bg-hover/60', s.activeTab === `fn:${f.id}` && 'bg-hover text-fg')}
            style={{ paddingLeft: pad + 28 }}
          >
            <span className={cn('h-1.5 w-1.5 flex-none rounded-full', STATUS[f.status].dot)} />
            <span className="mono min-w-0 flex-1 truncate">{f.name}</span>
            {f.speedup ? <span className="tnum text-ok">{fmtX(f.speedup)}</span> : null}
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
        <span className="flex items-center gap-0.5 text-fg3" title={`${b.hotspots} hotspots`}>
          <Flame size={10} />
          {b.hotspots}
        </span>
      )}
      {b.accelerated > 0 && (
        <span className="rounded bg-ok/15 px-1 text-ok" title={`${b.accelerated} accelerated`}>
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

  return (
    <>
      <PanelTitle right={<span className="tnum text-xs text-fg3">{list.length}</span>}>{ranked ? 'Hotspots · ranked' : 'Hotspots'}</PanelTitle>
      <div className="flex flex-none flex-col gap-2 border-b border-line p-2">
        <label className="flex h-6 items-center gap-1.5 rounded-md border border-line2 bg-bg px-2 text-fg3 focus-within:border-accent">
          <Search size={12} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter functions" aria-label="Filter functions" className="min-w-0 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-fg3" />
        </label>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f.v}
              onClick={() => setFilter(f.v)}
              aria-pressed={filter === f.v}
              className={cn('rounded px-1.5 py-0.5 text-xs transition-colors', filter === f.v ? 'bg-hover text-fg' : 'text-fg3 hover:text-fg2')}
            >
              {f.l}
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {!js.jobId ? (
          <Empty title="No hotspots yet" icon={<Flame size={20} />}>
            Open a project and PYTHIA will rank its functions by real time spent and by how well they compile.
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
            {list.slice(0, limit).map((f, i) => (
              <li key={f.id}>
                <button
                  onClick={() => openFunction(f.id)}
                  className={cn('block w-full border-b border-line/60 px-3 py-2 text-left transition-colors hover:bg-hover/60', activeTab === `fn:${f.id}` && 'bg-hover')}
                >
                  <div className="flex items-baseline gap-2">
                    {ranked && <span className="tnum w-5 flex-none text-right text-2xs text-fg3">{js.order.indexOf(f.id) + 1}</span>}
                    <span className="mono min-w-0 flex-1 truncate text-fg">{f.name}</span>
                    <span className={cn('tnum flex-none text-sm font-medium', f.speedup ? 'text-ok' : f.probe_speedup ? 'text-fg3' : 'text-fg3')}>
                      {f.speedup ? fmtX(f.speedup) : f.probe_speedup ? `${fmtX(f.probe_speedup)} probe` : ''}
                    </span>
                  </div>
                  <div className={cn('mt-0.5 truncate text-xs text-fg3', ranked && 'pl-7')}>{basename(f.file)}</div>
                  <div className={cn('mt-1.5 flex items-center gap-2', ranked && 'pl-7')}>
                    <Bar value={f.share ?? 0} max={maxShare} className="h-[5px] flex-1" color={f.status === 'not_eligible' ? 'bg-line2' : 'bg-accent/80'} />
                    <span className="tnum w-9 flex-none text-right text-2xs text-fg3">{fmtPct(f.share, f.share != null && f.share < 0.1 ? 1 : 0)}</span>
                    <StatusChip status={f.status} dense />
                  </div>
                </button>
                {i === limit - 1 && list.length > limit && (
                  <button onClick={() => setLimit(limit + 200)} className="w-full py-2 text-xs text-accent hover:underline">
                    Show {Math.min(200, list.length - limit)} more
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  )
}
