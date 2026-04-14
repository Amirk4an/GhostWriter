import { useCallback, useEffect, useState } from 'react'
import type { GhostStatusPayload } from '../wispr-shell'
import { ghostIpc } from '../services/ipc'
import type { VoiceCaptureState } from '../types/voice'

function mapGhostStatusToVoiceState(status: string): VoiceCaptureState {
  if (status === 'Recording') return 'recording'
  if (status === 'Processing') return 'processing'
  if (status === 'Error') return 'error'
  return 'idle'
}

export function voiceStatusLabel(
  state: VoiceCaptureState,
  detail: string | null,
): string {
  if (state === 'recording') {
    return 'Слушаю…'
  }
  if (state === 'processing') {
    const d = detail?.trim()
    if (d) return d
    return 'Распознаю речь…'
  }
  if (state === 'error') return 'Что-то пошло не так'
  return 'Готово'
}

export type UseGhostVoiceSessionOptions = {
  /** Режим Electron: состояние приходит с бэкенда, локальный цикл микрофона отключён. */
  shell: boolean
}

/**
 * Состояние записи/распознавания и обработчик клика по микрофону (мок IPC или бэкенд).
 */
export function useGhostVoiceSession({ shell }: UseGhostVoiceSessionOptions) {
  const backendControlled = shell
  const [voiceState, setVoiceState] = useState<VoiceCaptureState>('idle')
  const [statusDetail, setStatusDetail] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!shell || !window.wisprShell?.onGhostStatus) return
    return window.wisprShell.onGhostStatus((msg: GhostStatusPayload) => {
      setVoiceState(mapGhostStatusToVoiceState(msg.status))
      setStatusDetail(msg.detail)
      if (msg.status === 'Error') {
        setErrorMessage(msg.detail ?? 'Неожиданная ошибка бэкенда.')
      } else {
        setErrorMessage(null)
      }
    })
  }, [shell])

  const handleMicActivate = useCallback(async () => {
    if (backendControlled) return
    if (voiceState === 'processing') return
    if (voiceState === 'error') {
      setVoiceState('idle')
      setErrorMessage(null)
      return
    }
    if (voiceState === 'recording') {
      setVoiceState('processing')
      try {
        const res = await ghostIpc.stopRecording()
        setStatusDetail(res.detail)
      } catch {
        setVoiceState('error')
        setErrorMessage('Не удалось завершить распознавание.')
        return
      }
      setVoiceState('idle')
      return
    }
    setVoiceState('recording')
    setErrorMessage(null)
    try {
      await ghostIpc.startRecording()
    } catch {
      setVoiceState('error')
      setErrorMessage('Не удалось начать запись.')
    }
  }, [backendControlled, voiceState])

  return {
    voiceState,
    statusDetail,
    errorMessage,
    handleMicActivate,
    statusText: voiceStatusLabel(voiceState, statusDetail),
  }
}
