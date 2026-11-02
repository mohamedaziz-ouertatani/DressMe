import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from './api/client'
import type { TryOnResult } from './api/types'
import type { ProgressPiece } from './ui/TryOnProgress'

// The try-on in progress, kept ABOVE the pages (mounted in AppShell): it takes a few
// minutes, so the user can keep browsing while it runs. The try-on page starts it and
// shows its result; the front panel (ui/TryOnPanel) and the floating pill follow it.

export type TryOnState = 'running' | 'done' | 'fallback' | 'failed' | 'stopped'

export interface TryOnJob {
  backTo: string               // the try-on page (with its ?items=) that started it
  personUrl: string            // the job's own copy of the photo (kept while browsing)
  person: File
  pieces: ProgressPiece[]      // what is being put on, in dressing order
  secondsPer: number
  startedAt: number
  state: TryOnState
  result?: TryOnResult
  tookSeconds?: number
  why?: string                 // the backend's reason when it fell back to the 2D preview
  error?: unknown
}

interface StartArgs {
  backTo: string; person: File; pieces: ProgressPiece[]; secondsPer: number
  itemIds: string[]; candidate?: string
}

interface TryOnCtx {
  job: TryOnJob | null
  panelOpen: boolean
  start: (args: StartArgs) => void
  cancel: () => void
  dismiss: () => void          // forget the job (and its photo)
  openPanel: () => void
  minimise: () => void         // "Keep browsing"
}

const Ctx = createContext<TryOnCtx | null>(null)

export function TryOnProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const [job, setJob] = useState<TryOnJob | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const abort = useRef<AbortController | null>(null)
  const panelRef = useRef(false)
  panelRef.current = panelOpen

  // the photo URL belongs to the job: freed when the job is replaced or forgotten
  useEffect(() => () => { if (job) URL.revokeObjectURL(job.personUrl) }, [job?.personUrl])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => abort.current?.abort(), [])       // logging out stops waiting

  const start = useCallback(({ backTo, person, pieces, secondsPer, itemIds, candidate }: StartArgs) => {
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    const startedAt = Date.now()
    setJob({ backTo, person, personUrl: URL.createObjectURL(person), pieces, secondsPer, startedAt, state: 'running' })
    setPanelOpen(true)

    const finish = (patch: Partial<TryOnJob>) => {
      if (abort.current !== controller) return             // stopped or replaced meanwhile
      abort.current = null
      setJob((j) => (j ? { ...j, ...patch } : j))
      // the user was watching: take them to the result
      if (panelRef.current) {
        setPanelOpen(false)
        navigate(backTo)
      }
    }
    api.tryOn(person, itemIds, candidate, controller.signal)
      .then((result) => finish({ state: 'done', result, tookSeconds: (Date.now() - startedAt) / 1000 }))
      .catch((e) => {
        if (controller.signal.aborted) return
        // the AI is off (503), failed or over quota (502), or we're offline: the 2D preview
        if (e instanceof ApiError && [0, 502, 503].includes(e.status)) {
          finish({ state: 'fallback', why: e.status === 0 ? '' : e.message })
        } else {
          finish({ state: 'failed', error: e })
        }
      })
  }, [navigate])

  const cancel = useCallback(() => {
    abort.current?.abort()
    abort.current = null
    setPanelOpen(false)
    setJob((j) => (j && j.state === 'running' ? { ...j, state: 'stopped' } : j))
  }, [])

  const dismiss = useCallback(() => {
    abort.current?.abort()
    abort.current = null
    setPanelOpen(false)
    setJob(null)
  }, [])

  const value: TryOnCtx = {
    job, panelOpen, start, cancel, dismiss,
    openPanel: useCallback(() => setPanelOpen(true), []),
    minimise: useCallback(() => setPanelOpen(false), []),
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useTryOn(): TryOnCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useTryOn outside TryOnProvider')
  return ctx
}
