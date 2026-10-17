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
    { token: 'comment', foreground: '5f6778', fontStyle: 'italic' },
    { token: 'keyword', foreground: 'a99fff' },
    { token: 'keyword.flow', foreground: 'a99fff' },
    { token: 'string', foreground: '7ddcae' },
    { token: 'string.escape', foreground: '9ae6c1' },
    { token: 'number', foreground: 'f5c06a' },
    { token: 'type', foreground: '78c8f0' },
    { token: 'type.identifier', foreground: '78c8f0' },
    { token: 'identifier', foreground: 'dfe2ea' },
    { token: 'delimiter', foreground: '7f8798' },
    { token: 'operator', foreground: '9aa3b5' },
    { token: 'predefined', foreground: 'e8a0c4' },
    { token: 'annotation', foreground: 'e8a0c4' },
  ],
  colors: {
    'editor.background': '#07080b',
    'editor.foreground': '#dfe2ea',
    'editorLineNumber.foreground': '#464c5a',
    'editorLineNumber.activeForeground': '#9aa3b5',
    'editor.lineHighlightBackground': '#0e1015',
    'editor.lineHighlightBorder': '#0e1015',
    'editorGutter.background': '#07080b',
    'editor.selectionBackground': '#8178ff40',
    'editor.inactiveSelectionBackground': '#8178ff22',
    'editorWidget.background': '#171a21',
    'editorWidget.border': '#2a2e3a',
    'editorHoverWidget.background': '#171a21',
    'editorHoverWidget.border': '#2a2e3a',
    'editorHoverWidget.statusBarBackground': '#12141a',
    'diffEditor.insertedTextBackground': '#3ecf8e26',
    'diffEditor.insertedLineBackground': '#3ecf8e12',
    'diffEditor.removedTextBackground': '#f2645a2b',
    'diffEditor.removedLineBackground': '#f2645a12',
    'diffEditor.diagonalFill': '#14161c',
    'diffEditor.unchangedRegionBackground': '#0c0e12',
    'diffEditor.unchangedRegionForeground': '#6c7483',
    'scrollbarSlider.background': '#2a2e3a80',
    'scrollbarSlider.hoverBackground': '#3a4050aa',
    'editorOverviewRuler.border': '#07080b',
    'editorIndentGuide.background1': '#161920',
    'editorIndentGuide.activeBackground1': '#2a2e3a',
    'editorError.foreground': '#f2645a',
  },
})
monaco.editor.defineTheme('pythia-light', {
  base: 'vs',
  inherit: true,
  rules: [
    { token: 'comment', foreground: '8b93a3', fontStyle: 'italic' },
    { token: 'keyword', foreground: '5a49e0' },
    { token: 'string', foreground: '0f7f56' },
    { token: 'number', foreground: 'a8620a' },
    { token: 'type', foreground: '1a6e99' },
    { token: 'identifier', foreground: '1c2030' },
    { token: 'delimiter', foreground: '7a8294' },
  ],
  colors: {
    'editor.background': '#f3f4f7',
    'editorGutter.background': '#f3f4f7',
    'editor.lineHighlightBackground': '#eaecf2',
    'editor.lineHighlightBorder': '#eaecf2',
    'editorLineNumber.foreground': '#aab0bd',
    'editorLineNumber.activeForeground': '#5b6273',
    'editor.selectionBackground': '#584bf033',
    'editorWidget.background': '#ffffff',
    'editorWidget.border': '#dfe2ea',
    'editorHoverWidget.background': '#ffffff',
    'editorHoverWidget.border': '#dfe2ea',
    'diffEditor.insertedLineBackground': '#0f8f6016',
    'diffEditor.insertedTextBackground': '#0f8f6022',
    'diffEditor.removedLineBackground': '#cd372e14',
    'diffEditor.removedTextBackground': '#cd372e22',
    'diffEditor.diagonalFill': '#e6e8ee',
    'diffEditor.unchangedRegionBackground': '#ebedf2',
    'editorIndentGuide.background1': '#e3e6ec',
  },
})

export { monaco }
export const monacoTheme = (t: 'dark' | 'light') => (t === 'dark' ? 'pythia-dark' : 'pythia-light')
