import { useEffect, useRef, useState, type ReactNode } from 'react'
import { AlertTriangle, ArrowRight, Braces, FolderOpen, GitBranch, History, Play, RotateCcw, Upload, X, Folder, ChevronUp, FileCode2 } from 'lucide-react'
import { api, errMsg } from './api'
import { useStudio } from './store'
import { Btn, Skeleton } from './ui'
import { Logo } from './shell'
import { cn, fileToB64, fmtAgo, fmtX } from './lib/format'
import type { FsList, JobInput } from './types'

export function Welcome() {
  const s = useStudio()
  const [path, setPath] = useState('')
  const [url, setUrl] = useState('')
  const [cmd, setCmd] = useState('')
  const [lang, setLang] = useState('Python')
  const [picker, setPicker] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const env = s.env
  const noCompiler = env && !env.compiler.found
  const offline = s.settings?.offline ?? env?.offline ?? false
  const notPy = lang !== 'Python'

  useEffect(() => {
    s.loadRecent()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const run = (input: JobInput) => {
    if (notPy) return
    s.startJob(input, { trace_cmd: cmd.trim() || null, offline })
  }
  const chooseFile = async (f: File | undefined) => {
    if (!f) return
    run({ kind: 'file', filename: f.name, content_b64: await fileToB64(f) })
  }

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto flex min-h-full max-w-[1040px] flex-col px-8 py-10">
        <div className="mb-8 flex items-start justify-between gap-6">
          <div>
            <div className="mb-4 flex items-center gap-2.5">
              <Logo size={26} />
              <span className="text-[15px] font-semibold tracking-tight">PYTHIA Studio</span>
            </div>
            <h1 className="max-w-[640px] text-[26px] font-semibold leading-8 tracking-tight">Speed up the slow, compilable parts of your Python. Review every change.</h1>
            <p className="mt-2 max-w-[600px] text-base text-fg2">
              PYTHIA finds hot functions, compiles them to C++17, and proves each one behaves identically before you accept it. The LLM suggests, the compiler proves.
            </p>
          </div>
          <label className="flex flex-none items-center gap-2 pt-1 text-sm text-fg3">
            Language
            <select value={lang} onChange={(e) => setLang(e.target.value)} className="h-7 rounded-md border border-line2 bg-raised px-2 text-sm text-fg" aria-label="Source language">
              {['Python', 'Java', 'JavaScript', 'TypeScript', 'Go', 'Rust', 'C#'].map((l) => <option key={l}>{l}</option>)}
            </select>
          </label>
        </div>

        {noCompiler && (
          <div role="alert" className="mb-5 flex gap-3 rounded-lg border border-warn/30 bg-warn/10 p-4">
            <AlertTriangle size={18} className="mt-0.5 flex-none text-warn" />
            <div className="text-sm">
              <div className="font-medium text-fg">A C++ compiler is needed to accelerate code</div>
              <p className="mt-0.5 text-fg2">{env?.compiler.hint ?? 'Install g++ or clang++ with C++17 support, then reload.'} You can still browse, scan and trace projects, but nothing can be compiled or verified until it is installed.</p>
            </div>
          </div>
        )}
        {s.envError && (
          <div role="alert" className="mb-5 rounded-lg border border-bad/30 bg-bad/10 p-4 text-sm">
            <div className="font-medium">Cannot reach the PYTHIA server</div>
            <p className="mt-0.5 text-fg2">{s.envError} Start it with <code className="mono rounded bg-hover px-1">./studio.sh</code>, or add <code className="mono rounded bg-hover px-1">?mock=1</code> to the address to explore with sample data.</p>
          </div>
        )}
        {notPy && (
          <div className="mb-5 rounded-lg border border-line2 bg-raised p-4 text-sm text-fg2">
            Python projects supported; architecture is source-language-agnostic past the IR.
          </div>
        )}

        <div className="grid grid-cols-4 gap-4 max-xl:grid-cols-2 max-md:grid-cols-1">
          <Tile icon={<FolderOpen size={18} />} title="Open folder" desc="A project on this machine.">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                path.trim() && run({ kind: 'folder', path: path.trim() })
              }}
              className="mt-auto space-y-2"
            >
              <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="/home/you/project" aria-label="Folder path" className="mono h-8 w-full rounded-md border border-line2 bg-bg px-2 text-sm outline-none placeholder:text-fg3 focus:border-accent" />
              <div className="flex gap-2">
                <Btn onClick={() => setPicker(true)} className="flex-1"><Folder size={13} /> Browse</Btn>
                <Btn type="submit" kind="primary" disabled={!path.trim() || notPy || s.starting}>Open</Btn>
              </div>
            </form>
          </Tile>
          <Tile icon={<GitBranch size={18} />} title="Clone repository" desc="A public GitHub URL.">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                url.trim() && run({ kind: 'git', url: url.trim() })
              }}
              className="mt-auto space-y-2"
            >
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://github.com/user/repo" aria-label="Repository URL" className="mono h-8 w-full rounded-md border border-line2 bg-bg px-2 text-sm outline-none placeholder:text-fg3 focus:border-accent" />
              <Btn type="submit" kind="primary" className="w-full" disabled={!url.trim() || notPy || s.starting}>Clone and analyse</Btn>
            </form>
          </Tile>
          <Tile icon={<Upload size={18} />} title="Drop a file" desc="Drag a .py file anywhere in this window.">
            <button
              onClick={() => fileRef.current?.click()}
              className="mt-auto flex h-[74px] w-full flex-col items-center justify-center gap-0.5 rounded-md border border-dashed border-line2 text-sm text-fg3 transition-colors hover:border-accent hover:text-fg"
            >
              <span>Drop here or choose a file</span>
              <span className="text-xs">.py, up to 5 MB</span>
            </button>
            <input ref={fileRef} type="file" accept=".py,text/x-python" hidden onChange={(e) => chooseFile(e.target.files?.[0])} aria-label="Choose a Python file" />
          </Tile>
          <Tile icon={<Braces size={18} />} title="Playground" desc="Type PySub, see C++ live.">
            <Btn onClick={() => s.openSpecial('playground')} className="mt-auto w-full">Open playground <ArrowRight size={13} /></Btn>
          </Tile>
        </div>

        <div className="mt-5 grid grid-cols-[1fr_auto] items-end gap-4 rounded-lg border border-line bg-raised p-4 max-md:grid-cols-1">
          <label className="block">
            <span className="mb-1 block text-xs text-fg3">Entry command (optional, enables real hot-spot ranking)</span>
            <input value={cmd} onChange={(e) => setCmd(e.target.value)} placeholder="Entry command, e.g. python main.py --small" aria-label="Entry command" className="mono h-8 w-full rounded-md border border-line2 bg-bg px-2 text-sm outline-none placeholder:text-fg3 focus:border-accent" />
          </label>
          <div className="flex items-center gap-5">
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <button
                role="switch"
                aria-checked={offline}
                onClick={async () => {
                  const next = !offline
                  await api.putSettings({ offline: next }).catch(() => {})
                  s.loadEnv()
                }}
                className={cn('relative h-5 w-9 rounded-full border transition-colors', offline ? 'border-accent bg-accent/30' : 'border-line2 bg-bg')}
              >
                <span className={cn('absolute top-[2px] h-3.5 w-3.5 rounded-full transition-all', offline ? 'left-[18px] bg-accent' : 'left-[2px] bg-fg3')} />
              </button>
              Offline mode
            </label>
            <span className="max-w-[240px] text-xs text-fg3">{env ? env.llm.enabled ? (offline ? 'LLM rewrites replay from the offline cache.' : `LLM fixer on · ${env.llm.model}`) : env.llm.hint : 'Checking environment'}</span>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-6 max-lg:grid-cols-1">
          <section aria-label="Recent workspaces">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-medium text-fg2">Recent workspaces</h2>
            </div>
            <ul className="divide-y divide-line rounded-lg border border-line bg-raised">
              {s.recent.length === 0 && <li className="px-4 py-4 text-sm text-fg3">Nothing yet. Open the demo project to see PYTHIA end to end.</li>}
              {s.recent.slice(0, 5).map((r) => (
                <li key={r.workspace_id}>
                  <button
                    onClick={() => (r.job_id ? s.openJob(r.job_id) : r.path && run({ kind: 'folder', path: r.path }))}
                    className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-hover/50"
                  >
                    <History size={14} className="flex-none text-fg3" />
                    <span className="min-w-0 flex-1"><span className="block truncate text-sm">{r.name}</span><span className="mono block truncate text-xs text-fg3">{r.path ?? r.workspace_id}</span></span>
                    <span className="flex-none text-xs text-fg3">{fmtAgo(r.opened as number | null)}</span>
                  </button>
                </li>
              ))}
            </ul>
            <Btn onClick={() => run({ kind: 'demo' })} disabled={s.starting || notPy} className="mt-3 h-9 w-full text-base" kind="primary">
              <Play size={14} /> Open demo project
            </Btn>
            <p className="mt-1.5 text-xs text-fg3">textlab: about 60 functions with a mix of fast wins, fixable code, and code that should stay Python.</p>
          </section>
          <section aria-label="Recent jobs">
            <h2 className="mb-2 text-sm font-medium text-fg2">Previous runs</h2>
            <ul className="divide-y divide-line rounded-lg border border-line bg-raised">
              {s.jobs.length === 0 && <li className="px-4 py-4 text-sm text-fg3">Finished runs are saved. Replay one here without re-running anything.</li>}
              {s.jobs.slice(0, 6).map((j) => (
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

function Tile({ icon, title, desc, children }: { icon: ReactNode; title: string; desc: string; children: ReactNode }) {
  return (
    <section className="flex min-h-[188px] flex-col rounded-lg border border-line bg-raised p-4 transition-colors hover:border-line2">
      <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-md border border-line2 bg-bg text-accent">{icon}</div>
      <h2 className="text-base font-medium">{title}</h2>
      <p className="mb-3 text-sm text-fg3">{desc}</p>
      {children}
    </section>
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
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[12vh]" onClick={onClose} role="dialog" aria-modal aria-label="Choose a folder">
      <div className="w-[520px] max-w-[92vw] animate-fadeIn rounded-xl border border-line2 bg-panel shadow-2xl" onClick={(e) => e.stopPropagation()}>
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
