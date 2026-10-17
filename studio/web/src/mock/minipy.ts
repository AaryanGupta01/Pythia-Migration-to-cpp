// A tiny PySub-ish front end used ONLY by the in-browser mock (?mock=1):
// tokenizer, parser, type annotator, PIR lowering, C++ emitter, fidelity notes, interpreter.
// It lets the mock produce internally-consistent stage dumps and playground output for any source.
import type { Diagnostic, FidelityNote, StageDump, Token, TreeNodeT } from '../types'

const KEYWORDS = new Set([
  'def', 'return', 'if', 'elif', 'else', 'for', 'while', 'in', 'not', 'and', 'or', 'True', 'False', 'None',
  'pass', 'break', 'continue', 'import', 'from', 'class', 'lambda', 'is', 'with', 'try', 'except', 'global',
])
const OPS3 = ['**=', '//=', '<<=', '>>=']
const OPS2 = ['==', '!=', '<=', '>=', '+=', '-=', '*=', '/=', '%=', '//', '**', '->', '<<', '>>', '&=', '|=']

export function tokenize(src: string): Token[] {
  const toks: Token[] = []
  const lines = src.replace(/\r\n/g, '\n').split('\n')
  const indents = [0]
  let depth = 0
  for (let li = 0; li < lines.length; li++) {
    const line = lines[li]
    const ln = li + 1
    let i = 0
    if (depth === 0) {
      const m = /^[ \t]*/.exec(line)!
      const w = m[0].replace(/\t/g, '    ').length
      const rest = line.slice(m[0].length)
      if (rest === '' || rest.startsWith('#')) continue
      if (w > indents[indents.length - 1]) {
        indents.push(w)
        toks.push({ kind: 'INDENT', value: '', line: ln, col: 1 })
      } else {
        while (w < indents[indents.length - 1]) {
          indents.pop()
          toks.push({ kind: 'DEDENT', value: '', line: ln, col: 1 })
        }
      }
      i = m[0].length
    }
    while (i < line.length) {
      const c = line[i]
      if (c === ' ' || c === '\t') { i++; continue }
      if (c === '#') break
      const col = i + 1
      if (/[A-Za-z_]/.test(c)) {
        let j = i
        while (j < line.length && /\w/.test(line[j])) j++
        const w = line.slice(i, j)
        toks.push({ kind: KEYWORDS.has(w) ? 'KEYWORD' : 'NAME', value: w, line: ln, col })
        i = j
      } else if (/\d/.test(c) || (c === '.' && /\d/.test(line[i + 1] ?? ''))) {
        const m = /^(0[xX][0-9a-fA-F_]+|\d[\d_]*\.?\d*(?:[eE][+-]?\d+)?|\.\d+)/.exec(line.slice(i))!
        toks.push({ kind: 'NUMBER', value: m[0], line: ln, col })
        i += m[0].length
      } else if (c === '"' || c === "'") {
        const triple = line.startsWith(c.repeat(3), i)
        if (triple) {
          const end = line.indexOf(c.repeat(3), i + 3)
          toks.push({ kind: 'STRING', value: '"""…"""', line: ln, col })
          if (end >= 0) { i = end + 3; continue }
          // multi-line docstring: skip until the closing quotes
          let cur = li + 1
          while (cur < lines.length && !lines[cur].includes(c.repeat(3))) cur++
          li = cur
          break
        }
        let j = i + 1
        while (j < line.length && line[j] !== c) j += line[j] === '\\' ? 2 : 1
        toks.push({ kind: 'STRING', value: line.slice(i, j + 1), line: ln, col })
        i = j + 1
      } else {
        const t3 = line.slice(i, i + 3)
        const t2 = line.slice(i, i + 2)
        const op = OPS3.includes(t3) ? t3 : OPS2.includes(t2) ? t2 : c
        if ('([{'.includes(op)) depth++
        if (')]}'.includes(op)) depth = Math.max(0, depth - 1)
        toks.push({ kind: 'OP', value: op, line: ln, col })
        i += op.length
      }
    }
    if (depth === 0) toks.push({ kind: 'NEWLINE', value: '', line: ln, col: line.length + 1 })
  }
  while (indents.length > 1) { indents.pop(); toks.push({ kind: 'DEDENT', value: '', line: lines.length, col: 1 }) }
  toks.push({ kind: 'ENDMARKER', value: '', line: lines.length + 1, col: 1 })
  return toks
}

// ---------------- parser ----------------
class ParseError extends Error {
  line: number
  col: number
  constructor(msg: string, line: number, col: number) { super(msg); this.line = line; this.col = col }
}
type N = TreeNodeT
const mk = (t: string, tok: { line: number; col: number }, attrs?: Record<string, unknown>, kids?: Record<string, N | N[]>): N =>
  ({ t, line: tok.line, col: tok.col, ty: null, ...(attrs ? { attrs } : {}), ...(kids ? { kids } : {}) })

class Parser {
  p = 0
  constructor(public toks: Token[]) {}
  get cur() { return this.toks[this.p] }
  peekIs(v: string) { return this.cur.value === v && (this.cur.kind === 'OP' || this.cur.kind === 'KEYWORD') }
  accept(v: string) { if (this.peekIs(v)) { this.p++; return true } return false }
  expect(v: string) { if (!this.accept(v)) throw new ParseError(`expected '${v}' but found '${this.cur.value || this.cur.kind.toLowerCase()}'`, this.cur.line, this.cur.col); }
  expectKind(k: string) { if (this.cur.kind !== k) throw new ParseError(`expected ${k.toLowerCase()} but found '${this.cur.value || this.cur.kind.toLowerCase()}'`, this.cur.line, this.cur.col); return this.toks[this.p++] }

