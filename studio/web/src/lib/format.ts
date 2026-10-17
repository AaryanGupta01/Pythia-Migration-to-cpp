import type { Status } from '../types'

export const fmtX = (x: number | null | undefined, digits = 1) =>
  x == null ? '—' : x >= 100 ? `${Math.round(x)}×` : x < 1 ? `${x.toFixed(2)}×` : `${x.toFixed(digits)}×`
export const fmtPct = (x: number | null | undefined, digits = 1) => (x == null ? '—' : `${(x * 100).toFixed(digits)}%`)
export const fmtInt = (x: number | null | undefined) => (x == null ? '—' : x.toLocaleString('en-US'))
export const fmtMs = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : ms >= 10 ? `${ms.toFixed(0)} ms` : `${ms.toFixed(2)} ms`)
export const fmtBytes = (b: number) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : b > 1e3 ? `${(b / 1e3).toFixed(0)} kB` : `${b} B`)
export const fmtAgo = (ts: number | null | undefined) => {
  if (!ts) return ''
  const s = Date.now() / 1000 - ts
  if (s < 90) return 'just now'
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  return `${Math.round(s / 86400)} d ago`
}

export interface StatusMeta {
  label: string
  text: string // tailwind text color class
  bg: string // chip background
  dot: string
  rank: number
}
export const STATUS: Record<Status, StatusMeta> = {
  verified: { label: 'Verified', text: 'text-ok', bg: 'bg-ok/10 border-ok/30', dot: 'bg-ok', rank: 0 },
  guarded: { label: 'Guarded', text: 'text-warn', bg: 'bg-warn/10 border-warn/30', dot: 'bg-warn', rank: 1 },
  pending: { label: 'Pending', text: 'text-fg2', bg: 'bg-hover border-line2', dot: 'bg-fg3', rank: 2 },
  fixable: { label: 'Fixable', text: 'text-accent', bg: 'bg-accent/10 border-accent/30', dot: 'bg-accent', rank: 3 },
  declined: { label: 'Declined', text: 'text-fg2', bg: 'bg-hover border-line2 border-dashed', dot: 'bg-fg3', rank: 4 },
  not_eligible: { label: 'Not eligible', text: 'text-fg3', bg: 'bg-transparent border-line2', dot: 'bg-line2', rank: 5 },
  failed: { label: 'Failed', text: 'text-bad', bg: 'bg-bad/10 border-bad/30', dot: 'bg-bad', rank: 6 },
}

export const SEV_COLOR = { exact: 'text-ok', guarded: 'text-warn', divergent: 'text-bad' } as const
export const SEV_BG = { exact: 'bg-ok', guarded: 'bg-warn', divergent: 'bg-bad' } as const

export function b64(s: string) {
  const bytes = new TextEncoder().encode(s)
  let bin = ''
  bytes.forEach((b) => (bin += String.fromCharCode(b)))
  return btoa(bin)
}
export function fileToB64(f: File): Promise<string> {
  return new Promise((res, rej) => {
    const r = new FileReader()
    r.onload = () => res(String(r.result).split(',')[1] ?? '')
    r.onerror = () => rej(r.error)
    r.readAsDataURL(f)
  })
}

export const basename = (p: string) => p.split('/').pop() ?? p
export const cn = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')
