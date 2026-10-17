import { useMemo, useState, type ReactNode } from 'react'
import { cn, fmtMs, fmtPct, fmtX } from './lib/format'
import type { E2E } from './reducer'

export interface BenchRow {
  id: string
  name: string
  py_ms: number
  cpp_ms: number
  speedup: number
  probe?: boolean
}

/** Pointer-following tooltip used by the charts. */
function useTip() {
  const [tip, setTip] = useState<{ x: number; y: number; body: ReactNode } | null>(null)
  const bind = (body: ReactNode) => ({
    onPointerMove: (e: React.PointerEvent) => setTip({ x: e.clientX, y: e.clientY, body }),
    onPointerLeave: () => setTip(null),
  })
  const el = tip && (
    <div className="surface-2 pointer-events-none fixed z-[80] max-w-[280px] rounded-lg px-3 py-2 text-xs" style={{ left: Math.min(tip.x + 14, window.innerWidth - 300), top: tip.y + 14 }}>
      {tip.body}
    </div>
  )
  return { bind, el }
}

/**
 * Dumbbell chart on a log10 axis: a hollow dot for CPython, a filled dot for C++, joined by a line.
 * The distance between the dots is the speedup; probes (slower than Python) are drawn in red.
 */
export function BenchChart({ rows, onPick, compact }: { rows: BenchRow[]; onPick?: (id: string) => void; compact?: boolean }) {
  const { bind, el: tip } = useTip()
  const { lo, hi, ticks } = useMemo(() => {
    const vals = rows.flatMap((r) => [r.py_ms, r.cpp_ms]).filter((v) => v > 0)
    if (!vals.length) return { lo: -1, hi: 2, ticks: [-1, 0, 1, 2] }
    const lo = Math.floor(Math.log10(Math.min(...vals)))
    const hi = Math.max(Math.ceil(Math.log10(Math.max(...vals))), lo + 1)
    const ticks: number[] = []
    for (let t = lo; t <= hi; t++) ticks.push(t)
    return { lo, hi, ticks }
  }, [rows])
  const pos = (v: number) => Math.max(0, Math.min(100, ((Math.log10(Math.max(v, 1e-6)) - lo) / (hi - lo)) * 100))
  const tickLabel = (t: number) => (t >= 3 ? `${10 ** (t - 3)} s` : t >= 0 ? `${10 ** t} ms` : `${(10 ** t).toFixed(-t)} ms`)
  const every = ticks.length > 6 ? 2 : 1
  const rowH = compact ? 24 : 28
  if (!rows.length) return null
  return (
    <div role="img" aria-label="CPython versus C++ time per function on a log scale" className="select-none">
      <div className="mb-2 flex items-center gap-5 pl-[148px] pr-[72px] text-2xs text-fg3">
        <span className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-full border-2 border-fg3 bg-transparent" /> CPython</span>
        <span className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-full bg-accent shadow-[0_0_8px_rgb(var(--accent)/0.7)]" /> C++</span>
        <span className="ml-auto whitespace-nowrap">log scale</span>
      </div>
      <div className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-[148px] right-[72px]">
          {ticks.map((t) => (
            <div key={t} className="absolute inset-y-0 border-l border-dashed border-line" style={{ left: `${((t - lo) / (hi - lo)) * 100}%` }} />
          ))}
        </div>
        <ul>
          {rows.map((r) => {
            const a = pos(r.py_ms)
            const b = pos(r.cpp_ms)
            const left = Math.min(a, b)
            const w = Math.abs(a - b)
            return (
              <li key={r.id}>
                <button
                  onClick={() => onPick?.(r.id)}
                  {...bind(
                    <div className="space-y-0.5">
                      <div className="mono font-medium text-fg">{r.name}</div>
                      <div className="flex justify-between gap-6"><span className="text-fg3">CPython</span><span className="tnum">{fmtMs(r.py_ms)}</span></div>
                      <div className="flex justify-between gap-6"><span className="text-fg3">C++</span><span className="tnum">{fmtMs(r.cpp_ms)}</span></div>
                      <div className="flex justify-between gap-6"><span className="text-fg3">{r.probe ? 'Probe (not spliced)' : 'Speedup'}</span><span className={cn('tnum font-medium', r.speedup >= 1 ? 'text-ok' : 'text-bad')}>{fmtX(r.speedup)}</span></div>
                    </div>,
                  )}
                  className="group flex w-full items-center rounded-md text-left transition-colors hover:bg-hover/60"
                  style={{ height: rowH }}
                >
                  <span className="mono w-[148px] flex-none truncate pr-3 text-right text-xs text-fg2 group-hover:text-fg">{r.name}</span>
                  <span className="relative h-full flex-1">
                    <span className="absolute top-1/2 h-[2px] -translate-y-1/2 rounded-full" style={{ left: `${left}%`, width: `${w}%`, background: r.probe ? 'linear-gradient(90deg, rgb(var(--bad)), rgb(var(--fg3)))' : 'linear-gradient(90deg, rgb(var(--accent)), rgb(var(--fg3) / 0.6))' }} />
                    <span className="absolute top-1/2 h-[10px] w-[10px] -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-fg3 bg-bg" style={{ left: `${a}%` }} />
                    <span className={cn('absolute top-1/2 h-[10px] w-[10px] -translate-x-1/2 -translate-y-1/2 rounded-full', r.probe ? 'bg-bad shadow-[0_0_8px_rgb(var(--bad)/0.7)]' : 'bg-accent shadow-[0_0_8px_rgb(var(--accent)/0.7)]')} style={{ left: `${b}%` }} />
                  </span>
                  <span className={cn('tnum w-[72px] flex-none pl-3 text-right text-sm font-semibold', r.speedup >= 1 ? 'text-ok' : 'text-bad')}>{fmtX(r.speedup)}</span>
                </button>
              </li>
            )
          })}
        </ul>
        <div className="relative ml-[148px] mr-[72px] mt-1 h-4 border-t border-line">
          {ticks.map((t, i) => (
            i % every === 0 && (
              <span key={t} className="tnum absolute top-1 -translate-x-1/2 whitespace-nowrap text-2xs text-fg3" style={{ left: `${((t - lo) / (hi - lo)) * 100}%` }}>
                {tickLabel(t)}
              </span>
            )
          ))}
        </div>
      </div>
      {tip}
    </div>
  )
}

