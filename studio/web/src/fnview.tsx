import { useEffect, useMemo, useState } from 'react'
import { Check, Undo2, X } from 'lucide-react'
import { api } from './api'
import { useStudio } from './store'
import { CodeView, DiffView, cppNotes, pyNotes } from './editors'
import { Journey, Legend, useRecord } from './journey'
import { Btn, Empty, Segmented, Skeleton, StatusChip } from './ui'
import { cn, fmtInt, fmtPct, fmtX } from './lib/format'
import type { FunctionRecord } from './types'

export function FunctionView({ id }: { id: string }) {
  const { rec, loading } = useRecord(id)
  const sum = useStudio((s) => s.js.functions[id])
  const view = useStudio((s) => s.fnViews[id])
  const setViews = useStudio.setState
  const presenter = useStudio((s) => s.presenter)
  const decide = useStudio((s) => s.decide)

  if (loading || !rec) {
    return (
      <div className="p-6" aria-busy>
        <Skeleton className="mb-4 h-6 w-64" />
        <Skeleton className="mb-2 h-4 w-full" />
        <Skeleton className="mb-2 h-4 w-5/6" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }
  const status = sum?.status ?? rec.status
  const decision = sum?.decision ?? rec.decision
  const accelerated = status === 'verified' || status === 'guarded'
  const defView = accelerated ? 'diff' : 'journey'
  const v = view ?? (presenter ? 'journey' : defView)
  const setView = (nv: 'diff' | 'three' | 'journey') => setViews((s) => ({ fnViews: { ...s.fnViews, [id]: nv } }))
  const notesN = rec.fidelity.length
  const sev = (k: string) => rec.fidelity.filter((f) => f.severity === k).length

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex-none border-b border-line bg-panel px-4 py-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h2 className="mono text-[15px] font-medium text-fg">{rec.qualname}</h2>
          <StatusChip status={status} />
          {accelerated && rec.speedup && <span className="tnum text-lg font-semibold text-ok">{fmtX(rec.speedup)}</span>}
          {status === 'declined' && rec.probe_speedup != null && <span className="tnum text-sm text-fg2">probe {fmtX(rec.probe_speedup)}</span>}
          <span className="mono text-xs text-fg3">{rec.file}:{rec.line}</span>
          <div className="ml-auto flex items-center gap-2">
            <Segmented
              value={v}
              onChange={setView}
              options={[
                { value: 'diff', label: 'Diff' },
                { value: 'three', label: 'Three-way' },
                { value: 'journey', label: 'Journey' },
              ]}
            />
            {accelerated && (
              decision === 'pending' ? (
                <>
                  <Btn kind="ok" onClick={() => decide(id, 'accepted')}><Check size={13} /> Accept</Btn>
                  <Btn kind="danger" onClick={() => decide(id, 'rejected')}><X size={13} /> Reject</Btn>
                </>
              ) : (
                <div className="flex items-center gap-2">
                  <span className={cn('rounded-full border px-2.5 py-1 text-xs', decision === 'accepted' ? 'border-ok/30 bg-ok/10 text-ok' : 'border-bad/30 bg-bad/10 text-bad')}>{decision === 'accepted' ? 'Accepted' : 'Rejected'}</span>
                  <Btn kind="ghost" onClick={() => decide(id, 'pending')}><Undo2 size={13} /> Undo</Btn>
                </div>
              )
            )}
          </div>
        </div>
        <div className="tnum mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-fg3">
          {rec.share != null && <span>{fmtPct(rec.share)} of runtime</span>}
          {rec.calls != null && <span>{fmtInt(rec.calls)} calls</span>}
          {rec.replay && <span>{rec.replay.matched}/{rec.replay.total} replays match</span>}
          {notesN > 0 && (
            <span className="flex items-center gap-2">
              {notesN} fidelity note{notesN === 1 ? '' : 's'}
              {sev('exact') > 0 && <span className="text-ok">{sev('exact')} exact</span>}
              {sev('guarded') > 0 && <span className="text-warn">{sev('guarded')} guarded</span>}
              {sev('divergent') > 0 && <span className="text-bad">{sev('divergent')} divergent</span>}
            </span>
          )}
        </div>
        {rec.reason && !accelerated && <p className="mt-2 max-w-[900px] text-sm text-fg2">{rec.reason}</p>}
      </header>
      <div className="min-h-0 flex-1">
        {v === 'diff' && <DiffMode rec={rec} />}
        {v === 'three' && <ThreeWay rec={rec} />}
        {v === 'journey' && (
          <div className="h-full overflow-auto">
            <Journey rec={rec} />
          </div>
        )}
      </div>
    </div>
  )
}