  module(): N {
    const body: N[] = []
    while (this.cur.kind !== 'ENDMARKER') {
      if (this.cur.kind === 'NEWLINE') { this.p++; continue }
      body.push(this.stmt())
    }
    return mk('Module', { line: 1, col: 1 }, undefined, { body })
  }
  block(): N[] {
    this.expect(':')
    const body: N[] = []
    if (this.cur.kind === 'NEWLINE') {
      this.p++
      this.expectKind('INDENT')
      while ((this.cur.kind as string) !== 'DEDENT' && (this.cur.kind as string) !== 'ENDMARKER') {
        if ((this.cur.kind as string) === 'NEWLINE') { this.p++; continue }
        body.push(this.stmt())
      }
      if ((this.cur.kind as string) === 'DEDENT') this.p++
    } else {
      body.push(this.simple())
    }
    return body
  }
  stmt(): N {
    const t = this.cur
    if (t.kind === 'KEYWORD') {
      switch (t.value) {
        case 'def': return this.funcdef()
        case 'if': return this.ifstmt()
        case 'while': { this.p++; const test = this.expr(); return mk('While', t, undefined, { test, body: this.block() }) }
        case 'for': {
          this.p++
          const target = this.targetList()
          this.expect('in')
          const iter = this.expr()
          const body = this.block()
          return mk('For', t, undefined, { target, iter, body })
        }
        case 'class': throw new ParseError('classes are not supported in the playground subset', t.line, t.col)
        case 'import': case 'from': throw new ParseError('imports are not part of PySub', t.line, t.col)
        case 'lambda': throw new ParseError('lambda is not part of PySub', t.line, t.col)
      }
    }
    return this.simple()
  }
  targetList(): N {
    const first = this.postfix()
    if (this.peekIs(',')) {
      const elts = [first]
      while (this.accept(',')) { if (this.peekIs('in')) break; elts.push(this.postfix()) }
      return mk('Tuple', first, undefined, { elts })
    }
    return first
  }
  funcdef(): N {
    const t = this.cur
    this.expect('def')
    const name = this.expectKind('NAME').value
    this.expect('(')
    const args: N[] = []
    while (!this.peekIs(')')) {
      const a = this.expectKind('NAME')
      let ann: N | undefined
      if (this.accept(':')) ann = this.annotation()
      args.push(mk('Arg', a, { name: a.value }, ann ? { annotation: ann } : undefined))
      if (!this.accept(',')) break
    }
    this.expect(')')
    let returns: N | undefined
    if (this.accept('->')) returns = this.annotation()
    const body = this.block()
    const kids: Record<string, N | N[]> = { args, body }
    if (returns) kids.returns = returns
    return mk('FunctionDef', t, { name }, kids)
  }
  annotation(): N {
    const t = this.cur
    const name = this.cur.kind === 'NAME' || this.cur.kind === 'KEYWORD' ? this.toks[this.p++].value : ((): string => { throw new ParseError('bad annotation', t.line, t.col) })()
    if (this.accept('[')) {
      const params: N[] = [this.annotation()]
      while (this.accept(',')) params.push(this.annotation())
      this.expect(']')
      return mk('TypeRef', t, { name }, { params })
    }
    return mk('TypeRef', t, { name })
  }
  ifstmt(): N {
    const t = this.cur
    this.p++ // if / elif
    const test = this.expr()
    const body = this.block()
    let orelse: N[] = []
    if (this.peekIs('elif')) orelse = [this.ifstmt()]
    else if (this.peekIs('else')) { this.p++; orelse = this.block() }
    return mk('If', t, undefined, { test, body, orelse })
  }
  simple(): N {
    const t = this.cur
    let n: N
    if (this.accept('return')) {
      n = mk('Return', t, undefined, this.cur.kind === 'NEWLINE' ? undefined : { value: this.exprList() })
    } else if (this.accept('pass')) n = mk('Pass', t)
    else if (this.accept('break')) n = mk('Break', t)
    else if (this.accept('continue')) n = mk('Continue', t)
    else {
      const lhs = this.exprList()
      if (this.accept(':')) {
        const ann = this.annotation()
        const value = this.accept('=') ? this.expr() : undefined
        n = mk('AnnAssign', t, undefined, { target: lhs, annotation: ann, ...(value ? { value } : {}) })
      } else if (this.cur.kind === 'OP' && /^(\*\*|\/\/|<<|>>|[+\-*/%&|])=$/.test(this.cur.value)) {
        const op = this.toks[this.p++].value.slice(0, -1)
        n = mk('AugAssign', t, { op }, { target: lhs, value: this.expr() })
      } else if (this.accept('=')) {
        let rhs = this.exprList()
        const targets = [lhs]
        while (this.accept('=')) { targets.push(rhs); rhs = this.exprList() }
        n = mk('Assign', t, undefined, { targets, value: rhs })
      } else n = mk('Expr', t, undefined, { value: lhs })
    }
    if (this.cur.kind === 'NEWLINE') this.p++
    else if (this.cur.kind !== 'DEDENT' && this.cur.kind !== 'ENDMARKER') throw new ParseError(`unexpected '${this.cur.value}'`, this.cur.line, this.cur.col)
    return n
  }
  exprList(): N {
    const first = this.expr()
    if (this.peekIs(',')) {
      const elts = [first]
      while (this.accept(',')) { if (this.cur.kind === 'NEWLINE' || this.peekIs(')') || this.peekIs('=')) break; elts.push(this.expr()) }
      return mk('Tuple', first, undefined, { elts })
    }
    return first
  }
  expr(): N {
    const e = this.orExpr()
    if (this.peekIs('if')) {
      this.p++
      const test = this.orExpr()
      this.expect('else')
      const orelse = this.expr()
      return mk('IfExp', e, undefined, { test, body: e, orelse })
    }
    return e
  }
  orExpr(): N {
    let l = this.andExpr()
    while (this.peekIs('or')) { const t = this.toks[this.p++]; l = mk('BoolOp', t, { op: 'or' }, { values: [l, this.andExpr()] }) }
    return l
  }
  andExpr(): N {
    let l = this.notExpr()
    while (this.peekIs('and')) { const t = this.toks[this.p++]; l = mk('BoolOp', t, { op: 'and' }, { values: [l, this.notExpr()] }) }
    return l
  }
  notExpr(): N {
    if (this.peekIs('not')) { const t = this.toks[this.p++]; return mk('UnaryOp', t, { op: 'not' }, { operand: this.notExpr() }) }
    return this.compare()
  }
  compare(): N {
    const left = this.bin(0)
    const ops: string[] = []
    const comps: N[] = []
    for (;;) {
      const c = this.cur
      let op: string | null = null
      if (c.kind === 'OP' && ['<', '>', '<=', '>=', '==', '!='].includes(c.value)) { op = c.value; this.p++ }
      else if (c.kind === 'KEYWORD' && c.value === 'in') { op = 'in'; this.p++ }
      else if (c.kind === 'KEYWORD' && c.value === 'not' && this.toks[this.p + 1]?.value === 'in') { op = 'not in'; this.p += 2 }
      else if (c.kind === 'KEYWORD' && c.value === 'is') { this.p++; op = this.accept('not') ? 'is not' : 'is' }
      if (!op) break
      ops.push(op)
      comps.push(this.bin(0))
    }
    return ops.length ? mk('Compare', left, { ops }, { left, comparators: comps }) : left
  }
  bin(level: number): N {
    const LV = [['|'], ['^'], ['&'], ['<<', '>>'], ['+', '-'], ['*', '/', '//', '%']]
    if (level >= LV.length) return this.unary()
    let l = this.bin(level + 1)
    while (this.cur.kind === 'OP' && LV[level].includes(this.cur.value)) {
      const t = this.toks[this.p++]
      l = mk('BinOp', t, { op: t.value }, { left: l, right: this.bin(level + 1) })
    }
    return l
  }
  unary(): N {
    if (this.cur.kind === 'OP' && ['-', '+', '~'].includes(this.cur.value)) {
      const t = this.toks[this.p++]
      return mk('UnaryOp', t, { op: t.value }, { operand: this.unary() })
    }
    return this.power()
  }
  power(): N {
    const base = this.postfix()
    if (this.peekIs('**')) { const t = this.toks[this.p++]; return mk('BinOp', t, { op: '**' }, { left: base, right: this.unary() }) }
    return base
  }
  postfix(): N {
    let e = this.atom()
    for (;;) {
      if (this.peekIs('(')) {
        const t = this.toks[this.p++]
        const args: N[] = []
        while (!this.peekIs(')')) { args.push(this.expr()); if (!this.accept(',')) break }
        this.expect(')')
        e = mk('Call', t, undefined, { func: e, args })
      } else if (this.peekIs('[')) {
        const t = this.toks[this.p++]
        let idx = this.expr()
        if (this.peekIs(':')) {
          this.p++
          const upper = this.peekIs(']') ? undefined : this.expr()
          idx = mk('Slice', t, undefined, { lower: idx, ...(upper ? { upper } : {}) })
        }
        this.expect(']')
        e = mk('Subscript', t, undefined, { value: e, index: idx })
      } else if (this.peekIs('.')) {
        const t = this.toks[this.p++]
        const name = this.expectKind('NAME').value
        e = mk('Attribute', t, { attr: name }, { value: e })
      } else break
    }
    return e
  }
  atom(): N {
    const t = this.cur
    if (t.kind === 'NUMBER') { this.p++; return mk('Constant', t, { value: t.value, kind: /[.eE]/.test(t.value) && !/^0[xX]/.test(t.value) ? 'float' : 'int' }) }
    if (t.kind === 'STRING') { this.p++; return mk('Constant', t, { value: t.value, kind: 'str' }) }
    if (t.kind === 'KEYWORD' && (t.value === 'True' || t.value === 'False')) { this.p++; return mk('Constant', t, { value: t.value, kind: 'bool' }) }
    if (t.kind === 'KEYWORD' && t.value === 'None') { this.p++; return mk('Constant', t, { value: 'None', kind: 'None' }) }
    if (t.kind === 'NAME') { this.p++; return mk('Name', t, { id: t.value }) }
    if (this.accept('(')) {
      if (this.accept(')')) return mk('Tuple', t, undefined, { elts: [] })
      const e = this.expr()
      if (this.peekIs(',')) {
        const elts = [e]
        while (this.accept(',')) { if (this.peekIs(')')) break; elts.push(this.expr()) }
        this.expect(')')
        return mk('Tuple', t, undefined, { elts })
      }
      this.expect(')')
      return e
    }
    if (this.accept('[')) {
      if (this.accept(']')) return mk('List', t, undefined, { elts: [] })
      const first = this.expr()
      if (this.peekIs('for')) {
        this.p++
        const target = this.targetList()
        this.expect('in')
        const iter = this.orExpr()
        let cond: N | undefined
        if (this.accept('if')) cond = this.orExpr()
        this.expect(']')
        return mk('ListComp', t, undefined, { elt: first, target, iter, ...(cond ? { cond } : {}) })
      }
      const elts = [first]
      while (this.accept(',')) { if (this.peekIs(']')) break; elts.push(this.expr()) }
      this.expect(']')
      return mk('List', t, undefined, { elts })
    }
    if (this.accept('{')) {
      const keys: N[] = []
      const values: N[] = []
      while (!this.peekIs('}')) { keys.push(this.expr()); this.expect(':'); values.push(this.expr()); if (!this.accept(',')) break }
      this.expect('}')
      return mk('Dict', t, undefined, { keys, values })
    }
    if (t.kind === 'KEYWORD' && t.value === 'lambda') throw new ParseError('lambda is not part of PySub', t.line, t.col)
    throw new ParseError(`unexpected '${t.value || t.kind.toLowerCase()}'`, t.line, t.col)
  }
}

