// Builds the full mock project: files, FunctionRecords (with journeys, stage dumps, replay/bench numbers).
import type {
  Diagnostic, FidelityNote, FunctionRecord, FunctionSummary, JourneyNode, Mismatch, Rewrite, Score, StageDump, Status, TreeNode,
} from '../types'
import { HEADERS, SPECS, type Kind, type Spec } from './sources'
import { dumpStages, emitCpp, fidelityNotes, lower, parse, typecheck, wrapperCpp, type Sig } from './minipy'

export interface MockFile {
  path: string
  content: string
  /** function ids in order of appearance */
  fns: string[]
  lines: Record<string, { line: number; end_line: number }>
}
export interface MockFn {
  spec: Spec
  rec: FunctionRecord
  attemptsFinal: Rewrite[]
  finalStatus: Status
  modname: string
}
export interface MockProject {
  files: MockFile[]
  fns: MockFn[]
  byId: Record<string, MockFn>
  stagesCache: Record<string, StageDump>
}

const hash8 = (s: string) => {
  let h = 0x811c9dc5
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0 }
  return h.toString(16).padStart(8, '0')
}
const rng = (seed: string) => {
  let a = parseInt(hash8(seed), 16) >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
const r1 = (x: number) => Math.round(x * 10) / 10
const r2 = (x: number) => Math.round(x * 100) / 100

export const SPLICE_HEADER = `try:
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f
`

function sigOf(src: string): [string, Sig] | null {
  const m = /def\s+(\w+)\(([^)]*)\)\s*(?:->\s*([^:]+))?:/.exec(src)
  if (!m || /self/.test(m[2])) return null
  const params = m[2].split(',').map((p) => p.trim()).filter(Boolean).map((p) => (p.includes(':') ? p.split(':')[1].trim() : '?'))
  return [m[1], { params, ret: (m[3] ?? 'None').trim() }]
}

const guessTypes = (src: string) => {
  const m = /def\s+\w+\(([^)]*)\)\s*(?:->\s*([^:]+))?:/.exec(src)!
  const args = m[1].split(',').map((p) => p.trim()).filter(Boolean).map((p) => (p.includes(':') ? p.split(':')[1].trim() : 'object'))
  return { args, ret: (m[2] ?? 'None').trim() }
}

