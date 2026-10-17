import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import type { Status } from './types'
import { STATUS, cn } from './lib/format'

export function StatusChip({ status, className, dense }: { status: Status; className?: string; dense?: boolean }) {
  const m = STATUS[status]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border whitespace-nowrap font-medium leading-none',
        dense ? 'px-1.5 py-[3px] text-2xs' : 'px-2 py-1 text-xs',
        m.bg,
        m.text,
        className,
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', m.dot)} />
      {m.label}
    </span>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex items-center rounded border border-line2 bg-raised px-1.5 py-px font-sans text-2xs text-fg2 leading-4">
      {children}
    </kbd>
  )
}

export const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)
export const MOD = isMac ? '⌘' : 'Ctrl+'
export const SHIFT = isMac ? '⇧' : 'Shift+'

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('skeleton', className)} aria-hidden />
}

export function SkeletonLines({ n = 5, className }: { n?: number; className?: string }) {
  return (
    <div className={cn('space-y-2', className)} aria-busy="true" aria-label="Loading">
      {Array.from({ length: n }, (_, i) => (
        <Skeleton key={i} className="h-3.5" />
      ))}
    </div>
  )
}

export function IconBtn({
  title,
  onClick,
  children,
  active,
  className,
  disabled,
}: {
  title: string
  onClick?: () => void
  children: ReactNode
  active?: boolean
  className?: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'inline-flex h-6 w-6 items-center justify-center rounded text-fg2 transition-colors hover:bg-hover hover:text-fg disabled:opacity-40 disabled:pointer-events-none',
        active && 'bg-hover text-fg',
        className,
      )}
    >
      {children}
    </button>
  )
}

export function Btn({
  children,
  onClick,
  kind = 'default',
  className,
  disabled,
  title,
  type = 'button',
}: {
  children: ReactNode
  onClick?: () => void
  kind?: 'default' | 'primary' | 'ok' | 'danger' | 'ghost'
  className?: string
  disabled?: boolean
  title?: string
  type?: 'button' | 'submit'
}) {
  const styles = {
    default: 'border-line2 bg-raised text-fg hover:bg-hover',
    primary: 'border-accent bg-accent text-[rgb(11,12,14)] hover:brightness-110 font-medium',
    ok: 'border-ok/40 bg-ok/10 text-ok hover:bg-ok/20',
    danger: 'border-bad/40 bg-bad/10 text-bad hover:bg-bad/20',
    ghost: 'border-transparent text-fg2 hover:bg-hover hover:text-fg',
  }[kind]
  return (
    <button
      type={type}
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'inline-flex h-7 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border px-2.5 text-sm transition-[background,filter] disabled:pointer-events-none disabled:opacity-40',
        styles,
        className,
      )}
    >
      {children}
    </button>
  )
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  className,
}: {
  value: T
  onChange: (v: T) => void
  options: { value: T; label: ReactNode; title?: string }[]
  className?: string
}) {
  return (
    <div role="tablist" className={cn('inline-flex rounded-md border border-line2 bg-bg p-0.5', className)}>
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          title={o.title}
          onClick={() => onChange(o.value)}
          className={cn(
            'rounded px-2.5 py-0.5 text-sm transition-colors',
            value === o.value ? 'bg-hover text-fg' : 'text-fg3 hover:text-fg2',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Bar({ value, max = 1, className, color = 'bg-accent' }: { value: number; max?: number; className?: string; color?: string }) {
  const w = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className={cn('h-1.5 w-full overflow-hidden rounded-full bg-hover', className)}>
      <div className={cn('h-full rounded-full', color)} style={{ width: `${w}%`, transition: 'width 300ms ease-out' }} />
    </div>
  )
}

export function Empty({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex h-full min-h-[120px] flex-col items-center justify-center gap-1.5 px-6 py-8 text-center">
      {icon && <div className="mb-1 text-fg3">{icon}</div>}
      <div className="text-base text-fg">{title}</div>
      {children && <div className="max-w-sm text-sm text-fg3">{children}</div>}
    </div>
  )
}

export function PanelTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex h-9 flex-none items-center justify-between border-b border-line px-3">
      <div className="text-xs font-medium text-fg2">{children}</div>
      <div className="flex items-center gap-1">{right}</div>
    </div>
  )
}

export function Dot({ state }: { state: 'idle' | 'running' | 'done' | 'failed' | 'skipped' | 'pending' }) {
  const cls =
    state === 'done'
      ? 'bg-ok'
      : state === 'failed'
        ? 'bg-bad'
        : state === 'running'
          ? 'bg-accent animate-pulseDot'
          : 'bg-line2'
  return <span className={cn('inline-block h-2 w-2 flex-none rounded-full', cls)} />
}

/** Draggable splitter. `dir`: 'h' resizes widths, 'v' heights. onDrag receives pixel delta. */
export function Splitter({ dir, onDrag, onDone }: { dir: 'h' | 'v'; onDrag: (delta: number) => void; onDone?: () => void }) {
  const [active, setActive] = useState(false)
  const start = useRef(0)
  const down = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault()
      ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
      start.current = dir === 'h' ? e.clientX : e.clientY
      setActive(true)
    },
    [dir],
  )
  const move = useCallback(
    (e: React.PointerEvent) => {
      if (!active) return
      const cur = dir === 'h' ? e.clientX : e.clientY
      onDrag(cur - start.current)
      start.current = cur
    },
    [active, dir, onDrag],
  )
  return (
    <div
      role="separator"
      aria-orientation={dir === 'h' ? 'vertical' : 'horizontal'}
      className={cn(dir === 'h' ? 'hsplit' : 'vsplit', active && 'splitting')}
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={() => {
        setActive(false)
        onDone?.()
      }}
    />
  )
}

export function useDebounced<T>(v: T, ms: number) {
  const [d, setD] = useState(v)
  useEffect(() => {
    const t = setTimeout(() => setD(v), ms)
    return () => clearTimeout(t)
  }, [v, ms])
  return d
}

export function Spark({ values, className, color = 'rgb(var(--accent))' }: { values: number[]; className?: string; color?: string }) {
  if (values.length < 2) return <svg className={className} />
  const max = Math.max(...values, 1)
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 100},${100 - (v / max) * 90 - 5}`).join(' ')
  return (
    <svg className={className} viewBox="0 0 100 100" preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

export function KV({ k, v, mono }: { k: string; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-[3px]">
      <span className="text-fg3">{k}</span>
      <span className={cn('text-right text-fg', mono && 'mono')}>{v}</span>
    </div>
  )
}

export function CodeBlock({ children, className, maxH = 260 }: { children: string; className?: string; maxH?: number }) {
  return (
    <pre className={cn('mono overflow-auto rounded-md border border-line bg-bg p-3 leading-5 text-fg2', className)} style={{ maxHeight: maxH }}>
      {children}
    </pre>
  )
}
