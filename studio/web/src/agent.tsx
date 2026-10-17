import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { AlertCircle, Check, ChevronRight, Download, Minus, RotateCcw, Sparkles } from 'lucide-react'
import { useStudio } from './store'
import { countStatus, totalSpeedup, type StepItem } from './reducer'
import { exportProject } from './actions'
import { Btn, Empty, PanelTitle, Kbd, MOD, SHIFT } from './ui'
import { cn, fmtX, llmLabel } from './lib/format'
import { CountUp, DrawCheck, reducedMotion } from './motion'

/** `code` -> <code> */
export function inlineCode(s: string): ReactNode {
  return s.split(/(`[^`]+`)/g).map((p, i) =>
    p.startsWith('`') ? (
      <code key={i} className="mono rounded bg-hover px-1 py-px text-[11.5px] text-fg">
        {p.slice(1, -1)}
      </code>
    ) : (
      <Fragment key={i}>{p}</Fragment>
    ),
  )
}

function StepIcon({ state }: { state: StepItem['state'] }) {
  if (state === 'running')
    return (
      <span className="relative flex h-4 w-4 flex-none items-center justify-center">
        <span className="h-2 w-2 animate-pulseDot rounded-full bg-accent" />
      </span>
    )
  if (state === 'done') return <DrawCheck size={14} className="text-ok" />
  if (state === 'failed') return <AlertCircle size={14} className="flex-none text-bad" />
  return <Minus size={14} className="flex-none text-fg3" />
}

function Step({ s }: { s: StepItem }) {
  const open = useStudio((st) => st.activeTab === `fn:${s.fn_id}`)
  const openFunction = useStudio((st) => st.openFunction)
  const [exp, setExp] = useState(false)
  const has = !!s.detail
  return (
    <motion.li initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}>
      <div className={cn('group rounded-lg px-2 py-1.5 transition-colors hover:bg-hover/60', open && 'bg-hover')}>
        <div className="flex items-start gap-2">
          <span className="mt-[2px]">
            <StepIcon state={s.state} />
          </span>
          <button
            className="min-w-0 flex-1 text-left text-sm leading-[18px] text-fg"
            onClick={() => (s.fn_id ? openFunction(s.fn_id, 'journey') : has && setExp(!exp))}
            title={s.fn_id ? 'Open this function’s journey' : undefined}
          >
            {inlineCode(s.title)}
          </button>
          {has && (
            <button aria-label={exp ? 'Collapse step' : 'Expand step'} aria-expanded={exp} onClick={() => setExp(!exp)} className="mt-[1px] flex-none rounded p-0.5 text-fg3 hover:bg-line hover:text-fg">
              <ChevronRight size={13} className={cn('transition-transform', exp && 'rotate-90')} />
            </button>
          )}
        </div>
        {has && exp && <p className="mt-1 whitespace-pre-wrap pl-6 text-xs leading-[17px] text-fg2">{s.detail}</p>}
      </div>
    </motion.li>
  )
}

/** Reveal text quickly, a few characters per frame (skipped under reduced motion). */
function Typewriter({ text }: { text: string }) {
  const [n, setN] = useState(reducedMotion() ? text.length : 0)
  useEffect(() => {
    if (reducedMotion()) return setN(text.length)
    setN(0)
    const step = Math.max(2, Math.ceil(text.length / 22))
    const t = setInterval(() => setN((x) => (x + step >= text.length ? (clearInterval(t), text.length) : x + step)), 16)
    return () => clearInterval(t)
  }, [text])
  return <>{text.slice(0, n)}<span className={n < text.length ? 'ml-px inline-block h-3.5 w-[2px] translate-y-[2px] bg-accent' : 'hidden'} /></>
}

