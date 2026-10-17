import { useEffect, useMemo, useRef } from 'react'
import Editor, { DiffEditor, type OnMount } from '@monaco-editor/react'
import { monaco, monacoTheme } from './lib/monaco'
import { useStudio } from './store'
import { Skeleton } from './ui'
import type { Diagnostic, FidelityNote, FunctionRecord, Severity } from './types'

export interface LineNote {
  line: number
  severity: Severity
  cls: string
  detail: string
  mitigation: string
}
const SEV_ORDER: Record<Severity, number> = { exact: 0, guarded: 1, divergent: 2 }
const SEV_LABEL: Record<Severity, string> = { exact: 'exact', guarded: 'guarded', divergent: 'divergent' }

function md(notes: LineNote[]) {
  return notes
    .map((n) => `**${n.cls}** · _${SEV_LABEL[n.severity]}_\n\n${n.detail}\n\n**Mitigation:** ${n.mitigation}`)
    .join('\n\n---\n\n')
}

/** pysub-relative notes -> notes on the Python/PySub view lines (function-only text). */
export const pyNotes = (fid: FidelityNote[], offset = 0): LineNote[] =>
  fid.map((f) => ({ line: f.line + offset, severity: f.severity, cls: f.cls, detail: f.detail, mitigation: f.mitigation }))

/** map notes onto C++ lines using cpp_line_map (pysub line -> cpp lines). */
export function cppNotes(rec: Pick<FunctionRecord, 'fidelity' | 'cpp_line_map'>): LineNote[] {
  const out: LineNote[] = []
  for (const f of rec.fidelity) {
    const lines = rec.cpp_line_map[String(f.line)] ?? []
    for (const l of lines) out.push({ line: l, severity: f.severity, cls: f.cls, detail: f.detail, mitigation: f.mitigation })
  }
  return out
}

function decorations(notes: LineNote[]): monaco.editor.IModelDeltaDecoration[] {
  const by = new Map<number, LineNote[]>()
  for (const n of notes) by.set(n.line, [...(by.get(n.line) ?? []), n])
  return [...by.entries()].map(([line, ns]) => {
    const worst = ns.reduce((a, b) => (SEV_ORDER[b.severity] > SEV_ORDER[a.severity] ? b : a)).severity
    return {
      range: new monaco.Range(line, 1, line, 1),
      options: {
        isWholeLine: true,
        linesDecorationsClassName: `fid-${worst}`,
        className: worst === 'exact' ? undefined : `fid-line-${worst}`,
        hoverMessage: { value: md(ns) },
      },
    }
  })
}

export const EDITOR_OPTS: monaco.editor.IStandaloneEditorConstructionOptions = {
  readOnly: true,
  minimap: { enabled: false },
  fontFamily: "'JetBrains Mono Variable', 'JetBrains Mono', ui-monospace, monospace",
  fontLigatures: true,
  fontSize: 12.5,
  lineHeight: 19,
  scrollBeyondLastLine: false,
  automaticLayout: true,
  renderLineHighlight: 'none',
  overviewRulerLanes: 0,
  hideCursorInOverviewRuler: true,
  folding: false,
  glyphMargin: false,
  lineDecorationsWidth: 10,
  lineNumbersMinChars: 3,
  padding: { top: 8, bottom: 8 },
  scrollbar: { verticalScrollbarSize: 10, horizontalScrollbarSize: 10, useShadows: false },
  smoothScrolling: true,
  renderWhitespace: 'none',
  guides: { indentation: true },
  contextmenu: false,
  occurrencesHighlight: 'off',
  selectionHighlight: false,
  fixedOverflowWidgets: true,
}

const Loading = () => (
  <div className="space-y-2 p-4" aria-busy>
    <Skeleton className="h-3.5 w-2/5" />
    <Skeleton className="h-3.5 w-3/5" />
    <Skeleton className="h-3.5 w-1/3" />
    <Skeleton className="h-3.5 w-1/2" />
  </div>
)

export interface CodeViewProps {
  value: string
  language?: 'python' | 'cpp' | 'plaintext'
  path?: string
  notes?: LineNote[]
  /** extra highlighted lines (sync with other panes) */
  syncLines?: number[]
  markers?: Diagnostic[]
  readOnly?: boolean
  onChange?: (v: string) => void
  onLineClick?: (line: number) => void
  revealLine?: number
  className?: string
  lineNumbersStart?: number
}