export function parse(src: string): { ast: N | null; diagnostics: Diagnostic[]; tokens: Token[] } {
  const tokens = tokenize(src)
  try {
    return { ast: new Parser(tokens).module(), diagnostics: [], tokens }
  } catch (e) {
    if (e instanceof ParseError) return { ast: null, diagnostics: [{ line: e.line, col: e.col, kind: 'SyntaxError', msg: e.message }], tokens }
    throw e
  }
}

// ---------------- type annotation ----------------
const kidsOf = (n: N, k: string): N[] => { const v = n.kids?.[k]; return v ? (Array.isArray(v) ? v : [v]) : [] }
const kid = (n: N, k: string): N | undefined => { const v = n.kids?.[k]; return v && !Array.isArray(v) ? v : undefined }
const typeStr = (a: N | undefined): string | null => {
  if (!a) return null
  const name = String(a.attrs?.name)
  const ps = kidsOf(a, 'params')
  const m: Record<string, string> = { List: 'list', Dict: 'dict' }
  const nm = m[name] ?? name
  return ps.length ? `${nm}[${ps.map(typeStr).join(', ')}]` : nm
}
const elemOf = (t: string | null) => { const m = /^list\[(.+)\]$/.exec(t ?? ''); return m ? m[1] : null }
const dictV = (t: string | null) => { const m = /^dict\[[^,]+,\s*(.+)\]$/.exec(t ?? ''); return m ? m[1] : null }

const BUILTIN_RET: Record<string, string> = { len: 'int', int: 'int', float: 'float', str: 'str', abs: 'int', ord: 'int', chr: 'str', sqrt: 'float', bool: 'bool', range: 'range', sum: 'int', min: 'int', max: 'int', round: 'int', print: 'None', floor: 'int', exp: 'float', log: 'float', sin: 'float', cos: 'float' }

export interface Sig { params: string[]; ret: string }
export interface TypeResult { ast: N; diagnostics: Diagnostic[]; sigs: Record<string, Sig> }

const clone = (n: N): N => JSON.parse(JSON.stringify(n))

