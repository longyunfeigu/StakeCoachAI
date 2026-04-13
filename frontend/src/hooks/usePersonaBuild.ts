// input: 无 (caller invokes start with PersonaBuildRequest)
// output: { status, events, personaId, error, start, abort, reset } — SSE state machine
// owner: wanhua.gu
// pos: 表示层 - persona build SSE 状态机 hook (idle→running→done/error)；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
import { useCallback, useRef, useState } from 'react'
import type { BuildEvent, PersonaBuildRequest } from '../services/api'
import { startPersonaBuild } from '../services/personaBuildSSE'

export type BuildStatus = 'idle' | 'running' | 'done' | 'error'

export interface BuildErrorInfo {
  code?: string
  message: string
  status?: number
}

interface UsePersonaBuildResult {
  status: BuildStatus
  events: BuildEvent[]
  personaId: string | null
  error: BuildErrorInfo | null
  start: (req: PersonaBuildRequest) => Promise<void>
  abort: () => void
  reset: () => void
}

/**
 * Manages a single persona build SSE stream lifecycle.
 *
 * Status transitions:
 *   idle → running                       (start called)
 *   running → done                       (persist_done event received)
 *   running → error                      (error event received OR HTTP error OR stream closed prematurely)
 *
 * persist_done event sets personaId; consumers wait for status === 'done' AND
 * personaId !== null before navigating.
 */
export function usePersonaBuild(): UsePersonaBuildResult {
  const [status, setStatus] = useState<BuildStatus>('idle')
  const [events, setEvents] = useState<BuildEvent[]>([])
  const [personaId, setPersonaId] = useState<string | null>(null)
  const [error, setError] = useState<BuildErrorInfo | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const start = useCallback(async (req: PersonaBuildRequest) => {
    // Cancel any in-flight stream before starting a new one
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setStatus('running')
    setEvents([])
    setPersonaId(null)
    setError(null)

    try {
      await startPersonaBuild(
        req,
        (ev) => {
          setEvents((prev) => [...prev, ev])
          if (ev.type === 'persist_done') {
            const pid = (ev.data as { persona_id?: string }).persona_id
            if (pid) setPersonaId(pid)
            setStatus('done')
          } else if (ev.type === 'error') {
            const d = ev.data as { error_code?: string; message?: string }
            setError({
              code: d.error_code,
              message: d.message || 'Unknown error',
            })
            setStatus('error')
          }
        },
        controller.signal,
      )
      // Stream ended cleanly — if we never saw persist_done OR error, treat as error
      setStatus((cur) => {
        if (cur === 'running') {
          setError({ message: '连接关闭但未收到完成事件' })
          return 'error'
        }
        return cur
      })
    } catch (e: unknown) {
      const err = e as { name?: string; code?: string; message?: string; status?: number }
      if (err?.name === 'AbortError') {
        // user-initiated abort — caller manages status via reset() if needed
        return
      }
      setError({
        code: err?.code,
        message: err?.message || String(e),
        status: err?.status,
      })
      setStatus('error')
    } finally {
      abortRef.current = null
    }
  }, [])

  const abort = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
  }, [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setStatus('idle')
    setEvents([])
    setPersonaId(null)
    setError(null)
  }, [])

  return { status, events, personaId, error, start, abort, reset }
}
