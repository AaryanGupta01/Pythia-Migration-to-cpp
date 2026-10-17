import { api, errMsg } from './api'
import { useStudio } from './store'
import { reduceAll } from './reducer'
import type { StudioEvent } from './types'

/** Apply client-originated events (e.g. export finished) through the shared reducer. */
export function applyLocal(events: Omit<StudioEvent, 'seq' | 'ts'>[]) {
  useStudio.setState((s) => {
    let seq = s.js.lastSeq
    const evs = events.map((e) => ({ ...e, seq: ++seq, ts: Date.now() / 1000 }) as StudioEvent)
    return { js: reduceAll(evs, s.js) }
  })
}

export async function exportProject(zip = false) {
  const { js, toast } = useStudio.getState()
  if (!js.jobId) return
  try {
    applyLocal([{ type: 'stage', stage: 'export', caption: 'Exporting the accelerated project.', data: { stage: 'export', state: 'running', summary: null, progress: null } }])
    if (zip) {
      window.location.href = api.exportZipUrl(js.jobId)
      applyLocal([{ type: 'stage', stage: 'export', caption: null, data: { stage: 'export', state: 'done', summary: 'zip', progress: 1 } }])
      toast('Downloading export.zip', 'ok')
      return
    }
    const r = await api.exportProject(js.jobId, undefined, false)
    const nFiles = Object.keys(js.functions).length ? new Set(Object.values(js.functions).map((f) => f.file)).size + 4 : 0
    applyLocal([
      { type: 'export.done', stage: 'export', caption: `Exported to ${r.path}`, data: { path: r.path, zip: false, files: nFiles } },
      { type: 'stage', stage: 'export', caption: null, data: { stage: 'export', state: 'done', summary: `${nFiles} files`, progress: 1 } },
    ])
    toast(`Exported to ${r.path}`, 'ok')
  } catch (e) {
    applyLocal([{ type: 'stage', stage: 'export', caption: null, data: { stage: 'export', state: 'failed', summary: null, progress: null } }])
    toast(errMsg(e), 'error')
  }
}