function metrics(src: string, globalsList: string[]) {
  const lines = src.split('\n')
  let depth = 0
  let maxDepth = 0
  const stack: number[] = []
  for (const l of lines) {
    const ind = l.length - l.trimStart().length
    while (stack.length && stack[stack.length - 1] >= ind) { stack.pop(); depth-- }
    if (/^\s*(for|while)\b/.test(l)) { stack.push(ind); depth++; maxDepth = Math.max(maxDepth, depth) }
  }
  const ops = (src.match(/[-+*/%]=?|\/\//g) ?? []).length
  const calls = [...new Set([...src.matchAll(/\b([A-Za-z_]\w*)\(/g)].map((m) => m[1]).filter((n) => !['def', 'if', 'while', 'for', 'and', 'or', 'not', 'in'].includes(n)))]
  return {
    size_lines: lines.length,
    loop_depth: maxDepth,
    arith_density: r2(Math.min(0.95, ops / Math.max(8, src.length / 6))),
    calls: calls.slice(0, 8),
    imports: [] as string[],
    uses_globals: globalsList,
  }
}

const buildLog = (mod: string, fn: string, secs: number, cached: boolean) =>
  cached
    ? `[cache] hit ${mod}.so (sha256 ${hash8(mod)}${hash8(fn)}…)\n[cache] copied to _pythia_accel/lib/${mod}.so`
    : `c++ -std=c++17 -O3 -shared -fPIC -I/usr/include/python3.14 -I.../pybind11/include -o ${mod}.cpython-314-x86_64-linux-gnu.so ${mod}.cpp pyrt.o\n` +
      `${mod}.cpp: In function 'PYBIND11_MODULE':\n` +
      `${mod}.cpp:42:5: note: inlined from '${fn}' (-O3)\n` +
      `[pyrt] reused cached object pyrt.o\n` +
      `link ${mod}.so  ... ok (${secs.toFixed(1)}s)`

function indentOf(l: string) { return l.length - l.trimStart().length }

export function buildProject(): MockProject {
  const sigs: Record<string, Sig> = {}
  for (const s of SPECS) {
    const sg = sigOf(s.kind === 'a' || s.kind === 'l' ? (s.annotated ?? s.src) : s.src)
    if (sg) sigs[sg[0]] = sg[1]
  }

  // ---- group specs per file, compute line numbers ----
  const byFile = new Map<string, Spec[]>()
  for (const s of SPECS) { const a = byFile.get(s.file) ?? []; a.push(s); byFile.set(s.file, a) }
  const files: MockFile[] = []
  const placed = new Map<Spec, { id: string; name: string; qualname: string; line: number; end_line: number; text: string }>()
  const allPaths = new Set<string>([...byFile.keys(), ...Object.keys(HEADERS)])
  for (const path of [...allPaths].sort()) {
    const header = HEADERS[path] ?? ''
    let text = header ? header.replace(/\n+$/, '') + '\n\n\n' : ''
    let cur = text.split('\n').length
    const fns: string[] = []
    const lines: Record<string, { line: number; end_line: number }> = {}
    let inClass = false
    for (const s of byFile.get(path) ?? []) {
      const name = /def\s+(\w+)\(/.exec(s.src)![1]
      const isMethod = /\(self\b/.test(s.src)
      let body = s.src
      let qualname = name
      if (isMethod) {
        if (!inClass) { text += 'class Body:\n    def __init__(self, x, y, z, mass):\n        self.x, self.y, self.z, self.mass = x, y, z, mass\n\n'; cur += 4; inClass = true }
        qualname = `Body.${name}`
        body = '    ' + body
      }
      const n = body.split('\n').length
      const id = `${path}::${qualname}`
      placed.set(s, { id, name, qualname, line: cur, end_line: cur + n - 1, text: s.src })
      lines[id] = { line: cur, end_line: cur + n - 1 }
      fns.push(id)
      text += body + '\n\n\n'
      cur += n + 3
      void indentOf
    }
    files.push({ path, content: text.replace(/\n+$/, '\n'), fns, lines })
  }

  const fnsOut: MockFn[] = []
  const byId: Record<string, MockFn> = {}
  const stagesCache: Record<string, StageDump> = {}

  for (const spec of SPECS) {
    const pl = placed.get(spec)!
    const rnd = rng(pl.id)
    const kind: Kind = spec.kind
    const eligible = kind === 'v' || kind === 'g' || kind === 'd' || kind === 'f'
    const fixable = kind === 'a' || kind === 'l' || kind === 'lx' || kind === 'fx'
    const eligibility = eligible ? 'verifiable' : fixable ? 'fixable' : 'not_eligible'
    const annotated = spec.annotated ?? null
    const types = guessTypes(annotated ?? spec.src)
    const compiled = kind === 'v' || kind === 'g' || kind === 'a' || kind === 'l' || kind === 'd' || kind === 'f'

    // --- final PySub
    let pysub: string | null = null
    let attempts: Rewrite[] = []
    if (kind === 'l' || kind === 'lx') {
      attempts = (spec.attempts ?? []).map((a, i) => ({ attempt: i + 1, source: a.source ?? 'api', pysub: a.pysub, error: a.error, ok: a.error === null }))
      if (kind === 'l') pysub = attempts[attempts.length - 1].pysub
    } else if (kind === 'a') pysub = annotated
    else if (compiled) pysub = spec.src

    // --- compiler stages
    let stages: StageDump | null = null
    let cpp: string | null = null
    let wrapper: string | null = null
    let cppMap: Record<string, number[]> = {}
    let fidelity: FidelityNote[] = []
    const mod = `pythia_${hash8(pl.id + (pysub ?? ''))}`
    if (pysub) {
      const { ast, tokens } = parse(pysub)
      if (ast) {
        const tc = typecheck(ast, sigs)
        const lw = lower(tc.ast, kind === 'v' || kind === 'a' || kind === 'l' || kind === 'd' || kind === 'f')
        const em = emitCpp(lw.pir)
        cpp = em.cpp
        cppMap = em.line_map
        wrapper = wrapperCpp(mod, lw.pir)
        fidelity = fidelityNotes(lw.pir)
        // classic hot-path function that mutates arguments gets an explicit mutation note
        if (/\+=|\] = /.test(pysub) && /: list\[/.test(pysub.split('\n')[0]) && /-> None/.test(pysub.split('\n')[0])) {
          const l = pysub.split('\n').findIndex((x) => /\]\s*\+=/.test(x)) + 1
          fidelity.push({ line: l || 1, col: 1, cls: 'M1 argument mutation', detail: 'The function mutates a list argument in place; the C++ side works on a copy.', mitigation: 'The wrapper writes the final list state back into the caller\'s Python object after the call.', severity: 'exact' })
        }
        for (const x of spec.extraNotes ?? []) fidelity.push({ line: x.line, col: 1, cls: x.cls, detail: x.detail, mitigation: x.mitigation, severity: x.severity })
        fidelity.sort((a, b) => a.line - b.line)
        stages = {
          ok: true, diagnostics: [], tokens, ast, typed_ast: tc.ast, pir: lw.pir, cpp: em.cpp, fidelity,
          guard_elision: { elided: lw.elided, kept: lw.kept },
        }
        stagesCache[pl.id] = stages
      }
    }

    // --- eligibility diagnostics (against original / annotated source)
    let diagnostics: Diagnostic[] = []
    if (kind === 'n') diagnostics = [{ line: 1, col: 1, kind: 'UnsupportedConstruct', msg: spec.reason!, phase: 'eligibility' }]
    else if (fixable) {
      const { ast, diagnostics: pd } = parse(spec.src)
      if (ast) diagnostics = typecheck(ast, sigs).diagnostics.map((d) => ({ ...d, phase: 'eligibility' as const }))
      else diagnostics = pd.map((d) => ({ ...d, phase: 'eligibility' as const }))
      if (!diagnostics.length) diagnostics = [{ line: 1, col: 1, kind: 'TypeError', msg: spec.reason ?? 'not accepted as written', phase: 'eligibility' }]
    }
    for (const a of attempts) if (a.error) { const m = /line (\d+)/.exec(a.error); diagnostics.push({ line: m ? +m[1] : 1, col: 1, kind: 'TypeError', msg: a.error.replace(/^line \d+:\s*/, ''), phase: 'fix' }) }

    // --- status
    let finalStatus: Status
    const hasGuard = fidelity.some((f) => f.severity !== 'exact')
    if (kind === 'n' || kind === 'lx') finalStatus = 'not_eligible'
    else if (kind === 'fx') finalStatus = 'fixable'
    else if (kind === 'd') finalStatus = 'declined'
    else if (kind === 'f') finalStatus = 'failed'
    else finalStatus = hasGuard ? 'guarded' : 'verified'

    // --- numbers
    const share = spec.share ?? null
    const calls = spec.calls ?? null
    const total = r2(Math.min(0.98, (share ?? 0) * 3.1 + Math.log10((spec.speedup ?? spec.probe ?? 1) + 1) * 0.07) * (eligibility === 'not_eligible' ? 0.1 : eligible || kind === 'a' || kind === 'l' ? 1 : 0.35))
    const score: Score = {
      total,
      trace_share: share,
      static_heuristic: r2(0.25 + rnd() * 0.55),
      eligibility_factor: eligibility === 'verifiable' ? 1 : eligibility === 'fixable' ? 0.7 : 0,
      expected_benefit: spec.speedup ? r1(spec.speedup * (0.4 + 0.2 * rnd())) : spec.probe ? 0.8 : null,
      boundary_penalty: kind === 'd' ? 0.91 : r2((spec.elems ?? 1) > 1000 ? 0.12 + rnd() * 0.1 : rnd() * 0.04),
      basis: 'trace',
      notes: [
        share != null ? `${(share * 100).toFixed(1)}% of traced runtime` : 'no trace data',
        eligibility === 'fixable' ? 'discounted: needs annotation or rewrite' : eligibility === 'not_eligible' ? 'not compilable' : 'compiles as written',
        ...(kind === 'd' ? ['boundary penalty dominates: marshalling cost exceeds expected saving'] : []),
      ],
    }
    const trace = calls == null ? null : {
      calls, cum_s: r2(((share ?? 0) * 14.8)), self_s: r2(((share ?? 0) * 14.8) * 0.93), share: share ?? 0,
      arg_types: types.args.map((t) => (t === 'object' ? 'str' : t)), ret_type: types.ret, samples: Math.min(500, calls),
      avg_arg_elems: spec.elems ?? 1, avg_ret_elems: kind === 'v' ? 1 : 3,
    }
    const speedup = compiled && kind !== 'd' && kind !== 'f' ? spec.speedup ?? null : null
    const nrep = Math.min(500, calls ?? 500)
    const mismatch: Mismatch | null = kind === 'f' ? (spec.mismatch ?? null) : null
    const replay = compiled && kind !== 'd' ? {
      total: nrep, matched: kind === 'f' ? Math.floor(nrep * 0.37) : nrep, exc_matches: kind === 'v' ? Math.floor(rnd() * 4) : 0, first_mismatch: mismatch,
    } : null
    const pyMs = r1(18 + rnd() * 240)
    const sp = kind === 'd' ? spec.probe! : speedup
    const bench = compiled && kind !== 'f' && sp ? { py_ms: pyMs, cpp_ms: r2(pyMs / sp), speedup: r1(sp), calls_timed: Math.min(200, nrep), repeats: 5 } : null
    const compile_s = r1(4.2 + rnd() * 4.8)
    const cached = rnd() < 0.3
    const build = compiled ? { ok: true, module: mod, so: `_pythia_accel/lib/${mod}.cpython-314-x86_64-linux-gnu.so`, cached, compile_s: cached ? 0.1 : compile_s, log: buildLog(mod, pl.name, compile_s, cached) } : null
    const spliced = finalStatus === 'verified' || finalStatus === 'guarded'
    const diff = spliced
      ? `--- a/${pl.id.split('::')[0]}\n+++ b/${pl.id.split('::')[0]}\n@@ -${pl.line},${pl.end_line - pl.line + 1} +${pl.line},${pl.end_line - pl.line + 2} @@\n+@_pythia_accelerated("${mod}", "${pl.name}")\n ${spec.src.split('\n')[0]}\n ${(spec.src.split('\n')[1] ?? '').trimEnd()}\n …`
      : null

    // --- journey
    const j = (key: JourneyNode['key'], title: string, state: JourneyNode['state'], summary: string, reason: string | null = null): JourneyNode => ({ key, title, state, summary, reason })
    const stopWhy = kind === 'n' ? `Not eligible: ${spec.reason}` : kind === 'fx' ? 'Skipped: fixable, but below the rewrite threshold' : kind === 'lx' ? 'No valid PySub produced after 3 attempts' : null
    const sk = (key: JourneyNode['key'], title: string, why: string) => j(key, title, 'skipped', why, stopWhy ?? why)
    const journey: JourneyNode[] = [
      j('original', 'Original Python', 'done', `${spec.src.split('\n').length} lines · ${pl.id.split('::')[0]}:${pl.line}`),
      trace ? j('observed_types', 'Observed types', 'done', `(${trace.arg_types.join(', ')}) -> ${trace.ret_type} · ${trace.samples} samples`) : j('observed_types', 'Observed types', 'skipped', 'no trace', 'No trace data was recorded for this function'),
      eligible ? j('eligibility', 'Eligibility check', 'done', 'Typechecker accepts it as written')
        : kind === 'a' ? j('eligibility', 'Eligibility check', 'failed', 'Missing annotations', diagnostics[0]?.msg ?? null)
        : kind === 'l' || kind === 'lx' || kind === 'fx' ? j('eligibility', 'Eligibility check', 'failed', `${diagnostics.length} issue${diagnostics.length === 1 ? '' : 's'}`, diagnostics[0]?.msg ?? spec.reason ?? null)
        : j('eligibility', 'Eligibility check', 'failed', 'Not eligible', spec.reason!),
      kind === 'l' ? j('rewrites', 'LLM rewrite attempts', 'done', `${attempts.length} attempt${attempts.length === 1 ? '' : 's'} · ${attempts.filter((a) => !a.ok).length} rejected, 1 accepted`)
        : kind === 'lx' ? j('rewrites', 'LLM rewrite attempts', 'failed', '3 attempts, none accepted', attempts[2]?.error ?? null)
        : kind === 'a' ? j('rewrites', 'LLM rewrite attempts', 'skipped', 'Not needed', 'Auto-annotation from observed types was enough; no LLM call made.')
        : kind === 'fx' || kind === 'n' ? sk('rewrites', 'LLM rewrite attempts', kind === 'n' ? 'Not fixable' : 'Below rewrite threshold')
        : j('rewrites', 'LLM rewrite attempts', 'skipped', 'Not needed', 'The typechecker accepted the function as written.'),
      pysub ? j('pysub', 'Final PySub', 'done', kind === 'l' ? 'LLM rewrite (typechecker-approved)' : kind === 'a' ? 'Annotated from observed types' : 'Unchanged') : sk('pysub', 'Final PySub', 'No PySub produced'),
      ...(stages
        ? [
            j('tokens', 'Tokens', 'done', `${stages.tokens.length} tokens`),
            j('ast', 'AST', 'done', 'Parsed'),
            j('typed_ast', 'Typed AST', 'done', 'All expressions typed'),
            j('pir', 'PIR', 'done', `${fidelity.length} fidelity note${fidelity.length === 1 ? '' : 's'} · guards ${stages.guard_elision?.elided ?? 0} elided / ${stages.guard_elision?.kept ?? 0} kept`),
            j('cpp', 'Generated C++', 'done', `${cpp!.split('\n').length} lines`),
            j('wrapper', 'pybind11 wrapper', 'done', `${wrapper!.split('\n').length} lines`),
            j('build', 'Build', 'done', cached ? 'Cache hit' : `${compile_s.toFixed(1)}s`),
          ]
        : (['tokens', 'ast', 'typed_ast', 'pir', 'cpp', 'wrapper', 'build'] as const).map((k) => sk(k, ({ tokens: 'Tokens', ast: 'AST', typed_ast: 'Typed AST', pir: 'PIR', cpp: 'Generated C++', wrapper: 'pybind11 wrapper', build: 'Build' } as const)[k], 'Skipped'))),
      kind === 'f' ? j('replay', 'Oracle replay', 'failed', `${replay!.matched}/${replay!.total} matched`, `First counterexample: ${spec.mismatch!.args} -> Python ${spec.mismatch!.python}, C++ ${spec.mismatch!.cpp}`)
        : replay ? j('replay', 'Oracle replay', 'done', `${replay.matched}/${replay.total} matched`)
        : kind === 'd' ? j('replay', 'Oracle replay', 'skipped', 'Probe only', 'Declined by the ranker; compiled as a probe and not replayed.')
        : sk('replay', 'Oracle replay', 'Skipped'),
      bench ? j('benchmark', kind === 'd' ? 'Benchmark (probe)' : 'Benchmark', 'done', `${bench.py_ms.toFixed(1)} ms -> ${bench.cpp_ms.toFixed(2)} ms · ${bench.speedup.toFixed(1)}x`)
        : sk('benchmark', 'Benchmark', kind === 'f' ? 'Not benchmarked: replay failed' : 'Skipped'),
      spliced ? j('splice', 'Splice', 'done', 'Decorator applied in work copy')
        : j('splice', 'Splice', 'skipped', 'Not spliced', kind === 'd' ? 'Declined: compiled as a probe only, never spliced.' : kind === 'f' ? 'Auto-rejected: replay mismatch.' : stopWhy ?? 'Skipped'),
      j('status', 'Status', finalStatus === 'failed' || finalStatus === 'not_eligible' ? 'failed' : 'done', finalStatus.replace('_', ' '), finalStatus === 'verified' || finalStatus === 'guarded' ? null : spec.reason ?? null),
    ]
    // 'status' node: a non-eligible function is a clean stop, not an error; keep failed only for real failures
    if (finalStatus === 'not_eligible' || finalStatus === 'declined' || finalStatus === 'fixable') journey[15].state = 'skipped'

    const rec: FunctionRecord = {
      id: pl.id, file: pl.id.split('::')[0], name: pl.name, qualname: pl.qualname, line: pl.line, end_line: pl.end_line, col: 0,
      status: finalStatus, eligibility, reason: finalStatus === 'verified' || finalStatus === 'guarded' ? null : (spec.reason ?? null),
      decision: 'pending', score, share, calls, speedup: finalStatus === 'verified' || finalStatus === 'guarded' ? speedup : null,
      probe_speedup: kind === 'd' ? spec.probe! : null,
      metrics: metrics(spec.src, /STOPWORDS|np\./.test(spec.src) ? ['STOPWORDS'].filter((g) => spec.src.includes(g)) : []),
      trace,
      sources: { original: spec.src, annotated, pysub, cpp, wrapper_cpp: wrapper },
      line_map_ok: kind !== 'l',
      cpp_line_map: cppMap,
      rewrites: attempts,
      diagnostics,
      fidelity,
      build,
      replay,
      bench,
      splice: spliced ? { applied: true, diff: diff! } : null,
      journey,
    }
    const mf: MockFn = { spec, rec, attemptsFinal: attempts, finalStatus, modname: mod }
    fnsOut.push(mf)
    byId[rec.id] = mf
  }
  return { files, fns: fnsOut, byId, stagesCache }
}

export const summaryOf = (r: FunctionRecord, statusOverride?: Status): FunctionSummary => ({
  id: r.id, file: r.file, name: r.name, qualname: r.qualname, line: r.line, end_line: r.end_line, col: r.col,
  status: statusOverride ?? r.status, eligibility: r.eligibility, reason: r.reason, decision: r.decision, score: r.score,
  share: r.share, calls: r.calls, speedup: r.speedup, probe_speedup: r.probe_speedup,
})

export function treeOf(p: MockProject, decisions: Record<string, string>): TreeNode[] {
  const root: TreeNode[] = []
  const dirs = new Map<string, TreeNode>()
  const ensure = (path: string): TreeNode[] => {
    if (!path) return root
    let d = dirs.get(path)
    if (!d) {
      const parts = path.split('/')
      const parent = ensure(parts.slice(0, -1).join('/'))
      d = { path, name: parts[parts.length - 1], type: 'dir', children: [], badges: { hotspots: 0, accelerated: 0 } }
      parent.push(d)
      dirs.set(path, d)
    }
    return d.children!
  }
  for (const f of p.files) {
    const dir = f.path.split('/').slice(0, -1).join('/')
    const kids = ensure(dir)
    const mine = f.fns.map((id) => p.byId[id].rec)
    const hot = mine.filter((r) => r.eligibility !== 'not_eligible' && (r.share ?? 0) >= 0.01).length
    const acc = mine.filter((r) => (r.status === 'verified' || r.status === 'guarded') && decisions[r.id] !== 'rejected').length
    kids.push({ path: f.path, name: f.path.split('/').pop()!, type: 'file', badges: { hotspots: hot, accelerated: acc } })
    // roll up
    let d = dir
    while (d) { const n = dirs.get(d)!; n.badges!.hotspots += hot; n.badges!.accelerated += acc; d = d.split('/').slice(0, -1).join('/') }
  }
  const sortRec = (n: TreeNode[]) => { n.sort((a, b) => (a.type === b.type ? a.name.localeCompare(b.name) : a.type === 'dir' ? -1 : 1)); n.forEach((x) => x.children && sortRec(x.children)) }
  sortRec(root)
  return root
}

export function workFile(p: MockProject, f: MockFile, decisions: Record<string, string>): string {
  const lines = f.content.split('\n')
  const accel = f.fns.map((id) => p.byId[id]).filter((m) => (m.finalStatus === 'verified' || m.finalStatus === 'guarded') && decisions[m.rec.id] !== 'rejected')
  if (!accel.length) return f.content
  const insertAt = new Map<number, string>()
  for (const m of accel) insertAt.set(m.rec.line, `@_pythia_accelerated("${m.modname}", "${m.rec.name}")`)
  const out: string[] = []
  const hdr = (HEADERS[f.path] ?? '').replace(/\n+$/, '')
  const headerEnd = hdr ? hdr.split('\n').length : 0
  lines.forEach((l, i) => {
    const n = i + 1
    if (n === headerEnd + 1 && headerEnd > 0) out.push('', ...SPLICE_HEADER.split('\n').slice(0, -1))
    const dec = insertAt.get(n)
    if (dec) out.push(/\(self\b/.test(l) ? '    ' + dec : dec)
    out.push(l)
  })
  return out.join('\n')
}
