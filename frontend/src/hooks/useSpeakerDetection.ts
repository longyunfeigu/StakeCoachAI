import { useState, useCallback } from 'react'
import { detectSpeakers, type DetectedSpeaker } from '../services/api'

export type DetectionStatus = 'idle' | 'detecting' | 'done' | 'error'

export interface UseSpeakerDetectionResult {
  status: DetectionStatus
  speakers: DetectedSpeaker[]
  error: string | null
  detect: (materials: string[]) => Promise<void>
  reset: () => void
}

export function useSpeakerDetection(): UseSpeakerDetectionResult {
  const [status, setStatus] = useState<DetectionStatus>('idle')
  const [speakers, setSpeakers] = useState<DetectedSpeaker[]>([])
  const [error, setError] = useState<string | null>(null)

  const detect = useCallback(async (materials: string[]) => {
    setStatus('detecting')
    setError(null)
    setSpeakers([])
    try {
      const result = await detectSpeakers(materials)
      setSpeakers(result)
      setStatus('done')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }, [])

  const reset = useCallback(() => {
    setStatus('idle')
    setSpeakers([])
    setError(null)
  }, [])

  return { status, speakers, error, detect, reset }
}
