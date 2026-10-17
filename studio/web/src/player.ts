import type { StudioEvent } from './types'

/**
 * Sits between any event source (live WS, mock, saved-job replay) and the reducer.
 * instant: events flow straight through (batched). paced: events are released at a readable rhythm.
 */
const BASE_DELAY: Record<string, number> = {
  stage: 650,
  'agent.step': 420,
  'fix.attempt': 1300,
  'fix.done': 700,
  'compile.done': 520,
  'verify.result': 480,
  'bench.result': 420,
  'bench.e2e': 900,
  'rank.done': 1100,
  'scan.done': 700,
  'trace.done': 900,
  'trace.progress': 140,
  'ingest.progress': 90,
  'ingest.done': 500,
  'scan.function': 38,
  'splice.ready': 800,
  'export.done': 700,
  'job.done': 900,
  'job.start': 400,
  log: 22,
  error: 600,
}
export const BEATS = new Set(['stage', 'agent.step', 'fix.attempt', 'fix.done', 'compile.done', 'verify.result', 'bench.result', 'bench.e2e', 'rank.done', 'scan.done', 'trace.done', 'splice.ready', 'export.done', 'job.done', 'ingest.done'])

export type PlayerMode = 'instant' | 'paced'

export class Player {
  queue: StudioEvent[] = []
  mode: PlayerMode = 'instant'
  speed = 1
  paused = false
  presenter = false
  private timer: ReturnType<typeof setTimeout> | null = null
  private lastStage: string | null = null
  constructor(
    private emit: (batch: StudioEvent[]) => void,
    private notify: () => void,
  ) {}

  get pending() {
    return this.queue.length
  }

  push(e: StudioEvent | StudioEvent[]) {
    if (Array.isArray(e)) this.queue.push(...e)
    else this.queue.push(e)
    this.kick()
  }

  configure(p: { mode?: PlayerMode; speed?: number; presenter?: boolean }) {
    if (p.mode) this.mode = p.mode
    if (p.speed) this.speed = p.speed
    if (p.presenter !== undefined) this.presenter = p.presenter
    this.kick()
    this.notify()
  }

  setPaused(v: boolean) {
    this.paused = v
    if (v && this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
    this.kick()
    this.notify()
  }

  /** Release everything that is queued right now. */
  flush() {
    if (this.timer) clearTimeout(this.timer)
    this.timer = null
    if (this.queue.length) {
      const b = this.queue
      this.queue = []
      this.emit(b)
    }
    this.notify()
  }

  /** Release events up to and including the next presenter "beat". */
  stepBeat() {
    if (this.timer) clearTimeout(this.timer)
    this.timer = null
    const out: StudioEvent[] = []
    while (this.queue.length) {
      const e = this.queue.shift()!
      out.push(e)
      if (BEATS.has(e.type)) break
    }
    if (out.length) this.emit(out)
    this.notify()
    if (!this.paused) this.kick()
  }

  clear() {
    if (this.timer) clearTimeout(this.timer)
    this.timer = null
    this.queue = []
    this.notify()
  }

  private delayFor(e: StudioEvent): number {
    let d = BASE_DELAY[e.type] ?? 100
    if (e.type === 'stage' && e.data.state !== 'running') d = 380
    if (this.presenter) {
      d *= 1.5
      if (e.caption) d = Math.max(d, 1100)
    }
    return d / this.speed
  }

  private kick() {
    if (this.timer || this.paused) return
    if (!this.queue.length) return
    if (this.mode === 'instant') {
      const b = this.queue
      this.queue = []
      this.emit(b)
      this.notify()
      return
    }
    const tick = () => {
      this.timer = null
      if (this.paused || !this.queue.length) {
        this.notify()
        return
      }
      const e = this.queue.shift()!
      // coalesce runs of cheap events into one render
      const batch = [e]
      let wait = this.delayFor(e)
      if (wait < 60 / Math.max(1, this.speed)) {
        while (this.queue.length && this.delayFor(this.queue[0]) < 60 / Math.max(1, this.speed) && batch.length < 40) {
          const n = this.queue.shift()!
          batch.push(n)
          wait += this.delayFor(n)
        }
      }
      this.lastStage = e.stage
      this.emit(batch)
      this.notify()
      if (this.queue.length) this.timer = setTimeout(tick, wait)
    }
    this.timer = setTimeout(tick, 0)
  }
}