export function typecheck(ast: N, extraSigs: Record<string, Sig> = {}): TypeResult {
  const t = clone(ast)
  const diags: Diagnostic[] = []
  const sigs: Record<string, Sig> = { ...extraSigs }
  const err = (n: N, kind: string, msg: string) => diags.push({ line: n.line, col: n.col, kind, msg })
  for (const f of kidsOf(t, 'body')) {
    if (f.t === 'FunctionDef') sigs[String(f.attrs?.name)] = { params: kidsOf(f, 'args').map((a) => typeStr(kid(a, 'annotation')) ?? '?'), ret: typeStr(kid(f, 'returns')) ?? 'None' }
  }
  const fnRet = { v: 'None' }
  const expr = (n: N, env: Record<string, string>): string | null => {
    let ty: string | null = null
    switch (n.t) {
      case 'Constant': { const k = String(n.attrs?.kind); ty = k; break }
      case 'Name': { const id = String(n.attrs?.id); ty = env[id] ?? null; if (!ty && !(id in sigs) && !(id in BUILTIN_RET)) err(n, 'NameError', `name '${id}' is not defined`); break }
      case 'BinOp': {
        const a = expr(kid(n, 'left')!, env), b = expr(kid(n, 'right')!, env)
        const op = String(n.attrs?.op)
        if (a === 'str' && b === 'str' && op === '+') ty = 'str'
        else if (a === 'str' && b === 'int' && op === '*') ty = 'str'
        else if (a?.startsWith('list') && op === '+') ty = a
        else if (a === 'str' || b === 'str') { err(n, 'TypeError', `unsupported operand types for ${op}: '${a}' and '${b}'`); ty = a }
        else if (op === '/') ty = 'float'
        else if (a === 'float' || b === 'float') ty = 'float'
        else ty = a === 'bool' ? 'int' : (a ?? b)
        break
      }
      case 'UnaryOp': { const o = expr(kid(n, 'operand')!, env); ty = n.attrs?.op === 'not' ? 'bool' : o; break }
      case 'BoolOp': { kidsOf(n, 'values').forEach((v) => expr(v, env)); ty = 'bool'; break }
      case 'Compare': { expr(kid(n, 'left')!, env); kidsOf(n, 'comparators').forEach((v) => expr(v, env)); ty = 'bool'; break }
      case 'IfExp': { expr(kid(n, 'test')!, env); const a = expr(kid(n, 'body')!, env); const b = expr(kid(n, 'orelse')!, env); ty = a === 'int' && b === 'float' ? 'float' : a; break }
      case 'Call': {
        const f = kid(n, 'func')!
        const args = kidsOf(n, 'args').map((a) => expr(a, env))
        if (f.t === 'Name') {
          const nm = String(f.attrs?.id)
          f.ty = null
          if (nm in sigs) ty = sigs[nm].ret
          else if (nm in BUILTIN_RET) {
            ty = BUILTIN_RET[nm]
            if (['abs', 'min', 'max', 'sum'].includes(nm)) ty = args[0] === 'float' ? 'float' : elemOf(args[0]) ?? args[0] ?? 'int'
          } else err(f, 'NameError', `call to unknown function '${nm}'`)
        } else if (f.t === 'Attribute') {
          const base = expr(kid(f, 'value')!, env)
          const at = String(f.attrs?.attr)
          if (base && (base.startsWith('list') || base.startsWith('dict') || base === 'str')) {
            ty = at === 'append' || at === 'sort' || at === 'reverse' ? 'None' : at === 'pop' ? elemOf(base) ?? 'int' : at === 'get' ? dictV(base) ?? 'int' : at === 'join' || at === 'lower' || at === 'upper' || at === 'strip' ? 'str' : at === 'split' ? 'list[str]' : at === 'count' || at === 'find' || at === 'index' ? 'int' : null
          } else err(n, 'TypeError', `calls on module or object '${(kid(f, 'value')?.attrs?.id as string) ?? '?'}' are outside PySub`)
        }
        break
      }
      case 'Subscript': {
        const v = expr(kid(n, 'value')!, env)
        const idx = kid(n, 'index')!
        if (idx.t === 'Slice') { kidsOf(idx, 'lower').forEach((x) => expr(x, env)); const u = kid(idx, 'upper'); if (u) expr(u, env); ty = v }
        else { expr(idx, env); ty = v === 'str' ? 'str' : v?.startsWith('dict') ? dictV(v) : elemOf(v) }
        break
      }
      case 'Attribute': { expr(kid(n, 'value')!, env); err(n, 'TypeError', 'attribute access is not part of PySub'); break }
      case 'List': { const es = kidsOf(n, 'elts').map((e) => expr(e, env)); ty = es.length ? `list[${es[0]}]` : 'list[int]'; break }
      case 'Tuple': { kidsOf(n, 'elts').forEach((e) => expr(e, env)); ty = 'tuple'; break }
      case 'Dict': { const ks = kidsOf(n, 'keys').map((e) => expr(e, env)); const vs = kidsOf(n, 'values').map((e) => expr(e, env)); ty = ks.length ? `dict[${ks[0]}, ${vs[0]}]` : 'dict[str, int]'; break }
      case 'ListComp': {
        err(n, 'UnsupportedConstruct', 'list comprehension is not part of PySub; rewrite with an explicit loop and .append')
        const e2 = { ...env }
        const it = expr(kid(n, 'iter')!, env)
        const tg = kid(n, 'target')!
        if (tg.t === 'Name') e2[String(tg.attrs?.id)] = it === 'range' ? 'int' : elemOf(it) ?? 'int'
        ty = `list[${expr(kid(n, 'elt')!, e2)}]`
        break
      }
    }
    n.ty = ty
    return ty
  }
  const stmts = (body: N[], env: Record<string, string>) => {
    for (const s of body) {
      switch (s.t) {
        case 'Assign': {
          const v = expr(kid(s, 'value')!, env)
          for (const tg of kidsOf(s, 'targets')) {
            if (tg.t === 'Name') {
              const id = String(tg.attrs?.id)
              if (env[id] && v && env[id] !== v && !(env[id] === 'float' && v === 'int')) err(tg, 'TypeError', `variable '${id}' changes type from ${env[id]} to ${v}`)
              else if (!env[id] && v) env[id] = v
              tg.ty = env[id] ?? v
            } else if (tg.t === 'Tuple') {
              kidsOf(tg, 'elts').forEach((e) => { if (e.t === 'Name') { env[String(e.attrs?.id)] = env[String(e.attrs?.id)] ?? 'int'; e.ty = env[String(e.attrs?.id)] } })
            } else expr(tg, env)
          }
          break
        }
        case 'AnnAssign': { const tg = kid(s, 'target')!; const a = typeStr(kid(s, 'annotation')); if (tg.t === 'Name' && a) { env[String(tg.attrs?.id)] = a; tg.ty = a } const v = kid(s, 'value'); if (v) expr(v, env); break }
        case 'AugAssign': { const tg = kid(s, 'target')!; const a = expr(tg, env); const b = expr(kid(s, 'value')!, env); if (a === 'int' && b === 'float') err(s, 'TypeError', `variable changes type from int to float in augmented assignment`); break }
        case 'Return': { const v = kid(s, 'value'); const r = v ? expr(v, { ...env }) : 'None'; if (r && fnRet.v !== r && !(fnRet.v === 'float' && r === 'int') && fnRet.v !== '?') err(s, 'TypeError', `return type ${r} does not match declared ${fnRet.v}`); break }
        case 'Expr': expr(kid(s, 'value')!, env); break
        case 'If': expr(kid(s, 'test')!, env); stmts(kidsOf(s, 'body'), env); stmts(kidsOf(s, 'orelse'), env); break
        case 'While': expr(kid(s, 'test')!, env); stmts(kidsOf(s, 'body'), env); break
        case 'For': {
          const it = expr(kid(s, 'iter')!, env)
          const tg = kid(s, 'target')!
          const et = it === 'range' ? 'int' : it === 'str' ? 'str' : elemOf(it) ?? 'int'
          if (tg.t === 'Name') { env[String(tg.attrs?.id)] = et; tg.ty = et }
          else if (tg.t === 'Tuple') kidsOf(tg, 'elts').forEach((e) => { if (e.t === 'Name') { env[String(e.attrs?.id)] = 'int'; e.ty = 'int' } })
          stmts(kidsOf(s, 'body'), env)
          break
        }
      }
    }
  }
  for (const f of kidsOf(t, 'body')) {
    if (f.t !== 'FunctionDef') continue
    const env: Record<string, string> = {}
    for (const a of kidsOf(f, 'args')) {
      const ann = typeStr(kid(a, 'annotation'))
      if (!ann) err(a, 'TypeError', `missing annotation for parameter '${a.attrs?.name}' (fixable: observed types can supply it)`)
      env[String(a.attrs?.name)] = ann ?? 'int'
      a.ty = ann
    }
    const r = typeStr(kid(f, 'returns'))
    if (!r) err(f, 'TypeError', `missing return annotation for '${f.attrs?.name}' (fixable)`)
    fnRet.v = r ?? '?'
    f.ty = r
    stmts(kidsOf(f, 'body'), env)
  }
  const top = kidsOf(t, 'body').filter((x) => x.t !== 'FunctionDef')
  fnRet.v = '?'
  stmts(top, {})
  return { ast: t, diagnostics: diags, sigs }
}

