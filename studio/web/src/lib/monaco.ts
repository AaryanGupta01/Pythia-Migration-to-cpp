// Bundled Monaco (no CDN): core editor + python/cpp tokenizers + a single worker.
import * as monaco from 'monaco-editor/esm/vs/editor/edcore.main'
import 'monaco-editor/esm/vs/basic-languages/python/python.contribution'
import 'monaco-editor/esm/vs/basic-languages/cpp/cpp.contribution'
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import { loader } from '@monaco-editor/react'

;(self as unknown as { MonacoEnvironment: unknown }).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
}

loader.config({ monaco })

monaco.editor.defineTheme('pythia-dark', {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: 'comment', foreground: '6b727d', fontStyle: 'italic' },
    { token: 'keyword', foreground: 'b5a8ff' },
    { token: 'string', foreground: '8fd0a8' },
    { token: 'number', foreground: 'e5b778' },
    { token: 'type', foreground: '7fc4e8' },
    { token: 'identifier', foreground: 'd9dce1' },
    { token: 'delimiter', foreground: '8a919c' },
    { token: 'operator', foreground: '9aa1ac' },
  ],
  colors: {
    'editor.background': '#0b0c0e',
    'editor.foreground': '#d9dce1',
    'editorLineNumber.foreground': '#4b515b',
    'editorLineNumber.activeForeground': '#9aa1ac',
    'editor.lineHighlightBackground': '#14161a',
    'editor.lineHighlightBorder': '#14161a',
    'editorGutter.background': '#0b0c0e',
    'editor.selectionBackground': '#8b85ff40',
    'editorWidget.background': '#15171b',
    'editorWidget.border': '#2e323a',
    'editorHoverWidget.background': '#15171b',
    'editorHoverWidget.border': '#2e323a',
    'diffEditor.insertedTextBackground': '#46b98a24',
    'diffEditor.insertedLineBackground': '#46b98a14',
    'diffEditor.removedTextBackground': '#e5625a28',
    'diffEditor.removedLineBackground': '#e5625a14',
    'diffEditor.diagonalFill': '#1f2228',
    'scrollbarSlider.background': '#2e323a80',
    'editorOverviewRuler.border': '#0b0c0e',
    'editorIndentGuide.background1': '#1a1c21',
    'editorIndentGuide.activeBackground1': '#2e323a',
  },
})
monaco.editor.defineTheme('pythia-light', {
  base: 'vs',
  inherit: true,
  rules: [
    { token: 'comment', foreground: '8a919c', fontStyle: 'italic' },
    { token: 'keyword', foreground: '5a4fe0' },
    { token: 'string', foreground: '1a7f55' },
    { token: 'number', foreground: 'a8620a' },
    { token: 'type', foreground: '1a6e99' },
  ],
  colors: {
    'editor.background': '#fcfcfb',
    'editorGutter.background': '#fcfcfb',
    'editor.lineHighlightBackground': '#f1f1ee',
    'editor.lineHighlightBorder': '#f1f1ee',
    'editorLineNumber.foreground': '#a9aeb7',
    'diffEditor.insertedLineBackground': '#1a8c6218',
    'diffEditor.removedLineBackground': '#c83b3218',
  },
})

export { monaco }
export const monacoTheme = (t: 'dark' | 'light') => (t === 'dark' ? 'pythia-dark' : 'pythia-light')