/** Headline end-to-end card: big number, before/after bars, output check. */
export function E2EBars({ e2e }: { e2e: E2E }) {
  const max = Math.max(e2e.before_s, e2e.after_s)
  return (
    <div role="img" aria-label={`End to end ${e2e.before_s} seconds before, ${e2e.after_s} seconds after`}>
      <div className="mb-4 flex items-end justify-between">
        <div>
          <div className="text-xs text-fg3">Whole program</div>
          <div className="tnum text-[40px] font-semibold leading-[44px] tracking-tight text-grad">{fmtX(e2e.speedup)}</div>
        </div>
        <span className={cn('mb-1.5 rounded-full border px-2.5 py-1 text-xs', e2e.output_match ? 'border-ok/30 bg-ok/10 text-ok' : 'border-bad/30 bg-bad/10 text-bad')}>
          {e2e.output_match ? 'Output identical' : 'Output differs'}
        </span>
      </div>
      <div className="space-y-2.5">
        <div className="flex items-center gap-3">
          <span className="w-12 flex-none text-xs text-fg3">Before</span>
          <div className="h-6 flex-1 overflow-hidden rounded-md bg-hover">
            <div className="h-full rounded-md bg-fg3/45" style={{ width: `${(e2e.before_s / max) * 100}%` }} />
          </div>
          <span className="tnum w-14 flex-none text-right text-sm">{e2e.before_s.toFixed(1)} s</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="w-12 flex-none text-xs text-fg3">After</span>
          <div className="h-6 flex-1 overflow-hidden rounded-md bg-hover">
            <div className="accent-grad h-full rounded-md shadow-[0_0_14px_-2px_rgb(var(--accent)/0.6)]" style={{ width: `${(e2e.after_s / max) * 100}%`, transition: 'width 700ms cubic-bezier(.2,.8,.2,1)' }} />
          </div>
          <span className="tnum w-14 flex-none text-right text-sm font-medium text-ok">{e2e.after_s.toFixed(1)} s</span>
        </div>
      </div>
    </div>
  )
}