// ---------------- PIR lowering ----------------
export function lower(typed: N, elideAll = false): { pir: N; elided: number; kept: number } {
  const pir = clone(typed)
  let elided = 0
  let kept = 0
  const loopVars = new Set<string>()
  const walk = (n: N, inLoop: boolean) => {
    if (n.t === 'For') {
      const tg = kid(n, 'target')
      if (tg?.t === 'Name' && kid(n, 'iter')?.t === 'Call') loopVars.add(String(tg.attrs?.id))
    }
    if (n.t === 'BinOp' || n.t === 'AugAssign') {
      const op = String(n.attrs?.op)
      const l = kid(n, n.t === 'BinOp' ? 'left' : 'target')
      const r = kid(n, n.t === 'BinOp' ? 'right' : 'value')
      if (['+', '-', '*'].includes(op) && n.ty !== 'float' && l?.ty !== 'float' && r?.ty !== 'float' && n.ty !== 'str' && !(n.ty ?? '').startsWith('list')) {
        const small = (x?: N) => x && ((x.t === 'Constant' && Number(x.attrs?.value) < 1e6) || (x.t === 'Name' && loopVars.has(String(x.attrs?.id))))
        const noGuard = !!(elideAll || (small(l) && small(r)) || ((small(l) || small(r)) && op !== '*') || (op === '*' && (small(l) || small(r)) && n.t === 'BinOp' && Number(small(l) ? l?.attrs?.value : r?.attrs?.value) < 1e6))
        n.attrs = { ...n.attrs, no_guard: noGuard }
        if (noGuard) elided++
        else kept++
      }
      // int -> float promotion becomes an explicit Coerce node
      if (n.t === 'BinOp' && (l?.ty === 'int') !== (r?.ty === 'int') && (l?.ty === 'float' || r?.ty === 'float')) {
        const side = l?.ty === 'int' ? 'left' : 'right'
        const x = kid(n, side)!
        n.kids![side] = { t: 'Coerce', line: x.line, col: x.col, ty: 'float', attrs: { from: 'int', to: 'float' }, kids: { value: x } }
      }
    }
    for (const v of Object.values(n.kids ?? {})) (Array.isArray(v) ? v : [v]).forEach((c) => walk(c, inLoop || n.t === 'For' || n.t === 'While'))
  }
  walk(pir, false)
  return { pir, elided, kept }
}

// ---------------- C++ emission ----------------
const cppType = (t: string | null): string => {
  if (!t) return 'auto'
  if (t === 'int') return 'int64_t'
  if (t === 'float') return 'double'
  if (t === 'bool') return 'bool'
  if (t === 'str') return 'PyStr'
  if (t === 'None') return 'void'
  const l = /^list\[(.+)\]$/.exec(t)
  if (l) return `PyList<${cppType(l[1])}>`
  const d = /^dict\[(.+?),\s*(.+)\]$/.exec(t)
  if (d) return `PyDict<${cppType(d[1])}, ${cppType(d[2])}>`
  return 'auto'
}

export interface CppResult { cpp: string; line_map: Record<string, number[]> }

