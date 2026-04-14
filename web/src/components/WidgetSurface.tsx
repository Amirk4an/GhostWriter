import { useEffect, useMemo } from 'react'
import { MicLauncherButton } from './voice/MicLauncherButton'
import {
  useGhostVoiceSession,
  voiceStatusLabel,
} from '../hooks/useGhostVoiceSession'
import {
  ghostIpc,
  GHOST_UI_SETTINGS_STORAGE_KEY,
} from '../services/ipc'
import { defaultGhostAppSettings } from '../types/settings'
import type { GhostAppSettings } from '../types/settings'
import { overlayPillClassNames } from './wispr/constants'
import type { VoiceCaptureState } from '../types/voice'

function mapVoiceToOverlay(state: VoiceCaptureState): Parameters<
  typeof overlayPillClassNames
>[0] {
  if (state === 'error') return 'error'
  if (state === 'recording') return 'recording'
  if (state === 'processing') return 'processing'
  return 'idle'
}

/**
 * Отдельное компактное окно: капсула записи по центру и перетаскивание за фон окна.
 * Весь фрейм — `app-region-drag`, микрофон — `no-drag`, чтобы клики доходили до кнопки.
 */
export function WidgetSurface() {
  const shell = typeof window !== 'undefined' && window.wisprShell != null
  const { voiceState, statusDetail, errorMessage, handleMicActivate } =
    useGhostVoiceSession({ shell })
  const micDisabled = voiceState === 'processing'
  const statusText = voiceStatusLabel(voiceState, statusDetail)

  const capsuleTitle = useMemo(() => {
    const err = errorMessage ? ` — ${errorMessage}` : ''
    return `${statusText}${err}`
  }, [statusText, errorMessage])

  useEffect(() => {
    void ghostIpc.getSettings().then((s) => {
      document.documentElement.classList.toggle('dark', s.theme === 'dark')
    })
  }, [])

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== GHOST_UI_SETTINGS_STORAGE_KEY || !e.newValue) return
      try {
        const parsed = JSON.parse(e.newValue) as GhostAppSettings
        const merged = { ...defaultGhostAppSettings, ...parsed }
        document.documentElement.classList.toggle(
          'dark',
          merged.theme === 'dark',
        )
      } catch {
        /* ignore */
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  useEffect(() => {
    if (!shell || !window.wisprShell?.setWindowPassthrough) return

    const setPassthrough = window.wisprShell.setWindowPassthrough
    setPassthrough(true)

    const onMove = (e: MouseEvent) => {
      const el = document.elementFromPoint(e.clientX, e.clientY)
      const over = el?.closest('[data-wispr-hit-target]')
      setPassthrough(!over)
    }

    document.addEventListener('mousemove', onMove, { passive: true })
    return () => {
      document.removeEventListener('mousemove', onMove)
    }
  }, [shell])

  useEffect(() => {
    if (!shell) return
    document.documentElement.classList.add('wispr-electron-shell')
    document.body.classList.add('wispr-electron-shell')
    return () => {
      document.documentElement.classList.remove('wispr-electron-shell')
      document.body.classList.remove('wispr-electron-shell')
    }
  }, [shell])

  return (
    <div
      className="relative box-border flex h-full w-full min-h-0 min-w-0 flex-col"
      onContextMenu={(e) => {
        e.preventDefault()
      }}
    >
      <div
        data-wispr-hit-target
        title={capsuleTitle}
        className="app-region-drag flex min-h-0 min-w-0 flex-1 cursor-grab items-center justify-center active:cursor-grabbing"
      >
        <div
          className={`app-region-no-drag flex shrink-0 cursor-default items-center justify-center rounded-full px-2 py-1 ${overlayPillClassNames(mapVoiceToOverlay(voiceState))}`}
        >
          <MicLauncherButton
            compact
            state={voiceState}
            micDisabled={micDisabled}
            onMicActivate={handleMicActivate}
          />
        </div>
      </div>
    </div>
  )
}
