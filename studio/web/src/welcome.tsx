import { useEffect, useRef, useState, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { AlertTriangle, ArrowRight, Braces, ChevronUp, Cpu, FileCode2, Folder, FolderOpen, GitBranch, History, Play, RotateCcw, Sparkles, Upload, X } from 'lucide-react'
import { api, errMsg, IS_MOCK } from './api'
import { useStudio } from './store'
import { Btn, Kbd, MOD, Skeleton } from './ui'
import { Logo, Wordmark } from './brand'
import { GlowCard } from './motion'
import { HeroCanvas, SpeedTicker } from './hero'
import { cn, fileToB64, fmtAgo, fmtX, llmLabel } from './lib/format'
import type { DemoInfo, FsList, JobInfo, JobInput } from './types'

const FALLBACK_DEMO: DemoInfo[] = [{ id: 'demo', name: 'textlab', description: 'About sixty functions: fast wins, fixable code, and code that should stay Python.' }]

const rise = (i: number) => ({ initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.28, delay: 0.04 * i, ease: 'easeOut' as const } })

export function Welcome() {
  const s = useStudio()
  const [path, setPath] = useState('')
  const [url, setUrl] = useState('')
  const [cmd, setCmd] = useState('')
  const [lang, setLang] = useState('Python')
  const [picker, setPicker] = useState(false)
  const [demos, setDemos] = useState<DemoInfo[]>(FALLBACK_DEMO)
  const fileRef = useRef<HTMLInputElement>(null)
  const env = s.env
  const noCompiler = env && !env.compiler.found
  const offline = s.settings?.offline ?? env?.offline ?? false
  const notPy = lang !== 'Python'
  const best = [...s.jobs].filter((j) => j.summary?.e2e_speedup).sort((a, b) => (b.summary!.e2e_speedup ?? 0) - (a.summary!.e2e_speedup ?? 0))[0]
  const headline = best?.summary?.e2e_speedup ?? 5.7
  const [bestRows, setBestRows] = useState<{ name: string; x: number }[] | null>(null)
  const bestId = best?.job_id
  useEffect(() => {
    setBestRows(null)
    if (!bestId || IS_MOCK) return
    let live = true
    api.functions(bestId).then((fs) => {
      const rows = fs.filter((f) => f.speedup && f.speedup > 1 && (f.status === 'verified' || f.status === 'guarded'))
        .sort((a, b) => (b.speedup ?? 0) - (a.speedup ?? 0)).slice(0, 5).map((f) => ({ name: f.name, x: f.speedup as number }))
      if (live && rows.length) setBestRows(rows)
    }).catch(() => {})
    return () => { live = false }
  }, [bestId])

  useEffect(() => {
    s.loadRecent()
    // feature-detect GET /api/demos; fall back to the single built-in demo
    if (api.demos) api.demos().then((d) => Array.isArray(d) && d.length && setDemos(d)).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const run = (input: JobInput) => {
    if (notPy) return
    s.startJob(input, { trace_cmd: cmd.trim() || null, offline })
  }
  const demoInput = (d: DemoInfo): JobInput => (d.id === 'demo' || demos.length === 1 ? { kind: 'demo' } : { kind: 'demo', demo: d.id })
  const chooseFile = async (f: File | undefined) => {
    if (!f) return
    run({ kind: 'file', filename: f.name, content_b64: await fileToB64(f) })
  }

  return (
    <div className="relative h-full overflow-auto">
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-[640px] [mask-image:radial-gradient(ellipse_85%_75%_at_50%_0%,#000_25%,transparent_78%)]">
        <HeroCanvas className="pointer-events-none" />
      </div>
      <div className="relative mx-auto max-w-[1120px] px-8 pb-20 pt-9 max-lg:px-5">
        <div className="mb-10 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Logo size={26} />
            <Wordmark size="md" />
          </div>
          <label className="flex items-center gap-2 text-sm text-fg3">
            Language
            <select value={lang} onChange={(e) => setLang(e.target.value)} className="h-7 rounded-md border border-line2 bg-raised px-2 text-sm text-fg" aria-label="Source language">
              {['Python', 'Java', 'JavaScript', 'TypeScript', 'Go', 'Rust', 'C#'].map((l) => <option key={l}>{l}</option>)}
            </select>
          </label>
        </div>

        <div className="grid grid-cols-[1.12fr_1fr] items-center gap-12 max-lg:grid-cols-1 max-lg:gap-8">
          <div>
            <motion.div {...rise(0)} className="mb-5 inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs text-fg2">
              <Sparkles size={12} className="text-accent" />
              The LLM suggests. The compiler proves.
            </motion.div>
            <motion.h1 {...rise(1)} className="text-grad text-[44px] font-semibold leading-[48px] tracking-[-0.025em] max-md:text-[34px] max-md:leading-[38px]">
              Make slow Python fast.<br />Prove it before you merge.
            </motion.h1>
            <motion.p {...rise(2)} className="mt-4 max-w-[520px] text-[15px] leading-6 text-fg2">
              PYTHIA traces your project, compiles the hot functions to C++17, then replays real calls through both versions. You review every change as a diff.
            </motion.p>
            <motion.div {...rise(3)} className="mt-7 flex flex-wrap items-center gap-3">
              <button
                onClick={() => run(demoInput(demos[0]))}
                disabled={s.starting || notPy}
                className="accent-grad glow-accent group inline-flex h-10 items-center gap-2 rounded-[10px] px-5 text-[14px] font-medium text-white transition-[filter,transform] hover:brightness-110 active:scale-[0.98] disabled:opacity-50"
              >
                <Play size={15} fill="currentColor" />
                Open the demo project
                <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
              </button>
              <Btn onClick={() => s.openSpecial('playground')} className="h-10 rounded-[10px] px-4 text-[14px]">
                <Braces size={15} /> Playground
              </Btn>
              <span className="hidden items-center gap-1.5 text-xs text-fg3 sm:flex">
                or press <Kbd>{MOD}K</Kbd>
              </span>
            </motion.div>
            <motion.div {...rise(4)} className="mt-6 flex flex-wrap items-center gap-2 text-xs">
              <Chip ok={!!env?.compiler.found} icon={<Cpu size={12} />}>{env ? (env.compiler.found ? `${env.compiler.name} ${env.compiler.version?.match(/\d+(\.\d+)*/)?.[0] ?? ''}` : 'No C++ compiler') : 'Checking toolchain'}</Chip>
              <Chip ok={!!env?.llm.enabled} icon={<Sparkles size={12} />}>{env ? llmLabel(env) : 'Checking LLM'}</Chip>
              {offline && <Chip ok icon={<History size={12} />}>Offline mode</Chip>}
              {IS_MOCK && <Chip>Sample data</Chip>}
            </motion.div>
          </div>
          <motion.div {...rise(2)}>
            <SpeedTicker headline={headline} rows={bestRows ?? undefined} caption={bestRows ? `Best run so far · ${best?.name}` : 'Sample result · illustrative'} />
          </motion.div>
        </div>

        {noCompiler && (
          <div role="alert" className="mt-8 flex gap-3 rounded-xl border border-warn/30 bg-warn/10 p-4">
            <AlertTriangle size={18} className="mt-0.5 flex-none text-warn" />
            <div className="text-sm">
              <div className="font-medium text-fg">A C++ compiler is needed to accelerate code</div>
              <p className="mt-0.5 text-fg2">{env?.compiler.hint ?? 'Install g++ or clang++ with C++17 support, then reload.'} You can still browse, scan and trace projects, but nothing can be compiled or verified until it is installed.</p>
            </div>
          </div>
        )}
        {s.envError && (
          <div role="alert" className="mt-8 rounded-xl border border-bad/30 bg-bad/10 p-4 text-sm">
            <div className="font-medium">Cannot reach the PYTHIA server</div>
            <p className="mt-0.5 text-fg2">{s.envError} Start it with <code className="mono rounded bg-hover px-1">./studio.sh</code>, or add <code className="mono rounded bg-hover px-1">?mock=1</code> to the address to explore with sample data.</p>
          </div>
        )}
        {notPy && (
          <div className="mt-8 rounded-xl border border-line2 bg-raised p-4 text-sm text-fg2">Python projects supported; architecture is source-language-agnostic past the IR.</div>
        )}

        <h2 className="mb-3 mt-12 text-sm font-medium text-fg2">Start with your code</h2>
        <div className="grid grid-cols-4 gap-4 max-xl:grid-cols-2 max-md:grid-cols-1">
          <Tile i={0} icon={<FolderOpen size={18} />} title="Open folder" desc="A project on this machine.">
            <form onSubmit={(e) => { e.preventDefault(); path.trim() && run({ kind: 'folder', path: path.trim() }) }} className="mt-auto space-y-2">
              <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="/home/you/project" aria-label="Folder path" className="mono h-8 w-full rounded-md border border-line2 bg-bg px-2.5 text-sm outline-none transition-colors placeholder:text-fg3 focus:border-accent" />
              <div className="flex gap-2">
                <Btn onClick={() => setPicker(true)} className="flex-1"><Folder size={13} /> Browse</Btn>
                <Btn type="submit" kind="primary" disabled={!path.trim() || notPy || s.starting}>Open</Btn>
              </div>
            </form>
          </Tile>
          <Tile i={1} icon={<GitBranch size={18} />} title="Clone repository" desc="A public GitHub URL.">
            <form onSubmit={(e) => { e.preventDefault(); url.trim() && run({ kind: 'git', url: url.trim() }) }} className="mt-auto space-y-2">
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://github.com/user/repo" aria-label="Repository URL" className="mono h-8 w-full rounded-md border border-line2 bg-bg px-2.5 text-sm outline-none transition-colors placeholder:text-fg3 focus:border-accent" />
              <Btn type="submit" kind="primary" className="w-full" disabled={!url.trim() || notPy || s.starting}>Clone and analyse</Btn>
            </form>
          </Tile>
          <Tile i={2} icon={<Upload size={18} />} title="Drop a file" desc="Drag a .py file anywhere in this window.">
            <button onClick={() => fileRef.current?.click()} className="mt-auto flex h-[74px] w-full flex-col items-center justify-center gap-0.5 rounded-lg border border-dashed border-line2 text-sm text-fg3 transition-colors hover:border-accent/60 hover:bg-accent/5 hover:text-fg">
              <span>Drop here or choose a file</span>
              <span className="text-xs">.py, up to 5 MB</span>
            </button>
            <input ref={fileRef} type="file" accept=".py,text/x-python" hidden onChange={(e) => chooseFile(e.target.files?.[0])} aria-label="Choose a Python file" />
          </Tile>
          <Tile i={3} icon={<Braces size={18} />} title="Playground" desc="Type PySub, see C++ live.">
            <Btn onClick={() => s.openSpecial('playground')} className="mt-auto w-full">Open playground <ArrowRight size={13} /></Btn>
          </Tile>
        </div>

        <div className="surface mt-4 grid grid-cols-[1fr_auto] items-end gap-5 rounded-[14px] p-4 max-md:grid-cols-1">
          <label className="block">
            <span className="mb-1.5 block text-xs text-fg3">Entry command (optional: real timings rank the hot spots)</span>
            <input value={cmd} onChange={(e) => setCmd(e.target.value)} placeholder="Entry command, e.g. python main.py --small" aria-label="Entry command" className="mono h-8 w-full rounded-md border border-line2 bg-bg px-2.5 text-sm outline-none transition-colors placeholder:text-fg3 focus:border-accent" />
          </label>
          <div className="flex items-center gap-5">
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <Toggle on={offline} label="Offline mode" onClick={async () => { await api.putSettings({ offline: !offline }).catch(() => {}); s.loadEnv() }} />
              Offline mode
            </label>
            <span className="max-w-[240px] text-xs leading-4 text-fg3">{env ? env.llm.enabled ? (offline ? 'LLM rewrites replay from the offline cache.' : llmLabel(env)) : env.llm.hint : 'Checking environment'}</span>
          </div>
        </div>

        {demos.length > 1 && (
          <>
            <h2 className="mb-3 mt-10 text-sm font-medium text-fg2">Demo projects</h2>
            <div className="grid grid-cols-2 gap-4 max-md:grid-cols-1">
              {demos.map((d, i) => (
                <GlowCard key={d.id} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-base font-medium">{d.name}</div>
                      <p className="mt-0.5 text-sm text-fg3">{d.description ?? 'A bundled Python project.'}</p>
                    </div>
                    <Btn kind={i === 0 ? 'primary' : 'default'} onClick={() => run(demoInput(d))} disabled={s.starting || notPy}><Play size={12} /> Open</Btn>
                  </div>
                </GlowCard>
              ))}
            </div>
          </>
        )}

        <div className="mt-10 grid grid-cols-2 gap-6 max-lg:grid-cols-1">
          <section aria-label="Recent workspaces">
            <h2 className="mb-3 text-sm font-medium text-fg2">Recent workspaces</h2>
            <ul className="surface divide-y divide-line overflow-hidden rounded-[14px]">
              {s.recent.length === 0 && <li className="px-4 py-5 text-sm text-fg3">Nothing yet. Open the demo project to see PYTHIA end to end.</li>}
              {s.recent.slice(0, 5).map((r) => {
                const job = s.jobs.find((j) => j.workspace_id === r.workspace_id)
                return (
                  <li key={r.workspace_id}>
                    <button onClick={() => (r.job_id || job ? s.openJob((r.job_id ?? job!.job_id) as string) : r.path && run({ kind: 'folder', path: r.path }))} className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-hover/60">
                      <span className="flex h-8 w-8 flex-none items-center justify-center rounded-lg border border-line2 bg-bg text-fg3"><FileCode2 size={15} /></span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm">{r.name}</span>
                        <span className="mono block truncate text-xs text-fg3">{r.path ?? r.workspace_id}</span>
                      </span>
                      {job?.summary && <MiniBar job={job} />}
                      <span className="w-14 flex-none text-right text-xs text-fg3">{fmtAgo((r.opened ?? job?.started) as number | null)}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </section>
          <section aria-label="Recent jobs">
            <h2 className="mb-3 text-sm font-medium text-fg2">Previous runs</h2>
            <ul className="surface divide-y divide-line overflow-hidden rounded-[14px]">
              {s.jobs.length === 0 && <li className="px-4 py-5 text-sm text-fg3">Finished runs are saved. Replay one here without re-running anything.</li>}
              {s.jobs.slice(0, 5).map((j) => (
                <li key={j.job_id} className="flex items-center gap-3 px-4 py-2.5">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm">{j.name}</span>
                    <span className="block truncate text-xs text-fg3">
                      {j.state}{j.summary ? ` · ${j.summary.verified + j.summary.guarded} accelerated` : ''}{j.summary?.e2e_speedup ? ` · ${fmtX(j.summary.e2e_speedup)} end to end` : ''}
                    </span>
                  </span>
                  <Btn kind="ghost" onClick={() => s.openJob(j.job_id)}>Open</Btn>
                  <Btn onClick={() => s.openJob(j.job_id, { replay: true })} title="Replay the saved event log with pacing"><RotateCcw size={12} /> Replay</Btn>
                </li>
              ))}
            </ul>
            {s.starting && <div className="mt-3 space-y-2" aria-busy><Skeleton className="h-4 w-2/3" /><Skeleton className="h-4 w-1/2" /></div>}
            {s.startError && <p role="alert" className="mt-3 text-sm text-bad">{s.startError}</p>}
          </section>
        </div>
      </div>
      {picker && <FolderPicker onClose={() => setPicker(false)} onPick={(p) => { setPath(p); setPicker(false) }} />}
    </div>
  )
}

export function Toggle({ on, onClick, label }: { on: boolean; onClick: () => void; label: string }) {
  return (
    <button role="switch" aria-checked={on} aria-label={label} onClick={onClick} className={cn('relative h-5 w-9 flex-none rounded-full border transition-colors', on ? 'border-accent bg-accent/35' : 'border-line2 bg-bg')}>
      <span className={cn('absolute top-[2px] h-3.5 w-3.5 rounded-full transition-all', on ? 'left-[18px] bg-accent' : 'left-[2px] bg-fg3')} />
    </button>
  )
}

function Chip({ children, ok, icon }: { children: ReactNode; ok?: boolean; icon?: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1', ok ? 'border-line2 bg-raised text-fg2' : 'border-line bg-transparent text-fg3')}>
      <span className={cn(ok ? 'text-ok' : 'text-fg3')}>{icon}</span>
      {children}
    </span>
  )
}

function MiniBar({ job }: { job: JobInfo }) {
  const s = job.summary!
  const parts = [
    ['bg-ok', s.verified],
    ['bg-warn', s.guarded],
    ['bg-fg3/50', s.declined + s.not_eligible],
    ['bg-bad', s.failed],
  ] as const
  const tot = Math.max(1, parts.reduce((a, [, n]) => a + n, 0))
  return (
    <span className="hidden w-24 flex-none sm:block" title={`${s.verified} verified, ${s.guarded} guarded, ${s.declined + s.not_eligible} stopped, ${s.failed} failed`}>
      <span className="flex h-1.5 overflow-hidden rounded-full bg-hover">
        {parts.map(([c, n], i) => n > 0 && <span key={i} className={c} style={{ width: `${(n / tot) * 100}%` }} />)}
      </span>
      <span className="tnum mt-1 block text-right text-2xs text-fg3">{s.e2e_speedup ? fmtX(s.e2e_speedup) : `${s.functions} fn`}</span>
    </span>
  )
}

function Tile({ icon, title, desc, children, i }: { icon: ReactNode; title: string; desc: string; children: ReactNode; i: number }) {
  return (
    <motion.div {...rise(5 + i)} className="min-h-[196px]">
      <GlowCard className="h-full p-4">
        <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-[10px] border border-line2 bg-bg text-accent shadow-[inset_0_1px_0_rgb(var(--hl)/0.05)]">{icon}</div>
        <h3 className="text-base font-medium">{title}</h3>
        <p className="mb-3 text-sm text-fg3">{desc}</p>
        {children}
      </GlowCard>
    </motion.div>
  )
}

function FolderPicker({ onClose, onPick }: { onClose: () => void; onPick: (p: string) => void }) {
  const [data, setData] = useState<FsList | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const go = (p: string) => {
    setData(null)
    api.fsList(p).then((d) => (setData(d), setErr(null))).catch((e) => setErr(errMsg(e)))
  }
  useEffect(() => go('~'), [])
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/55 pt-[12vh] backdrop-blur-[2px]" onClick={onClose} role="dialog" aria-modal aria-label="Choose a folder">
      <div className="surface-2 w-[520px] max-w-[92vw] animate-fadeIn overflow-hidden rounded-[14px]" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-line px-4 py-3">
          <h2 className="text-base font-medium">Choose a folder</h2>
          <button onClick={onClose} aria-label="Close" className="ml-auto rounded p-1 text-fg3 hover:bg-hover hover:text-fg"><X size={14} /></button>
        </div>
        <div className="mono border-b border-line px-4 py-2 text-xs text-fg2">{data?.path ?? '…'}</div>
        <div className="h-[300px] overflow-auto py-1">
          {err ? <p className="p-4 text-sm text-bad">{err}</p> : !data ? <div className="space-y-2 p-4"><Skeleton className="h-4" /><Skeleton className="h-4 w-2/3" /><Skeleton className="h-4 w-1/2" /></div> : (
            <ul>
              {data.parent && <li><button onClick={() => go(data.parent!)} className="flex w-full items-center gap-2 px-4 py-1.5 text-left text-sm text-fg2 hover:bg-hover/60"><ChevronUp size={14} /> Up one level</button></li>}
              {data.entries.map((e) => (
                <li key={e.name}>
                  {e.type === 'dir' ? (
                    <button onClick={() => go(`${data.path.replace(/\/$/, '')}/${e.name}`)} className="flex w-full items-center gap-2 px-4 py-1.5 text-left text-sm hover:bg-hover/60"><Folder size={14} className="text-fg3" />{e.name}</button>
                  ) : (
                    <div className="flex items-center gap-2 px-4 py-1.5 text-sm text-fg3"><FileCode2 size={14} />{e.name}</div>
                  )}
                </li>
              ))}
              {data.entries.length === 0 && <li className="p-4 text-sm text-fg3">This folder is empty.</li>}
            </ul>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-line px-4 py-3">
          <Btn onClick={onClose}>Cancel</Btn>
          <Btn kind="primary" disabled={!data} onClick={() => data && onPick(data.path)}>Select this folder</Btn>
        </div>
      </div>
    </div>
  )
}
