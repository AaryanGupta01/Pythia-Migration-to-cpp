import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cn } from './lib/format'

export const reducedMotion = () => typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches

/** Animate a number toward `target` (ease-out). Re-animates from the previous value when target changes. */
export function useCountUp(target: number, ms = 600, decimals = 0, start?: number) {
  const [v, setV] = useState(start ?? target)
  const from = useRef(start ?? target)
  useEffect(() => {
    if (reducedMotion() || from.current === target) {
      setV(target)
      from.current = target
      return
    }
    const a = from.current
    const t0 = performance.now()
    let raf = 0
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / ms)
      const e = 1 - Math.pow(1 - p, 3)
      setV(a + (target - a) * e)
      if (p < 1) raf = requestAnimationFrame(tick)
      else from.current = target
    }
    raf = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(raf)
      from.current = target
    }
  }, [target, ms])
  return decimals ? Number(v.toFixed(decimals)) : Math.round(v)
}

export function CountUp({ value, ms = 600, decimals = 0, suffix = '', prefix = '', className }: { value: number; ms?: number; decimals?: number; suffix?: string; prefix?: string; className?: string }) {
  const v = useCountUp(value, ms, decimals)
  return (
    <span className={cn('tnum', className)}>
      {prefix}
      {decimals ? v.toFixed(decimals) : v.toLocaleString('en-US')}
      {suffix}
    </span>
  )
}

/** Count the first number found in a string ("58 functions" -> counts to 58), keeping the rest as is. */
export function CountText({ text, className }: { text: string; className?: string }) {
  const m = /(\d[\d,]*\.?\d*)/.exec(text)
  const target = m ? parseFloat(m[1].replace(/,/g, '')) : 0
  const dec = m && m[1].includes('.') ? m[1].split('.')[1].length : 0
  const v = useCountUp(target, 500, dec)
  if (!m) return <span className={className}>{text}</span>
  const shown = dec ? v.toFixed(dec) : Math.round(v).toLocaleString('en-US')
  return (
    <span className={cn('tnum', className)}>
      {text.slice(0, m.index)}
      {m[1].includes(',') && !dec ? shown : shown.replace(/,/g, m[1].includes(',') ? ',' : '')}
      {text.slice(m.index + m[1].length)}
    </span>
  )
}

/** Success check that draws itself. */
export function DrawCheck({ size = 14, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={cn('flex-none', className)} aria-hidden>
      <path d="M3.2 8.4l3 3 6.6-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="draw" />
    </svg>
  )
}

/** Card whose border glows under the pointer. */
export function GlowCard({ children, className, as: Tag = 'section' }: { children: ReactNode; className?: string; as?: 'section' | 'div' | 'button' }) {
  const ref = useRef<HTMLElement>(null)
  return (
    <Tag
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ref={ref as any}
      onPointerMove={(e: React.PointerEvent) => {
        const r = ref.current!.getBoundingClientRect()
        ref.current!.style.setProperty('--mx', `${e.clientX - r.left}px`)
        ref.current!.style.setProperty('--my', `${e.clientY - r.top}px`)
      }}
      className={cn('group relative overflow-hidden rounded-[14px] surface transition-[border-color,transform] duration-200 hover:border-line2 focus-within:border-accent/50', className)}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{ background: 'radial-gradient(260px circle at var(--mx,50%) var(--my,0%), rgb(var(--accent) / 0.12), transparent 70%)' }}
      />
      <span aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/0 to-transparent transition-all duration-300 group-hover:via-accent/60" />
      <div className="relative flex h-full flex-col">{children}</div>
    </Tag>
  )
}
