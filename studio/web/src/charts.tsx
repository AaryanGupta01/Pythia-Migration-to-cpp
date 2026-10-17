import { useMemo } from 'react'
import { cn, fmtMs, fmtX } from './lib/format'
import type { E2E } from './reducer'

export interface BenchRow {
  id: string
  name: string
  py_ms: number
  cpp_ms: number
  speedup: number
  probe?: boolean
}

/** Grouped horizontal bars on a log10 axis: Python (muted) vs C++ (accent). */
export function BenchChart({ rows, onPick, compact }: { rows: BenchRow[]; onPick?: (id: string) => void; compact?: boolean }) {
  const { lo, hi, ticks } = useMemo(() => {
    const vals = rows.flatMap((r) => [r.py_ms, r.cpp_ms]).filter((v) => v > 0)
    if (!vals.length) return { lo: -1, hi: 2, ticks: [-1, 0, 1, 2] }
    const lo = Math.floor(Math.log10(Math.min(...vals))) - 0
    const hi = Math.ceil(Math.log10(Math.max(...vals)))
    const ticks: number[] = []
    for (let t = lo; t <= hi; t++) ticks.push(t)
    return { lo, hi: Math.max(hi, lo + 1), ticks }
  }, [rows])
  const pos = (v: number) => Math.max(1.5, ((Math.log10(Math.max(v, 1e-6)) - lo) / (hi - lo)) * 100)
  const tickLabel = (t: number) => (t >= 3 ? `${10 ** (t - 3)} s` : t >= 0 ? `${10 ** t} ms` : `${(10 ** t).toFixed(-t)} ms`)
  const h = compact ? 'h-[7px]' : 'h-2'

  if (!rows.length) return null
  return (
    <div role="img" aria-label="Python versus C++ time per function, log scale" className="select-none">
      <div className="mb-1 flex items-center gap-4 pl-[148px] pr-[84px] text-2xs text-fg3">
        <span className="flex items-center gap-1.5">
          <i className="inline-block h-2 w-3 rounded-sm bg-fg3/60" /> CPython
        </span>
        <span className="flex items-center gap-1.5">
          <i className="inline-block h-2 w-3 rounded-sm bg-accent" /> C++
        </span>
        <span className="ml-auto whitespace-nowrap">log scale</span>
      </div>
      <div className="relative">
        {/* grid */}
        <div className="pointer-events-none absolute inset-y-0 left-[148px] right-[84px]">
          {ticks.map((t) => (
            <div key={t} className="absolute inset-y-0 border-l border-line" style={{ left: `${((t - lo) / (hi - lo)) * 100}%` }}>
              <span className="absolute -top-0 left-1 translate-y-[-100%] whitespace-nowrap text-2xs text-fg3 opacity-0">{tickLabel(t)}</span>
            </div>
          ))}
        </div>
        <ul>
          {rows.map((r) => (
            <li key={r.id}>
              <button
                onClick={() => onPick?.(r.id)}
                className="group flex w-full items-center gap-0 rounded py-[3px] text-left hover:bg-hover/60"
                title={`${r.name}: ${fmtMs(r.py_ms)} → ${fmtMs(r.cpp_ms)}`}
              >
                <span className="mono w-[148px] flex-none truncate pr-3 text-right text-xs text-fg2 group-hover:text-fg">{r.name}</span>
                <span className="relative flex-1 space-y-[3px]">
                  <span className="block">
                    <span className={cn('block rounded-sm bg-fg3/50', h)} style={{ width: `${pos(r.py_ms)}%` }} />
                  </span>
                  <span className="block">
                    <span className={cn('block rounded-sm', h, r.probe ? 'bg-bad/80' : 'bg-accent')} style={{ width: `${pos(r.cpp_ms)}%` }} />
                  </span>
                </span>
                <span className={cn('tnum w-[84px] flex-none pl-3 text-right text-sm font-medium', r.speedup >= 1 ? 'text-ok' : 'text-bad')}>{fmtX(r.speedup)}</span>
              </button>
            </li>
          ))}
        </ul>
        <div className="relative ml-[148px] mr-[84px] mt-1 h-4 border-t border-line">
          {ticks.map((t) => (
            <span key={t} className="tnum absolute top-0.5 -translate-x-1/2 whitespace-nowrap text-2xs text-fg3" style={{ left: `${((t - lo) / (hi - lo)) * 100}%` }}>
              {tickLabel(t)}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

export function E2EBars({ e2e }: { e2e: E2E }) {
  const max = Math.max(e2e.before_s, e2e.after_s)
  return (
    <div className="space-y-2" role="img" aria-label={`End to end ${e2e.before_s} seconds before, ${e2e.after_s} seconds after`}>
      <div className="flex items-center gap-3">
        <span className="w-14 flex-none text-xs text-fg3">Before</span>
        <div className="h-5 flex-1 overflow-hidden rounded bg-hover">
          <div className="h-full rounded bg-fg3/50" style={{ width: `${(e2e.before_s / max) * 100}%` }} />
        </div>
        <span className="tnum w-14 flex-none text-right text-sm">{e2e.before_s.toFixed(1)} s</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="w-14 flex-none text-xs text-fg3">After</span>
        <div className="h-5 flex-1 overflow-hidden rounded bg-hover">
          <div className="h-full rounded bg-accent" style={{ width: `${(e2e.after_s / max) * 100}%`, transition: 'width 500ms ease-out' }} />
        </div>
        <span className="tnum w-14 flex-none text-right text-sm text-ok">{e2e.after_s.toFixed(1)} s</span>
      </div>
      <div className="flex items-center justify-between pl-[68px] text-xs text-fg3">
        <span className="font-medium text-ok">{fmtX(e2e.speedup)} faster end to end</span>
        <span className={e2e.output_match ? 'text-fg3' : 'text-bad'}>{e2e.output_match ? 'program output identical' : 'program output differs'}</span>
      </div>
    </div>
  )
}

/** Sorted horizontal bars used for the trace profile and score breakdowns. */
export function HBars({ rows, fmt, onPick, color = 'bg-accent' }: { rows: { id: string; label: string; value: number; sub?: string }[]; fmt: (v: number) => string; onPick?: (id: string) => void; color?: string }) {
  const max = Math.max(1e-9, ...rows.map((r) => r.value))
  return (
    <ul>
      {rows.map((r) => (
        <li key={r.id}>
          <button onClick={() => onPick?.(r.id)} className="group flex w-full items-center gap-3 rounded py-[3px] text-left hover:bg-hover/60">
            <span className="mono w-40 flex-none truncate text-right text-xs text-fg2 group-hover:text-fg">{r.label}</span>
            <span className="h-3 flex-1 overflow-hidden rounded-sm bg-hover">
              <span className={cn('block h-full rounded-sm', color)} style={{ width: `${Math.max(0.6, (r.value / max) * 100)}%` }} />
            </span>
            <span className="tnum w-16 flex-none text-right text-xs text-fg2">{fmt(r.value)}</span>
            {r.sub && <span className="tnum w-20 flex-none text-right text-xs text-fg3">{r.sub}</span>}
          </button>
        </li>
      ))}
    </ul>
  )
}
