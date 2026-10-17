import { useEffect, useRef, useState } from 'react'
import { reducedMotion, useCountUp } from './motion'
import { cn } from './lib/format'

const rgb = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim().split(/\s+/).join(',')

/**
 * Faint code-flow background: a dot grid plus streaks that drift left to right (source going through the compiler)
 * and light up near the pointer. 30 fps cap, pauses when hidden/offscreen, static under prefers-reduced-motion.
 */
export function HeroCanvas({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const ctx = cv.getContext('2d')
    if (!ctx) return
    const parent = cv.parentElement!
    const GAP = 28
    const reduced = reducedMotion()
    let w = 0
    let h = 0
    let dpr = 1
    let accent = rgb('--accent')
    let fg = rgb('--fg')
    const dots = document.createElement('canvas')
    const mouse = { x: -999, y: -999, on: false }
    type Streak = { y: number; x: number; v: number; len: number; a: number }
    let streaks: Streak[] = []
    let raf = 0
    let last = 0
    let visible = true

    const build = () => {
      const r = parent.getBoundingClientRect()
      w = Math.max(1, Math.floor(r.width))
      h = Math.max(1, Math.floor(r.height))
      dpr = Math.min(2, window.devicePixelRatio || 1)
      cv.width = w * dpr
      cv.height = h * dpr
      cv.style.width = `${w}px`
      cv.style.height = `${h}px`
      dots.width = w * dpr
      dots.height = h * dpr
      const d = dots.getContext('2d')!
      d.scale(dpr, dpr)
      d.fillStyle = `rgba(${fg},0.09)`
      for (let y = GAP / 2; y < h; y += GAP) for (let x = GAP / 2; x < w; x += GAP) d.fillRect(x - 0.5, y - 0.5, 1.2, 1.2)
      const n = Math.max(8, Math.min(26, Math.round(w / 70)))
      streaks = Array.from({ length: n }, () => ({
        y: (Math.floor(Math.random() * (h / GAP)) + 0.5) * GAP,
        x: Math.random() * w,
        v: 14 + Math.random() * 38,
        len: 50 + Math.random() * 130,
        a: 0.16 + Math.random() * 0.22,
      }))
      accent = rgb('--accent')
      fg = rgb('--fg')
    }

    const draw = (dt: number) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)
      ctx.drawImage(dots, 0, 0, w, h)
      // dots near the pointer light up
      if (mouse.on) {
        const R = 130
        const c0 = Math.max(0, Math.floor((mouse.x - R) / GAP))
        const c1 = Math.min(Math.floor(w / GAP), Math.ceil((mouse.x + R) / GAP))
        const r0 = Math.max(0, Math.floor((mouse.y - R) / GAP))
        const r1 = Math.min(Math.floor(h / GAP), Math.ceil((mouse.y + R) / GAP))
        for (let r = r0; r <= r1; r++)
          for (let c = c0; c <= c1; c++) {
            const x = c * GAP + GAP / 2
            const y = r * GAP + GAP / 2
            const dd = Math.hypot(x - mouse.x, y - mouse.y)
            if (dd < R) {
              ctx.fillStyle = `rgba(${accent},${((1 - dd / R) * 0.7).toFixed(3)})`
              ctx.fillRect(x - 1, y - 1, 2.4, 2.4)
            }
          }
      }
      for (const s of streaks) {
        const near = mouse.on ? Math.max(0, 1 - Math.hypot(s.x - mouse.x, s.y - mouse.y) / 200) : 0
        if (!reduced) s.x += (s.v * (1 + near * 3) * dt) / 1000
        if (s.x - s.len > w) {
          s.x = -10
          s.y = (Math.floor(Math.random() * (h / GAP)) + 0.5) * GAP
        }
        const a = Math.min(0.85, s.a + near * 0.5)
        const g = ctx.createLinearGradient(s.x - s.len, 0, s.x, 0)
        g.addColorStop(0, `rgba(${accent},0)`)
        g.addColorStop(1, `rgba(${accent},${a.toFixed(3)})`)
        ctx.fillStyle = g
        ctx.fillRect(s.x - s.len, s.y - 0.75, s.len, 1.5)
        ctx.fillStyle = `rgba(${accent},${Math.min(1, a + 0.25).toFixed(3)})`
        ctx.fillRect(s.x - 1, s.y - 1.5, 3, 3)
      }
    }

    const loop = (t: number) => {
      raf = requestAnimationFrame(loop)
      if (document.hidden || !visible) return
      const dt = t - last
      if (dt < 33) return
      last = t
      draw(Math.min(dt, 100))
    }

    build()
    draw(0)
    const ro = new ResizeObserver(() => {
      build()
      draw(0)
    })
    ro.observe(parent)
    const mo = new MutationObserver(() => {
      accent = rgb('--accent')
      fg = rgb('--fg')
      build()
      draw(0)
    })
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting))
    io.observe(cv)
    const move = (e: PointerEvent) => {
      const r = cv.getBoundingClientRect()
      mouse.x = e.clientX - r.left
      mouse.y = e.clientY - r.top
      mouse.on = mouse.x >= 0 && mouse.y >= 0 && mouse.x <= w && mouse.y <= h
      if (reduced) draw(0)
    }
    const leave = () => {
      mouse.on = false
      if (reduced) draw(0)
    }
    window.addEventListener('pointermove', move, { passive: true })
    document.addEventListener('pointerleave', leave)
    if (!reduced) raf = requestAnimationFrame(loop)
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      mo.disconnect()
      io.disconnect()
      window.removeEventListener('pointermove', move)
      document.removeEventListener('pointerleave', leave)
    }
  }, [])
  return <canvas ref={ref} aria-hidden className={cn('pointer-events-none absolute left-0 top-0', className)} />
}

