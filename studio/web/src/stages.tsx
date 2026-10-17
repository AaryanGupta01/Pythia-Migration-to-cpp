import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { ArrowDown, ArrowUp, ChevronRight, Download, FileText, Folder, FileCode2 } from 'lucide-react'
import { api } from './api'
import { useStudio } from './store'
import { useBenchRows } from './bottom'
import { BenchChart, E2EBars, FlameChart, HBars, ReplayMatrix } from './charts'
import { Code, MiniDiff } from './code'
import { DiffView } from './editors'
import { Journey, useRecord } from './journey'
import { exportProject } from './actions'
import { Bar, Btn, Empty, Skeleton, Spark, StatusChip, Dot } from './ui'
import { STATUS, attemptSource, basename, cn, fmtBytes, fmtInt, fmtLatency, fmtMs, fmtPct, fmtX, llmLabel } from './lib/format'
import { Logo } from './shell'
import { STAGES, type FunctionSummary, type StageName } from './types'

const BLURB: Record<StageName, string> = {
  ingest: 'Copy the project into an isolated workspace. The original is never touched.',
  scan: 'Parse every function and ask the typechecker whether PYTHIA can compile it, and if not, why.',
  trace: 'Run the entry command under a tracer to measure where time really goes and record real arguments.',
  rank: 'Order functions by trace share, expected benefit, eligibility and the cost of crossing the Python/C++ boundary.',
  fix: 'Give almost-eligible functions types from the trace, or ask the LLM for a PySub rewrite the typechecker must accept.',
  compile: 'Transpile each accepted PySub function to C++17 and build a pybind11 extension module.',
  verify: 'Replay recorded calls through CPython and the compiled module. Anything that differs is rejected.',
  benchmark: 'Time Python against C++ on the recorded inputs, then run the whole program before and after.',
  splice: 'Route calls to the compiled modules inside the workspace copy, with a Python fallback.',
  export: 'Write the accelerated project, a report, and a script that rebuilds the modules elsewhere.',
}

export function StageInspector({ stage }: { stage: StageName }) {
  const js = useStudio((s) => s.js)
  const info = js.stages[stage]
  const idx = STAGES.indexOf(stage)
  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex-none border-b border-line bg-panel px-5 py-3">
        <div className="flex items-baseline gap-3">
          <span className="tnum text-xs text-fg3">Stage {idx + 1} of {STAGES.length}</span>
          <h2 className="text-[15px] font-medium capitalize">{stage}</h2>
          <span className="flex items-center gap-1.5 text-sm text-fg2">
            <Dot state={info.state} />
            {info.state === 'idle' ? (js.jobId ? 'Waiting' : 'Not started') : info.state === 'running' ? 'Running' : info.state === 'done' ? 'Done' : info.state === 'failed' ? 'Failed' : 'Skipped'}
            {info.summary && <span className="text-fg">· {info.summary}</span>}
          </span>
        </div>
        <p className="mt-1 max-w-[760px] text-sm text-fg3">{BLURB[stage]}</p>
      </header>
      <div className="min-h-0 flex-1 overflow-auto">
        {!js.jobId ? (
          <Empty title="Nothing to inspect yet" icon={<Logo size={22} />}>Open a project from the Welcome tab. Each stage shows its real output here as it runs.</Empty>
        ) : (
          <div className="px-5 py-4">
            {stage === 'ingest' && <IngestView />}
            {stage === 'scan' && <ScanView />}
            {stage === 'trace' && <TraceView />}
            {stage === 'rank' && <RankView />}
            {stage === 'fix' && <FixView />}
            {stage === 'compile' && <CompileView />}
            {stage === 'verify' && <VerifyView />}
            {stage === 'benchmark' && <BenchView />}
            {stage === 'splice' && <SpliceView />}
            {stage === 'export' && <ExportView />}
          </div>
        )}
      </div>
    </div>
  )
}

