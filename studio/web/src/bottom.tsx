import { useEffect, useMemo, useRef, useState } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { AlertTriangle, ChevronDown, CircleAlert, Info, Search, X } from 'lucide-react'
import { api } from './api'
import { useStudio, type BottomTab } from './store'
import { BenchChart, E2EBars, type BenchRow } from './charts'
import { Empty, IconBtn, Skeleton } from './ui'
import { SEV_BG, cn, fmtMs, fmtX } from './lib/format'
import type { FidelityNote, FunctionRecord, Severity } from './types'

export function BottomPanel() {
  const s = useStudio()
  const tab = s.bottomTab
  const problems = useProblems()
  const tabs: { v: BottomTab; l: string; n?: number }[] = [
    { v: 'terminal', l: 'Terminal' },
    { v: 'problems', l: 'Problems', n: problems.filter((p) => p.sev !== 'info').length },
    { v: 'fidelity', l: 'Fidelity' },
    { v: 'benchmarks', l: 'Benchmarks' },
  ]
  return (
    <section aria-label="Bottom panel" className="no-print flex h-full min-h-0 flex-col border-t border-line bg-panel">
      <div role="tablist" className="flex h-8 flex-none items-center gap-1 border-b border-line px-2">
        {tabs.map((t) => (
          <button
            key={t.v}
            role="tab"
            aria-selected={tab === t.v}
            onClick={() => s.set({ bottomTab: t.v })}
            className={cn('relative flex h-8 items-center gap-1.5 px-2.5 text-sm transition-colors', tab === t.v ? 'text-fg' : 'text-fg3 hover:text-fg2')}
          >
            {t.l}
            {t.n ? <span className="tnum rounded-full bg-hover px-1.5 text-2xs text-fg2">{t.n}</span> : null}
            {tab === t.v && <span className="absolute inset-x-2 bottom-0 h-[2px] bg-accent" />}
          </button>
        ))}
        <span className="ml-auto" />
        <IconBtn title="Hide panel" onClick={() => s.set({ bottomOpen: false })}>
          <ChevronDown size={14} />
        </IconBtn>
      </div>
      <div className="min-h-0 flex-1">
        <div className={cn('h-full', tab === 'terminal' ? 'block' : 'hidden')}>
          <TerminalPane visible={tab === 'terminal'} />
        </div>
        {tab === 'problems' && <ProblemsPane problems={problems} />}
        {tab === 'fidelity' && <FidelityPane />}
        {tab === 'benchmarks' && <BenchmarksPane />}
      </div>
    </section>
  )
}