export function AgentPanel() {
  const js = useStudio((s) => s.js)
  const env = useStudio((s) => s.env)
  const decide = useStudio((s) => s.decide)
  const ref = useRef<HTMLDivElement>(null)
  const stick = useRef(true)
  const c = useMemo(() => countStatus(js), [js.functions])
  const sp = totalSpeedup(js)
  const done = js.state === 'done' || js.state === 'failed' || js.state === 'cancelled'
  const nAcc = c.verified + c.guarded

  useEffect(() => {
    const el = ref.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [js.steps.length, js.steps[js.steps.length - 1]?.title, done])

  return (
    <aside aria-label="PYTHIA agent" className="no-print flex h-full min-h-0 w-full flex-col bg-panel">
      <PanelTitle
        right={
          js.state === 'running' ? (
            <span className="flex items-center gap-1.5 text-xs text-accent">
              <span className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-accent" />
              Working
            </span>
          ) : done ? (
            <span className="text-xs text-fg3">{js.state === 'done' ? 'Finished' : js.state}</span>
          ) : null
        }
      >
        <span className="flex items-center gap-1.5">
          <Sparkles size={13} className="text-accent" />
          PYTHIA agent
        </span>
      </PanelTitle>
      <div
        ref={ref}
        onScroll={(e) => {
          const el = e.currentTarget
          stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40
        }}
        className="min-h-0 flex-1 overflow-auto px-2 py-2"
      >
        {!js.jobId ? (
          <Empty title="The LLM suggests. The compiler proves." icon={<Sparkles size={20} />}>
            When you open a project, every step PYTHIA takes appears here: what it traced, what it rewrote, and what the oracle replay confirmed.
            {env && <span className="mt-2 block text-xs">{env.llm.enabled ? llmLabel(env) : env.llm.hint}</span>}
          </Empty>
        ) : (
          <>
            {js.caption && js.state === 'running' && (
              <p key={js.captionSeq} className="mb-2 rounded-lg border border-accent/25 bg-accent/10 px-3 py-2.5 text-sm leading-[19px] text-fg shadow-[0_0_24px_-10px_rgb(var(--accent)/0.6)]">
                <Typewriter text={js.caption} />
              </p>
            )}
            <ul className="space-y-px">
              {js.steps.map((s) => (
                <Step key={s.step_id} s={s} />
              ))}
            </ul>
            {js.steps.length === 0 && (
              <div className="space-y-2 p-2" aria-busy>
                <div className="skeleton h-4 w-3/4" />
                <div className="skeleton h-4 w-1/2" />
              </div>
            )}
            {done && (
              <section className="surface shine relative mt-3 animate-fadeIn rounded-[14px] p-3.5" aria-label="Run summary">
                <div aria-hidden className="pointer-events-none absolute -right-10 -top-12 h-32 w-32 rounded-full bg-ok/15 blur-2xl" />
                <div className="relative flex items-end justify-between">
                  <div>
                    <div className="text-xs text-fg3">{js.e2e?.ok ? 'End-to-end speedup' : 'Geometric-mean speedup'}</div>
                    <div className="text-[34px] font-semibold leading-10 tracking-tight text-grad">{sp ? <CountUp value={sp} decimals={1} suffix="×" ms={1100} /> : '—'}</div>
                  </div>
                  {js.e2e?.ok && (
                    <div className="tnum pb-1 text-right text-xs text-fg3">
                      {js.e2e.before_s.toFixed(1)} s → {js.e2e.after_s.toFixed(1)} s
                      <div className={js.e2e.output_match ? 'text-ok' : 'text-bad'}>{js.e2e.output_match ? 'output identical' : 'output differs'}</div>
                    </div>
                  )}
                </div>
                <dl className="tnum mt-3 grid grid-cols-3 gap-x-3 gap-y-1.5 border-t border-line pt-3 text-xs">
                  <Stat k="Verified" v={c.verified} cls="text-ok" />
                  <Stat k="Guarded" v={c.guarded} cls="text-warn" />
                  <Stat k="Fixable" v={c.fixable} cls="text-accent" />
                  <Stat k="Declined" v={c.declined} cls="text-fg2" />
                  <Stat k="Failed" v={c.failed} cls="text-bad" />
                  <Stat k="Not eligible" v={c.not_eligible} cls="text-fg3" />
                </dl>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <Btn kind="ok" onClick={() => decide('all', 'accepted')} disabled={!nAcc} title={`Accept all (${MOD}${SHIFT}A)`}>
                    <Check size={13} /> Accept all
                  </Btn>
                  <Btn kind="danger" onClick={() => decide('all', 'rejected')} disabled={!nAcc}>
                    Reject all
                  </Btn>
                  <Btn kind="primary" onClick={() => exportProject(false)} className="ml-auto">
                    <Download size={13} /> Export
                  </Btn>
                  <Btn kind="ghost" onClick={() => useStudio.getState().replayCurrent()} title="Replay this run with pacing">
                    <RotateCcw size={12} /> Replay
                  </Btn>
                </div>
                <p className="mt-2 text-2xs text-fg3">
                  <Kbd>{MOD}{SHIFT}A</Kbd> accepts everything verified. The original project is never modified.
                </p>
              </section>
            )}
          </>
        )}
      </div>
    </aside>
  )
}

function Stat({ k, v, cls }: { k: string; v: number; cls: string }) {
  return (
    <div>
      <dt className="text-fg3">{k}</dt>
      <dd className={cn('text-base font-medium', v ? cls : 'text-fg3')}>{v}</dd>
    </div>
  )
}
