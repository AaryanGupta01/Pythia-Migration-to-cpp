// First-run setup: check the computer, connect an AI model (free Groq key, tested live), then pick a start.
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowRight, Braces, Check, ExternalLink, KeyRound, Play, RotateCcw, ShieldCheck, Sparkles, X } from 'lucide-react'
import { api, errMsg, IS_MOCK, query } from './api'
import { useStudio } from './store'
import { Btn, Skeleton } from './ui'
import { Logo } from './brand'
import { cn } from './lib/format'

type Check = { id: string; label: string; ok: boolean; required: boolean; detail: string; hint: string | null }
type Provider = 'groq' | 'anthropic'

const PROVIDERS: Record<Provider, { name: string; blurb: string; url: string; prefix: string; steps: string[] }> = {
  groq: {
    name: 'Groq (free)',
    blurb: 'Runs the open gpt-oss-120b model on a free tier. Recommended.',
    url: 'https://console.groq.com/keys',
    prefix: 'gsk_',
    steps: ['Open console.groq.com/keys and sign in (free, no card)', 'Click "Create API Key" and copy it', 'Paste it below and press Test & save'],
  },
  anthropic: {
    name: 'Anthropic',
    blurb: 'Claude models (paid API). Use this if you already have a key.',
    url: 'https://console.anthropic.com/settings/keys',
    prefix: 'sk-ant-',
    steps: ['Open console.anthropic.com and create an API key', 'Paste it below and press Test & save'],
  },
}