export function CodeView({ value, language = 'python', path, notes = [], syncLines = [], markers = [], readOnly = true, onChange, onLineClick, revealLine, className, lineNumbersStart }: CodeViewProps) {
  const theme = useStudio((s) => s.theme)
  const edRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null)
  const decoRef = useRef<monaco.editor.IEditorDecorationsCollection | null>(null)
  const clickRef = useRef(onLineClick)
  clickRef.current = onLineClick

  const deco = useMemo(
    () => [
      ...decorations(notes),
      ...syncLines.map((l) => ({ range: new monaco.Range(l, 1, l, 1), options: { isWholeLine: true, className: 'sync-line' } })),
    ],
    [notes, syncLines],
  )

  const apply = () => {
    const ed = edRef.current
    if (!ed) return
    decoRef.current?.clear()
    decoRef.current = ed.createDecorationsCollection(deco)
    const model = ed.getModel()
    if (model) {
      monaco.editor.setModelMarkers(
        model,
        'pythia',
        markers.map((d) => ({
          severity: monaco.MarkerSeverity.Error,
          message: `${d.kind}: ${d.msg}`,
          startLineNumber: Math.max(1, d.line),
          startColumn: Math.max(1, d.col || 1),
          endLineNumber: Math.max(1, d.line),
          endColumn: Math.max(2, (model.getLineMaxColumn(Math.max(1, Math.min(d.line, model.getLineCount()))) ?? 2)),
        })),
      )
    }
  }
  useEffect(apply, [deco, markers, value])
  useEffect(() => {
    if (revealLine && edRef.current) edRef.current.revealLineInCenterIfOutsideViewport(revealLine)
  }, [revealLine, value])

  const onMount: OnMount = (ed) => {
    edRef.current = ed
    ed.onMouseDown((e) => {
      const l = e.target.position?.lineNumber
      if (l) clickRef.current?.(l)
    })
    apply()
    if (revealLine) ed.revealLineInCenter(revealLine)
  }

  return (
    <div className={className ?? 'h-full w-full'}>
      <Editor
        value={value}
        language={language}
        path={path}
        theme={monacoTheme(theme)}
        loading={<Loading />}
        onMount={onMount}
        onChange={(v) => onChange?.(v ?? '')}
        options={{ ...EDITOR_OPTS, readOnly, domReadOnly: readOnly, lineNumbers: lineNumbersStart ? (n) => String(n + lineNumbersStart - 1) : 'on', renderLineHighlight: readOnly ? 'none' : 'line' }}
      />
    </div>
  )
}

export interface DiffViewProps {
  original: string
  modified: string
  language?: 'python' | 'cpp' | 'plaintext'
  originalNotes?: LineNote[]
  modifiedNotes?: LineNote[]
  revealLine?: number
  sideBySide?: boolean
  hideUnchanged?: boolean
  path?: string
}

export function DiffView({ original, modified, language = 'python', originalNotes = [], modifiedNotes = [], revealLine, sideBySide = true, hideUnchanged = true, path }: DiffViewProps) {
  const theme = useStudio((s) => s.theme)
  const ref = useRef<monaco.editor.IStandaloneDiffEditor | null>(null)
  const colls = useRef<monaco.editor.IEditorDecorationsCollection[]>([])

  const apply = () => {
    const d = ref.current
    if (!d) return
    colls.current.forEach((c) => c.clear())
    colls.current = [d.getOriginalEditor().createDecorationsCollection(decorations(originalNotes)), d.getModifiedEditor().createDecorationsCollection(decorations(modifiedNotes))]
  }
  useEffect(apply, [originalNotes, modifiedNotes, original, modified])

  return (
    <DiffEditor
      original={original}
      modified={modified}
      language={language}
      originalModelPath={path ? `orig:${path}` : undefined}
      modifiedModelPath={path ? `mod:${path}` : undefined}
      theme={monacoTheme(theme)}
      loading={<Loading />}
      keepCurrentOriginalModel
      keepCurrentModifiedModel
      onMount={(d) => {
        ref.current = d
        apply()
        if (revealLine) setTimeout(() => d.getModifiedEditor().revealLineInCenter(revealLine), 80)
      }}
      options={{
        ...EDITOR_OPTS,
        renderSideBySide: sideBySide,
        originalEditable: false,
        enableSplitViewResizing: true,
        renderOverviewRuler: false,
        hideUnchangedRegions: { enabled: hideUnchanged, contextLineCount: 4, minimumLineCount: 4, revealLineCount: 20 },
        glyphMargin: false,
        diffAlgorithm: 'advanced',
        useInlineViewWhenSpaceIsLimited: false,
      }}
    />
  )
}