/** A number that repeatedly counts up from 1.0x to its target, holding between loops. */
function LoopX({ target, className }: { target: number; className?: string }) {
  const [n, setN] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setN((x) => x + 1), 6500)
    return () => clearInterval(t)
  }, [])
  return <LoopInner key={n} target={target} className={className} />
}
function LoopInner({ target, className }: { target: number; className?: string }) {
  const [go, setGo] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setGo(true), 300)
    return () => clearTimeout(t)
  }, [])
  const v = useCountUp(go ? target : 1, 1500, 1, 1)
  return <span className={cn('tnum', className)}>{v.toFixed(1)}×</span>
}

export const SAMPLE_ROWS = [
  { name: 'step', x: 54.0 },
  { name: 'assign_clusters', x: 42.7 },
  { name: 'edit_distance', x: 38.2 },
  { name: 'count_pairs', x: 24.6 },
  { name: 'char_histogram', x: 14.9 },
]

export function SpeedTicker({ headline, caption, rows = SAMPLE_ROWS }: { headline: number; caption: string; rows?: { name: string; x: number }[] }) {
  return (
    <div className="surface relative overflow-hidden rounded-[16px] p-5">
      <div aria-hidden className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-accent/20 blur-3xl" />
      <div className="relative">
        <div className="text-xs text-fg3">{caption}</div>
        <div className="mt-1 flex items-end gap-2">
          <LoopX target={headline} className="text-[56px] font-semibold leading-[56px] tracking-tight text-grad" />
          <span className="pb-1.5 text-sm text-fg3">end to end</span>
        </div>
        <ul className="mt-5 space-y-2.5">
          {rows.map((r, i) => (
            <li key={r.name} className="flex items-center gap-3">
              <span className="mono w-[116px] flex-none truncate text-xs text-fg2">{r.name}</span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-hover">
                <span className="block h-full origin-left animate-[growX_900ms_ease-out_both] rounded-full accent-grad" style={{ width: `${(Math.log10(r.x) / Math.log10(70)) * 100}%`, animationDelay: `${i * 90 + 200}ms` }} />
              </span>
              <span className="tnum w-12 flex-none text-right text-xs font-medium text-ok">{r.x.toFixed(1)}×</span>
            </li>
          ))}
        </ul>
        <div className="mt-4 flex items-center justify-between border-t border-line pt-3 text-xs text-fg3">
          <span>Every number is median CPython time over compiled time</span>
        </div>
      </div>
    </div>
  )
}
