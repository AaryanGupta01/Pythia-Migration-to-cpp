import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { X } from 'lucide-react'
import { useStudio } from './store'
import { Kbd, MOD, SHIFT } from './ui'

const GROUPS: { title: string; rows: [string, string][] }[] = [
  {
    title: 'Navigate',
    rows: [
      [`${MOD}K`, 'Command palette'],
      [`${MOD}P`, 'Quick open a file or function'],
      ['?', 'This sheet'],
      ['Esc', 'Close dialogs and menus'],
    ],
  },
  {
    title: 'Run and review',
    rows: [
      [`${MOD}↵`, 'Run the analysis (Run in the Playground)'],
      [`${MOD}${SHIFT}A`, 'Accept every verified function'],
      ['Right click', 'Hotspot menu: journey, diff, accept, reject'],
    ],
  },
  {
    title: 'Presenter mode',
    rows: [
      ['Space', 'Pause or resume'],
      ['→', 'Step to the next beat'],
    ],
  },
  {
    title: 'Editor',
    rows: [
      ['Double-click a tab', 'Keep a preview tab open'],
      ['Hover a gutter bar', 'Fidelity class, explanation, mitigation'],
      ['Click a PySub line', 'Highlight the C++ it became'],
    ],
  },
]

export function ShortcutsSheet() {
  const open = useStudio((s) => s.shortcutsOpen)
  const set = useStudio((s) => s.set)
  useEffect(() => {
    if (!open) return
    const k = (e: KeyboardEvent) => e.key === 'Escape' && set({ shortcutsOpen: false })
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [open, set])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-[65] flex items-start justify-center bg-black/55 pt-[10vh] backdrop-blur-[2px]" onMouseDown={() => set({ shortcutsOpen: false })} role="dialog" aria-modal aria-label="Keyboard shortcuts">
      <motion.div initial={{ opacity: 0, y: 8, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.16 }} className="surface-2 w-[640px] max-w-[94vw] rounded-[16px]" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h2 className="text-base font-medium">Keyboard shortcuts</h2>
          <button aria-label="Close" onClick={() => set({ shortcutsOpen: false })} className="rounded p-1 text-fg3 hover:bg-hover hover:text-fg">
            <X size={14} />
          </button>
        </div>
        <div className="grid grid-cols-2 gap-x-8 gap-y-5 p-5 max-sm:grid-cols-1">
          {GROUPS.map((g) => (
            <section key={g.title}>
              <h3 className="mb-2 text-xs font-medium text-fg3">{g.title}</h3>
              <ul className="space-y-1.5">
                {g.rows.map(([k, d]) => (
                  <li key={k} className="flex items-center justify-between gap-4 text-sm">
                    <span className="text-fg2">{d}</span>
                    <Kbd>{k}</Kbd>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </motion.div>
    </div>
  )
}