export function emitCpp(pir: N, withHeader = true): CppResult {
  const out: string[] = []
  const map: Record<string, number[]> = {}
  const mark = (srcLine: number) => { (map[srcLine] ||= []).push(out.length) }
  if (withHeader) out.push('#include "pyrt.hpp"', 'using namespace pyrt;', '', 'namespace pythia_mod {', '')
  const E = (n: N): string => {
    switch (n.t) {
      case 'Constant': {
        const k = n.attrs?.kind; const v = String(n.attrs?.value)
        if (k === 'str') return `PyStr(${v.replace(/^'|'$/g, '"')})`
        if (k === 'bool') return v === 'True' ? 'true' : 'false'
        if (k === 'None') return 'nullptr'
        return v
      }
      case 'Name': return String(n.attrs?.id)
      case 'Coerce': return `static_cast<double>(${E(kid(n, 'value')!)})`
      case 'BinOp': {
        const op = String(n.attrs?.op); const a = E(kid(n, 'left')!); const b = E(kid(n, 'right')!)
        const isInt = n.ty === 'int'
        if (n.ty === 'str' || (n.ty ?? '').startsWith('list')) return op === '+' ? `py_concat(${a}, ${b})` : `py_repeat(${a}, ${b})`
        if (op === '//') return `py_floordiv(${a}, ${b})`
        if (op === '%') return `py_mod(${a}, ${b})`
        if (op === '/') return `py_truediv(${a}, ${b})`
        if (op === '**') return `py_pow(${a}, ${b})`
        if (isInt && ['+', '-', '*'].includes(op) && !n.attrs?.no_guard) return `${{ '+': 'py_add', '-': 'py_sub', '*': 'py_mul' }[op]}(${a}, ${b})`
        return `(${a} ${op} ${b})`
      }
      case 'UnaryOp': return n.attrs?.op === 'not' ? `!${E(kid(n, 'operand')!)}` : `${n.attrs?.op}${E(kid(n, 'operand')!)}`
      case 'BoolOp': return `(${kidsOf(n, 'values').map(E).join(n.attrs?.op === 'and' ? ' && ' : ' || ')})`
      case 'Compare': {
        let l = E(kid(n, 'left')!); const parts: string[] = []
        const ops = n.attrs?.ops as string[]
        kidsOf(n, 'comparators').forEach((c, i) => {
          const r = E(c); const op = ops[i]
          if (op === 'in') parts.push(`py_contains(${r}, ${l})`)
          else if (op === 'not in') parts.push(`!py_contains(${r}, ${l})`)
          else parts.push(`(${l} ${op === 'is' ? '==' : op === 'is not' ? '!=' : op} ${r})`)
          l = r
        })
        return parts.join(' && ')
      }
      case 'IfExp': return `(${E(kid(n, 'test')!)} ? ${E(kid(n, 'body')!)} : ${E(kid(n, 'orelse')!)})`
      case 'Call': {
        const f = kid(n, 'func')!; const args = kidsOf(n, 'args').map(E)
        if (f.t === 'Name') { const nm = String(f.attrs?.id); if (nm === 'len') return `py_len(${args[0]})`; if (nm === 'print') return `py_print(${args.join(', ')})`; return `${nm}(${args.join(', ')})` }
        if (f.t === 'Attribute') return `${E(kid(f, 'value')!)}.${f.attrs?.attr}(${args.join(', ')})`
        return `/*call*/`
      }
      case 'Subscript': { const idx = kid(n, 'index')!; return idx.t === 'Slice' ? `py_slice(${E(kid(n, 'value')!)}, ${E(kid(idx, 'lower')!)}${kid(idx, 'upper') ? ', ' + E(kid(idx, 'upper')!) : ''})` : `${E(kid(n, 'value')!)}.at(${E(idx)})` }
      case 'List': return `${cppType(n.ty)}{${kidsOf(n, 'elts').map(E).join(', ')}}`
      case 'Tuple': return `std::make_tuple(${kidsOf(n, 'elts').map(E).join(', ')})`
      case 'Dict': return `${cppType(n.ty)}{${kidsOf(n, 'keys').map((k, i) => `{${E(k)}, ${E(kidsOf(n, 'values')[i])}}`).join(', ')}}`
      default: return `/*${n.t}*/`
    }
  }
  const declared: Set<string>[] = []
  const S = (body: N[], ind: string) => {
    for (const s of body) {
      mark(s.line)
      switch (s.t) {
        case 'Return': { const v = kid(s, 'value'); out.push(`${ind}return${v ? ' ' + E(v) : ''};`); break }
        case 'Pass': out.push(`${ind}/* pass */`); break
        case 'Break': out.push(`${ind}break;`); break
        case 'Continue': out.push(`${ind}continue;`); break
        case 'Expr': out.push(`${ind}${E(kid(s, 'value')!)};`); break
        case 'Assign': {
          const tg = kidsOf(s, 'targets')[0]; const v = E(kid(s, 'value')!)
          const d = declared[declared.length - 1]
          if (tg.t === 'Name') { const id = String(tg.attrs?.id); if (d.has(id)) out.push(`${ind}${id} = ${v};`); else { d.add(id); out.push(`${ind}${cppType(tg.ty)} ${id} = ${v};`) } }
          else if (tg.t === 'Subscript') out.push(`${ind}${E(kid(tg, 'value')!)}.set(${E(kid(tg, 'index')!)}, ${v});`)
          else if (tg.t === 'Tuple') { const names = kidsOf(tg, 'elts').map(E); out.push(`${ind}std::tie(${names.join(', ')}) = std::make_tuple(${E(kid(s, 'value')!).replace(/^std::make_tuple\(|\)$/g, '')});`) }
          else out.push(`${ind}/* unsupported target */`)
          break
        }
        case 'AnnAssign': { const tg = kid(s, 'target')!; const v = kid(s, 'value'); declared[declared.length - 1].add(String(tg.attrs?.id)); out.push(`${ind}${cppType(tg.ty)} ${E(tg)}${v ? ' = ' + E(v) : ''};`); break }
        case 'AugAssign': {
          const tg = kid(s, 'target')!; const op = String(s.attrs?.op); const v = E(kid(s, 'value')!)
          if (tg.ty === 'int' && ['+', '-', '*'].includes(op) && !s.attrs?.no_guard) out.push(`${ind}${E(tg)} = ${{ '+': 'py_add', '-': 'py_sub', '*': 'py_mul' }[op]}(${E(tg)}, ${v});`)
          else if (op === '//' || op === '%') out.push(`${ind}${E(tg)} = ${op === '//' ? 'py_floordiv' : 'py_mod'}(${E(tg)}, ${v});`)
          else out.push(`${ind}${E(tg)} ${op}= ${v};`)
          break
        }
        case 'If': {
          out.push(`${ind}if (${E(kid(s, 'test')!)}) {`); S(kidsOf(s, 'body'), ind + '    ')
          let oe = kidsOf(s, 'orelse')
          while (oe.length === 1 && oe[0].t === 'If') { out.push(`${ind}} else if (${E(kid(oe[0], 'test')!)}) {`); mark(oe[0].line); S(kidsOf(oe[0], 'body'), ind + '    '); oe = kidsOf(oe[0], 'orelse') }
          if (oe.length) { out.push(`${ind}} else {`); S(oe, ind + '    ') }
          out.push(`${ind}}`); break
        }
        case 'While': out.push(`${ind}while (${E(kid(s, 'test')!)}) {`); S(kidsOf(s, 'body'), ind + '    '); out.push(`${ind}}`); break
        case 'For': {
          const tg = kid(s, 'target')!; const it = kid(s, 'iter')!
          const name = tg.t === 'Name' ? String(tg.attrs?.id) : '_it'
          declared[declared.length - 1].add(name)
          if (it.t === 'Call' && kid(it, 'func')?.attrs?.id === 'range') {
            const a = kidsOf(it, 'args').map(E)
            const [lo, hi, st] = a.length === 1 ? ['0', a[0], '1'] : [a[0], a[1], a[2] ?? '1']
            out.push(`${ind}for (int64_t ${name} = ${lo}; ${name} < ${hi}; ${name} += ${st}) {`)
          } else out.push(`${ind}for (auto ${name} : ${E(it)}) {`)
          S(kidsOf(s, 'body'), ind + '    '); out.push(`${ind}}`); break
        }
        default: out.push(`${ind}/* ${s.t} */`)
      }
    }
  }
  for (const f of kidsOf(pir, 'body')) {
    if (f.t !== 'FunctionDef') continue
    const args = kidsOf(f, 'args').map((a) => `${cppType(a.ty)}${/^(PyStr|PyList|PyDict)/.test(cppType(a.ty)) ? ' const&' : ''} ${a.attrs?.name}`)
    mark(f.line)
    out.push(`${cppType(f.ty)} ${f.attrs?.name}(${args.join(', ')}) {`)
    declared.push(new Set(kidsOf(f, 'args').map((a) => String(a.attrs?.name))))
    S(kidsOf(f, 'body'), '    ')
    declared.pop()
    out.push('}', '')
  }
  const topStmts = kidsOf(pir, 'body').filter((x) => x.t !== 'FunctionDef')
  if (topStmts.length) {
    out.push('int main() {')
    declared.push(new Set())
    S(topStmts, '    ')
    declared.pop()
    out.push('    return 0;', '}', '')
  }
  if (withHeader) out.push('}  // namespace pythia_mod')
  // convert 0-based indexes captured by mark() into 1-based line numbers of the *next* emitted line
  const lm: Record<string, number[]> = {}
  for (const [k, v] of Object.entries(map)) lm[k] = v.map((i) => i + 1)
  return { cpp: out.join('\n'), line_map: lm }
}

export function wrapperCpp(modname: string, pir: N): string {
  const fns = kidsOf(pir, 'body').filter((f) => f.t === 'FunctionDef')
  const lines = [
    '#include <pybind11/pybind11.h>', '#include <pybind11/stl.h>', '#include "pyrt.hpp"', '#include "' + modname + '_fns.hpp"', '',
    'namespace py = pybind11;', 'static PyObject* g_fallback = nullptr;', '',
    `PYBIND11_MODULE(${modname}, m) {`,
    '    g_fallback = py::exception<std::runtime_error>(m, "FallbackError").ptr();',
  ]
  for (const f of fns) {
    const args = kidsOf(f, 'args')
    const sig = args.map((a) => `${cppType(a.ty)} ${a.attrs?.name}`).join(', ')
    lines.push(`    m.def("${f.attrs?.name}", [](${sig}) {`, '        pyrt::arena_begin();', `        auto r = pythia_mod::${f.attrs?.name}(${args.map((a) => a.attrs?.name).join(', ')});`, '        pyrt::arena_end();', '        return r;', '    });')
  }
  lines.push('}')
  return lines.join('\n')
}

