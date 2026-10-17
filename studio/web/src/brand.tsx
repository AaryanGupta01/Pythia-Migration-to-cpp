import { useId } from 'react'
import { cn } from './lib/format'

/** The PYTHIA mark: a P drawn as one continuous line (source becoming a compiled path) with a node at its end. */
export function Logo({ size = 18, className, plain }: { size?: number; className?: string; plain?: boolean }) {
  const id = useId().replace(/:/g, '')
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className={cn('flex-none', className)}>
      <defs>
        <linearGradient id={`g${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#9a92ff" />
          <stop offset="1" stopColor="#5a49f0" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8.5" fill={plain ? 'rgb(var(--raised))' : `url(#g${id})`} stroke={plain ? 'rgb(var(--line2))' : 'none'} />
      <path d="M11.5 24.5V7.5h6a5 5 0 010 10h-6" fill="none" stroke={plain ? 'rgb(var(--accent))' : '#fff'} strokeWidth="2.7" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="22.6" cy="23.2" r="2.1" fill={plain ? 'rgb(var(--accent))' : '#fff'} fillOpacity=".92" />
    </svg>
  )
}

export function Wordmark({ className, size = 'md' }: { className?: string; size?: 'sm' | 'md' | 'lg' }) {
  const s = { sm: 'text-[13px]', md: 'text-[15px]', lg: 'text-[20px]' }[size]
  return (
    <span className={cn('inline-flex items-baseline gap-1.5 font-semibold leading-none tracking-[0.02em]', s, className)}>
      <span>PYTHIA</span>
      <span className="font-normal tracking-normal text-fg3">Studio</span>
    </span>
  )
}