// ------------------------------------------------------------------ terminal
function cssRgb(name: string) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim().split(/\s+/).join(',')
  return `rgb(${v})`
}
function TerminalPane({ visible }: { visible: boolean }) {
  const host = useRef<HTMLDivElement>(null)
  const term = useRef<XTerm | null>(null)
  const fit = useRef<FitAddon | null>(null)
  const written = useRef({ job: '', n: 0 })
  const logs = useStudio((s) => s.js.logs)
  const jobId = useStudio((s) => s.js.jobId)
  const theme = useStudio((s) => s.theme)

  const [ready, setReady] = useState(0)
  useEffect(() => {
    if (!host.current) return
    let alive = true
    let ro: ResizeObserver | null = null
    let t: XTerm | null = null
    // created on the next tick so React StrictMode's instant unmount never touches a half-built terminal
    const timer = setTimeout(() => {
      if (!alive || !host.current) return
      t = new XTerm({
        fontFamily: "'JetBrains Mono', ui-monospace, monospace",
        fontSize: 12,
        lineHeight: 1.35,
        cursorBlink: false,
        disableStdin: true,
        convertEol: true,
        scrollback: 8000,
        theme: { background: cssRgb('--panel'), foreground: cssRgb('--fg2'), cursor: 'transparent', selectionBackground: 'rgba(139,133,255,0.3)' },
      })
      const f = new FitAddon()
      t.loadAddon(f)
      t.open(host.current)
      term.current = t
      fit.current = f
      written.current = { job: '', n: 0 }
      ro = new ResizeObserver(() => {
        try {
          if (alive && host.current && host.current.clientHeight > 10 && host.current.clientWidth > 10) f.fit()
        } catch {
          /* hidden */
        }
      })
      ro.observe(host.current)
      setReady((n) => n + 1)
    }, 0)
    return () => {
      alive = false
      clearTimeout(timer)
      ro?.disconnect()
      term.current = null
      fit.current = null
      setTimeout(() => t?.dispose(), 50)
    }
  }, [])

  useEffect(() => {
    if (term.current) term.current.options.theme = { background: cssRgb('--panel'), foreground: cssRgb('--fg2'), cursor: 'transparent', selectionBackground: 'rgba(139,133,255,0.3)' }
  }, [theme])

  useEffect(() => {
    const t = term.current
    if (!t) return
    if (written.current.job !== (jobId ?? '')) {
      t.reset()
      written.current = { job: jobId ?? '', n: 0 }
      if (!jobId) t.writeln('\x1b[90mBuild and trace output will stream here.\x1b[0m')
    }
    for (let i = written.current.n; i < logs.length; i++) {
      const l = logs[i]
      const tag = l.stream === 'build' ? '\x1b[36mbuild\x1b[0m' : l.stream === 'trace' ? '\x1b[35mtrace\x1b[0m' : '\x1b[90msystem\x1b[0m'
      const col = l.level === 'error' ? '\x1b[31m' : l.level === 'warn' ? '\x1b[33m' : ''
      t.writeln(`${tag}  ${col}${l.text}${col ? '\x1b[0m' : ''}`)
    }
    written.current.n = logs.length
  }, [logs, jobId, ready])

  useEffect(() => {
    if (visible) setTimeout(() => { try { fit.current?.fit() } catch { /* */ } }, 30)
  }, [visible])

  return <div ref={host} className="h-full w-full overflow-hidden" aria-label="Terminal output" role="log" />
}

// ------------------------------------------------------------------ problems
interface Problem {
  key: string
  sev: 'error' | 'warn' | 'info'
  msg: string
  fnId: string | null
  fnName: string
  file: string
  line: number
  src: string
}
function useProblems(): Problem[] {
  const js = useStudio((s) => s.js)
  return useMemo(() => {
    const out: Problem[] = []
    const name = (id: string) => js.functions[id]?.name ?? id.split('::').pop() ?? id
    for (const [id, fx] of Object.entries(js.fix)) {
      const f = js.functions[id]
      for (const a of fx.attempts) {
        if (!a.error) continue
        const m = /line (\d+)/.exec(a.error)
        out.push({ key: `fix:${id}:${a.attempt}`, sev: 'error', msg: a.error.replace(/^line \d+:\s*/, ''), fnId: id, fnName: name(id), file: f?.file ?? '', line: m ? +m[1] : 1, src: `rewrite ${a.attempt}` })
      }
    }
    for (const [id, c] of Object.entries(js.compile)) for (const d of c.diagnostics) out.push({ key: `c:${id}:${d.line}:${d.msg}`, sev: 'error', msg: d.msg, fnId: id, fnName: name(id), file: js.functions[id]?.file ?? '', line: d.line, src: 'compile' })
    for (const f of Object.values(js.functions)) {
      if (f.status === 'failed') out.push({ key: `f:${f.id}`, sev: 'error', msg: f.reason ?? 'Replay mismatch', fnId: f.id, fnName: f.name, file: f.file, line: 1, src: 'replay' })
      else if (f.status === 'fixable' || f.status === 'declined') out.push({ key: `w:${f.id}`, sev: 'warn', msg: f.reason ?? f.status, fnId: f.id, fnName: f.name, file: f.file, line: 1, src: f.status })
      else if (f.status === 'not_eligible') out.push({ key: `n:${f.id}`, sev: 'info', msg: f.reason ?? 'Not eligible', fnId: f.id, fnName: f.name, file: f.file, line: 1, src: 'eligibility' })
    }
    for (const e of js.errors) out.push({ key: `e:${e.seq}`, sev: 'error', msg: e.message, fnId: null, fnName: e.where, file: '', line: 1, src: 'engine' })
    const rank = { error: 0, warn: 1, info: 2 }
    return out.sort((a, b) => rank[a.sev] - rank[b.sev])
  }, [js.fix, js.compile, js.functions, js.errors])
}