export function SetupWizard() {
  const env = useStudio((s) => s.env)
  const settings = useStudio((s) => s.settings)
  const loadEnv = useStudio((s) => s.loadEnv)
  const jobs = useStudio((s) => s.jobs)
  const startJob = useStudio((s) => s.startJob)
  const openJob = useStudio((s) => s.openJob)
  const openSpecial = useStudio((s) => s.openSpecial)
  const [dismissed, setDismissed] = useState(false)
  const [step, setStep] = useState(0)
  const [checks, setChecks] = useState<Check[] | null>(null)
  const [provider, setProvider] = useState<Provider>('groq')
  const [key, setKey] = useState('')
  const [testing, setTesting] = useState(false)
  const [keyMsg, setKeyMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const open = !dismissed && !IS_MOCK && !query.has('presenter') && !!env && !!settings && !settings.setup_done

  useEffect(() => {
    if (open && checks == null) api.doctor().then((d) => setChecks(d.checks)).catch(() => setChecks([]))
  }, [open, checks])
  if (!open) return null

  const llmOn = !!env?.llm.enabled && env.llm.provider !== 'offline-cache'
  const sample = jobs.find((j) => j.sample && j.state === 'done')
  const required = (checks ?? []).filter((c) => c.required)
  const allOk = checks != null && required.every((c) => c.ok)

  const finish = async (then?: () => void) => {
    try {
      await api.putSettings({ setup_done: true })
    } catch { /* still close */ }
    await loadEnv()
    setDismissed(true)
    then?.()
  }
  const testAndSave = async () => {
    setTesting(true)
    setKeyMsg(null)
    try {
      const r = await api.testKey(provider, key.trim())
      if (!r.ok) {
        setKeyMsg({ ok: false, text: r.error ?? 'The key did not work.' })
      } else {
        await api.putSettings({ provider, api_key: key.trim(), offline: false })
        await loadEnv()
        setKeyMsg({ ok: true, text: `Connected: ${(r.model ?? '').replace(/^openai\//, '')} on ${PROVIDERS[provider].name.replace(' (free)', '')}. The key is stored only on this computer.` })
        setKey('')
      }
    } catch (e) {
      setKeyMsg({ ok: false, text: errMsg(e) })
    }
    setTesting(false)
  }
  const p = PROVIDERS[provider]

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-bg/85 p-6 backdrop-blur-md" role="dialog" aria-modal="true" aria-label="PYTHIA Studio setup">
      <motion.div initial={{ opacity: 0, y: 12, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.22 }}
        className="surface relative w-full max-w-[720px] overflow-hidden rounded-2xl border border-line2 shadow-2xl">
        <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-accent/20 blur-3xl" />
        <div className="relative flex items-center gap-3 border-b border-line px-6 py-4">
          <Logo size={26} />
          <div>
            <div className="text-[15px] font-semibold">Set up PYTHIA Studio</div>
            <div className="text-xs text-fg3">Takes a minute. You can change everything later in Settings.</div>
          </div>
          <ol className="ml-auto flex items-center gap-2 text-xs">
            {['Check', 'AI model', 'Start'].map((t, i) => (
              <li key={t} className={cn('flex items-center gap-1.5 rounded-full px-2 py-0.5', i === step ? 'bg-accent/15 text-fg' : i < step ? 'text-ok' : 'text-fg3')}>
                <span className={cn('flex h-4 w-4 items-center justify-center rounded-full border text-[10px]', i < step ? 'border-ok bg-ok/20' : i === step ? 'border-accent' : 'border-line2')}>{i < step ? <Check size={10} /> : i + 1}</span>
                {t}
              </li>
            ))}
          </ol>
          <button onClick={() => finish()} className="ml-2 rounded p-1 text-fg3 hover:bg-hover hover:text-fg" aria-label="Skip setup"><X size={15} /></button>
        </div>

        <div className="relative min-h-[330px] px-6 py-5">
          {step === 0 && (
            <div>
              <h2 className="text-lg font-semibold">Checking your computer</h2>
              <p className="mt-1 text-sm text-fg2">PYTHIA compiles Python to C++. Everything it needs ships with the app; this just confirms it all works here.</p>
              <ul className="mt-4 space-y-1.5">
                {checks == null
                  ? [0, 1, 2, 3].map((i) => <li key={i}><Skeleton className="h-6 w-full" /></li>)
                  : checks.map((c) => (
                      <li key={c.id} className="flex items-start gap-2.5 rounded-md border border-line bg-panel px-3 py-1.5 text-sm">
                        <span className={cn('mt-0.5 flex h-4 w-4 flex-none items-center justify-center rounded-full', c.ok ? 'bg-ok/20 text-ok' : c.required ? 'bg-bad/20 text-bad' : 'bg-warn/20 text-warn')}>{c.ok ? <Check size={10} /> : <X size={10} />}</span>
                        <span className="w-56 flex-none text-fg">{c.label}</span>
                        <span className="min-w-0 flex-1 truncate text-xs text-fg3" title={c.detail}>{c.detail}{!c.ok && c.hint ? ` · ${c.hint}` : ''}</span>
                      </li>
                    ))}
              </ul>
              {checks != null && !allOk && <p className="mt-3 text-sm text-warn">Something required is missing (see the hints above). The app still opens, but compiling is disabled until it is fixed.</p>}
            </div>
          )}

          {step === 1 && (
            <div>
              <h2 className="flex items-center gap-2 text-lg font-semibold"><Sparkles size={17} className="text-accent" /> Connect an AI model <span className="text-sm font-normal text-fg3">(optional)</span></h2>
              <p className="mt-1 text-sm text-fg2">
                Ordinary Python often needs small rewrites before it can be compiled: dictionaries become classes, shared state becomes parameters, lambdas become loops. An AI model proposes the rewrite; the PYTHIA type checker and a side-by-side run check every answer, so a wrong answer cannot slip through.
              </p>
              {llmOn && !keyMsg?.ok && (
                <div className="mt-3 flex items-center gap-2 rounded-lg border border-ok/30 bg-ok/10 px-3 py-2 text-sm text-ok">
                  <ShieldCheck size={15} /> Already connected: {env?.llm.provider} · {env?.llm.model.replace(/^openai\//, '')}. You can keep it or paste a different key.
                </div>
              )}
              <div className="mt-4 grid grid-cols-2 gap-2">
                {(Object.keys(PROVIDERS) as Provider[]).map((k) => (
                  <button key={k} onClick={() => { setProvider(k); setKeyMsg(null) }}
                    className={cn('rounded-lg border px-3 py-2 text-left transition-colors', provider === k ? 'border-accent bg-accent/10' : 'border-line hover:border-line2 hover:bg-hover/50')}>
                    <div className="text-sm font-medium">{PROVIDERS[k].name}</div>
                    <div className="text-xs text-fg3">{PROVIDERS[k].blurb}</div>
                  </button>
                ))}
              </div>
              <ol className="mt-3 list-decimal space-y-0.5 pl-5 text-sm text-fg2">
                {p.steps.map((t) => <li key={t}>{t}</li>)}
              </ol>
              <a href={p.url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-sm text-accent hover:underline">{p.url.replace('https://', '')} <ExternalLink size={12} /></a>
              <div className="mt-3 flex items-center gap-2">
                <div className="relative flex-1">
                  <KeyRound size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-fg3" />
                  <input type="password" value={key} onChange={(e) => setKey(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && key.trim() && testAndSave()}
                    placeholder={`${p.prefix}…`} autoComplete="off" spellCheck={false} aria-label="API key"
                    className="mono h-9 w-full rounded-md border border-line2 bg-bg pl-8 pr-2 text-sm outline-none transition-colors placeholder:text-fg3 focus:border-accent" />
                </div>
                <Btn kind="primary" onClick={testAndSave} disabled={!key.trim() || testing} className="h-9">{testing ? 'Testing…' : 'Test & save'}</Btn>
              </div>
              {keyMsg && <p className={cn('mt-2 text-sm', keyMsg.ok ? 'text-ok' : 'text-bad')}>{keyMsg.text}</p>}
              <p className="mt-3 text-xs text-fg3">The key is saved only on this computer ({'~/.pythia-studio/settings.json'}) and sent only to the provider you picked. Without a key everything else works; AI conversion stays off.</p>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-lg font-semibold">You're ready</h2>
              <p className="mt-1 text-sm text-fg2">Pick a place to start. The welcome screen has all of these too.</p>
              <div className="mt-4 grid gap-2.5">
                {sample && (
                  <StartCard icon={<RotateCcw size={17} />} title="Replay the sample run (instant)" text="A finished analysis of the bundled Quanta project plays back stage by stage: hot spots, AI rewrites, compiled C++, proofs and speedups."
                    onClick={() => finish(() => openJob(sample.job_id, { replay: true }))} primary />
                )}
                <StartCard icon={<Play size={17} />} title="Analyse the demo project for real" text="Traces, compiles and verifies a 3,800-line Python project on this computer (a few minutes the first time)."
                  onClick={() => finish(() => startJob({ kind: 'demo' }))} primary={!sample} />
                <StartCard icon={<Braces size={17} />} title="Open the Playground" text="Paste any Python program. If it is not PySub yet, convert it with AI, then run the original and the compiled version side by side."
                  onClick={() => finish(() => openSpecial('playground'))} />
              </div>
            </div>
          )}
        </div>

        <div className="relative flex items-center justify-between border-t border-line bg-panel/60 px-6 py-3">
          <Btn kind="ghost" onClick={() => (step === 0 ? finish() : setStep(step - 1))}>{step === 0 ? 'Skip setup' : 'Back'}</Btn>
          {step < 2 && (
            <Btn kind="primary" onClick={() => setStep(step + 1)} disabled={step === 0 && checks == null}>
              {step === 1 && !llmOn && !keyMsg?.ok ? 'Skip for now' : 'Continue'} <ArrowRight size={13} />
            </Btn>
          )}
        </div>
      </motion.div>
    </div>
  )
}

function StartCard({ icon, title, text, onClick, primary }: { icon: React.ReactNode; title: string; text: string; onClick: () => void; primary?: boolean }) {
  return (
    <button onClick={onClick} className={cn('group flex items-start gap-3 rounded-xl border px-4 py-3 text-left transition-colors', primary ? 'border-accent/50 bg-accent/10 hover:bg-accent/15' : 'border-line hover:border-line2 hover:bg-hover/50')}>
      <span className={cn('mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-lg', primary ? 'bg-accent/20 text-accent' : 'bg-hover text-fg2')}>{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium text-fg">{title}</span>
        <span className="block text-xs text-fg3">{text}</span>
      </span>
      <ArrowRight size={15} className="mt-2 flex-none text-fg3 transition-transform group-hover:translate-x-0.5" />
    </button>
  )
}