/** Sorted horizontal bars used for score breakdowns. */
export function HBars({ rows, fmt, onPick, color = 'accent-grad' }: { rows: { id: string; label: string; value: number; sub?: string }[]; fmt: (v: number) => string; onPick?: (id: string) => void; color?: string }) {
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

// ------------------------------------------------------------------ icicle / flame chart
export interface FlameRow {
  id: string
  name: string
  file: string
  share: number
  calls: number
  cum_s: number
}

/** Icicle chart: program > files > functions. Width is share of traced time (the trace is a flat profile, so no call edges). */
export function FlameChart({ rows, totalS, cmd, onPick }: { rows: FlameRow[]; totalS: number; cmd: string; onPick?: (id: string) => void }) {
  const { bind, el } = useTip()
  const model = useMemo(() => {
    const sum = rows.reduce((a, r) => a + r.share, 0)
    const norm = sum > 1 ? sum : 1
    const files = new Map<string, FlameRow[]>()
    for (const r of rows) files.set(r.file, [...(files.get(r.file) ?? []), r])
    const fl = [...files.entries()]
      .map(([file, fns]) => ({ file, fns: fns.sort((a, b) => b.share - a.share), share: fns.reduce((a, r) => a + r.share, 0) / norm }))
      .sort((a, b) => b.share - a.share)
    return { fl, norm, covered: Math.min(1, sum / norm) }
  }, [rows])
  const maxShare = Math.max(0.001, ...rows.map((r) => r.share))
  return (
    <div className="select-none" role="img" aria-label="Icicle chart of traced time by file and function">
      <div className="flex h-8 items-center overflow-hidden rounded-t-md border border-line bg-hover/60 px-3 text-xs">
        <span className="mono truncate text-fg2">{cmd}</span>
        <span className="tnum ml-auto flex-none pl-3 text-fg3">{totalS.toFixed(1)} s total</span>
      </div>
      <div className="flex h-8 border-x border-line">
        {model.fl.map((f, i) => (
          <div
            key={f.file}
            {...bind(<div><div className="mono font-medium text-fg">{f.file}</div><div className="mt-0.5 text-fg3">{f.fns.length} functions · {fmtPct(f.share)} of traced time</div></div>)}
            className="flex h-full min-w-0 items-center overflow-hidden border-r border-bg bg-accent/15 px-2 text-xs text-fg2"
            style={{ width: `${f.share * 100}%`, opacity: 1 - (i % 2) * 0.12 }}
          >
            <span className="truncate">{f.file.split('/').pop()}</span>
          </div>
        ))}
        {model.covered < 1 && <div className="flex-1 bg-[repeating-linear-gradient(135deg,transparent_0_4px,rgb(var(--line))_4px_5px)]" />}
      </div>
      <div className="flex h-12 overflow-hidden rounded-b-md border border-line">
        {model.fl.flatMap((f) =>
          f.fns.map((r) => (
            <button
              key={r.id}
              onClick={() => onPick?.(r.id)}
              {...bind(
                <div className="space-y-0.5">
                  <div className="mono font-medium text-fg">{r.name}</div>
                  <div className="flex justify-between gap-6"><span className="text-fg3">Time</span><span className="tnum">{r.cum_s.toFixed(2)} s · {fmtPct(r.share)}</span></div>
                  <div className="flex justify-between gap-6"><span className="text-fg3">Calls</span><span className="tnum">{r.calls.toLocaleString('en-US')}</span></div>
                  <div className="text-fg3">{r.file}</div>
                </div>,
              )}
              className="group relative h-full min-w-px overflow-hidden border-r border-bg text-left transition-[filter] hover:brightness-125"
              style={{ width: `${(r.share / model.norm) * 100}%`, background: `rgb(var(--accent) / ${0.28 + 0.62 * (r.share / maxShare)})` }}
            >
              <span className="absolute inset-x-0 top-0 h-px bg-white/20" />
              <span className="mono block truncate px-1.5 pt-1 text-[11px] leading-4 text-fg">{r.share / model.norm > 0.05 ? r.name : ''}</span>
              <span className="tnum block truncate px-1.5 text-[10.5px] text-fg/70">{r.share / model.norm > 0.05 ? fmtPct(r.share) : ''}</span>
            </button>
          )),
        )}
        {model.covered < 1 && <div className="flex-1" />}
      </div>
      <div className="mt-1.5 text-2xs text-fg3">Width is share of traced runtime. Hover for details, click a function to open it.</div>
      {el}
    </div>
  )
}

// ------------------------------------------------------------------ replay matrix
/** One cell per recorded call: green matched, red mismatched (mismatches are grouped at the end). */
export function ReplayMatrix({ total, matched, cell = 7, max = 600, className }: { total: number; matched: number; cell?: number; max?: number; className?: string }) {
  const shown = Math.min(total, max)
  const okN = total <= max ? matched : Math.round((matched / Math.max(1, total)) * shown)
  const cells = useMemo(() => Array.from({ length: shown }, (_, i) => i < okN), [shown, okN])
  return (
    <div className={cn('grid gap-[2px]', className)} style={{ gridTemplateColumns: `repeat(auto-fill, ${cell}px)` }} role="img" aria-label={`${matched} of ${total} recorded calls matched`}>
      {cells.map((ok, i) => (
        <span key={i} className={cn('rounded-[2px]', ok ? 'bg-ok/70' : 'bg-bad')} style={{ width: cell, height: cell, animation: `fadeIn 220ms ${Math.min(i, 240) * 2}ms ease-out both` }} />
      ))}
    </div>
  )
}
