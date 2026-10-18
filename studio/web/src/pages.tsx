import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BookOpen, Check, Copy, Download, FileDown, KeyRound, Play, Printer, RotateCcw, ShieldCheck, Sparkles, Wand2, X } from 'lucide-react'
import { api, errMsg } from './api'
import { useStudio } from './store'
import { CodeView, cppNotes, pyNotes, type LineNote } from './editors'
import { MiniDiff } from './code'
import { BenchChart, E2EBars } from './charts'
import { useBenchRows } from './bottom'
import { exportProject } from './actions'
import { Btn, Empty, IconBtn, Segmented, Skeleton, StatusChip, useDebounced, MOD, Kbd } from './ui'
import { STATUS, basename, cn, compilerLabel, fmtInt, fmtPct, fmtX, llmLabel } from './lib/format'
import { Legend } from './journey'
import { countStatus, totalSpeedup } from './reducer'
import type { ConvertStatus, FunctionRecord, PlaygroundCompile, PlaygroundConvert, PlaygroundRun } from './types'
import { EXAMPLES } from './examples'

// ------------------------------------------------------------------ file view
export function FileView({ path, line }: { path: string; line?: number }) {
  const js = useStudio((s) => s.js)
  const rev = useStudio((s) => s.rev)
  const openFunction = useStudio((s) => s.openFunction)
  const [ver, setVer] = useState<'work' | 'original'>('work')
  const [content, setContent] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const ws = js.workspaceId
  useEffect(() => {
    if (!ws) return
    let dead = false
    setContent(null)
    api.file(ws, path, ver).then((f) => !dead && (setContent(f.content), setErr(null))).catch((e) => !dead && setErr(errMsg(e)))
    return () => {
      dead = true
    }
  }, [ws, path, ver, rev, js.splice])
  const fns = useMemo(() => Object.values(js.functions).filter((f) => f.file === path).sort((a, b) => a.line - b.line), [js.functions, path])
  const notes: LineNote[] = useMemo(() => {
    if (ver !== 'original') return []
    const sev = { verified: 'exact', guarded: 'guarded', failed: 'divergent' } as const
    return fns
      .filter((f) => f.status === 'verified' || f.status === 'guarded' || f.status === 'failed')
      .map((f) => ({ line: f.line, severity: sev[f.status as keyof typeof sev], cls: STATUS[f.status].label, detail: f.reason ?? (f.speedup ? `${fmtX(f.speedup)} faster than CPython` : ''), mitigation: 'Open the function from Hotspots to see its journey.' }))
  }, [fns, ver])
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-9 flex-none items-center gap-3 border-b border-line bg-panel px-3 text-sm">
        <span className="mono text-fg2">{path}</span>
        <Segmented value={ver} onChange={setVer} options={[{ value: 'work', label: 'Accelerated' }, { value: 'original', label: 'Original' }]} className="scale-90" />
        <span className="ml-auto flex items-center gap-1 overflow-hidden">
          {fns.slice(0, 6).map((f) => (
            <button key={f.id} onClick={() => openFunction(f.id)} className="flex items-center gap-1.5 rounded px-1.5 py-0.5 text-xs text-fg2 hover:bg-hover hover:text-fg">
              <span className={cn('h-1.5 w-1.5 rounded-full', STATUS[f.status].dot)} />
              <span className="mono">{f.name}</span>
            </button>
          ))}
          {fns.length > 6 && <span className="text-xs text-fg3">+{fns.length - 6}</span>}
        </span>
      </div>
      <div className="min-h-0 flex-1">
        {err ? <Empty title="Could not open the file">{err}</Empty> : content == null ? <div className="space-y-2 p-4"><Skeleton className="h-4 w-1/2" /><Skeleton className="h-4 w-2/3" /><Skeleton className="h-4 w-1/3" /></div> : <CodeView path={`file:${path}:${ver}`} value={content} notes={notes} revealLine={line} syncLines={line ? [line] : []} />}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ playground
const LS = (k: string, v?: string | null) => {
  try {
    if (v === undefined) return localStorage.getItem(k)
    if (v === null) localStorage.removeItem(k)
    else localStorage.setItem(k, v)
  } catch {
    /* private mode */
  }
  return null
}

type ConvState = { state: 'idle' | 'running' | 'done' | 'failed'; result?: PlaygroundConvert; original?: string; started?: number }

export function Playground() {
  const active = useStudio((s) => s.activeTab === 'playground')
  const openSpecial = useStudio((s) => s.openSpecial)
  const settingsRev = useStudio((s) => s.settings)
  const [src, setSrc] = useState(() => LS('pythia:playground') || EXAMPLES[0].code)
  const [stdin, setStdin] = useState(() => LS('pythia:playground:stdin') ?? '')
  const [reference, setReference] = useState<string | null>(() => LS('pythia:playground:ref'))
  const [exampleId, setExampleId] = useState<string>('')
  const dsrc = useDebounced(src, 450)
  const [comp, setComp] = useState<PlaygroundCompile | null>(null)
  const [compiling, setCompiling] = useState(true)
  const [cerr, setCerr] = useState<string | null>(null)
  const [run, setRun] = useState<PlaygroundRun | null>(null)
  const [running, setRunning] = useState(false)
  const [pyLine, setPyLine] = useState<number | null>(null)
  const [conv, setConv] = useState<ConvState>({ state: 'idle' })
  const [cstat, setCstat] = useState<ConvertStatus | null>(null)
  const seq = useRef(0)

  useEffect(() => { LS('pythia:playground', src) }, [src])
  useEffect(() => { LS('pythia:playground:stdin', stdin) }, [stdin])
  useEffect(() => { LS('pythia:playground:ref', reference) }, [reference])
  useEffect(() => {
    api.pgConvertStatus().then(setCstat).catch(() => setCstat(null))
  }, [settingsRev])
  useEffect(() => {
    const id = ++seq.current
    setCompiling(true)
    api.pgCompile(dsrc).then((r) => id === seq.current && (setComp(r), setCerr(null), setCompiling(false))).catch((e) => id === seq.current && (setCerr(errMsg(e)), setCompiling(false)))
  }, [dsrc])

  const doRun = useCallback(async () => {
    setRunning(true)
    try {
      setRun(await api.pgRun(src, stdin, reference ?? undefined))
    } catch (e) {
      setRun({ ok: false, error: errMsg(e), python: { stdout: '', exception: null, time_ms: 0 }, cpp: null, same: false })
    }
    setRunning(false)
  }, [src, stdin, reference])
  useEffect(() => {
    if (!active) return
    const h = () => doRun()
    window.addEventListener('pythia:run', h)
    return () => window.removeEventListener('pythia:run', h)
  }, [active, doRun])

  const doConvert = useCallback(async () => {
    const original = src
    setConv({ state: 'running', original, started: Date.now() })
    try {
      const r = await api.pgConvert(original, stdin)
      setConv({ state: r.ok ? 'done' : 'failed', result: r, original })
    } catch (e) {
      setConv({ state: 'failed', result: { ok: false, error: errMsg(e), attempts: [] }, original })
    }
  }, [src, stdin])
  const applyConversion = () => {
    if (!conv.result?.source || conv.original == null) return
    setReference(conv.original)
    setSrc(conv.result.source)
    setConv({ state: 'idle' })
    setRun(null)
  }
  const loadExample = (id: string) => {
    const ex = EXAMPLES.find((x) => x.id === id)
    setExampleId('')
    if (!ex) return
    setSrc(ex.code)
    setStdin(ex.stdin ?? '')
    setReference(null)
    setRun(null)
    setConv({ state: 'idle' })
  }

  const pyN = useMemo(() => (comp ? pyNotes(comp.fidelity) : []), [comp])
  const cN = useMemo(() => (comp ? cppNotes({ fidelity: comp.fidelity, cpp_line_map: comp.cpp_line_map }) : []), [comp])
  const sync = comp && pyLine ? comp.cpp_line_map[String(pyLine)] ?? [] : []
  const nErr = comp?.diagnostics.length ?? 0
  const wantsInput = /\binput\s*\(/.test(src) || (!!reference && /\binput\s*\(/.test(reference))
  const showConvert = !compiling && !cerr && nErr > 0 && conv.state === 'idle'

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-10 flex-none items-center gap-3 border-b border-line bg-panel px-3">
        <h2 className="text-sm font-medium">Playground</h2>
        <span className="text-xs text-fg3">
          {compiling ? 'Compiling…' : cerr ? 'Server error' : nErr ? `${nErr} typechecker error${nErr === 1 ? '' : 's'}` : 'Compiled to C++17'}
        </span>
        {reference && (
          <span className="flex items-center gap-1 rounded-full border border-ok/30 bg-ok/10 px-2 py-0.5 text-2xs text-ok" title="Run executes your ORIGINAL program under CPython and this converted program as compiled C++, on the same input.">
            <ShieldCheck size={11} /> AI conversion: Run checks it against your original
            <button onClick={() => setReference(null)} className="ml-0.5 rounded hover:text-fg" aria-label="Stop comparing with the original"><X size={11} /></button>
          </span>
        )}
        <span className="ml-auto flex items-center gap-3 text-xs text-fg3">
          <label className="flex items-center gap-1.5">
            <BookOpen size={13} />
            <select value={exampleId} onChange={(e) => loadExample(e.target.value)} aria-label="Load an example" className="h-7 rounded-md border border-line2 bg-bg px-1.5 text-xs text-fg2 outline-none focus:border-accent">
              <option value="">Examples…</option>
              {EXAMPLES.map((x) => <option key={x.id} value={x.id}>{x.title} ({x.note})</option>)}
            </select>
          </label>
          <Legend />
          <Btn kind="primary" onClick={doRun} disabled={running || compiling}
            title={nErr > 0 ? `Not PySub yet: runs under Python only (${MOD}+Enter). Convert it to also run it as compiled C++.` : `Run under CPython and as compiled C++ (${MOD}+Enter)`}>
            <Play size={12} /> {running ? 'Running…' : nErr > 0 ? 'Run in Python' : 'Run'} <Kbd>{MOD}↵</Kbd>
          </Btn>
        </span>
      </div>
      {showConvert && (
        <div className="flex flex-none items-center gap-3 border-b border-accent/30 bg-accent/10 px-3 py-2 text-sm">
          <Sparkles size={15} className="flex-none text-accent" />
          <div className="min-w-0 flex-1">
            <span className="font-medium text-fg">This is regular Python, not PySub yet.</span>{' '}
            <span className="text-fg2">PySub needs types and a few rewrites (records become classes, shared state becomes parameters, enumerate and lambdas become loops). The AI does it; the type checker checks every answer.</span>
          </div>
          {cstat?.enabled ? (
            <Btn kind="primary" onClick={doConvert} className="flex-none"><Wand2 size={13} /> Convert to PySub with AI</Btn>
          ) : (
            <Btn onClick={() => openSpecial('settings')} className="flex-none" title={cstat?.hint ?? ''}><KeyRound size={13} /> Add a free API key to convert</Btn>
          )}
        </div>
      )}
      <div className="grid min-h-0 flex-1 grid-cols-2">
        <div className="flex min-h-0 flex-col border-r border-line">
          <PaneTitle l={reference ? 'PySub (converted from your Python)' : 'PySub / Python'} r="edit here" />
          <div className="min-h-0 flex-1">
            <CodeView path="playground.py" value={src} readOnly={false} onChange={setSrc} notes={pyN} markers={comp?.diagnostics ?? []} onLineClick={setPyLine} />
          </div>
          {comp && comp.diagnostics.length > 0 && (
            <ul className="max-h-24 flex-none overflow-auto border-t border-line bg-panel px-3 py-1.5 text-xs">
              {comp.diagnostics.map((d, i) => (
                <li key={i} className="py-0.5 text-bad"><span className="mono text-fg3">line {d.line}</span> {d.kind}: {d.msg}</li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex min-h-0 flex-col">
          {conv.state !== 'idle' ? (
            <ConvertPanel conv={conv} provider={cstat} onApply={applyConversion} onRetry={doConvert} onClose={() => setConv({ state: 'idle' })} />
          ) : (
            <>
              <PaneTitle l="Generated C++17" r={compiling ? 'updating…' : 'live'} />
              <div className="min-h-0 flex-1">
                {cerr ? <Empty title="Compile request failed">{cerr}</Empty> : comp?.ok ? <CodeView path="playground.cpp" value={comp.cpp} language="cpp" notes={cN} syncLines={sync} /> : <Empty title={comp ? 'Nothing to compile yet' : 'Compiling'}>{comp ? (cstat?.enabled ? 'Fix the errors on the left, or let the AI convert the program to PySub (button above).' : 'Fix the typechecker errors on the left and the C++ appears here.') : ''}</Empty>}
              </div>
            </>
          )}
        </div>
      </div>
      <RunOutput run={run} running={running} stdin={stdin} setStdin={setStdin} showStdin={wantsInput || stdin.length > 0} comparedToOriginal={!!reference} />
    </div>
  )
}
const PaneTitle = ({ l, r }: { l: string; r: string }) => (
  <div className="flex h-7 flex-none items-center justify-between border-b border-line bg-panel px-3 text-xs"><span className="font-medium text-fg2">{l}</span><span className="text-fg3">{r}</span></div>
)

function ConvertPanel({ conv, provider, onApply, onRetry, onClose }: { conv: ConvState; provider: ConvertStatus | null; onApply: () => void; onRetry: () => void; onClose: () => void }) {
  const r = conv.result
  const [secs, setSecs] = useState(0)
  useEffect(() => {
    if (conv.state !== 'running') return
    const t = setInterval(() => setSecs(Math.round((Date.now() - (conv.started ?? Date.now())) / 1000)), 500)
    return () => clearInterval(t)
  }, [conv.state, conv.started])
  const model = (r?.model ?? provider?.model ?? '').replace(/^openai\//, '')
  const who = `${r?.provider ?? provider?.provider ?? 'LLM'}${model ? ' · ' + model : ''}`
  const last = r?.attempts?.[r.attempts.length - 1]
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-7 flex-none items-center justify-between border-b border-line bg-panel px-3 text-xs">
        <span className="flex items-center gap-1.5 font-medium text-fg2"><Wand2 size={12} className="text-accent" /> AI conversion to PySub</span>
        <button onClick={onClose} className="rounded p-0.5 text-fg3 hover:bg-hover hover:text-fg" aria-label="Close"><X size={13} /></button>
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-auto p-3">
        {conv.state === 'running' && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-fg2"><span className="h-2 w-2 animate-pulse rounded-full bg-accent" /> Asking {who} for a PySub version… {secs}s</div>
            <p className="text-xs text-fg3">Each answer goes straight to the PySub type checker, then is compiled to C++ and run next to your original on the same input. A type error or any difference in the output goes back to the model (up to 4 rounds). Nothing is accepted on the model's word.</p>
            <Skeleton className="h-4 w-2/3" /><Skeleton className="h-4 w-1/2" /><Skeleton className="h-4 w-3/5" />
          </div>
        )}
        {r && (
          <>
            <div className={cn('rounded-lg border px-3 py-2 text-sm', r.ok ? 'border-ok/30 bg-ok/10 text-ok' : 'border-bad/30 bg-bad/10 text-bad')}>
              {r.ok
                ? (r.already ? 'This program is already valid PySub; nothing to convert.' : `Converted on attempt ${r.attempts.length} (${who}): it passes the PySub type checker${r.behaviour_checked ? ' and, compiled to C++, prints exactly what your original prints on the current input' : ''}. Use it, then press Run: your original runs under CPython, the conversion as compiled C++, on the same input.`)
                : (r.error ?? 'The conversion failed.')}
            </div>
            {r.blockers && r.blockers.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-medium text-fg2">Why this program can't become compiled C++</div>
                {r.blockers.map((b, i) => (
                  <div key={i} className="rounded-md border border-line bg-panel px-2.5 py-2 text-xs">
                    <div className="font-medium text-fg"><span className="mono text-fg3">line {b.line}</span> {b.what}</div>
                    <div className="mt-0.5 text-fg2">{b.why}.</div>
                    <div className="mt-0.5 text-fg3">What you can do: {b.fix}.</div>
                  </div>
                ))}
                <p className="text-xs text-fg3">PySub is a typed subset of Python made of numbers, strings, lists, dicts, classes, input() and print(): exactly the parts a C++ compiler can reproduce bit for bit. Programs that also use libraries, files or randomness run under Python here (press Run); open them as a Project and PYTHIA accelerates only their plain-Python hot functions.</p>
              </div>
            )}
            {r.attempts.length > 0 && (
              <ol className="space-y-1.5 text-xs">
                {r.attempts.map((a) => (
                  <li key={a.attempt} className="rounded-md border border-line bg-panel px-2.5 py-1.5">
                    <div className="flex items-center gap-2">
                      {a.ok ? <Check size={12} className="text-ok" /> : <X size={12} className="text-bad" />}
                      <span className="font-medium text-fg2">Attempt {a.attempt}</span>
                      <span className="text-fg3">{(a.latency_ms / 1000).toFixed(1)} s</span>
                      <span className={cn('ml-auto', a.ok ? 'text-ok' : 'text-bad')}>{a.ok ? 'accepted' : a.error ? 'no answer' : a.behaviour ? 'compiled, it prints different output: sent back' : `type checker: ${a.diagnostics.length} error${a.diagnostics.length === 1 ? '' : 's'} sent back`}</span>
                    </div>
                    {!a.ok && (a.error || a.diagnostics.length > 0) && (
                      <ul className="mt-1 space-y-0.5 pl-5 text-fg3">
                        {a.error && <li>{a.error}</li>}
                        {a.diagnostics.slice(0, 4).map((d, i) => <li key={i}><span className="mono">line {d.line}</span> {d.msg}</li>)}
                      </ul>
                    )}
                    {a.behaviour && <pre className="mono mt-1 max-h-32 overflow-auto rounded bg-bg px-2 py-1 text-2xs text-fg3">{a.behaviour}</pre>}
                  </li>
                ))}
              </ol>
            )}
            {r.ok && r.source && !r.already && conv.original != null && (
              <div>
                <div className="mb-1 text-xs font-medium text-fg2">Your Python → PySub</div>
                <MiniDiff a={conv.original} b={r.source} maxH={9999} />
              </div>
            )}
            {!r.ok && last?.source && conv.original != null && (
              <div>
                <div className="mb-1 text-xs font-medium text-fg2">Last attempt (rejected)</div>
                <MiniDiff a={conv.original} b={last.source} maxH={9999} />
              </div>
            )}
          </>
        )}
      </div>
      {r && (
        <div className="flex flex-none items-center justify-end gap-2 border-t border-line bg-panel px-3 py-2">
          {!r.ok && <Btn onClick={onRetry}><RotateCcw size={12} /> Try again</Btn>}
          <Btn kind="ghost" onClick={onClose}>{r.ok ? 'Discard' : 'Close'}</Btn>
          {r.ok && !r.already && <Btn kind="primary" onClick={onApply}><Check size={12} /> Use the PySub version</Btn>}
        </div>
      )}
    </div>
  )
}

function RunOutput({ run, running, stdin, setStdin, showStdin, comparedToOriginal }: { run: PlaygroundRun | null; running: boolean; stdin: string; setStdin: (s: string) => void; showStdin: boolean; comparedToOriginal: boolean }) {
  const lines = (s: string) => s.replace(/\n$/, '').split('\n')
  const a = run ? lines(run.python.stdout) : []
  const b = run?.cpp ? lines(run.cpp.stdout) : []
  const both = !!run && run.ok && !!run.cpp
  const diff = (i: number, x: string[], y: string[]) => x[i] !== y[i]
  const leftLabel = comparedToOriginal ? 'CPython · your original Python' : 'CPython'
  const rightLabel = comparedToOriginal ? 'Compiled C++ · PySub conversion' : 'Compiled C++'
  return (
    <div className={cn('flex flex-none border-t border-line bg-panel', showStdin ? 'h-[230px]' : 'h-[170px]')}>
      {showStdin && (
        <div className="flex w-[260px] flex-none flex-col border-r border-line">
          <div className="flex h-7 flex-none items-center justify-between border-b border-line px-3 text-xs">
            <span className="font-medium text-fg2">Input (stdin)</span>
            <span className="text-fg3">one line per input()</span>
          </div>
          <textarea value={stdin} onChange={(e) => setStdin(e.target.value)} spellCheck={false} aria-label="Program input"
            placeholder={'Lines your program reads with input(),\none per line. Both versions get the same input.'}
            className="mono min-h-0 flex-1 resize-none bg-bg px-3 py-2 text-xs text-fg outline-none placeholder:text-fg3" />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex h-7 items-center gap-3 border-b border-line px-3 text-xs">
          <span className="font-medium text-fg2">Output</span>
          {both && <span className={run.same ? 'text-ok' : 'text-bad'}>{run.same ? (comparedToOriginal ? 'Identical: the conversion behaves exactly like your original program' : 'CPython and compiled output are identical') : 'Outputs differ'}</span>}
          {run?.ok && run.python_only && <span className="text-warn">Ran under Python only: this code isn't PySub yet, so there is no compiled version to compare</span>}
          {both && run.cpp!.time_ms > 0 && <span className="tnum ml-auto text-fg2">{run.python.time_ms} ms vs {run.cpp!.time_ms} ms{run.python.time_ms / run.cpp!.time_ms >= 1.05 ? <> · <b className="text-ok">{fmtX(run.python.time_ms / run.cpp!.time_ms)}</b></> : <span className="text-fg3"> · startup-bound (interactive programs gain little)</span>}</span>}
        </div>
        {running ? (
          <div className="space-y-2 p-3"><Skeleton className="h-4 w-1/3" /><Skeleton className="h-4 w-1/4" /></div>
        ) : !run ? (
          <div className="p-3 text-sm text-fg3">Press Run to execute the program under CPython and as compiled C++, side by side{showStdin ? ', both reading the input on the left' : ''}. Code that isn't PySub yet runs under Python only.</div>
        ) : !run.ok ? (
          <div className="p-3 text-sm text-bad">{run.error ?? 'The program could not be run.'}</div>
        ) : !run.cpp ? (
          <div className="h-[calc(100%-28px)] min-h-0 overflow-auto px-3 py-1.5">
            <div className="mb-0.5 flex justify-between text-2xs text-fg3"><span>CPython · your program{run.reason ? ` · not compiled: ${run.reason}` : ''}</span><span className="tnum">{run.python.time_ms} ms</span></div>
            <pre className="mono text-xs">{a.map((l, i) => <div key={i}>{l || ' '}</div>)}{run.python.exception && <div className="text-bad">{run.python.exception}</div>}</pre>
          </div>
        ) : (
          <div className="flex h-[calc(100%-28px)] min-h-0 flex-col">
          {run.explain && <div className="flex-none border-b border-line bg-warn/10 px-3 py-1.5 text-xs text-warn">{run.explain}</div>}
          <div className="grid min-h-0 flex-1 grid-cols-2 divide-x divide-line">
            {[[leftLabel, a, b, run.python] as const, [rightLabel, b, a, run.cpp] as const].map(([label, x, y, side]) => (
              <div key={label} className="min-h-0 overflow-auto px-3 py-1.5">
                <div className="mb-0.5 flex justify-between text-2xs text-fg3"><span>{label}</span><span className="tnum">{side.time_ms} ms</span></div>
                <pre className="mono text-xs">{x.map((l, i) => <div key={i} className={cn(diff(i, x, y) && 'bg-bad/15 text-bad')}>{l || ' '}</div>)}{side.exception && <div className="text-bad">{side.exception}</div>}</pre>
              </div>
            ))}
          </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ report
export function Report() {
  const js = useStudio((s) => s.js)
  const fetchRecord = useStudio((s) => s.fetchRecord)
  const records = useStudio((s) => s.records)
  const openFunction = useStudio((s) => s.openFunction)
  const rows = useBenchRows()
  const [md, setMd] = useState<string | null>(null)
  const fns = useMemo(() => Object.values(js.functions), [js.functions])
  const c = countStatus(js)
  const sp = totalSpeedup(js)
  const needed = useMemo(() => fns.filter((f) => f.status === 'verified' || f.status === 'guarded' || f.status === 'failed' || f.status === 'declined').map((f) => f.id), [fns])
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    let dead = false
    const need = needed.filter((id) => !records[id])
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
  }, [needed.join('|')])
  useEffect(() => {
    if (js.jobId && js.state === 'done') api.report(js.jobId).then((r) => setMd(r.markdown)).catch(() => {})
  }, [js.jobId, js.state])

  if (!js.jobId) return <Empty title="No report yet">Run an analysis and the report fills in: headline speedup, per-function results, fidelity notes and every LLM rewrite.</Empty>
  const recs = needed.map((id) => records[id]).filter(Boolean) as FunctionRecord[]
  const accel = fns.filter((f) => f.status === 'verified' || f.status === 'guarded').sort((a, b) => (b.speedup ?? 0) - (a.speedup ?? 0))
  const stopped = fns.filter((f) => ['failed', 'declined', 'not_eligible', 'fixable'].includes(f.status))
  const rewritten = recs.filter((r) => r.rewrites.length && r.sources.pysub)
  const allFid = recs.flatMap((r) => r.fidelity)
  const byCls = new Map<string, { n: number; sev: string }>()
  for (const f of allFid) byCls.set(f.cls, { n: (byCls.get(f.cls)?.n ?? 0) + 1, sev: f.severity })
  const download = (name: string, text: string) => {
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }))
    a.download = name
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div className="print-flow h-full overflow-auto">
      <article className="print-flow mx-auto max-w-[900px] px-8 py-8">
        <header className="mb-8 flex items-start justify-between gap-6 border-b border-line pb-6">
          <div>
            <div className="text-sm text-fg3">PYTHIA report</div>
            <h1 className="mt-1 text-[24px] font-semibold tracking-tight">{js.name}</h1>
            <p className="mt-1 text-sm text-fg3">{fns.length} functions analysed{js.e2e ? ` · ${js.e2e.cmd}` : ''}</p>
          </div>
          <div className="text-right">
            <div className="tnum text-[44px] font-semibold leading-[46px] tracking-tight text-ok">{sp ? fmtX(sp) : '—'}</div>
            <div className="text-sm text-fg3">{js.e2e?.ok ? `end to end · ${js.e2e.before_s.toFixed(1)} s to ${js.e2e.after_s.toFixed(1)} s` : 'geometric mean per function'}</div>
          </div>
        </header>
        <div className="no-print mb-8 flex flex-wrap gap-2">
          <Btn kind="primary" onClick={() => exportProject(false)} disabled={!accel.length}><Download size={13} /> Export project</Btn>
          <Btn onClick={() => exportProject(true)} disabled={!accel.length}><FileDown size={13} /> Download zip</Btn>
          <Btn onClick={() => window.print()}><Printer size={13} /> Print or save as PDF</Btn>
          <Btn onClick={() => md && download(`${js.name ?? 'pythia'}-report.md`, md)} disabled={!md}><Copy size={13} /> Download Markdown</Btn>
        </div>

        <dl className="tnum mb-10 grid grid-cols-6 gap-4 max-md:grid-cols-3">
          {([['Verified', c.verified, 'text-ok'], ['Guarded', c.guarded, 'text-warn'], ['Declined', c.declined, 'text-fg2'], ['Failed', c.failed, 'text-bad'], ['Fixable', c.fixable, 'text-accent'], ['Not eligible', c.not_eligible, 'text-fg3']] as const).map(([k, v, cl]) => (
            <div key={k} className="surface rounded-[12px] px-3 py-2.5"><dt className="text-xs text-fg3">{k}</dt><dd className={cn('text-xl font-semibold', v ? cl : 'text-fg3')}>{v}</dd></div>
          ))}
        </dl>

        <Section title="Accelerated functions" note="Median CPython time over median compiled time, measured on recorded inputs.">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line text-left text-xs text-fg3"><th className="py-2 font-medium">Function</th><th className="font-medium">Status</th><th className="text-right font-medium">Speedup</th><th className="text-right font-medium">Replays</th><th className="text-right font-medium">Time share</th><th className="text-right font-medium">Decision</th></tr></thead>
            <tbody>
              {accel.map((f) => {
                const r = records[f.id]
                return (
                  <tr key={f.id} className="border-b border-line/60 break-inside-avoid">
                    <td className="py-1.5"><button onClick={() => openFunction(f.id)} className="mono text-left hover:underline">{f.name}</button><div className="text-2xs text-fg3">{basename(f.file)}</div></td>
                    <td><StatusChip status={f.status} dense /></td>
                    <td className="tnum text-right font-medium text-ok">{fmtX(f.speedup)}</td>
                    <td className="tnum text-right text-fg2">{r?.replay ? `${r.replay.matched}/${r.replay.total}` : '—'}</td>
                    <td className="tnum text-right text-fg2">{fmtPct(f.share)}</td>
                    <td className="text-right text-fg2 capitalize">{f.decision}</td>
                  </tr>
                )
              })}
              {!accel.length && <tr><td colSpan={6} className="py-4 text-fg3">No function has been verified yet.</td></tr>}
            </tbody>
          </table>
        </Section>

        {rows.length > 0 && (
          <Section title="Benchmarks" note="Logarithmic axis: each gridline is ten times slower.">
            <BenchChart rows={rows} compact />
            {js.e2e && <div className="mt-6 max-w-[520px]"><E2EBars e2e={js.e2e} /></div>}
          </Section>
        )}

        <Section title="Fidelity" note="Where compiled behaviour could differ from CPython, and what guards it.">
          {loading && !allFid.length ? <Skeleton className="h-16" /> : allFid.length === 0 ? <p className="text-sm text-fg3">No notes recorded.</p> : (
            <ul className="divide-y divide-line surface rounded-[12px]">
              {[...byCls.entries()].sort((a, b) => b[1].n - a[1].n).map(([cls, v]) => (
                <li key={cls} className="flex items-center gap-3 px-4 py-2 text-sm">
                  <span className={cn('h-2 w-2 rounded-sm', v.sev === 'exact' ? 'bg-ok' : v.sev === 'guarded' ? 'bg-warn' : 'bg-bad')} />
                  <span className="flex-1">{cls}</span>
                  <span className="text-xs capitalize text-fg3">{v.sev}</span>
                  <span className="tnum w-14 text-right text-fg2">{v.n} sites</span>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="LLM rewrites" note="The LLM only rewrites Python into valid PySub. Every rewrite below passed the typechecker, then oracle replay.">
          {rewritten.length === 0 ? <p className="text-sm text-fg3">{loading ? 'Loading…' : 'No function needed a rewrite.'}</p> : rewritten.map((r) => (
            <div key={r.id} className="mb-5 break-inside-avoid">
              <div className="mb-1.5 flex items-baseline gap-3"><span className="mono text-base">{r.name}</span><span className="text-xs text-fg3">{r.rewrites.length} attempt{r.rewrites.length === 1 ? '' : 's'}</span><StatusChip status={js.functions[r.id]?.status ?? r.status} dense /></div>
              <MiniDiff a={r.sources.annotated ?? r.sources.original} b={r.sources.pysub!} maxH={9999} />
            </div>
          ))}
        </Section>

        <Section title="Left as Python" note="Each stop is a decision, not a failure. The reason is the one PYTHIA recorded.">
          <ul className="divide-y divide-line surface rounded-[12px]">
            {stopped.map((f) => (
              <li key={f.id} className="px-4 py-2 text-sm break-inside-avoid">
                <div className="flex items-center gap-3"><span className="mono flex-1">{f.name}</span><StatusChip status={f.status} dense /></div>
                {f.reason && <p className="mt-0.5 text-xs text-fg3">{f.reason}</p>}
              </li>
            ))}
          </ul>
        </Section>
        <p className="mt-10 border-t border-line pt-4 text-xs text-fg3">The LLM suggests, the compiler proves. Nothing is marked verified until recorded calls replay identically through CPython and the compiled module.</p>
      </article>
    </div>
  )
}
const Section = ({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) => (
  <section className="mb-10">
    <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
    {note && <p className="mb-3 mt-0.5 text-sm text-fg3">{note}</p>}
    {children}
  </section>
)

// ------------------------------------------------------------------ settings
export function SettingsPage() {
  const s = useStudio()
  const [key, setKey] = useState('')
  const [model, setModel] = useState(s.settings?.model ?? '')
  const [saved, setSaved] = useState(false)
  useEffect(() => { if (s.settings?.model) setModel(s.settings.model) }, [s.settings?.model])
  const save = async (patch: Record<string, unknown>) => {
    try {
      await api.putSettings(patch)
      await s.loadEnv()
      setSaved(true)
      setTimeout(() => setSaved(false), 1600)
    } catch (e) {
      s.toast(errMsg(e), 'error')
    }
  }
  const env = s.env
  const provider = (s.settings?.offline ? 'offline' : s.settings?.provider && s.settings.provider !== 'offline' ? s.settings.provider : 'auto') as 'auto' | 'groq' | 'anthropic' | 'offline'
  const pickProvider = (p: 'auto' | 'groq' | 'anthropic' | 'offline') => save({ provider: p, offline: p === 'offline' })
  const hints: Record<string, string> = {
    auto: 'Use Anthropic if a key is set, otherwise Groq (free tier).',
    groq: 'Groq runs open models such as gpt-oss-120b on a free tier. Needs a GROQ_API_KEY.',
    anthropic: 'Claude models through the Anthropic API. Needs an ANTHROPIC_API_KEY.',
    offline: 'Replay recorded rewrites and prebuilt modules. No network, no key.',
  }
  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto max-w-[720px] px-8 py-9">
        <h1 className="text-[22px] font-semibold tracking-tight">Settings</h1>
        <p className="mt-1.5 text-sm text-fg3">Stored by the local PYTHIA server. Keys are write-only: the browser never reads them back.</p>

        <SettingsGroup title="Appearance">
          <Row title="Theme" desc="Dark is the default and easiest on the code.">
            <Segmented value={s.theme} onChange={s.setTheme} options={[{ value: 'dark', label: 'Dark' }, { value: 'light', label: 'Light' }]} />
          </Row>
        </SettingsGroup>

        <SettingsGroup title="LLM fixer">
          <Row title="Provider" desc={hints[provider]}>
            <Segmented value={provider} onChange={pickProvider} options={[{ value: 'auto', label: 'Auto' }, { value: 'groq', label: 'Groq' }, { value: 'anthropic', label: 'Anthropic' }, { value: 'offline', label: 'Offline' }]} />
          </Row>
          <Row title="Model" desc="Leave empty to use the provider default.">
            <div className="flex gap-2">
              <input value={model} onChange={(e) => setModel(e.target.value)} placeholder={env?.llm.model ?? ''} aria-label="Model" className="mono h-7 w-56 rounded-md border border-line2 bg-bg px-2 text-sm outline-none transition-colors focus:border-accent" />
              <Btn onClick={() => save({ model })} disabled={model === (s.settings?.model ?? '')}>Save</Btn>
            </div>
          </Row>
          <Row title="API key" desc="Paste a Groq (gsk_…) or Anthropic (sk-ant-…) key. The provider is inferred from the prefix.">
            <div className="flex gap-2">
              <input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder={s.settings?.api_key_set ? 'Key saved (hidden)' : 'Paste a key'} autoComplete="off" aria-label="API key" className="mono h-7 w-56 rounded-md border border-line2 bg-bg px-2 text-sm outline-none transition-colors placeholder:text-fg3 focus:border-accent" />
              <Btn onClick={() => { save({ api_key: key }); setKey('') }} disabled={!key}>Save key</Btn>
            </div>
          </Row>
          <div className="flex items-center gap-2 px-5 py-3 text-sm">
            <Sparkles size={14} className={env?.llm.enabled ? 'text-accent' : 'text-fg3'} />
            <span className="text-fg3">Currently:</span>
            <span className="text-fg">{env ? (env.llm.enabled ? llmLabel(env).replace('LLM: ', '') : env.llm.hint || 'LLM off') : 'checking'}</span>
          </div>
        </SettingsGroup>
        {saved && <p className="mt-3 flex items-center gap-1.5 text-sm text-ok"><Check size={14} /> Saved</p>}

        <SettingsGroup title="Environment">
          {env ? ([
            ['C++ compiler', compilerLabel(env)],
            ['pybind11', env.pybind11 ? 'available' : 'missing'],
            ['Python', env.python],
            ['Platform', env.platform.length > 40 ? env.platform.split('-').slice(0, 2).join(' ') + (env.wsl ? ' (WSL)' : '') : env.platform + (env.wsl ? ' (WSL)' : '')],
            ['Offline cache', env.offline_available ? 'available' : 'not recorded'],
          ] as const).map(([k, v]) => <div key={k} className="flex justify-between px-5 py-2.5 text-sm"><dt className="text-fg3">{k}</dt><dd className="mono text-fg">{v}</dd></div>) : <div className="p-5"><Skeleton className="h-4" /></div>}
        </SettingsGroup>
      </div>
    </div>
  )
}
const SettingsGroup = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="mt-8">
    <h2 className="mb-2 text-xs font-medium text-fg3">{title}</h2>
    <div className="surface divide-y divide-line overflow-hidden rounded-[14px]">{children}</div>
  </section>
)
const Row = ({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) => (
  <div className="flex items-center justify-between gap-8 px-5 py-4">
    <div className="max-w-[340px]"><h3 className="text-sm font-medium">{title}</h3><p className="mt-0.5 text-xs leading-4 text-fg3">{desc}</p></div>
    <div className="flex-none">{children}</div>
  </div>
)
export { IconBtn, fmtInt }
