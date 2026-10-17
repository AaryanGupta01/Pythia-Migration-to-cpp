import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Activity, Binary, Braces, ChevronRight, FileCheck2, FileCode2, Flag, GitMerge, Hammer, Layers, Network, Plug, Repeat, ShieldCheck, Sparkles, Timer, Type, type LucideIcon } from 'lucide-react'
import { api } from './api'
import { useStudio } from './store'
import { nodeSeen } from './reducer'
import { Code, MiniDiff, TreeView, UnifiedDiff, countNodes, type CodeHL } from './code'
import { ReplayMatrix } from './charts'
import { Bar, CodeBlock, KV, Skeleton } from './ui'
import { attemptSource, cn, fmtInt, fmtLatency, fmtMs, fmtPct, fmtX, SEV_COLOR } from './lib/format'
import { inlineCode } from './agent'
import type { FunctionRecord, JourneyKey, JourneyNode, StageDump, TreeNodeT } from './types'

/** Fetch a function record, refetching when events touch it. Includes compiler stage dumps. */
export function useRecord(id: string) {
  const rec = useStudio((s) => s.records[id])
  const fetchRecord = useStudio((s) => s.fetchRecord)
  const touched = useStudio((s) => s.js.touched[id] ?? 0)
  const rev = useStudio((s) => s.rev)
  const jobId = useStudio((s) => s.js.jobId)
  const [loading, setLoading] = useState(!rec)
  const first = useRef(true)
  useEffect(() => {
    let dead = false
    const delay = first.current ? 0 : 350
    first.current = false
    const t = setTimeout(async () => {
      if (!rec) setLoading(true)
      await fetchRecord(id, true)
      if (!dead) setLoading(false)
    }, delay)
    return () => {
      dead = true
      clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, touched, rev, jobId])
  return { rec: rec as FunctionRecord | undefined, loading: loading && !rec }
}

export function useStages(rec: FunctionRecord | undefined, enabled: boolean) {
  const [dump, setDump] = useState<StageDump | null>(rec?.stages ?? null)
  const src = rec?.sources.pysub
  useEffect(() => {
    if (rec?.stages) return setDump(rec.stages)
    if (!enabled || !src) return
    let dead = false
    api.stages(src).then((d) => !dead && setDump(d)).catch(() => {})
    return () => {
      dead = true
    }
  }, [rec?.stages, src, enabled])
  return dump
}

const TITLES: Record<JourneyKey, string> = {
  original: 'Original Python', observed_types: 'Observed types', eligibility: 'Eligibility check', rewrites: 'LLM rewrite attempts', pysub: 'Final PySub',
  tokens: 'Tokens', ast: 'AST', typed_ast: 'Typed AST', pir: 'PIR', cpp: 'Generated C++', wrapper: 'pybind11 wrapper', build: 'Build', replay: 'Oracle replay',
  benchmark: 'Benchmark', splice: 'Splice', status: 'Status',
}

export function Journey({ rec }: { rec: FunctionRecord }) {
  const js = useStudio((s) => s.js)
  const presenter = useStudio((s) => s.presenter)
  const [open, setOpen] = useState<Set<string>>(new Set())
  const wanted = useMemo(() => new Set(['tokens', 'ast', 'typed_ast', 'pir']), [])
  const dump = useStages(rec, true)

  const shown = new Set<string>()
  const nodes: (JourneyNode & { seen: boolean })[] = rec.journey.map((n) => {
    const seen = nodeSeen(js, rec.id, n.key)
    let { summary, reason } = n
    // an identical reason is only spelled out once; later nodes just say they were not reached
    if (seen && reason) {
      if (shown.has(reason)) {
        reason = null
        if (n.state === 'skipped') summary = 'Not reached'
      } else shown.add(reason)
    }
    return { ...n, summary, reason, title: n.title || TITLES[n.key], seen, state: seen ? n.state : 'pending' }
  })
  const lastSeen = nodes.reduce((a, n, i) => (n.seen ? i : a), 0)
  // where the function's path ended: the first non-done node after the last completed one (status excluded)
  const lastDone = nodes.reduce((a, n, i) => (n.seen && n.state === 'done' && n.key !== 'status' ? i : a), -1)
  const stopCand = nodes.findIndex((n, i) => i > lastDone && n.key !== 'status' && n.seen && n.state !== 'done')
  const stopIdx = stopCand

  // presenter: follow the newest artifact
  const followed = useRef(-1)
  useEffect(() => {
    if (!presenter) return
    if (followed.current !== lastSeen && js.state === 'running') {
      followed.current = lastSeen
      setOpen(new Set([nodes[lastSeen].key]))
    }
  }, [presenter, lastSeen, js.state])

  const toggle = (k: string) =>
    setOpen((o) => {
      const n = new Set(o)
      n.has(k) ? n.delete(k) : n.add(k)
      return n
    })

  return (
    <div className="mx-auto max-w-[920px] px-6 py-5">
      {stopIdx >= 0 && (
        <div className="mb-4 rounded-md border border-line2 bg-raised px-3 py-2 text-sm text-fg2">
          <span className="font-medium text-fg">Stopped at {nodes[stopIdx].title.toLowerCase()}.</span> {nodes[stopIdx].reason ?? rec.reason ?? nodes[stopIdx].summary}
        </div>
      )}
      <ol className="relative">
        {nodes.map((n, i) => {
          const isOpen = open.has(n.key) && n.seen
          const grey = n.state === 'skipped' || n.state === 'pending'
          const last = i === nodes.length - 1
          const nextGrey = !last && (nodes[i + 1].state === 'skipped' || nodes[i + 1].state === 'pending')
          return (
            <li key={n.key} className="relative pl-12" data-node={n.key}>
              {!last && (
                <span
                  className={cn('absolute left-[15px] top-[34px] bottom-[-2px] w-px grow-y', grey || nextGrey ? 'border-l border-dashed border-line2' : 'bg-gradient-to-b from-ok/60 to-ok/20')}
                  style={{ animationDelay: `${i * 35}ms` }}
                />
              )}
              <span className="absolute left-0 top-[3px]">
                <NodeIcon nodeKey={n.key} state={n.state} running={presenter && js.state === 'running' && i === lastSeen} />
              </span>
              <button
                onClick={() => n.seen && toggle(n.key)}
                aria-expanded={isOpen}
                disabled={!n.seen}
                className={cn('flex w-full items-baseline gap-3 rounded-lg py-1.5 pl-1 pr-2 text-left transition-colors', n.seen && 'hover:bg-hover/50', isOpen && 'bg-hover/40')}
              >
                <span className={cn('text-[14px] font-medium', grey ? 'text-fg3' : 'text-fg')}>{n.title}</span>
                <span className={cn('min-w-0 flex-1 truncate text-sm', grey ? 'text-fg3' : n.state === 'failed' ? 'text-bad' : 'text-fg2')}>
                  {n.seen ? n.summary : 'waiting for earlier stages'}
                </span>
                {n.seen && <ChevronRight size={14} className={cn('flex-none text-fg3 transition-transform', isOpen && 'rotate-90')} />}
              </button>
              {n.seen && (n.state === 'skipped' || n.state === 'failed') && n.reason && !isOpen && (
                <p className={cn('mb-1.5 pl-1 text-sm', n.state === 'failed' ? 'text-bad/90' : 'text-fg3')}>{n.reason}</p>
              )}
              {isOpen && (
                <div className="surface mb-3 mt-1.5 animate-fadeIn rounded-[12px] p-3">
                  {n.reason && <p className={cn('mb-2 text-sm', n.state === 'failed' ? 'text-bad/90' : 'text-fg3')}>{n.reason}</p>}
                  <Artifact node={n} rec={rec} dump={wanted.has(n.key) ? dump : null} />
                </div>
              )}
              {!isOpen && <div className="h-1.5" />}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

const NODE_ICON: Record<JourneyKey, LucideIcon> = {
  original: FileCode2, observed_types: Activity, eligibility: ShieldCheck, rewrites: Sparkles, pysub: FileCheck2, tokens: Binary, ast: Network, typed_ast: Type,
  pir: Layers, cpp: Braces, wrapper: Plug, build: Hammer, replay: Repeat, benchmark: Timer, splice: GitMerge, status: Flag,
}
function NodeIcon({ nodeKey, state, running }: { nodeKey: JourneyKey; state: string; running?: boolean }) {
  const I = NODE_ICON[nodeKey]
  const base = 'flex h-[26px] w-[26px] items-center justify-center rounded-full border transition-colors'
  const cls =
    state === 'done' ? 'border-ok/40 bg-ok/10 text-ok' : state === 'failed' ? 'border-bad/50 bg-bad/10 text-bad' : state === 'skipped' ? 'border-line2 bg-bg text-fg3' : 'border-dashed border-line2 bg-bg text-fg3'
  return (
    <span className={cn(base, cls, running && 'ring-pulse')}>
      {state === 'pending' ? <span className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-fg3" /> : <I size={13} strokeWidth={2} />}
    </span>
  )
}

// ------------------------------------------------------------------ artifacts
function Artifact({ node, rec, dump }: { node: JourneyNode; rec: FunctionRecord; dump: StageDump | null }) {
  const js = useStudio((s) => s.js)
  const src = rec.sources
  const py = src.pysub ?? ''
  switch (node.key) {
    case 'original':
      return <Code code={src.original} startLine={rec.line} />
    case 'observed_types':
      return rec.trace ? (
        <div className="grid grid-cols-2 gap-6 surface rounded-[10px] p-3 text-sm">
          <div>
            <div className="mb-1 text-xs text-fg3">Signature seen at run time</div>
            <div className="mono text-fg">
              {rec.name}({rec.trace.arg_types.map((t, i) => <span key={i}>{i > 0 && ', '}<span className="text-accent">{t}</span></span>)}) → <span className="text-accent">{rec.trace.ret_type}</span>
            </div>
          </div>
          <div>
            <KV k="Calls" v={fmtInt(rec.trace.calls)} />
            <KV k="Time in function" v={`${rec.trace.cum_s.toFixed(2)} s · ${fmtPct(rec.trace.share)}`} />
            <KV k="Samples recorded" v={rec.trace.samples} />
            <KV k="Average argument size" v={`${rec.trace.avg_arg_elems} elements`} />
          </div>
        </div>
      ) : <Note>No trace was recorded for this function.</Note>
    case 'eligibility':
      return (
        <div className="space-y-2">
          {rec.diagnostics.filter((d) => d.phase === 'eligibility').length === 0 ? (
            <Note tone="ok">The typechecker accepts this function as written. Score {rec.score.total.toFixed(2)} ({rec.score.basis}).</Note>
          ) : (
            rec.diagnostics.filter((d) => d.phase === 'eligibility').map((d, i) => (
              <div key={i} className="rounded-md border border-bad/25 bg-bad/10 p-2.5">
                <div className="text-sm text-bad">{d.kind}: {d.msg}</div>
                <div className="mono mt-1 text-fg3">line {d.line}{d.col ? `:${d.col}` : ''}: <span className="text-fg2">{src.original.split('\n')[Math.max(0, d.line - 1)]?.trim()}</span></div>
              </div>
            ))
          )}
          <ScoreBreakdown rec={rec} />
        </div>
      )
    case 'rewrites':
      return rec.rewrites.length ? (
        <div className="space-y-3">
          {rec.rewrites.map((r, i) => {
            const prev = i === 0 ? src.annotated ?? src.original : rec.rewrites[i - 1].pysub
            return (
              <div key={r.attempt} className="surface rounded-[10px] p-2.5">
                <div className="mb-2 flex items-center gap-2 text-sm">
                  <span className="font-medium">Attempt {r.attempt}</span>
                  <span className="rounded-full border border-line2 bg-bg px-2 py-px text-xs text-fg2">{attemptSource(useStudio.getState().env, r)}</span>
                  {js.fix[rec.id]?.attempts.find((x) => x.attempt === r.attempt)?.latency_ms != null && <span className="tnum text-xs text-fg3">{fmtLatency(js.fix[rec.id].attempts.find((x) => x.attempt === r.attempt)!.latency_ms)}</span>}
                  <span className={cn('ml-auto rounded-full border px-2 py-0.5 text-xs', r.ok ? 'border-ok/30 bg-ok/10 text-ok' : 'border-bad/30 bg-bad/10 text-bad')}>{r.ok ? 'passed the typechecker' : 'rejected'}</span>
                </div>
                <div className="mb-1 text-xs text-fg3">{i === 0 ? 'Changes from the original' : `Changes from attempt ${i}`}</div>
                <MiniDiff a={prev} b={r.pysub} maxH={240} />
                {r.error && (
                  <div className="mt-2 rounded-md border border-bad/25 bg-bad/10 px-2.5 py-1.5 text-sm text-bad">
                    <b className="font-medium">Typechecker:</b> {r.error}
                    {i < rec.rewrites.length - 1 && <span className="text-fg3"> This error was sent back to the model for the next attempt.</span>}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      ) : <Note>No rewrite was requested.</Note>
    case 'pysub':
      return (
        <div className="space-y-2">
          {py !== src.original && <MiniDiff a={src.original} b={py} />}
          <Code code={py} />
        </div>
      )
    case 'tokens':
      return <StagePane code={py} dump={dump} kind="tokens" />
    case 'ast':
      return <StagePane code={py} dump={dump} kind="ast" />
    case 'typed_ast':
      return <StagePane code={py} dump={dump} kind="typed_ast" />
    case 'pir':
      return <StagePane code={py} dump={dump} kind="pir" rec={rec} />
    case 'cpp':
      return <CppPane rec={rec} />
    case 'wrapper':
      return src.wrapper_cpp ? <Code code={src.wrapper_cpp} lang="cpp" /> : <Note>No wrapper generated.</Note>
    case 'build':
      return rec.build ? (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-x-8 surface rounded-[10px] px-3 py-2 text-sm">
            <KV k="Module" v={rec.build.module} mono />
            <KV k="Compile time" v={rec.build.cached ? 'cache hit' : `${rec.build.compile_s.toFixed(1)} s`} />
            <KV k="Shared object" v={<span className="mono text-xs">{rec.build.so.split('/').pop()}</span>} />
            <KV k="Result" v={rec.build.ok ? 'built' : 'failed'} />
          </div>
          <CodeBlock>{rec.build.log || '(no output)'}</CodeBlock>
        </div>
      ) : <Note>Not built.</Note>
    case 'replay':
      return rec.replay ? <ReplayPane rec={rec} /> : <Note>No replay was run.</Note>
    case 'benchmark':
      return rec.bench ? <BenchPane rec={rec} /> : <Note>No benchmark.</Note>
    case 'splice':
      return rec.splice ? (
        <div className="space-y-2">
          <UnifiedDiff text={rec.splice.diff} />
          <p className="text-xs text-fg3">The original body stays in place; a decorator routes calls to the compiled module and falls back to Python if it cannot load.</p>
        </div>
      ) : <Note>Nothing was spliced for this function.</Note>
    case 'status':
      return <Note>{rec.reason ?? `Final status: ${rec.status.replace('_', ' ')}. Decision: ${rec.decision}.`}</Note>
  }
}

const Note = ({ children, tone }: { children: ReactNode; tone?: 'ok' }) => (
  <div className={cn('rounded-md border px-3 py-2 text-sm', tone === 'ok' ? 'border-ok/25 bg-ok/10 text-fg' : 'border-line bg-raised text-fg2')}>{children}</div>
)

function ScoreBreakdown({ rec }: { rec: FunctionRecord }) {
  const sc = rec.score
  const rows: [string, number | null, string][] = [
    ['Trace time share', sc.trace_share, fmtPct(sc.trace_share)],
    ['Static heuristic', sc.static_heuristic, sc.static_heuristic?.toFixed(2) ?? '—'],
    ['Eligibility factor', sc.eligibility_factor, sc.eligibility_factor?.toFixed(2) ?? '—'],
    ['Expected benefit', sc.expected_benefit != null ? Math.min(1, sc.expected_benefit / 40) : null, sc.expected_benefit != null ? `${sc.expected_benefit.toFixed(1)}×` : '—'],
    ['Boundary penalty', sc.boundary_penalty, sc.boundary_penalty?.toFixed(2) ?? '—'],
  ]
  return (
    <div className="surface rounded-[10px] p-3">
      <div className="mb-2 flex items-baseline justify-between"><span className="text-xs text-fg3">Ranking score</span><span className="tnum text-base font-medium">{sc.total.toFixed(2)}</span></div>
      <div className="space-y-1.5">
        {rows.map(([k, v, t]) => (
          <div key={k} className="flex items-center gap-3 text-sm">
            <span className="w-36 flex-none text-fg2">{k}</span>
            <Bar value={v ?? 0} className="flex-1" color={k === 'Boundary penalty' ? 'bg-bad/70' : 'bg-accent/80'} />
            <span className="tnum w-14 text-right text-fg2">{t}</span>
          </div>
        ))}
      </div>
      {sc.notes.length > 0 && <ul className="mt-2 list-disc pl-4 text-xs text-fg3">{sc.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
    </div>
  )
}

/** Source on the left, token table or syntax tree on the right, synced by selection. */
function StagePane({ code, dump, kind, rec }: { code: string; dump: StageDump | null; kind: 'tokens' | 'ast' | 'typed_ast' | 'pir'; rec?: FunctionRecord }) {
  const [hl, setHl] = useState<CodeHL | null>(null)
  const [sel, setSel] = useState<TreeNodeT | null>(null)
  if (!dump) return <div className="space-y-2" aria-busy><Skeleton className="h-4" /><Skeleton className="h-4 w-4/5" /><Skeleton className="h-4 w-2/3" /></div>
  const root = kind === 'ast' ? dump.ast : kind === 'typed_ast' ? dump.typed_ast : kind === 'pir' ? dump.pir : null
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-3">
        <Code code={code} hl={hl} maxH={340} onLine={(n) => setHl({ line: n })} />
        {kind === 'tokens' ? (
          <div className="mono max-h-[340px] overflow-auto rounded-md border border-line bg-bg text-[12px]" role="region" aria-label="Tokens">
            <table className="w-full">
              <thead className="sticky top-0 bg-raised text-fg3">
                <tr><th className="px-2 py-1 text-left font-normal">kind</th><th className="px-2 py-1 text-left font-normal">value</th><th className="px-2 py-1 text-right font-normal">line:col</th></tr>
              </thead>
              <tbody>
                {dump.tokens.map((t, i) => (
                  <tr key={i} onClick={() => setHl({ line: t.line, col: t.col, len: Math.max(1, t.value.length) })} className={cn('cursor-pointer hover:bg-hover/60', hl?.line === t.line && hl.col === t.col && 'bg-accent/15')}>
                    <td className="px-2 text-accent">{t.kind}</td>
                    <td className="px-2 text-fg">{t.value || ' '}</td>
                    <td className="px-2 text-right text-fg3">{t.line}:{t.col}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : root ? (
          <TreeView root={root} selected={sel} showGuards={kind === 'pir'} onSelect={(n) => { setSel(n); setHl({ line: n.line, col: n.col }) }} maxH={340} />
        ) : <Note>Not available.</Note>}
      </div>
      <div className="text-xs text-fg3">
        {kind === 'tokens' && `${dump.tokens.length} tokens. Click a token to find it in the source.`}
        {kind === 'ast' && `${countNodes(dump.ast)} nodes. Click a node to highlight its source position.`}
        {kind === 'typed_ast' && `${countNodes(dump.typed_ast)} nodes, every expression annotated with its inferred type.`}
        {kind === 'pir' && dump.guard_elision && `${countNodes(dump.pir)} nodes. Overflow guards: ${dump.guard_elision.elided} elided by range analysis, ${dump.guard_elision.kept} kept. Coerce nodes mark int to float promotions.`}
      </div>
      {kind === 'pir' && rec && rec.fidelity.length > 0 && <FidelityList rec={rec} />}
    </div>
  )
}

function FidelityList({ rec }: { rec: FunctionRecord }) {
  return (
    <div className="surface rounded-[10px]">
      <div className="border-b border-line px-3 py-1.5 text-xs font-medium text-fg2">Fidelity notes · {rec.fidelity.length}</div>
      <ul className="divide-y divide-line">
        {rec.fidelity.map((f, i) => (
          <li key={i} className="px-3 py-2 text-sm">
            <div className="flex items-baseline gap-2">
              <span className={cn('h-2 w-2 flex-none translate-y-[-1px] rounded-sm', f.severity === 'exact' ? 'bg-ok' : f.severity === 'guarded' ? 'bg-warn' : 'bg-bad')} />
              <span className="font-medium text-fg">{f.cls}</span>
              <span className={cn('text-xs', SEV_COLOR[f.severity])}>{f.severity}</span>
              <span className="mono ml-auto text-xs text-fg3">line {f.line}</span>
            </div>
            <p className="mt-0.5 pl-4 text-fg2">{f.detail}</p>
            <p className="pl-4 text-xs text-fg3">Mitigation: {f.mitigation}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}

function CppPane({ rec }: { rec: FunctionRecord }) {
  const [pyLine, setPyLine] = useState<number | null>(null)
  const cpp = rec.sources.cpp
  const notes = useMemo(() => {
    const m: Record<number, { severity: 'exact' | 'guarded' | 'divergent'; title: string }> = {}
    const rank = { exact: 0, guarded: 1, divergent: 2 }
    for (const f of rec.fidelity) for (const l of rec.cpp_line_map[String(f.line)] ?? []) if (!m[l] || rank[f.severity] > rank[m[l].severity]) m[l] = { severity: f.severity, title: `${f.cls}: ${f.detail}` }
    return m
  }, [rec])
  if (!cpp) return <Note>No C++ was generated.</Note>
  const cppLines = pyLine ? rec.cpp_line_map[String(pyLine)] ?? [] : []
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="mb-1 text-xs text-fg3">PySub</div>
          <Code code={rec.sources.pysub ?? ''} lines={pyLine ? [pyLine] : []} onLine={setPyLine} maxH={360} />
        </div>
        <div>
          <div className="mb-1 text-xs text-fg3">C++17 · gutter marks fidelity class</div>
          <Code code={cpp} lang="cpp" notes={notes} lines={cppLines} maxH={360} />
        </div>
      </div>
      <p className="text-xs text-fg3">Click a PySub line to see the C++ it became. <Legend /></p>
    </div>
  )
}

export function Legend() {
  return (
    <span className="ml-1 inline-flex items-center gap-3">
      <span className="inline-flex items-center gap-1"><i className="h-2 w-2 rounded-sm bg-ok" />exact</span>
      <span className="inline-flex items-center gap-1"><i className="h-2 w-2 rounded-sm bg-warn" />guarded</span>
      <span className="inline-flex items-center gap-1"><i className="h-2 w-2 rounded-sm bg-bad" />divergent</span>
    </span>
  )
}

function ReplayPane({ rec }: { rec: FunctionRecord }) {
  const r = rec.replay!
  const ok = r.matched === r.total
  return (
    <div className="space-y-2">
      <div className="surface rounded-[10px] p-3">
        <div className="flex items-baseline justify-between">
          <span className="text-base"><b className={cn('tnum', ok ? 'text-ok' : 'text-bad')}>{r.matched}/{r.total}</b> recorded calls matched</span>
          <span className="tnum text-xs text-fg3">{r.exc_matches} exception cases identical</span>
        </div>
        <ReplayMatrix total={r.total} matched={r.matched} cell={8} className="mt-3" />
        <p className="mt-2 text-xs text-fg3">Return values compare bit for bit (floats via their IEEE bytes); exception classes and the final state of list and dict arguments must match too.</p>
      </div>
      {r.first_mismatch && (
        <div className="rounded-md border border-bad/30 bg-bad/10 p-3 text-sm">
          <div className="mb-1 font-medium text-bad">First counterexample ({r.first_mismatch.kind})</div>
          <div className="mono space-y-0.5">
            <div><span className="text-fg3">call    </span>{rec.name}{r.first_mismatch.args}</div>
            <div><span className="text-fg3">python  </span><span className="text-ok">{r.first_mismatch.python}</span></div>
            <div><span className="text-fg3">c++     </span><span className="text-bad">{r.first_mismatch.cpp}</span></div>
          </div>
          <p className="mt-2 text-xs text-fg2">The function was rejected automatically and will not be spliced.</p>
        </div>
      )}
    </div>
  )
}

function BenchPane({ rec }: { rec: FunctionRecord }) {
  const b = rec.bench!
  const max = Math.max(b.py_ms, b.cpp_ms)
  return (
    <div className="surface rounded-[10px] p-3">
      <div className="space-y-2">
        {[['CPython', b.py_ms, 'bg-fg3/50'], ['C++', b.cpp_ms, b.speedup >= 1 ? 'bg-accent' : 'bg-bad/80']].map(([l, v, c]) => (
          <div key={l as string} className="flex items-center gap-3">
            <span className="w-16 flex-none text-xs text-fg3">{l as string}</span>
            <div className="h-4 flex-1 overflow-hidden rounded bg-hover"><div className={cn('h-full rounded', c as string)} style={{ width: `${Math.max(1, ((v as number) / max) * 100)}%` }} /></div>
            <span className="tnum w-20 flex-none text-right text-sm">{fmtMs(v as number)}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-baseline gap-4 border-t border-line pt-2 text-sm">
        <span className={cn('tnum text-xl font-semibold', b.speedup >= 1 ? 'text-ok' : 'text-bad')}>{fmtX(b.speedup)}</span>
        <span className="text-fg3">median of {b.repeats} repeats over {b.calls_timed} recorded calls</span>
      </div>
      {rec.status === 'declined' && <p className="mt-2 text-sm text-fg2">{inlineCode('This is a **probe**: measured to justify declining, never spliced.'.replace(/\*\*/g, ''))}</p>}
    </div>
  )
}