// ---------------- fidelity ----------------
export function fidelityNotes(pir: N): FidelityNote[] {
  const notes: FidelityNote[] = []
  const seen = new Set<string>()
  const add = (n: N, cls: string, detail: string, mitigation: string, severity: FidelityNote['severity']) => {
    const k = severity === 'exact' ? cls : `${n.line}:${cls}`
    if (seen.has(k)) return
    seen.add(k)
    notes.push({ line: n.line, col: n.col, cls, detail, mitigation, severity })
  }
  const walk = (n: N, loop: number) => {
    if ((n.t === 'BinOp' || n.t === 'AugAssign') && ['+', '-', '*'].includes(String(n.attrs?.op)) && n.ty === 'int' && n.attrs?.no_guard === false)
      add(n, 'D1 unbounded-int vs int64', 'Python integers are arbitrary precision; the compiled code uses int64_t. A result outside +/-2^63 cannot be represented.', 'Arithmetic is overflow-checked: the call raises OverflowError instead of wrapping, and replay would flag any mismatch.', 'guarded')
    if (n.t === 'BinOp' && (n.attrs?.op === '//' || n.attrs?.op === '%'))
      add(n, 'D3 floor division and modulo sign', 'C++ truncates toward zero; Python floors. Results differ for negative operands.', 'The runtime provides py_floordiv/py_mod which reproduce Python semantics exactly, including ZeroDivisionError.', 'exact')
    if (n.t === 'BinOp' && n.attrs?.op === '/')
      add(n, 'D4 true division', 'int / int yields float in Python; ZeroDivisionError message text differs between interpreters.', 'Division goes through py_truediv; the exception class is identical and the message is normalised.', 'exact')
    if (n.t === 'Subscript' && n.ty !== null && kid(n, 'index')?.t !== 'Slice')
      add(n, 'E2 indexing and bounds', 'Negative indexes and out-of-range access must behave like CPython.', 'Container access is bounds-checked and wraps negative indexes; IndexError is raised with the same class.', 'exact')
    if (n.ty === 'str' && (n.t === 'Subscript' || n.t === 'BinOp'))
      add(n, 'D5 ASCII-only strings', 'Compiled strings are byte strings. Non-ASCII text would index differently from Python code points.', 'The wrapper raises FallbackError for non-ASCII input so the original Python runs instead.', 'exact')
    if (n.t === 'BinOp' && n.ty === 'float')
      add(n, 'D2 float evaluation order', 'IEEE-754 doubles are used; evaluation order matches the source.', 'Compiled with -O3 but without -ffast-math, so floating-point results are bitwise identical.', 'exact')
    for (const v of Object.values(n.kids ?? {})) (Array.isArray(v) ? v : [v]).forEach((c) => walk(c, loop + (n.t === 'For' || n.t === 'While' ? 1 : 0)))
  }
  walk(pir, 0)
  return notes.sort((a, b) => a.line - b.line)
}

export function dumpStages(src: string, filename = '<input>'): StageDump {
  void filename
  const { ast, diagnostics, tokens } = parse(src)
  if (!ast) return { ok: false, diagnostics, tokens, ast: null, typed_ast: null, pir: null, cpp: '', fidelity: [] }
  const tc = typecheck(ast)
  if (tc.diagnostics.length) return { ok: false, diagnostics: tc.diagnostics, tokens, ast, typed_ast: tc.ast, pir: null, cpp: '', fidelity: [] }
  const { pir, elided, kept } = lower(tc.ast)
  const { cpp, line_map } = emitCpp(pir)
  const fid = fidelityNotes(pir)
  void line_map
  return { ok: true, diagnostics: [], tokens, ast, typed_ast: tc.ast, pir, cpp, fidelity: fid, guard_elision: { elided, kept } }
}

export function compileForPlayground(src: string) {
  const { ast, diagnostics } = parse(src)
  if (!ast) return { ok: false, cpp: '', diagnostics, fidelity: [] as FidelityNote[], cpp_line_map: {} as Record<string, number[]> }
  const tc = typecheck(ast)
  if (tc.diagnostics.length) return { ok: false, cpp: '', diagnostics: tc.diagnostics, fidelity: [], cpp_line_map: {} }
  const { pir } = lower(tc.ast)
  const { cpp, line_map } = emitCpp(pir)
  return { ok: true, cpp, diagnostics: [], fidelity: fidelityNotes(pir), cpp_line_map: line_map }
}

// ---------------- tiny interpreter (mock playground run) ----------------
type V = number | string | boolean | null | V[] | Map<V, V>
class ReturnSig { constructor(public v: V) {} }
class BreakSig {}
class ContinueSig {}
const py = (v: V): string => {
  if (v === null) return 'None'
  if (typeof v === 'boolean') return v ? 'True' : 'False'
  if (typeof v === 'string') return v
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : String(parseFloat(v.toPrecision(15)))
  if (Array.isArray(v)) return '[' + v.map(repr).join(', ') + ']'
  return '{' + [...v.entries()].map(([k, x]) => `${repr(k)}: ${repr(x)}`).join(', ') + '}'
}
const repr = (v: V): string => (typeof v === 'string' ? `'${v}'` : py(v))
const isFloatNode = (n: N) => n.ty === 'float'

