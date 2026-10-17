import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Check, Copy, Download, FileDown, Play, Printer, Sparkles } from 'lucide-react'
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
import type { FunctionRecord, PlaygroundCompile, PlaygroundRun } from './types'

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
const SAMPLE = `def edit_distance(a: str, b: str) -> int:
    n = len(a)
    m = len(b)
    prev: list[int] = []
    for j in range(m + 1):
        prev.append(j)
    for i in range(1, n + 1):
        cur = [i]
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[m]


print(edit_distance("kitten", "sitting"))
print(edit_distance("intention", "execution"))
`

export function Playground() {
  const active = useStudio((s) => s.activeTab === 'playground')
  const [src, setSrc] = useState(() => {
    try {
      return localStorage.getItem('pythia:playground') || SAMPLE
    } catch {
      return SAMPLE
    }
  })
  const dsrc = useDebounced(src, 450)
  const [comp, setComp] = useState<PlaygroundCompile | null>(null)
  const [compiling, setCompiling] = useState(true)
  const [cerr, setCerr] = useState<string | null>(null)
  const [run, setRun] = useState<PlaygroundRun | null>(null)
  const [running, setRunning] = useState(false)
  const [pyLine, setPyLine] = useState<number | null>(null)
  const seq = useRef(0)

  useEffect(() => {
    try { localStorage.setItem('pythia:playground', src) } catch { /* private mode */ }
  }, [src])
  useEffect(() => {
    const id = ++seq.current
    setCompiling(true)
    api.pgCompile(dsrc).then((r) => id === seq.current && (setComp(r), setCerr(null), setCompiling(false))).catch((e) => id === seq.current && (setCerr(errMsg(e)), setCompiling(false)))
  }, [dsrc])

  const doRun = useCallback(async () => {
    setRunning(true)
    try {
      setRun(await api.pgRun(src))
    } catch (e) {
      setRun({ ok: false, error: errMsg(e), python: { stdout: '', exception: null, time_ms: 0 }, cpp: { stdout: '', exception: null, time_ms: 0 }, same: false })
    }
    setRunning(false)
  }, [src])
  useEffect(() => {
    if (!active) return
    const h = () => doRun()
    window.addEventListener('pythia:run', h)
    return () => window.removeEventListener('pythia:run', h)
  }, [active, doRun])

  const pyN = useMemo(() => (comp ? pyNotes(comp.fidelity) : []), [comp])
  const cN = useMemo(() => (comp ? cppNotes({ fidelity: comp.fidelity, cpp_line_map: comp.cpp_line_map }) : []), [comp])
  const sync = comp && pyLine ? comp.cpp_line_map[String(pyLine)] ?? [] : []
  const nErr = comp?.diagnostics.length ?? 0

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-10 flex-none items-center gap-3 border-b border-line bg-panel px-3">
        <h2 className="text-sm font-medium">Playground</h2>
        <span className="text-xs text-fg3">
          {compiling ? 'Compiling…' : cerr ? 'Server error' : nErr ? `${nErr} typechecker error${nErr === 1 ? '' : 's'}` : 'Compiled to C++17'}
        </span>
        <span className="ml-auto flex items-center gap-3 text-xs text-fg3">
          <Legend />
          <Btn kind="primary" onClick={doRun} disabled={running || nErr > 0 || compiling} title={`Run (${MOD}+Enter)`}>
            <Play size={12} /> {running ? 'Running…' : 'Run'} <Kbd>{MOD}↵</Kbd>
          </Btn>
        </span>
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-2">
        <div className="flex min-h-0 flex-col border-r border-line">
          <PaneTitle l="PySub / Python" r="edit here" />
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
          <PaneTitle l="Generated C++17" r={compiling ? 'updating…' : 'live'} />
          <div className="min-h-0 flex-1">
            {cerr ? <Empty title="Compile request failed">{cerr}</Empty> : comp?.ok ? <CodeView path="playground.cpp" value={comp.cpp} language="cpp" notes={cN} syncLines={sync} /> : <Empty title={comp ? 'Nothing to compile yet' : 'Compiling'}>{comp ? 'Fix the typechecker errors on the left and the C++ appears here.' : ''}</Empty>}
          </div>
        </div>
      </div>
      <RunOutput run={run} running={running} />
    </div>
  )
}
const PaneTitle = ({ l, r }: { l: string; r: string }) => (
  <div className="flex h-7 flex-none items-center justify-between border-b border-line bg-panel px-3 text-xs"><span className="font-medium text-fg2">{l}</span><span className="text-fg3">{r}</span></div>
)

function RunOutput({ run, running }: { run: PlaygroundRun | null; running: boolean }) {
  const lines = (s: string) => s.replace(/\n$/, '').split('\n')
  const a = run ? lines(run.python.stdout) : []
  const b = run ? lines(run.cpp.stdout) : []
  const diff = (i: number, x: string[], y: string[]) => x[i] !== y[i]
  return (
    <div className="h-[170px] flex-none border-t border-line bg-panel">
      <div className="flex h-7 items-center gap-3 border-b border-line px-3 text-xs">
        <span className="font-medium text-fg2">Output</span>
        {run && run.ok && <span className={run.same ? 'text-ok' : 'text-bad'}>{run.same ? 'CPython and compiled output are identical' : 'Outputs differ'}</span>}
        {run && run.ok && run.cpp.time_ms > 0 && <span className="tnum ml-auto text-fg2">{run.python.time_ms} ms vs {run.cpp.time_ms} ms · <b className="text-ok">{fmtX(run.python.time_ms / run.cpp.time_ms)}</b></span>}
      </div>
      {running ? (
        <div className="space-y-2 p-3"><Skeleton className="h-4 w-1/3" /><Skeleton className="h-4 w-1/4" /></div>
      ) : !run ? (
        <div className="p-3 text-sm text-fg3">Press Run to execute the program under CPython and as compiled C++, side by side.</div>
      ) : !run.ok ? (
        <div className="p-3 text-sm text-bad">{run.error ?? 'The program could not be run.'}</div>
      ) : (
        <div className="grid h-[calc(100%-28px)] grid-cols-2 divide-x divide-line">
          {[['CPython', a, b, run.python] as const, ['Compiled C++', b, a, run.cpp] as const].map(([label, x, y, side]) => (
            <div key={label} className="min-h-0 overflow-auto px-3 py-1.5">
              <div className="mb-0.5 flex justify-between text-2xs text-fg3"><span>{label}</span><span className="tnum">{side.time_ms} ms</span></div>
              <pre className="mono text-xs">{x.map((l, i) => <div key={i} className={cn(diff(i, x, y) && 'bg-bad/15 text-bad')}>{l || ' '}</div>)}{side.exception && <div className="text-bad">{side.exception}</div>}</pre>
            </div>
          ))}
        </div>
      )}
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