function DiffMode({ rec }: { rec: FunctionRecord }) {
  const jobId = useStudio((s) => s.js.jobId)!
  const rev = useStudio((s) => s.rev)
  const decision = useStudio((s) => s.js.functions[rec.id]?.decision)
  const hasRewrite = !!rec.sources.pysub && rec.sources.pysub !== rec.sources.original
  const spliced = !!rec.splice
  const [mode, setMode] = useState<'file' | 'pysub'>(spliced ? 'file' : 'pysub')
  const [files, setFiles] = useState<{ original: string; modified: string } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    if (!spliced) return setFiles(null)
    let dead = false
    api.fileDiff(jobId, rec.file).then((d) => !dead && (setFiles(d), setErr(null))).catch((e) => !dead && setErr(String(e.message ?? e)))
    return () => {
      dead = true
    }
  }, [jobId, rec.file, spliced, rev, decision, rec.build?.module])

  const modDef = useMemo(() => {
    if (!files) return rec.line
    const re = new RegExp(`^\\s*def\\s+${rec.name}\\(`)
    const lines = files.modified.split('\n')
    const i = lines.findIndex((l, ix) => re.test(l) && ix + 1 >= rec.line)
    return i >= 0 ? i + 1 : rec.line
  }, [files, rec.line, rec.name])

  const origNotes = useMemo(() => (rec.line_map_ok ? pyNotes(rec.fidelity, rec.line - 1) : []), [rec])
  const modNotes = useMemo(() => (rec.line_map_ok ? pyNotes(rec.fidelity, modDef - 1) : []), [rec, modDef])
  const pysubNotes = useMemo(() => pyNotes(rec.fidelity), [rec])

  if (!spliced && !hasRewrite) {
    return (
      <div className="h-full overflow-auto">
        <Empty title={rec.status === 'declined' ? 'Declined, so nothing changed' : rec.status === 'failed' ? 'Rejected after replay' : 'No accelerated version'}>
          {rec.reason ?? 'This function stays as Python.'}
          <button className="mt-3 block w-full text-accent hover:underline" onClick={() => useStudio.setState((s) => ({ fnViews: { ...s.fnViews, [rec.id]: 'journey' } }))}>
            See where it stopped in the journey
          </button>
        </Empty>
      </div>
    )
  }
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-8 flex-none items-center gap-3 border-b border-line px-3 text-xs text-fg3">
        {spliced && hasRewrite ? (
          <Segmented value={mode} onChange={setMode} options={[{ value: 'file', label: 'Spliced file' }, { value: 'pysub', label: 'PySub rewrite' }]} className="scale-90 origin-left" />
        ) : (
          <span>{mode === 'file' ? 'Original file vs accelerated file' : 'Original function vs PySub'}</span>
        )}
        <span className="ml-auto flex items-center">Gutter: <Legend /></span>
      </div>
      <div className="min-h-0 flex-1">
        {mode === 'file' && spliced ? (
          err ? <Empty title="Could not load the diff">{err}</Empty> : !files ? <div className="p-4"><Skeleton className="h-40 w-full" /></div> : (
            <DiffView path={rec.file} original={files.original} modified={files.modified} originalNotes={origNotes} modifiedNotes={modNotes} revealLine={modDef} />
          )
        ) : (
          <DiffView path={`${rec.id}#pysub`} original={rec.sources.original} modified={rec.sources.pysub ?? rec.sources.original} modifiedNotes={pysubNotes} originalNotes={rec.line_map_ok ? pysubNotes : []} hideUnchanged={false} />
        )}
      </div>
    </div>
  )
}