export function interpret(src: string, maxSteps = 4_000_000): { stdout: string; exception: string | null; steps: number } {
  const { ast } = parse(src)
  if (!ast) return { stdout: '', exception: 'SyntaxError', steps: 0 }
  const tc = typecheck(ast)
  const root = tc.ast
  const funcs: Record<string, N> = {}
  for (const f of kidsOf(root, 'body')) if (f.t === 'FunctionDef') funcs[String(f.attrs?.name)] = f
  let out = ''
  let steps = 0
  const tick = () => { if (++steps > maxSteps) throw new Error('TimeoutError') }
  const floordiv = (a: number, b: number) => { if (b === 0) throw new Error('ZeroDivisionError'); return Math.floor(a / b) }
  const ev = (n: N, env: Map<string, V>): V => {
    tick()
    switch (n.t) {
      case 'Constant': { const k = n.attrs?.kind; const v = String(n.attrs?.value); if (k === 'str') return v.slice(1, -1); if (k === 'bool') return v === 'True'; if (k === 'None') return null; return Number(v.replace(/_/g, '')) }
      case 'Name': { const id = String(n.attrs?.id); if (!env.has(id)) throw new Error('NameError'); return env.get(id)! }
      case 'UnaryOp': { const v = ev(kid(n, 'operand')!, env); return n.attrs?.op === 'not' ? !v : n.attrs?.op === '-' ? -(v as number) : v }
      case 'BoolOp': { const vs = kidsOf(n, 'values'); let r: V = ev(vs[0], env); for (let i = 1; i < vs.length; i++) { if (n.attrs?.op === 'and' ? !r : !!r) return r; r = ev(vs[i], env) } return r }
      case 'IfExp': return ev(kid(n, 'test')!, env) ? ev(kid(n, 'body')!, env) : ev(kid(n, 'orelse')!, env)
      case 'BinOp': {
        const a = ev(kid(n, 'left')!, env), b = ev(kid(n, 'right')!, env); const op = String(n.attrs?.op)
        if (typeof a === 'string' && typeof b === 'string') return a + b
        if (typeof a === 'string' && typeof b === 'number') return a.repeat(b)
        if (Array.isArray(a) && Array.isArray(b)) return [...a, ...b]
        const x = Number(a), y = Number(b)
        switch (op) {
          case '+': return x + y; case '-': return x - y; case '*': return x * y
          case '/': if (y === 0) throw new Error('ZeroDivisionError'); return x / y
          case '//': return floordiv(x, y)
          case '%': if (y === 0) throw new Error('ZeroDivisionError'); return ((x % y) + y) % y
          case '**': return Math.pow(x, y)
          case '&': return x & y; case '|': return x | y; case '^': return x ^ y; case '<<': return x << y; case '>>': return x >> y
        }
        return 0
      }
      case 'Compare': {
        let l = ev(kid(n, 'left')!, env); const ops = n.attrs?.ops as string[]
        for (let i = 0; i < ops.length; i++) {
          const r = ev(kidsOf(n, 'comparators')[i], env); const op = ops[i]
          const ok = op === '<' ? (l as number) < (r as number) : op === '>' ? (l as number) > (r as number) : op === '<=' ? (l as number) <= (r as number) : op === '>=' ? (l as number) >= (r as number)
            : op === '==' || op === 'is' ? l === r : op === '!=' || op === 'is not' ? l !== r : op === 'in' ? (Array.isArray(r) ? r.includes(l) : String(r).includes(String(l))) : !(Array.isArray(r) ? r.includes(l) : String(r).includes(String(l)))
          if (!ok) return false
          l = r
        }
        return true
      }
      case 'List': return kidsOf(n, 'elts').map((e) => ev(e, env))
      case 'Tuple': return kidsOf(n, 'elts').map((e) => ev(e, env))
      case 'Dict': { const m = new Map<V, V>(); kidsOf(n, 'keys').forEach((k, i) => m.set(ev(k, env), ev(kidsOf(n, 'values')[i], env))); return m }
      case 'Subscript': {
        const v = ev(kid(n, 'value')!, env); const idx = kid(n, 'index')!
        if (idx.t === 'Slice') { const lo = Number(ev(kid(idx, 'lower')!, env)); const up = kid(idx, 'upper'); const hi = up ? Number(ev(up, env)) : undefined; return typeof v === 'string' ? v.slice(lo, hi) : (v as V[]).slice(lo, hi) }
        const i = ev(idx, env)
        if (v instanceof Map) { if (!v.has(i)) throw new Error('KeyError'); return v.get(i)! }
        const arr = v as string | V[]; const k = (i as number) < 0 ? arr.length + (i as number) : (i as number)
        if (k < 0 || k >= arr.length) throw new Error('IndexError')
        return typeof arr === 'string' ? arr[k] : arr[k]
      }
      case 'Call': {
        const f = kid(n, 'func')!; const args = kidsOf(n, 'args').map((a) => ev(a, env))
        if (f.t === 'Attribute') {
          const base = ev(kid(f, 'value')!, env); const at = String(f.attrs?.attr)
          if (Array.isArray(base) && at === 'append') { base.push(args[0]); return null }
          if (Array.isArray(base) && at === 'pop') return base.pop() ?? null
          if (typeof base === 'string' && at === 'upper') return base.toUpperCase()
          if (typeof base === 'string' && at === 'lower') return base.toLowerCase()
          throw new Error('AttributeError')
        }
        const nm = String(f.attrs?.id)
        if (nm === 'print') { out += args.map(py).join(' ') + '\n'; return null }
        if (nm === 'len') return typeof args[0] === 'string' ? args[0].length : args[0] instanceof Map ? args[0].size : (args[0] as V[]).length
        if (nm === 'range') { const [a, b, c] = args as number[]; const [lo, hi, st] = args.length === 1 ? [0, a, 1] : [a, b, c ?? 1]; const r: V[] = []; for (let i = lo; st > 0 ? i < hi : i > hi; i += st) { r.push(i); tick() } return r }
        if (nm === 'int') return Math.trunc(Number(args[0])); if (nm === 'float') return Number(args[0]); if (nm === 'str') return py(args[0]); if (nm === 'abs') return Math.abs(args[0] as number)
        if (nm === 'min') return Math.min(...((Array.isArray(args[0]) ? args[0] : args) as number[])); if (nm === 'max') return Math.max(...((Array.isArray(args[0]) ? args[0] : args) as number[]))
        if (nm === 'sum') return (args[0] as number[]).reduce((p, c) => p + c, 0); if (nm === 'ord') return (args[0] as string).charCodeAt(0); if (nm === 'chr') return String.fromCharCode(args[0] as number)
        if (nm === 'sqrt') return Math.sqrt(args[0] as number)
        const fd = funcs[nm]
        if (!fd) throw new Error('NameError')
        const e2 = new Map<string, V>()
        kidsOf(fd, 'args').forEach((a, i) => e2.set(String(a.attrs?.name), args[i]))
        try { run(kidsOf(fd, 'body'), e2) } catch (e) { if (e instanceof ReturnSig) return e.v; throw e }
        return null
      }
      default: return null
    }
  }
  const assign = (tg: N, v: V, env: Map<string, V>) => {
    if (tg.t === 'Name') env.set(String(tg.attrs?.id), v)
    else if (tg.t === 'Tuple') kidsOf(tg, 'elts').forEach((e, i) => assign(e, (v as V[])[i], env))
    else if (tg.t === 'Subscript') {
      const c = ev(kid(tg, 'value')!, env); const i = ev(kid(tg, 'index')!, env)
      if (c instanceof Map) c.set(i, v)
      else { const a = c as V[]; const k = (i as number) < 0 ? a.length + (i as number) : (i as number); if (k < 0 || k >= a.length) throw new Error('IndexError'); a[k] = v }
    }
  }
  const run = (body: N[], env: Map<string, V>) => {
    for (const s of body) {
      tick()
      switch (s.t) {
        case 'Assign': { const v = ev(kid(s, 'value')!, env); kidsOf(s, 'targets').forEach((t) => assign(t, v, env)); break }
        case 'AnnAssign': { const v = kid(s, 'value'); if (v) assign(kid(s, 'target')!, ev(v, env), env); break }
        case 'AugAssign': {
          const tg = kid(s, 'target')!; const cur = ev(tg, env); const b = ev(kid(s, 'value')!, env); const op = String(s.attrs?.op)
          let r: V
          if (typeof cur === 'string') r = (cur as string) + String(b)
          else { const x = cur as number, y = b as number; r = op === '+' ? x + y : op === '-' ? x - y : op === '*' ? x * y : op === '//' ? floordiv(x, y) : op === '%' ? ((x % y) + y) % y : op === '/' ? x / y : x }
          assign(tg, r, env); break
        }
        case 'Return': { const v = kid(s, 'value'); throw new ReturnSig(v ? ev(v, env) : null) }
        case 'Expr': ev(kid(s, 'value')!, env); break
        case 'Pass': break
        case 'Break': throw new BreakSig()
        case 'Continue': throw new ContinueSig()
        case 'If': run(ev(kid(s, 'test')!, env) ? kidsOf(s, 'body') : kidsOf(s, 'orelse'), env); break
        case 'While': { try { while (ev(kid(s, 'test')!, env)) { try { run(kidsOf(s, 'body'), env) } catch (e) { if (!(e instanceof ContinueSig)) throw e } } } catch (e) { if (!(e instanceof BreakSig)) throw e } break }
        case 'For': {
          const it = ev(kid(s, 'iter')!, env); const items = typeof it === 'string' ? it.split('') : it instanceof Map ? [...it.keys()] : (it as V[])
          try { for (const x of items) { assign(kid(s, 'target')!, x, env); try { run(kidsOf(s, 'body'), env) } catch (e) { if (!(e instanceof ContinueSig)) throw e } } } catch (e) { if (!(e instanceof BreakSig)) throw e }
          break
        }
      }
    }
  }
  void isFloatNode
  const g = new Map<string, V>()
  try {
    for (const s of kidsOf(root, 'body')) if (s.t !== 'FunctionDef') run([s], g)
  } catch (e) {
    return { stdout: out, exception: e instanceof Error ? e.message : String(e), steps }
  }
  return { stdout: out, exception: null, steps }
}
