// Scripted, realistic event stream covering every §4 event type for the mock demo project.
import type { EventType, JobOptions, JobSummary, RankRow, StageName, StageState, StudioEvent } from '../types'
import type { MockProject } from './project'
import { summaryOf } from './project'

export const MOCK_JOB_ID = 'demo0001'
export const MOCK_WS_ID = 'ws000001'
export const MOCK_CMD = 'python main.py --small'

export function buildScript(p: MockProject, opts: Partial<JobOptions> = {}): StudioEvent[] {
  const evs: StudioEvent[] = []
  let seq = 0
  let ts = 1000
  const E = (type: EventType, data: unknown, stage: StageName | null = null, caption: string | null = null, dt = 0.05) => {
    ts += dt
    evs.push({ seq: ++seq, ts: Math.round(ts * 1000) / 1000, type, stage, caption, data } as unknown as StudioEvent)
  }
  const stage = (s: StageName, state: StageState, summary: string | null = null, progress: number | null = null, caption: string | null = null) =>
    E('stage', { stage: s, state, summary, progress }, s, caption, 0.1)
  const log = (stream: 'build' | 'trace' | 'system', text: string, st: StageName | null, level: 'info' | 'warn' | 'error' = 'info') =>
    E('log', { stream, level, text }, st, null, 0.02)
  const step = (step_id: string, fn_id: string | null, title: string, state: 'running' | 'done' | 'failed' | 'info', detail: string | null, st: StageName, caption: string | null = null) =>
    E('agent.step', { step_id, fn_id, title, state, detail }, st, caption, 0.08)

  const fns = p.fns
  const recs = fns.map((f) => f.rec)
  const options: JobOptions = { trace_cmd: MOCK_CMD, trace_timeout_s: 60, offline: true, llm: true, model: 'claude-sonnet-5-5', pace_ms: 0, ...opts }

  // ---------------- job + ingest ----------------
  E('job.start', { job_id: MOCK_JOB_ID, workspace_id: MOCK_WS_ID, name: 'textlab', input_kind: 'demo', options }, null, 'Opening the textlab demo project. The original is never modified; PYTHIA works on a copy.')
  stage('ingest', 'running', null, 0)
  log('system', 'workspace ws000001 created', 'ingest')
  const pyFiles = p.files.length
  const totalFiles = pyFiles + 7
  const names = p.files.map((f) => f.path)
  for (let i = 0; i < 7; i++) {
    const n = Math.round(((i + 1) / 7) * totalFiles)
    E('ingest.progress', { phase: 'copy', files: n, bytes: n * 3100 + 480, current: names[i % names.length], message: `Copying ${names[i % names.length]}` }, 'ingest', i === 0 ? 'Copying the project into an isolated workspace.' : null, 0.12)
  }
  E('ingest.progress', { phase: 'index', files: totalFiles, bytes: totalFiles * 3100, current: null, message: `Indexed ${pyFiles} Python files` }, 'ingest', null, 0.1)
  E('ingest.done', {
    workspace_id: MOCK_WS_ID, name: 'textlab', files: totalFiles, py_files: pyFiles,
    skipped: [
      { path: '.git', reason: 'ignored directory' },
      { path: '__pycache__', reason: 'ignored directory' },
      { path: 'data/corpus_full.txt', reason: 'larger than 5 MB' },
      { path: '.venv', reason: 'ignored directory' },
    ],
  }, 'ingest', null, 0.1)
  stage('ingest', 'done', `${pyFiles} .py files`, 1)

  // ---------------- scan ----------------
  stage('scan', 'running', null, 0, 'Scanning every function and asking the typechecker which ones PYTHIA could compile.')
  for (const f of p.files) {
    if (!f.fns.length) continue
    step(`scan:${f.path}`, null, `Scanning \`${f.path.split('/').slice(-1)[0]}\``, 'done', `${f.fns.length} function${f.fns.length === 1 ? '' : 's'} · ${f.path}`, 'scan')
    for (const id of f.fns) {
      const r = p.byId[id].rec
      const s = summaryOf(r)
      s.status = r.eligibility === 'verifiable' ? 'pending' : r.eligibility === 'fixable' ? 'fixable' : 'not_eligible'
      s.reason = r.eligibility === 'verifiable' ? null : r.reason ?? r.diagnostics[0]?.msg ?? null
      s.share = null; s.calls = null; s.speedup = null; s.probe_speedup = null
      s.score = { total: Math.round((r.score.static_heuristic ?? 0.3) * (r.eligibility === 'not_eligible' ? 0.1 : 1) * 100) / 100, trace_share: null, static_heuristic: r.score.static_heuristic, eligibility_factor: r.score.eligibility_factor, expected_benefit: null, boundary_penalty: null, basis: 'static', notes: ['static estimate: no trace yet'] }
      E('scan.function', { function: s }, 'scan', null, 0.03)
    }
  }
  const cnt = (k: string) => recs.filter((r) => r.eligibility === k).length
  E('scan.done', { functions: recs.length, verifiable: cnt('verifiable'), fixable: cnt('fixable'), not_eligible: cnt('not_eligible') }, 'scan', `Found ${recs.length} functions: ${cnt('verifiable')} compile as written, ${cnt('fixable')} are fixable, ${cnt('not_eligible')} cannot be compiled.`, 0.1)
  stage('scan', 'done', `${recs.length} functions`, 1)

  // ---------------- trace ----------------
  stage('trace', 'running', null, 0, `Running \`${MOCK_CMD}\` under the tracer to find real hot spots and record real arguments.`)
  step('trace', null, `Tracing \`${MOCK_CMD}\``, 'running', 'sys.monitoring · 500 samples per function', 'trace')
  const totalCalls = recs.reduce((a, r) => a + (r.calls ?? 0), 0)
  const tail: string[] = ['textlab 0.4 · small corpus (600 docs)']
  const steps = 14
  for (let i = 1; i <= steps; i++) {
    const f = i / steps
    if (i % 3 === 0) tail.push(['loaded 600 documents', 'tokenised 4210 words', 'deduplicated 600 -> 412 words', 'k-means iteration ' + (i / 3) + ' / 4', 'simulated 300 steps'][Math.min(4, Math.floor(i / 3) - 1)])
    E('trace.progress', { calls: Math.round(totalCalls * f), functions_seen: Math.round(recs.length * Math.min(1, f * 1.4)), elapsed_s: Math.round(14.8 * f * 10) / 10, stdout_tail: tail.slice(-4).join('\n') }, 'trace', i === 6 ? `Recorded ${Math.round(totalCalls * f).toLocaleString('en-US')} calls so far.` : null, 0.15)
    if (i % 4 === 0) log('trace', tail[tail.length - 1], 'trace')
  }
  E('trace.done', {
    total_s: 14.8, exit_code: 0, timed_out: false, calls: totalCalls,
    profile: recs.filter((r) => r.calls).map((r) => ({ id: r.id, calls: r.calls!, cum_s: r.trace!.cum_s, share: r.share! })).sort((a, b) => b.share - a.share),
  }, 'trace', `Trace finished: ${totalCalls.toLocaleString('en-US')} calls in 14.8 s of real work.`, 0.1)
  step('trace', null, `Traced \`${MOCK_CMD}\``, 'done', `${totalCalls.toLocaleString('en-US')} calls · 14.8 s`, 'trace')
  stage('trace', 'done', `${(totalCalls / 1e6).toFixed(1)}M calls`, 1)

  // ---------------- rank ----------------
  stage('rank', 'running', null, 0, 'Ranking by trace time share, expected benefit and the cost of crossing the Python/C++ boundary.')
  const ranked = [...recs].sort((a, b) => b.score.total - a.score.total)
  const ranking: RankRow[] = ranked.map((r, i) => ({ id: r.id, rank: i + 1, score: r.score, status: r.status === 'declined' ? 'declined' : r.eligibility === 'not_eligible' ? 'not_eligible' : r.eligibility === 'fixable' ? 'fixable' : 'pending', reason: r.status === 'declined' ? r.reason : r.eligibility === 'verifiable' ? null : r.reason }))
  const top = ranked.find((r) => r.eligibility !== 'not_eligible')!
  const declined = recs.filter((r) => r.status === 'declined')
  E('rank.done', { ranking }, 'rank', `Top hotspot: ${top.name} (${((top.share ?? 0) * 100).toFixed(1)}% of runtime).${declined.length ? ` Declined ${declined[0].name}: marshalling would cost more than it saves.` : ''}`, 0.1)
  step('rank', null, 'Ranked hotspots', 'done', `${top.name} leads with ${((top.share ?? 0) * 100).toFixed(1)}% of traced runtime`, 'rank')
  for (const d of declined) step(`declined:${d.id}`, d.id, `\`${d.name}\` → declined by the ranker`, 'info', d.reason, 'rank')
  stage('rank', 'done', `top: ${top.name}`, 1)

  // ---------------- fix ----------------
  const fixList = ranked.filter((r) => ['a', 'l', 'lx', 'fx'].includes(p.byId[r.id].spec.kind))
  stage('fix', 'running', null, 0, 'Some functions are almost PySub. Auto-annotation and the LLM fixer try to make them compile.')
  const fixedOk: string[] = []
  for (const r of fixList) {
    const m = p.byId[r.id]
    const k = m.spec.kind
    const sid = `fn:${r.id}`
    if (k === 'fx') { step(sid, r.id, `\`${r.name}\` → skipped (below rewrite threshold)`, 'info', r.reason, 'fix', null); continue }
    if (k === 'a') {
      step(sid, r.id, `\`${r.name}\` → annotating from observed types`, 'running', `(${r.trace!.arg_types.join(', ')}) → ${r.trace!.ret_type}`, 'fix')
      step(sid, r.id, `\`${r.name}\` → annotated from observed types`, 'running', `(${r.trace!.arg_types.join(', ')}) → ${r.trace!.ret_type}. No LLM call needed.`, 'fix', `${r.name} only needs type annotations; the trace already observed them.`)
      fixedOk.push(r.id)
      continue
    }
    const err0 = r.diagnostics.find((d) => d.phase === 'eligibility')?.msg ?? r.reason ?? 'not PySub'
    step(sid, r.id, `\`${r.name}\` → asking the LLM for a PySub rewrite`, 'running', `Typechecker rejected: ${err0}`, 'fix', `Typechecker rejected: ${err0.replace(/\.$/, '')} → asking the LLM for a PySub rewrite`)
    m.attemptsFinal.forEach((a, i) => {
      E('fix.attempt', { id: r.id, attempt: a.attempt, source: a.source, ok: a.ok, error: a.error, pysub: a.pysub }, 'fix',
        a.ok ? `Attempt ${a.attempt} passes the typechecker.` : `Attempt ${a.attempt} rejected by the typechecker: ${a.error?.replace(/^line \d+:\s*/, '')}.${i < m.attemptsFinal.length - 1 ? ' Feeding the error back to the LLM.' : ''}`, 0.6)
      if (!a.ok) step(sid, r.id, `\`${r.name}\` → rewrite attempt ${a.attempt} rejected`, 'running', a.error, 'fix')
    })
    if (k === 'l') {
      E('fix.done', { id: r.id, ok: true, reason: null }, 'fix', null, 0.1)
      step(sid, r.id, `\`${r.name}\` → PySub ✓`, 'running', `Accepted after ${m.attemptsFinal.length} attempt${m.attemptsFinal.length === 1 ? '' : 's'}`, 'fix')
      fixedOk.push(r.id)
    } else {
      E('fix.done', { id: r.id, ok: false, reason: r.reason }, 'fix', `The fixer gave up on ${r.name}: ${r.reason}`, 0.1)
      step(sid, r.id, `\`${r.name}\` → not eligible`, 'failed', r.reason, 'fix')
    }
  }
  stage('fix', 'done', `${fixedOk.length}/${fixList.filter((r) => p.byId[r.id].spec.kind !== 'fx').length} fixed`, 1)

  // ---------------- compile ----------------
  const comp = ranked.filter((r) => ['v', 'g', 'a', 'l', 'd', 'f'].includes(p.byId[r.id].spec.kind))
  stage('compile', 'running', null, 0, `Compiling ${comp.length} functions: PySub → C++17 → pybind11 extension modules.`)
  for (const r of comp) {
    const m = p.byId[r.id]
    const b = r.build!
    const base = `\`${r.name}\``
    const prior = fixedOk.includes(r.id) ? (m.spec.kind === 'l' ? `${base} → PySub ✓` : `${base} → annotated`) : `${base}`
    step(`fn:${r.id}`, r.id, `${prior} → compiling`, 'running', null, 'compile')
    for (const line of b.log.split('\n')) log('build', line, 'compile')
    E('compile.done', { id: r.id, ok: true, cached: b.cached, compile_s: b.compile_s, module: b.module, error: null, diagnostics: [] }, 'compile', null, 0.2)
    step(`fn:${r.id}`, r.id, `${prior} → C++ ✓`, 'running', `${b.module} · ${b.cached ? 'cache hit' : b.compile_s.toFixed(1) + ' s'}`, 'compile')
  }
  stage('compile', 'done', `${comp.length} built`, 1)

  // ---------------- verify ----------------
  const ver = comp.filter((r) => p.byId[r.id].spec.kind !== 'd')
  stage('verify', 'running', null, 0, 'Replaying recorded calls through CPython and the compiled module. Return values, exceptions and mutations must match exactly.')
  let okCount = 0
  for (const r of ver) {
    const m = p.byId[r.id]
    const rp = r.replay!
    const st = m.spec.kind === 'f' ? 'failed' : m.finalStatus === 'guarded' ? 'guarded' : 'verified'
    if (st !== 'failed') okCount++
    const label = fixedOk.includes(r.id) ? (m.spec.kind === 'l' ? 'PySub ✓ → C++ ✓' : 'annotated → C++ ✓') : 'PySub ✓ → C++ ✓'
    E('verify.result', { id: r.id, status: st, total: rp.total, matched: rp.matched, first_mismatch: rp.first_mismatch }, 'verify',
      st === 'failed' ? `${r.name} FAILED replay: ${rp.first_mismatch!.args} gave ${rp.first_mismatch!.python} in Python but ${rp.first_mismatch!.cpp} in C++. Auto-rejected.` : null, 0.15)
    step(`fn:${r.id}`, r.id, `\`${r.name}\` → ${label} → ${rp.matched}/${rp.total} replays match`, st === 'failed' ? 'failed' : 'running',
      st === 'failed' ? `Counterexample ${rp.first_mismatch!.args}: Python ${rp.first_mismatch!.python}, C++ ${rp.first_mismatch!.cpp}` : st === 'guarded' ? `${r.fidelity.filter((f) => f.severity !== 'exact').length} guarded site(s)` : null, 'verify')
  }
  stage('verify', 'done', `${okCount}/${ver.length}`, 1)

  // ---------------- benchmark ----------------
  stage('benchmark', 'running', null, 0, 'Timing Python against C++ on the recorded inputs, then the whole program end to end.')
  const benchList = comp.filter((r) => p.byId[r.id].spec.kind !== 'f')
  for (const r of benchList) {
    const m = p.byId[r.id]
    const b = r.bench!
    const probe = m.spec.kind === 'd'
    E('bench.result', { id: r.id, py_ms: b.py_ms, cpp_ms: b.cpp_ms, speedup: b.speedup, calls_timed: b.calls_timed, probe }, 'benchmark',
      probe ? `Probe: ${r.name} would run at ${b.speedup.toFixed(2)}× — slower than Python, so it is not spliced.` : null, 0.15)
    if (probe) step(`fn:${r.id}`, r.id, `\`${r.name}\` → probe ${b.speedup.toFixed(2)}× (declined)`, 'done', 'Measured slower than CPython because of marshalling; never spliced.', 'benchmark')
    else step(`fn:${r.id}`, r.id, `\`${r.name}\` → ${fixedOk.includes(r.id) ? (m.spec.kind === 'l' ? 'PySub ✓ → ' : 'annotated → ') : 'PySub ✓ → '}C++ ✓ → ${r.replay!.matched}/${r.replay!.total} replays match → ${b.speedup.toFixed(1)}×`, 'done', null, 'benchmark')
  }
  const failedIds = comp.filter((r) => p.byId[r.id].spec.kind === 'f')
  for (const r of failedIds) step(`fn:${r.id}`, r.id, `\`${r.name}\` → replay mismatch → rejected`, 'failed', r.reason, 'benchmark')
  E('bench.e2e', { cmd: MOCK_CMD, before_s: 14.8, after_s: 2.6, speedup: 5.69, output_match: true, ok: true }, 'benchmark', 'End to end: 14.8 s → 2.6 s, 5.7× faster, and the program output is byte-identical.', 0.4)
  stage('benchmark', 'done', '5.7× e2e', 1)

  // ---------------- splice ----------------
  stage('splice', 'running', null, 0, 'Splicing the verified functions back into the workspace copy.')
  const acc = recs.filter((r) => r.status === 'verified' || r.status === 'guarded')
  const byFile = new Map<string, string[]>()
  for (const r of acc) byFile.set(r.file, [...(byFile.get(r.file) ?? []), r.id])
  E('splice.ready', { files: [...byFile.entries()].map(([path, functions]) => ({ path, functions })), functions: acc.length }, 'splice', `${acc.length} functions spliced into ${byFile.size} files. Review each diff, then accept or reject.`, 0.2)
  step('splice', null, 'Splice ready for review', 'done', `${acc.length} functions in ${byFile.size} files`, 'splice')
  stage('splice', 'done', `${acc.length} functions`, 1)
  stage('export', 'idle')

  const count = (s: string) => recs.filter((r) => r.status === s).length
  const sp = acc.map((r) => r.speedup!).filter(Boolean)
  const geo = Math.exp(sp.reduce((a, b) => a + Math.log(b), 0) / sp.length)
  const summary: JobSummary = {
    functions: recs.length, verified: count('verified'), guarded: count('guarded'), fixable: count('fixable'),
    not_eligible: count('not_eligible'), failed: count('failed'), declined: count('declined'),
    e2e_speedup: 5.69, geomean_speedup: Math.round(geo * 10) / 10,
  }
  E('job.done', { state: 'done', summary }, null, `Done. ${summary.verified + summary.guarded} functions verified, ${summary.e2e_speedup}× faster end to end. The LLM suggested; the compiler proved.`, 0.2)
  return evs
}