function ThreeWay({ rec }: { rec: FunctionRecord }) {
  const [pyLine, setPyLine] = useState<number | null>(null)
  const [cppLine, setCppLine] = useState<number | null>(null)
  const src = rec.sources
  const rewritten = !!src.pysub && src.pysub !== src.original
  const cppN = useMemo(() => cppNotes(rec), [rec])
  const pyN = useMemo(() => pyNotes(rec.fidelity), [rec])
  const cppSync = pyLine ? rec.cpp_line_map[String(pyLine)] ?? [] : []
  const pySync = useMemo(() => {
    if (!cppLine) return []
    return Object.entries(rec.cpp_line_map).filter(([, ls]) => ls.includes(cppLine)).map(([k]) => Number(k))
  }, [cppLine, rec.cpp_line_map])
  const hasLLM = rec.rewrites.length > 0
  const panes: { key: string; title: string; sub: string; el: JSX.Element }[] = [
    {
      key: 'orig', title: 'Original Python', sub: `${rec.file}:${rec.line}`,
      el: <CodeView path={`${rec.id}#o`} value={src.original} notes={rec.line_map_ok && !rewritten ? pyN : []} syncLines={!rewritten ? pyLine ? [pyLine] : pySync : []} onLineClick={(l) => { setCppLine(null); setPyLine(l) }} lineNumbersStart={rec.line} />,
    },
  ]
  if (rewritten) panes.push({ key: 'pysub', title: hasLLM ? 'PySub rewrite' : 'PySub (annotated)', sub: hasLLM ? `LLM attempt ${rec.rewrites.length}, typechecker-approved` : 'types filled in from the trace', el: <CodeView path={`${rec.id}#p`} value={src.pysub!} notes={pyN} syncLines={pyLine ? [pyLine] : pySync} onLineClick={(l) => { setCppLine(null); setPyLine(l) }} /> })
  panes.push({
    key: 'cpp', title: 'Generated C++17', sub: rec.build ? `${rec.build.module}` : 'not generated',
    el: src.cpp ? <CodeView path={`${rec.id}#c`} value={src.cpp} language="cpp" notes={cppN} syncLines={cppSync} onLineClick={(l) => { setPyLine(null); setCppLine(l) }} /> : <Empty title="No C++ was generated">{rec.reason ?? 'The function did not reach the compiler.'}</Empty>,
  })
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-8 flex-none items-center gap-3 border-b border-line px-3 text-xs text-fg3">
        <span>{rewritten ? 'Original | PySub | C++' : 'Original is already valid PySub: Original | C++'}</span>
        <span className="ml-auto flex items-center">Gutter: <Legend /> · hover a marked line for the explanation</span>
      </div>
      <div className="grid min-h-0 flex-1" style={{ gridTemplateColumns: `repeat(${panes.length}, minmax(0, 1fr))` }}>
        {panes.map((p, i) => (
          <div key={p.key} className={cn('flex min-h-0 min-w-0 flex-col', i > 0 && 'border-l border-line')}>
            <div className="flex h-7 flex-none items-baseline gap-2 border-b border-line bg-panel px-3 pt-1">
              <span className="text-xs font-medium text-fg2">{p.title}</span>
              <span className="mono truncate text-2xs text-fg3">{p.sub}</span>
            </div>
            <div className="min-h-0 flex-1">{p.el}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export type { FunctionRecord }