function ProblemsPane({ problems }: { problems: Problem[] }) {
  const s = useStudio()
  const [f, setF] = useState<'all' | 'error' | 'warn' | 'info'>('all')
  const list = problems.filter((p) => f === 'all' || p.sev === f)
  const n = (k: string) => problems.filter((p) => p.sev === k).length
  const Ico = { error: CircleAlert, warn: AlertTriangle, info: Info }
  const col = { error: 'text-bad', warn: 'text-warn', info: 'text-fg3' }
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-7 flex-none items-center gap-3 border-b border-line px-3 text-xs">
        {(['all', 'error', 'warn', 'info'] as const).map((k) => (
          <button key={k} onClick={() => setF(k)} aria-pressed={f === k} className={cn('capitalize transition-colors', f === k ? 'text-fg' : 'text-fg3 hover:text-fg2')}>
            {k === 'all' ? `All ${problems.length}` : `${k === 'warn' ? 'warnings' : k === 'info' ? 'notes' : 'errors'} ${n(k)}`}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {!list.length ? (
          <Empty title={s.js.jobId ? 'No problems' : 'No problems yet'}>Typechecker, compiler and replay diagnostics show up here, each linked to its line.</Empty>
        ) : (
          <ul>
            {list.map((p) => {
              const I = Ico[p.sev]
              return (
                <li key={p.key}>
                  <button
                    onClick={() => {
                      if (p.fnId) {
                        const fn = s.js.functions[p.fnId]
                        if (p.src.startsWith('rewrite') || p.src === 'compile') s.openFunction(p.fnId, 'journey')
                        else if (fn) s.openFile(fn.file, fn.line)
                      }
                    }}
                    className="flex w-full items-start gap-2 border-b border-line/50 px-3 py-1.5 text-left text-sm hover:bg-hover/60"
                  >
                    <I size={14} className={cn('mt-[3px] flex-none', col[p.sev])} />
                    <span className="min-w-0 flex-1">
                      <span className="text-fg">{p.msg}</span>
                    </span>
                    <span className="mono flex-none text-xs text-fg3">
                      {p.fnName}
                      {p.file ? ` · ${p.file.split('/').pop()}` : ''}
                    </span>
                    <span className="w-[72px] flex-none text-right text-xs text-fg3">{p.src}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ fidelity
interface FRow extends FidelityNote {
  fn: string
  fnId: string
}
function useAllRecords(): { rows: FRow[]; loading: boolean } {
  const js = useStudio((s) => s.js)
  const fetchRecord = useStudio((s) => s.fetchRecord)
  const records = useStudio((s) => s.records)
  const ids = useMemo(() => Object.values(js.functions).filter((f) => f.status === 'verified' || f.status === 'guarded' || f.status === 'failed').map((f) => f.id), [js.functions])
  const key = ids.join('|')
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    let dead = false
    const need = ids.filter((id) => !records[id])
    if (!need.length) return
    setLoading(true)
    ;(async () => {
      for (let i = 0; i < need.length && !dead; i += 6) await Promise.all(need.slice(i, i + 6).map((id) => fetchRecord(id)))
      if (!dead) setLoading(false)
    })()
    return () => {
      dead = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  const rows: FRow[] = useMemo(() => {
    const out: FRow[] = []
    for (const id of ids) {
      const r: FunctionRecord | undefined = records[id]
      if (r) for (const n of r.fidelity) out.push({ ...n, fn: r.name, fnId: id })
    }
    return out
  }, [ids, records])
  return { rows, loading }
}

function FidelityPane() {
  const { rows, loading } = useAllRecords()
  const openFunction = useStudio((s) => s.openFunction)
  const [sev, setSev] = useState<Severity | 'all'>('all')
  const [q, setQ] = useState('')
  const sevRank = { divergent: 0, guarded: 1, exact: 2 }
  const list = rows.filter((r) => (sev === 'all' || r.severity === sev) && (!q || (r.cls + r.fn + r.detail).toLowerCase().includes(q.toLowerCase()))).sort((a, b) => sevRank[a.severity] - sevRank[b.severity])
  const cnt = (k: Severity) => rows.filter((r) => r.severity === k).length
  const sevs: (Severity | 'all')[] = ['all', 'exact', 'guarded', 'divergent']
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-8 flex-none items-center gap-3 border-b border-line px-3 text-xs">
        {sevs.map((k) => (
          <button key={k} onClick={() => setSev(k)} aria-pressed={sev === k} className={cn('flex items-center gap-1.5 capitalize', sev === k ? 'text-fg' : 'text-fg3 hover:text-fg2')}>
            {k !== 'all' && <span className={cn('h-2 w-2 rounded-sm', SEV_BG[k])} />}
            {k} <span className="tnum text-fg3">{k === 'all' ? rows.length : cnt(k)}</span>
          </button>
        ))}
        <label className="ml-auto flex h-5 items-center gap-1.5 rounded border border-line2 bg-bg px-1.5 text-fg3 focus-within:border-accent">
          <Search size={11} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter notes" aria-label="Filter fidelity notes" className="w-36 bg-transparent text-xs text-fg outline-none placeholder:text-fg3" />
          {q && <button aria-label="Clear" onClick={() => setQ('')}><X size={10} /></button>}
        </label>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {loading && !rows.length ? (
          <div className="space-y-2 p-3"><Skeleton className="h-4" /><Skeleton className="h-4 w-4/5" /><Skeleton className="h-4 w-3/5" /></div>
        ) : !list.length ? (
          <Empty title="No fidelity notes">Notes appear once functions are compiled. Each one names where compiled behaviour could differ from CPython and how PYTHIA guards it.</Empty>
        ) : (
          <ul>
            {list.map((r, i) => (
              <li key={i}>
                <button onClick={() => openFunction(r.fnId, 'three')} className="flex w-full items-start gap-2.5 border-b border-line/50 px-3 py-1.5 text-left hover:bg-hover/60">
                  <span className={cn('mt-[7px] h-2 w-2 flex-none rounded-sm', SEV_BG[r.severity])} />
                  <span className="min-w-0 flex-1">
                    <span className="text-sm text-fg">{r.cls}</span>
                    <span className="block truncate text-xs text-fg3">{r.detail}</span>
                  </span>
                  <span className="mono flex-none pt-[1px] text-xs text-fg3">
                    {r.fn}:{r.line}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ benchmarks
export function useBenchRows(): BenchRow[] {
  const js = useStudio((s) => s.js)
  return useMemo(
    () =>
      Object.entries(js.bench)
        .map(([id, b]) => ({ id, name: js.functions[id]?.name ?? id.split('::').pop()!, py_ms: b.py_ms, cpp_ms: b.cpp_ms, speedup: b.speedup, probe: b.probe }))
        .sort((a, b) => b.speedup - a.speedup),
    [js.bench, js.functions],
  )
}
function BenchmarksPane() {
  const rows = useBenchRows()
  const e2e = useStudio((s) => s.js.e2e)
  const openFunction = useStudio((s) => s.openFunction)
  if (!rows.length && !e2e) return <Empty title="No benchmarks yet">Per-function CPython vs C++ timings and the end-to-end before/after appear after the Benchmark stage.</Empty>
  return (
    <div className="flex h-full gap-8 overflow-auto p-4">
      <div className="min-w-0 flex-1">
        <BenchChart rows={rows} onPick={(id) => openFunction(id, 'journey')} compact />
      </div>
      {e2e && (
        <div className="w-[300px] flex-none">
          <div className="mb-2 text-xs font-medium text-fg2">End to end · <span className="mono text-fg3">{e2e.cmd}</span></div>
          <E2EBars e2e={e2e} />
          <div className="mt-3 text-xs text-fg3">Median per-call timings use the recorded inputs; {rows.length} functions measured. Probe results (red) were not spliced.</div>
          <div className="tnum mt-1 text-xs text-fg3">Slowest accelerated call {fmtMs(Math.max(...rows.map((r) => r.cpp_ms), 0))} · best {fmtX(Math.max(...rows.map((r) => r.speedup), 0))}</div>
        </div>
      )}
    </div>
  )
}
export { api }