const Card = ({ title, children, right, className }: { title?: ReactNode; children: ReactNode; right?: ReactNode; className?: string }) => (
  <section className={cn('surface rounded-[12px]', className)}>
    {title && (
      <div className="flex items-center justify-between border-b border-line px-3.5 py-2">
        <h3 className="text-sm font-medium">{title}</h3>
        {right}
      </div>
    )}
    <div className="p-3.5">{children}</div>
  </section>
)
const Stat = ({ k, v, sub }: { k: string; v: ReactNode; sub?: string }) => (
  <div>
    <div className="text-xs text-fg3">{k}</div>
    <div className="tnum text-xl font-semibold leading-7 tracking-tight">{v}</div>
    {sub && <div className="text-xs text-fg3">{sub}</div>}
  </div>
)
const Waiting = ({ what }: { what: string }) => (
  <div className="space-y-2 py-2" aria-busy>
    <div className="text-sm text-fg3">Waiting for {what}…</div>
    <Skeleton className="h-4 w-2/3" />
    <Skeleton className="h-4 w-1/2" />
  </div>
)

// ------------------------------------------------------------------ ingest
function IngestView() {
  const js = useStudio((s) => s.js)
  const openFile = useStudio((s) => s.openFile)
  const ig = js.ingest
  const files = useMemo(() => {
    const m: Record<string, number> = {}
    for (const f of Object.values(js.functions)) m[f.file] = (m[f.file] ?? 0) + 1
    return Object.entries(m).sort()
  }, [js.functions])
  return (
    <div className="grid grid-cols-[1fr_340px] gap-4 max-xl:grid-cols-1">
      <div className="space-y-4">
        <div className="grid grid-cols-4 gap-4">
          <Card><Stat k="Files copied" v={fmtInt(ig.done?.files ?? ig.files)} /></Card>
          <Card><Stat k="Python files" v={ig.done ? fmtInt(ig.done.py_files) : '—'} /></Card>
          <Card><Stat k="Size" v={fmtBytes(ig.bytes)} /></Card>
          <Card><Stat k="Skipped" v={ig.done ? ig.done.skipped.length : '—'} /></Card>
        </div>
        <Card title="Python files">
          {files.length ? (
            <ul className="divide-y divide-line">
              {files.map(([p, n]) => (
                <li key={p}>
                  <button onClick={() => openFile(p)} className="flex w-full items-center gap-3 py-1.5 text-left hover:bg-hover/50">
                    <FileCode2 size={14} className="text-fg3" />
                    <span className="mono flex-1 truncate">{p}</span>
                    <span className="tnum text-xs text-fg3">{n} functions</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : ig.done ? (
            <p className="text-sm text-fg3">Files are listed once the scan finds functions.</p>
          ) : <Waiting what="the copy to finish" />}
        </Card>
      </div>
      <div className="space-y-4">
        <Card title="Skipped">
          {ig.done?.skipped.length ? (
            <ul className="space-y-1.5 text-sm">
              {ig.done.skipped.map((s) => (
                <li key={s.path} className="flex items-baseline justify-between gap-3"><span className="mono truncate">{s.path}</span><span className="flex-none text-xs text-fg3">{s.reason}</span></li>
              ))}
            </ul>
          ) : <p className="text-sm text-fg3">{ig.done ? 'Nothing was skipped.' : 'Ignored folders and files over 5 MB are listed here.'}</p>}
        </Card>
        <Card title="Progress log">
          <ul className="mono max-h-56 space-y-0.5 overflow-auto text-xs text-fg2">
            {ig.messages.slice(-30).map((m, i) => <li key={i}>{m}</li>)}
            {!ig.messages.length && <li className="text-fg3">No output yet.</li>}
          </ul>
        </Card>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ scan (sortable table)
type SortKey = 'name' | 'file' | 'lines' | 'eligibility' | 'status' | 'score'
function ScanView() {
  const js = useStudio((s) => s.js)
  const openFunction = useStudio((s) => s.openFunction)
  const [sort, setSort] = useState<{ k: SortKey; dir: 1 | -1 }>({ k: 'file', dir: 1 })
  const [q, setQ] = useState('')
  const rows = useMemo(() => {
    const val = (f: FunctionSummary): string | number => {
      switch (sort.k) {
        case 'name': return f.name
        case 'file': return f.file + String(f.line).padStart(6, '0')
        case 'lines': return f.end_line - f.line + 1
        case 'eligibility': return f.eligibility
        case 'status': return STATUS[f.status].rank
        case 'score': return f.score.total
      }
    }
    const needle = q.toLowerCase()
    return Object.values(js.functions)
      .filter((f) => !needle || f.name.includes(needle) || f.file.includes(needle) || (f.reason ?? '').toLowerCase().includes(needle))
      .sort((a, b) => (val(a) < val(b) ? -sort.dir : val(a) > val(b) ? sort.dir : 0))
  }, [js.functions, sort, q])
  const sc = js.scan
  const th = (k: SortKey, label: string, cls = '') => (
    <th className={cn('sticky top-0 z-10 bg-raised px-3 py-2 text-left text-xs font-medium text-fg3', cls)}>
      <button onClick={() => setSort({ k, dir: sort.k === k ? (-sort.dir as 1 | -1) : 1 })} className="inline-flex items-center gap-1 hover:text-fg">
        {label}
        {sort.k === k && (sort.dir === 1 ? <ArrowUp size={11} /> : <ArrowDown size={11} />)}
      </button>
    </th>
  )
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-4">
        <Card><Stat k="Functions found" v={sc?.functions ?? Object.keys(js.functions).length} /></Card>
        <Card><Stat k="Compile as written" v={sc?.verifiable ?? '—'} /></Card>
        <Card><Stat k="Fixable" v={sc?.fixable ?? '—'} /></Card>
        <Card><Stat k="Not eligible" v={sc?.not_eligible ?? '—'} /></Card>
      </div>
      <Card title="All functions" right={<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter" aria-label="Filter functions" className="h-6 w-44 rounded border border-line2 bg-bg px-2 text-sm outline-none focus:border-accent" />} className="overflow-hidden [&>div:last-child]:p-0">
        {!rows.length ? <div className="p-4"><Waiting what="the scan" /></div> : (
          <div className="max-h-[calc(100vh-420px)] min-h-[200px] overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line">{th('name', 'Function')}{th('file', 'File')}{th('lines', 'Lines', 'text-right')}{th('eligibility', 'Eligibility')}{th('status', 'Status')}{th('score', 'Score', 'text-right')}<th className="sticky top-0 bg-raised px-3 py-2 text-left text-xs font-medium text-fg3">Reason</th></tr>
              </thead>
              <tbody>
                {rows.map((f) => (
                  <tr key={f.id} onClick={() => openFunction(f.id)} className="cursor-pointer border-b border-line/50 hover:bg-hover/50">
                    <td className="mono px-3 py-1.5">{f.qualname}</td>
                    <td className="mono px-3 py-1.5 text-xs text-fg3">{f.file.replace('textlab/', '')}:{f.line}</td>
                    <td className="tnum px-3 py-1.5 text-right text-fg2">{f.end_line - f.line + 1}</td>
                    <td className="whitespace-nowrap px-3 py-1.5 text-fg2">{f.eligibility.replace('_', ' ')}</td>
                    <td className="px-3 py-1.5"><StatusChip status={f.status} dense /></td>
                    <td className="tnum px-3 py-1.5 text-right text-fg2">{f.score.total.toFixed(2)}</td>
                    <td className="max-w-[320px] truncate px-3 py-1.5 text-xs text-fg3" title={f.reason ?? undefined}>{f.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

// ------------------------------------------------------------------ trace
function TraceView() {
  const js = useStudio((s) => s.js)
  const openFunction = useStudio((s) => s.openFunction)
  const fetchRecord = useStudio((s) => s.fetchRecord)
  const records = useStudio((s) => s.records)
  const top = (js.trace.done?.profile ?? []).slice(0, 40)
  useEffect(() => {
    let dead = false
    const need = top.map((r) => r.id).filter((id) => !records[id])
    ;(async () => {
      for (let i = 0; i < need.length && !dead; i += 6) await Promise.all(need.slice(i, i + 6).map((id) => fetchRecord(id)))
    })()
    return () => {
      dead = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [top.length])
  // self time makes the icicle additive; fall back to cumulative share until the records have loaded
  const haveSelf = top.length > 0 && top.every((r) => records[r.id]?.trace)
  const t = js.trace
  const done = t.done
  const rows = (done?.profile ?? []).map((r) => ({ id: r.id, label: js.functions[r.id]?.name ?? r.id, value: r.share, sub: `${fmtInt(r.calls)} calls` })).slice(0, 24)
  const cmd = js.options?.trace_cmd
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-4">
        <Card><Stat k="Entry command" v={<span className="mono text-sm font-normal">{cmd ?? 'none (static ranking)'}</span>} /></Card>
        <Card><Stat k="Calls recorded" v={fmtInt(done?.calls ?? t.calls)} /></Card>
        <Card><Stat k="Run time" v={done ? `${done.total_s.toFixed(1)} s` : `${t.elapsed_s.toFixed(1)} s`} sub={done ? `exit code ${done.exit_code}${done.timed_out ? ', timed out' : ''}` : 'running'} /></Card>
        <Card><Stat k="Functions seen" v={done ? done.profile.length : t.functions_seen} /></Card>
      </div>
      {!done ? (
        <div className="grid grid-cols-2 gap-4">
          <Card title="Calls over time"><Spark values={t.history.map((h) => h.calls)} className="h-24 w-full" /></Card>
          <Card title="Program output (tail)"><pre className="mono min-h-[96px] whitespace-pre-wrap text-xs text-fg2">{t.stdout_tail || 'Waiting for output…'}</pre></Card>
        </div>
      ) : (
        <>
          <Card title="Where the time goes" right={<span className="text-xs text-fg3">{haveSelf ? 'self time' : 'cumulative time'} · program, files, functions</span>}>
            <FlameChart
              rows={done.profile.filter((r) => js.functions[r.id]).map((r) => ({ id: r.id, name: js.functions[r.id].name, file: js.functions[r.id].file, share: haveSelf && records[r.id]?.trace ? Math.max(0.0005, records[r.id]!.trace!.self_s / Math.max(0.001, done.total_s)) : haveSelf ? 0 : r.share, calls: r.calls, cum_s: haveSelf && records[r.id]?.trace ? records[r.id]!.trace!.self_s : r.cum_s })).filter((r) => r.share > 0)}
              totalS={done.total_s}
              cmd={cmd ?? 'traced run'}
              onPick={(id) => openFunction(id)}
            />
          </Card>
          <Card title="Hottest functions" right={<span className="text-xs text-fg3">cumulative share of traced runtime (includes callees) · top {rows.length}</span>}>
            <HBars rows={rows} fmt={(v) => fmtPct(v)} onPick={(id) => openFunction(id)} />
          </Card>
        </>
      )}
    </div>
  )
}

// ------------------------------------------------------------------ rank
function RankView() {
  const js = useStudio((s) => s.js)
  const openFunction = useStudio((s) => s.openFunction)
  if (!js.ranking) return <Waiting what="the ranking" />
  const mini = (v: number | null, max = 1, color = 'bg-accent/80') => (
    <div className="flex items-center gap-2">
      <Bar value={v ?? 0} max={max} className="h-[5px] w-14" color={color} />
      <span className="tnum w-9 text-right text-xs text-fg2">{v == null ? '—' : v < 1 ? v.toFixed(2) : v.toFixed(1)}</span>
    </div>
  )
  return (
    <Card title="Score breakdown" right={<span className="text-xs text-fg3">score = time share × eligibility × expected benefit, minus boundary cost</span>} className="overflow-hidden [&>div:last-child]:p-0">
      <div className="max-h-[calc(100vh-260px)] overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-fg3">
              {['#', 'Function', 'Score', 'Time share', 'Static', 'Eligibility', 'Benefit (×)', 'Boundary cost', 'Status'].map((h) => <th key={h} className="sticky top-0 bg-raised px-3 py-2 font-medium">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {js.ranking.slice(0, 80).map((r) => (
              <tr key={r.id} onClick={() => openFunction(r.id)} className="cursor-pointer border-b border-line/50 hover:bg-hover/50" title={r.reason ?? undefined}>
                <td className="tnum px-3 py-1.5 text-fg3">{r.rank}</td>
                <td className="mono px-3 py-1.5">{js.functions[r.id]?.name ?? r.id}</td>
                <td className="tnum px-3 py-1.5 font-medium">{r.score.total.toFixed(2)}</td>
                <td className="px-3 py-1.5">{mini(r.score.trace_share, 0.25)}</td>
                <td className="px-3 py-1.5">{mini(r.score.static_heuristic)}</td>
                <td className="px-3 py-1.5">{mini(r.score.eligibility_factor)}</td>
                <td className="px-3 py-1.5">{mini(r.score.expected_benefit, 60, 'bg-ok/70')}</td>
                <td className="px-3 py-1.5">{mini(r.score.boundary_penalty, 1, 'bg-bad/70')}</td>
                <td className="px-3 py-1.5"><StatusChip status={js.functions[r.id]?.status ?? r.status} dense /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

// ------------------------------------------------------------------ fix
function FixView() {
  const js = useStudio((s) => s.js)
  const ids = Object.keys(js.fix)
  const steps = js.steps.filter((s) => s.fn_id && /annotat|skipped/.test(s.title) && !js.fix[s.fn_id!])
  if (!ids.length && !steps.length) return js.stages.fix.state === 'done' ? <Empty title="Nothing needed fixing">Every eligible function compiled as written.</Empty> : <Waiting what="fix attempts" />
  const all = ids.flatMap((id) => js.fix[id].attempts)
  const lat = all.map((a) => a.latency_ms).filter((x): x is number => x != null && a_ok(x))
  const env = useStudio.getState().env
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-4 gap-4">
        <Card><Stat k="Functions sent to the LLM" v={ids.length} /></Card>
        <Card><Stat k="Rewrites accepted" v={ids.filter((i) => js.fix[i].done?.ok).length} sub={`of ${ids.length}`} /></Card>
        <Card><Stat k="Attempts" v={all.length} sub={`${all.filter((a) => !a.ok).length} rejected by the typechecker`} /></Card>
        <Card><Stat k="Median latency" v={lat.length ? fmtLatency(lat.sort((a, b) => a - b)[Math.floor(lat.length / 2)]) : '—'} sub={env ? llmLabel(env).replace('LLM: ', '') : undefined} /></Card>
      </div>
      {ids.map((id) => <FixCard key={id} id={id} />)}
      {steps.length > 0 && (
        <Card title="Handled without the LLM">
          <ul className="space-y-1.5 text-sm">
            {steps.map((s) => <li key={s.step_id} className="flex gap-3"><span className="mono w-44 flex-none truncate">{js.functions[s.fn_id!]?.name}</span><span className="text-fg2">{s.detail ?? s.title}</span></li>)}
          </ul>
        </Card>
      )}
    </div>
  )
}
const a_ok = (x: number) => x > 0
function FixCard({ id }: { id: string }) {
  const js = useStudio((s) => s.js)
  const fx = js.fix[id]
  const [open, setOpen] = useState(true)
  const f = js.functions[id]
  const { rec } = useRecord(id)
  const orig = rec?.sources.annotated ?? rec?.sources.original ?? ''
  return (
    <Card
      title={
        <button className="flex items-center gap-2" onClick={() => setOpen(!open)} aria-expanded={open}>
          <ChevronRight size={14} className={cn('transition-transform', open && 'rotate-90')} />
          <span className="mono">{f?.name ?? id}</span>
          <span className="text-xs font-normal text-fg3">{fx.attempts.length} attempt{fx.attempts.length === 1 ? '' : 's'}</span>
        </button>
      }
      right={fx.done ? <span className={cn('text-xs', fx.done.ok ? 'text-ok' : 'text-bad')}>{fx.done.ok ? 'accepted' : 'gave up'}</span> : <span className="text-xs text-accent">in progress</span>}
    >
      {open && (
        <div className="space-y-3">
          {fx.attempts.length === 0 && <p className="text-sm text-fg2">Annotated from observed types. The typechecker accepted it without an LLM call.</p>}
          {fx.attempts.map((a, i) => (
            <div key={a.attempt}>
              <div className="mb-1 flex items-center gap-2 text-sm">
                <b className="font-medium">Attempt {a.attempt}</b>
                <span className="rounded-full border border-line2 bg-bg px-2 py-px text-xs text-fg2">{attemptSource(useStudio.getState().env, a)}</span>
                {a.latency_ms != null && <span className="tnum text-xs text-fg3">{fmtLatency(a.latency_ms)}</span>}
                <span className={cn('ml-auto text-xs', a.ok ? 'text-ok' : 'text-bad')}>{a.ok ? 'passed the typechecker' : 'rejected'}</span>
              </div>
              <MiniDiff a={i === 0 ? orig || a.pysub : fx.attempts[i - 1].pysub} b={a.pysub} maxH={200} />
              {a.error && <div className="mt-1.5 rounded border border-bad/25 bg-bad/10 px-2.5 py-1.5 text-sm text-bad"><b className="font-medium">Typechecker:</b> {a.error}</div>}
            </div>
          ))}
          {fx.done && !fx.done.ok && fx.done.reason && <p className="text-sm text-fg2">{fx.done.reason}</p>}
        </div>
      )}
    </Card>
  )
}

// ------------------------------------------------------------------ compile
function CompileView() {
  const js = useStudio((s) => s.js)
  const ids = Object.keys(js.compile)
  const logs = js.logs.filter((l) => l.stream === 'build')
  if (!ids.length) return <Waiting what="the first build" />
  const totalS = ids.reduce((a, id) => a + js.compile[id].compile_s, 0)
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-4">
        <Card><Stat k="Modules built" v={ids.length} /></Card>
        <Card><Stat k="Cache hits" v={ids.filter((i) => js.compile[i].cached).length} sub="content-hash build cache" /></Card>
        <Card><Stat k="Compile time" v={`${totalS.toFixed(1)} s`} /></Card>
        <Card><Stat k="Failed" v={ids.filter((i) => !js.compile[i].ok).length} /></Card>
      </div>
      <Card title="Modules" className="overflow-hidden [&>div:last-child]:p-0">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-line text-left text-xs text-fg3"><th className="px-3 py-2 font-medium">Function</th><th className="px-3 py-2 font-medium">Module</th><th className="px-3 py-2 text-right font-medium">Time</th><th className="px-3 py-2 font-medium">Result</th></tr></thead>
          <tbody>
            {ids.map((id) => {
              const c = js.compile[id]
              return (
                <tr key={id} className="border-b border-line/50">
                  <td className="mono px-3 py-1.5">{js.functions[id]?.name}</td>
                  <td className="mono px-3 py-1.5 text-xs text-fg3">{c.module}</td>
                  <td className="tnum px-3 py-1.5 text-right text-fg2">{c.cached ? 'cached' : `${c.compile_s.toFixed(1)} s`}</td>
                  <td className={cn('px-3 py-1.5', c.ok ? 'text-ok' : 'text-bad')}>{c.ok ? (c.cached ? 'cache hit' : 'built') : c.error}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>
      <Card title="Build log" right={<span className="text-xs text-fg3">{logs.length} lines</span>}>
        <pre className="mono max-h-72 overflow-auto whitespace-pre text-xs text-fg2">{logs.map((l) => l.text).join('\n') || 'No build output.'}</pre>
      </Card>
    </div>
  )
}

// ------------------------------------------------------------------ verify
function VerifyView() {
  const js = useStudio((s) => s.js)
  const openFunction = useStudio((s) => s.openFunction)
  const ids = Object.keys(js.verify)
  if (!ids.length) return <Waiting what="oracle replay" />
  const tot = ids.reduce((a, i) => a + js.verify[i].total, 0)
  const mat = ids.reduce((a, i) => a + js.verify[i].matched, 0)
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-4">
        <Card><Stat k="Calls replayed" v={fmtInt(tot)} /></Card>
        <Card><Stat k="Matched exactly" v={fmtInt(mat)} sub={fmtPct(mat / Math.max(1, tot))} /></Card>
        <Card><Stat k="Functions verified" v={ids.filter((i) => js.verify[i].status !== 'failed').length} sub={`of ${ids.length}`} /></Card>
        <Card><Stat k="Rejected" v={ids.filter((i) => js.verify[i].status === 'failed').length} /></Card>
      </div>
      <Card title="Replay results" className="overflow-hidden [&>div:last-child]:p-0">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-line text-left text-xs text-fg3"><th className="px-3 py-2 font-medium">Function</th><th className="px-3 py-2 font-medium">Status</th><th className="px-3 py-2 font-medium">Recorded calls (one cell each)</th><th className="px-3 py-2 font-medium">First counterexample</th></tr></thead>
          <tbody>
            {ids.map((id) => {
              const v = js.verify[id]
              return (
                <tr key={id} onClick={() => openFunction(id)} className="cursor-pointer border-b border-line/50 hover:bg-hover/50">
                  <td className="mono px-3 py-1.5">{js.functions[id]?.name}</td>
                  <td className="px-3 py-1.5"><StatusChip status={v.status} dense /></td>
                  <td className="px-3 py-2"><div className="flex items-center gap-3"><ReplayMatrix total={v.total} matched={v.matched} cell={5} max={260} className="max-w-[340px] flex-1" /><span className="tnum w-14 flex-none text-xs text-fg2">{v.matched}/{v.total}</span></div></td>
                  <td className="mono max-w-[360px] truncate px-3 py-1.5 text-xs text-fg3">{v.first_mismatch ? `${js.functions[id]?.name}${v.first_mismatch.args}: Python ${v.first_mismatch.python}, C++ ${v.first_mismatch.cpp}` : '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>
    </div>
  )
}

// ------------------------------------------------------------------ benchmark
function BenchView() {
  const js = useStudio((s) => s.js)
  const rows = useBenchRows()
  const openFunction = useStudio((s) => s.openFunction)
  if (!rows.length && !js.e2e) return <Waiting what="timings" />
  return (
    <div className="grid grid-cols-[1fr_340px] gap-4 max-xl:grid-cols-1">
      <Card title="Python vs C++ per function" right={<span className="text-xs text-fg3">median, log scale</span>}>
        <BenchChart rows={rows} onPick={(id) => openFunction(id, 'journey')} />
      </Card>
      <div className="space-y-4">
        <Card title="End to end">{js.e2e ? <><div className="mono mb-3 text-xs text-fg3">{js.e2e.cmd}</div><E2EBars e2e={js.e2e} /></> : <Waiting what="the whole-program run" />}</Card>
        <Card title="Summary">
          <div className="space-y-1 text-sm">
            <div className="flex justify-between"><span className="text-fg3">Functions timed</span><span className="tnum">{rows.length}</span></div>
            <div className="flex justify-between"><span className="text-fg3">Faster than Python</span><span className="tnum text-ok">{rows.filter((r) => r.speedup > 1).length}</span></div>
            <div className="flex justify-between"><span className="text-fg3">Slower (probes)</span><span className="tnum text-bad">{rows.filter((r) => r.speedup <= 1).length}</span></div>
            <div className="flex justify-between"><span className="text-fg3">Best</span><span className="tnum">{fmtX(Math.max(...rows.map((r) => r.speedup), 0))}</span></div>
            <div className="flex justify-between"><span className="text-fg3">Total C++ time</span><span className="tnum">{fmtMs(rows.reduce((a, r) => a + r.cpp_ms, 0))}</span></div>
          </div>
        </Card>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ splice
function SpliceView() {
  const js = useStudio((s) => s.js)
  const rev = useStudio((s) => s.rev)
  const [file, setFile] = useState<string | null>(null)
  const [diff, setDiff] = useState<{ original: string; modified: string } | null>(null)
  const files = js.splice?.files ?? []
  useEffect(() => {
    if (!file && files.length) setFile(files[0].path)
  }, [files.length])
  useEffect(() => {
    if (!file || !js.jobId) return
    let dead = false
    setDiff(null)
    api.fileDiff(js.jobId, file).then((d) => !dead && setDiff(d)).catch(() => {})
    return () => {
      dead = true
    }
  }, [file, js.jobId, rev])
  if (!js.splice) return <Waiting what="the splice" />
  return (
    <div className="grid h-[calc(100vh-250px)] min-h-[360px] grid-cols-[260px_1fr] gap-4">
      <Card title={`${js.splice.functions} functions in ${files.length} files`} className="overflow-auto">
        <ul className="-mx-1.5 space-y-0.5">
          {files.map((f) => (
            <li key={f.path}>
              <button onClick={() => setFile(f.path)} className={cn('w-full rounded px-2 py-1.5 text-left hover:bg-hover/60', file === f.path && 'bg-hover')}>
                <div className="mono truncate text-sm">{basename(f.path)}</div>
                <div className="truncate text-xs text-fg3">{f.functions.map((x) => x.split('::').pop()).join(', ')}</div>
              </button>
            </li>
          ))}
        </ul>
      </Card>
      <div className="min-h-0 overflow-hidden rounded-lg border border-line">
        {diff && file ? <DiffView path={`splice:${file}`} original={diff.original} modified={diff.modified} /> : <div className="p-4"><Skeleton className="h-40" /></div>}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ export
function ExportView() {
  const js = useStudio((s) => s.js)
  const openSpecial = useStudio((s) => s.openSpecial)
  const acc = Object.values(js.functions).filter((f) => (f.status === 'verified' || f.status === 'guarded') && f.decision !== 'rejected')
  const files = new Set(acc.map((f) => f.file))
  const manifest: [string, string][] = [
    ['<project>/', 'accelerated copy of your project'],
    ...[...files].sort().map((f) => [`  ${f}`, `${acc.filter((a) => a.file === f).length} decorated`] as [string, string]),
    ['_pythia_accel/', 'loader shim with Python fallback'],
    ...acc.slice(0, 6).map((f) => [`  lib/${f.name}.so`, 'compiled module'] as [string, string]),
    ...(acc.length > 6 ? ([[`  … ${acc.length - 6} more modules`, '']] as [string, string][]) : []),
    ['PYTHIA_REPORT.md', 'per-function status, speedups, fidelity notes, rewrites'],
    ['build_accel.sh', 'rebuilds every module on another machine'],
  ]
  return (
    <div className="grid grid-cols-[1fr_320px] gap-4 max-xl:grid-cols-1">
      <Card title="Manifest" right={<span className="text-xs text-fg3">{acc.length} accelerated functions · rejected ones are left out</span>}>
        <ul className="mono space-y-0.5 text-[12.5px]">
          {manifest.map(([a, b], i) => (
            <li key={i} className="flex gap-4">
              <span className="flex items-center gap-1.5 whitespace-pre text-fg">{a.endsWith('/') ? <Folder size={13} className="text-fg3" /> : a.trim().startsWith('…') ? null : <FileCode2 size={13} className="text-fg3" />}{a}</span>
              <span className="font-sans text-xs text-fg3">{b}</span>
            </li>
          ))}
        </ul>
      </Card>
      <div className="space-y-4">
        <Card title="Export">
          {js.exported ? <div className="mb-3 rounded border border-ok/25 bg-ok/10 p-2.5 text-sm"><div className="font-medium text-ok">Exported</div><div className="mono mt-0.5 break-all text-xs text-fg2">{js.exported.path}</div></div> : null}
          <div className="flex flex-col gap-2">
            <Btn kind="primary" onClick={() => exportProject(false)} disabled={js.state === 'running' || !acc.length}><Download size={13} /> Export project folder</Btn>
            <Btn onClick={() => exportProject(true)} disabled={js.state === 'running' || !acc.length}><Download size={13} /> Download as .zip</Btn>
            <Btn kind="ghost" onClick={() => openSpecial('report')}><FileText size={13} /> Open the report</Btn>
          </div>
        </Card>
      </div>
    </div>
  )
}

export { Journey }
