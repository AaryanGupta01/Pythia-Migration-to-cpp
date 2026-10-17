// Lightweight code rendering for inline artifacts (journey, inspectors): line numbers, highlights, mini diff, tree view.
import { memo, useMemo, useState, type ReactNode } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from './lib/format'
import type { Severity, TreeNodeT } from './types'

const PY_KW = new Set(['def', 'return', 'if', 'elif', 'else', 'for', 'while', 'in', 'not', 'and', 'or', 'True', 'False', 'None', 'pass', 'break', 'continue', 'import', 'from', 'class', 'lambda', 'is', 'with', 'as', 'try', 'except'])
const CPP_KW = new Set(['int64_t', 'double', 'bool', 'void', 'auto', 'const', 'return', 'if', 'else', 'for', 'while', 'namespace', 'using', 'static_cast', 'true', 'false', 'nullptr', 'break', 'continue', 'struct', 'template', 'typename', 'static', 'inline', 'PyStr', 'PyList', 'PyDict', 'size_t'])

const RE = /(#.*|\/\/.*)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(\b\d[\d_]*\.?\d*(?:[eE][+-]?\d+)?\b)|([A-Za-z_]\w*)/g

export function highlightLine(line: string, lang: 'py' | 'cpp' | 'text'): ReactNode[] {
  if (lang === 'text') return [line]
  const kw = lang === 'py' ? PY_KW : CPP_KW
  const out: ReactNode[] = []
  let last = 0
  let m: RegExpExecArray | null
  RE.lastIndex = 0
  while ((m = RE.exec(line))) {
    if (lang === 'py' && m[1]?.startsWith('//')) continue
    if (m.index > last) out.push(line.slice(last, m.index))
    const [txt, com, str, num, id] = m
    const cls = com ? 'text-fg3 italic' : str ? 'text-ok/90' : num ? 'text-warn/90' : id && kw.has(id) ? 'text-accent' : id && lang === 'cpp' && /^py_|^Py/.test(id) ? 'text-fg' : ''
    out.push(cls ? <span key={m.index} className={cls}>{txt}</span> : txt)
    last = m.index + txt.length
  }
  if (last < line.length) out.push(line.slice(last))
  return out
}

export interface CodeHL {
  line: number
  col?: number
  len?: number
}
export const Code = memo(function Code({
  code, lang = 'py', hl, lines, notes, maxH = 300, startLine = 1, onLine, className, gutter,
}: {
  code: string
  lang?: 'py' | 'cpp' | 'text'
  hl?: CodeHL | null
  lines?: number[] // fully highlighted lines
  notes?: Record<number, { severity: Severity; title: string }>
  maxH?: number
  startLine?: number
  onLine?: (n: number) => void
  className?: string
  gutter?: boolean
}) {
  const ls = useMemo(() => code.replace(/\n$/, '').split('\n'), [code])
  const sevCls = { exact: 'bg-ok', guarded: 'bg-warn', divergent: 'bg-bad' }
  return (
    <div className={cn('mono overflow-auto rounded-md border border-line bg-bg', className)} style={{ maxHeight: maxH }} role="region" aria-label="Code">
      <div className="min-w-max py-1.5">
        {ls.map((l, i) => {
          const n = i + startLine
          const isHl = hl?.line === n
          const note = notes?.[n]
          let content: ReactNode = highlightLine(l, lang)
          if (isHl && hl?.col != null && hl.col >= 1) {
            const c = hl.col - 1
            const w = hl.len ?? (/^[\w.]+/.exec(l.slice(c))?.[0].length || 1)
            content = (
              <>
                {highlightLine(l.slice(0, c), lang)}
                <mark className="src-hl bg-transparent text-fg" style={{ background: 'rgb(var(--accent) / 0.35)' }}>{l.slice(c, c + w)}</mark>
                {highlightLine(l.slice(c + w), lang)}
              </>
            )
          }
          return (
            <div
              key={i}
              onClick={onLine ? () => onLine(n) : undefined}
              title={note?.title}
              className={cn('flex leading-[19px]', onLine && 'cursor-pointer hover:bg-hover/50', (isHl || lines?.includes(n)) && 'bg-accent/10')}
            >
              {gutter !== false && (
                <span className="relative w-10 flex-none select-none pr-3 text-right text-fg3/70">
                  {note && <i className={cn('absolute left-1 top-[2px] bottom-[2px] w-[3px] rounded-full', sevCls[note.severity])} />}
                  {n}
                </span>
              )}
              <span className="whitespace-pre pr-4 text-fg2">{content || ' '}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
})

// ---------------- mini line diff (LCS) ----------------
export function lineDiff(a: string, b: string): { t: ' ' | '+' | '-'; s: string }[] {
  const A = a.replace(/\n$/, '').split('\n')
  const B = b.replace(/\n$/, '').split('\n')
  const n = A.length, m = B.length
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
  const out: { t: ' ' | '+' | '-'; s: string }[] = []
  let i = 0, j = 0
  while (i < n && j < m) {
    if (A[i] === B[j]) { out.push({ t: ' ', s: A[i] }); i++; j++ }
    else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({ t: '-', s: A[i++] })
    else out.push({ t: '+', s: B[j++] })
  }
  while (i < n) out.push({ t: '-', s: A[i++] })
  while (j < m) out.push({ t: '+', s: B[j++] })
  return out
}

export function MiniDiff({ a, b, maxH = 320 }: { a: string; b: string; maxH?: number }) {
  const d = useMemo(() => lineDiff(a, b), [a, b])
  return (
    <div className="mono overflow-auto rounded-md border border-line bg-bg py-1.5" style={{ maxHeight: maxH }} role="region" aria-label="Diff">
      <div className="min-w-max">
        {d.map((l, i) => (
          <div key={i} className={cn('flex leading-[19px]', l.t === '+' && 'bg-ok/10', l.t === '-' && 'bg-bad/10')}>
            <span className={cn('w-6 flex-none select-none text-center', l.t === '+' ? 'text-ok' : l.t === '-' ? 'text-bad' : 'text-fg3/40')}>{l.t === ' ' ? '' : l.t}</span>
            <span className={cn('whitespace-pre pr-4', l.t === '-' ? 'text-fg2' : 'text-fg')}>{highlightLine(l.s, 'py')}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function UnifiedDiff({ text, maxH = 260 }: { text: string; maxH?: number }) {
  return (
    <div className="mono overflow-auto rounded-md border border-line bg-bg py-1.5" style={{ maxHeight: maxH }} role="region" aria-label="Splice diff">
      <div className="min-w-max">
        {text.split('\n').map((l, i) => (
          <div key={i} className={cn('whitespace-pre px-3 leading-[19px]', l.startsWith('+') && !l.startsWith('+++') ? 'bg-ok/10 text-ok' : l.startsWith('-') && !l.startsWith('---') ? 'bg-bad/10 text-bad' : l.startsWith('@@') ? 'text-accent' : 'text-fg3')}>
            {l || ' '}
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------- tree ----------------
const kidsOf = (n: TreeNodeT): [string, TreeNodeT[], boolean][] =>
  Object.entries(n.kids ?? {}).map(([k, v]) => [k, Array.isArray(v) ? v : [v], Array.isArray(v)])

function attrText(n: TreeNodeT) {
  const a = n.attrs ?? {}
  const parts: string[] = []
  for (const [k, v] of Object.entries(a)) {
    if (k === 'no_guard') continue
    if (v === null || v === undefined || v === false) continue
    parts.push(typeof v === 'string' ? (k === 'name' || k === 'id' || k === 'op' || k === 'attr' || k === 'value' ? v : `${k}=${v}`) : `${k}=${JSON.stringify(v)}`)
  }
  return parts.join(' ')
}

export function countNodes(n: TreeNodeT | null): number {
  if (!n) return 0
  return 1 + kidsOf(n).reduce((a, [, ks]) => a + ks.reduce((b, k) => b + countNodes(k), 0), 0)
}

export function TreeView({ root, selected, onSelect, maxH = 340, showGuards }: { root: TreeNodeT; selected: TreeNodeT | null; onSelect: (n: TreeNodeT) => void; maxH?: number; showGuards?: boolean }) {
  return (
    <div className="mono overflow-auto rounded-md border border-line bg-bg py-1.5 text-[12px]" style={{ maxHeight: maxH }} role="tree" aria-label="Syntax tree">
      <TNode n={root} depth={0} selected={selected} onSelect={onSelect} label={null} showGuards={showGuards} />
    </div>
  )
}

const STMT = new Set(['FunctionDef', 'For', 'While', 'If', 'Return', 'Assign', 'AugAssign', 'AnnAssign', 'Expr', 'Pass', 'Break', 'Continue', 'Module'])
const EXPR = new Set(['BinOp', 'UnaryOp', 'BoolOp', 'Compare', 'Call', 'Subscript', 'Attribute', 'IfExp', 'Coerce', 'Slice', 'ListComp'])
const nodeColor = (t: string) => (STMT.has(t) ? 'text-accent' : EXPR.has(t) ? 'text-[#6fa8e6]' : t === 'Constant' ? 'text-warn' : t === 'Name' || t === 'Arg' ? 'text-fg' : t === 'Coerce' ? 'text-warn' : 'text-ok/90')

function TNode({ n, depth, selected, onSelect, label, showGuards }: { n: TreeNodeT; depth: number; selected: TreeNodeT | null; onSelect: (n: TreeNodeT) => void; label: string | null; showGuards?: boolean }) {
  const ks = kidsOf(n)
  const [open, setOpen] = useState(depth < 3)
  const sel = selected === n
  const noGuard = n.attrs?.no_guard
  const isCoerce = n.t === 'Coerce'
  return (
    <div role="treeitem" aria-expanded={ks.length ? open : undefined}>
      <div
        onClick={() => onSelect(n)}
        className={cn('relative flex cursor-pointer items-center gap-1.5 whitespace-nowrap pr-3 leading-[20px] hover:bg-hover/60', sel && 'bg-accent/15 shadow-[inset_2px_0_0_rgb(var(--accent))]')}
        style={{ paddingLeft: 6 + depth * 14 }}
      >
        {Array.from({ length: depth }, (_, g) => (
          <span key={g} aria-hidden className="pointer-events-none absolute top-0 h-full w-px bg-line" style={{ left: 14 + g * 14 }} />
        ))}
        <span
          className="flex h-4 w-4 flex-none items-center justify-center text-fg3"
          onClick={(e) => {
            if (ks.length) {
              e.stopPropagation()
              setOpen(!open)
            }
          }}
        >
          {ks.length ? open ? <ChevronDown size={12} /> : <ChevronRight size={12} /> : <span className="h-1 w-1 rounded-full bg-line2" />}
        </span>
        {label && <span className="text-fg3">{label}</span>}
        <span className={cn('font-medium', isCoerce ? 'text-warn' : nodeColor(n.t))}>{n.t}</span>
        <span className="text-fg">{attrText(n)}</span>
        {n.ty && <span className="rounded bg-hover px-1 text-[11px] text-ok/90">{n.ty}</span>}
        {showGuards && noGuard === true && <span className="rounded bg-ok/15 px-1 text-[10.5px] text-ok">guard elided</span>}
        {showGuards && noGuard === false && <span className="rounded bg-warn/15 px-1 text-[10.5px] text-warn">guard kept</span>}
        <span className="ml-auto pl-4 text-[10.5px] text-fg3/70">{n.line}:{n.col}</span>
      </div>
      {open &&
        ks.map(([k, nodes, isArr]) =>
          isArr ? (
            <div key={k}>
              <div className="flex items-center gap-1.5 text-fg3 leading-[18px]" style={{ paddingLeft: 6 + (depth + 1) * 14 + 20 }}>
                {k}
                <span className="text-[10.5px]">[{nodes.length}]</span>
              </div>
              {nodes.map((c, i) => (
                <TNode key={i} n={c} depth={depth + 2} selected={selected} onSelect={onSelect} label={null} showGuards={showGuards} />
              ))}
            </div>
          ) : (
            <TNode key={k} n={nodes[0]} depth={depth + 1} selected={selected} onSelect={onSelect} label={`${k}:`} showGuards={showGuards} />
          ),
        )}
    </div>
  )
}
