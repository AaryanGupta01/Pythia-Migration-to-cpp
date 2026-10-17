import { useEffect, useMemo, useState } from 'react'
import { Command } from 'cmdk'
import { Braces, Check, Download, FileCode2, FileText, Flame, Moon, PanelBottom, PanelRight, Play, Presentation, RotateCcw, Settings, Workflow, X, Zap } from 'lucide-react'
import { useStudio } from './store'
import { exportProject } from './actions'
import { STAGES } from './types'
import { STATUS, basename, cn, fmtX } from './lib/format'
import { Kbd, MOD, SHIFT } from './ui'

interface Cmd {
  id: string
  label: string
  hint?: string
  icon: JSX.Element
  keys?: string
  run: () => void
  group: string
}

export function Palette({ mode, onClose }: { mode: 'commands' | 'files'; onClose: () => void }) {
  const s = useStudio()
  const [q, setQ] = useState('')
  const close = () => {
    setQ('')
    onClose()
  }
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === 'Escape' && close()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const cmds: Cmd[] = useMemo(() => {
    const done = () => close()
    const c: Cmd[] = [
      { group: 'Run', id: 'demo', label: 'Open demo project', icon: <Play size={14} />, run: () => s.startJob({ kind: 'demo' }) },
      { group: 'Run', id: 'rerun', label: 'Run analysis again', icon: <Zap size={14} />, keys: `${MOD}↵`, run: () => window.dispatchEvent(new Event('pythia:rerun')) },
      { group: 'Run', id: 'replay', label: 'Replay the current run', icon: <RotateCcw size={14} />, run: () => s.replayCurrent() },
      { group: 'Run', id: 'presenter', label: s.presenter ? 'Turn presenter mode off' : 'Turn presenter mode on', icon: <Presentation size={14} />, run: () => s.setPresenter(!s.presenter) },
      { group: 'Review', id: 'accept', label: 'Accept all verified functions', icon: <Check size={14} />, keys: `${MOD}${SHIFT}A`, run: () => s.decide('all', 'accepted') },
      { group: 'Review', id: 'reject', label: 'Reject all functions', icon: <X size={14} />, run: () => s.decide('all', 'rejected') },
      { group: 'Review', id: 'export', label: 'Export accelerated project', icon: <Download size={14} />, run: () => exportProject(false) },
      { group: 'Go to', id: 'pg', label: 'Playground', icon: <Braces size={14} />, run: () => s.openSpecial('playground') },
      { group: 'Go to', id: 'rep', label: 'Report', icon: <FileText size={14} />, run: () => s.openSpecial('report') },
      { group: 'Go to', id: 'set', label: 'Settings', icon: <Settings size={14} />, run: () => s.openSpecial('settings') },
      { group: 'Go to', id: 'welcome', label: 'Welcome', icon: <FileCode2 size={14} />, run: () => s.openSpecial('welcome') },
      { group: 'Go to', id: 'hot', label: 'Show hotspots', icon: <Flame size={14} />, run: () => s.set({ sideOpen: true, sideView: 'hotspots' }) },
      { group: 'Go to', id: 'exp', label: 'Show explorer', icon: <FileCode2 size={14} />, run: () => s.set({ sideOpen: true, sideView: 'explorer' }) },
      ...STAGES.map((st) => ({ group: 'Pipeline', id: `st-${st}`, label: `Inspect stage: ${st}`, icon: <Workflow size={14} />, run: () => s.openStage(st) })),
      { group: 'View', id: 'theme', label: `Switch to ${s.theme === 'dark' ? 'light' : 'dark'} theme`, icon: <Moon size={14} />, run: () => s.setTheme(s.theme === 'dark' ? 'light' : 'dark') },
      { group: 'View', id: 'agent', label: 'Toggle agent panel', icon: <PanelRight size={14} />, run: () => s.set({ agentOpen: !s.agentOpen }) },
      { group: 'View', id: 'bottom', label: 'Toggle bottom panel', icon: <PanelBottom size={14} />, run: () => s.set({ bottomOpen: !s.bottomOpen }) },
    ]
    return c.map((x) => ({ ...x, run: () => (x.run(), done()) }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.presenter, s.theme, s.agentOpen, s.bottomOpen, s.js.jobId])

  const fns = useMemo(() => Object.values(s.js.functions), [s.js.functions])
  const files = useMemo(() => [...new Set(fns.map((f) => f.file))].sort(), [fns])

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-black/45 pt-[14vh]" onMouseDown={close} role="dialog" aria-modal aria-label={mode === 'files' ? 'Quick open' : 'Command palette'}>
      <div className="w-[600px] max-w-[92vw] animate-fadeIn overflow-hidden rounded-xl border border-line2 bg-panel shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <Command loop label={mode === 'files' ? 'Quick open' : 'Command palette'}>
          <Command.Input
            autoFocus
            value={q}
            onValueChange={setQ}
            placeholder={mode === 'files' ? 'Go to file or function' : 'Type a command, function or file'}
            className="h-11 w-full border-b border-line bg-transparent px-4 text-base text-fg outline-none placeholder:text-fg3"
          />
          <Command.List className="max-h-[360px] overflow-auto p-1.5">
            <Command.Empty className="px-4 py-6 text-center text-sm text-fg3">Nothing matches “{q}”.</Command.Empty>
            {mode === 'commands' &&
              ['Run', 'Review', 'Go to', 'Pipeline', 'View'].map((g) => (
                <Command.Group key={g} heading={g}>
                  {cmds.filter((c) => c.group === g).map((c) => (
                    <Command.Item key={c.id} value={`${g} ${c.label}`} onSelect={c.run}>
                      <span className="text-fg3">{c.icon}</span>
                      <span className="flex-1 text-sm">{c.label}</span>
                      {c.keys && <Kbd>{c.keys}</Kbd>}
                    </Command.Item>
                  ))}
                </Command.Group>
              ))}
            {files.length > 0 && (
              <Command.Group heading="Files">
                {files.map((f) => (
                  <Command.Item key={f} value={`file ${f}`} onSelect={() => (s.openFile(f), close())}>
                    <FileCode2 size={14} className="text-fg3" />
                    <span className="flex-1 truncate text-sm">{basename(f)}</span>
                    <span className="mono truncate text-xs text-fg3">{f}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            )}
            {fns.length > 0 && (
              <Command.Group heading="Functions">
                {fns.map((f) => (
                  <Command.Item key={f.id} value={`fn ${f.name} ${f.file} ${f.status}`} onSelect={() => (s.openFunction(f.id), close())}>
                    <span className={cn('h-2 w-2 flex-none rounded-full', STATUS[f.status].dot)} />
                    <span className="mono flex-1 truncate text-sm">{f.name}</span>
                    <span className="mono truncate text-xs text-fg3">{basename(f.file)}</span>
                    <span className="tnum w-12 text-right text-xs text-ok">{f.speedup ? fmtX(f.speedup) : ''}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            )}
          </Command.List>
        </Command>
      </div>
    </div>
  )
}
