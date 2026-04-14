import { useCallback, useEffect, useState } from 'react'
import type { GhostStatusPayload } from './wispr-shell'
import { Home, type HomeVoiceState } from './components/Home'
import { SettingsLayout } from './components/Settings/SettingsLayout'
import { ghostIpc } from './services/ipc'
import type { GhostAppSettings } from './types/settings'
import { defaultGhostAppSettings } from './types/settings'

type ActiveView = 'home' | 'settings'

function mapGhostStatusToVoiceState(status: string): HomeVoiceState {
  if (status === 'Recording') return 'recording'
  if (status === 'Processing') return 'processing'
  if (status === 'Error') return 'error'
  return 'idle'
}

function statusLabel(state: HomeVoiceState, detail: string | null): string {
  if (state === 'recording') {
    return 'Listening…'
  }
  if (state === 'processing') {
    const d = detail?.trim()
    if (d) return d
    return 'Transcribing…'
  }
  if (state === 'error') return 'Something went wrong'
  return 'Ready'
}

export default function App() {
  const [shell] = useState(
    () => typeof window !== 'undefined' && window.wisprShell != null,
  )
  const [activeView, setActiveView] = useState<ActiveView>('home')
  const [ghostSettings, setGhostSettings] =
    useState<GhostAppSettings>(defaultGhostAppSettings)
  const [voiceState, setVoiceState] = useState<HomeVoiceState>('idle')
  const [statusDetail, setStatusDetail] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const backendControlled = shell

  useEffect(() => {
    document.documentElement.classList.toggle(
      'dark',
      ghostSettings.theme === 'dark',
    )
  }, [ghostSettings.theme])

  useEffect(() => {
    if (!shell) return
    document.documentElement.classList.add('wispr-electron-shell')
    document.body.classList.add('wispr-electron-shell')
    return () => {
      document.documentElement.classList.remove('wispr-electron-shell')
      document.body.classList.remove('wispr-electron-shell')
    }
  }, [shell])

  useEffect(() => {
    if (!shell || !window.wisprShell?.setShellLayout) return
    window.wisprShell.setShellLayout(
      activeView === 'settings' ? 'settings' : 'compact',
    )
  }, [shell, activeView])

  useEffect(() => {
    if (!shell || activeView !== 'home' || !window.wisprShell?.setWindowPassthrough)
      return

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
  }, [shell, activeView])

  useEffect(() => {
    if (!shell || !window.wisprShell?.onGhostStatus) return
    return window.wisprShell.onGhostStatus((msg: GhostStatusPayload) => {
      setVoiceState(mapGhostStatusToVoiceState(msg.status))
      setStatusDetail(msg.detail)
      if (msg.status === 'Error') {
        setErrorMessage(msg.detail ?? 'Unexpected error from backend.')
      } else {
        setErrorMessage(null)
      }
    })
  }, [shell])

  useEffect(() => {
    if (activeView !== 'settings') return
    void ghostIpc.getSettings().then(setGhostSettings)
  }, [activeView])

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
        setErrorMessage('Could not finish transcription.')
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
      setErrorMessage('Could not start recording.')
    }
  }, [backendControlled, voiceState])

  const openSettings = useCallback(() => {
    setActiveView('settings')
  }, [])

  const closeSettings = useCallback(() => {
    setActiveView('home')
  }, [])

  return (
    <div
      className={
        shell
          ? 'relative h-full min-h-svh w-full overflow-hidden bg-transparent text-zinc-900 dark:text-white'
          : 'relative min-h-svh overflow-hidden bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-white'
      }
    >
      {!shell && (
        <>
          <div
            className="pointer-events-none absolute inset-0 opacity-40 dark:opacity-40"
            style={{
              backgroundImage:
                'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(120, 119, 198, 0.35), transparent)',
            }}
          />
          <div
            className="pointer-events-none absolute inset-0 opacity-30 dark:opacity-30"
            style={{
              backgroundImage:
                'radial-gradient(circle at 50% 100%, rgba(59, 130, 246, 0.12), transparent 55%)',
            }}
          />
        </>
      )}

      {activeView === 'home' ? (
        <Home
          compact={shell}
          state={voiceState}
          statusText={statusLabel(voiceState, statusDetail)}
          errorMessage={errorMessage}
          onOpenSettings={openSettings}
          onMicActivate={handleMicActivate}
        />
      ) : (
        <div className="h-svh min-h-0 p-3">
          <SettingsLayout
            initialSettings={ghostSettings}
            onClose={closeSettings}
            onSettingsUpdated={setGhostSettings}
          />
        </div>
      )}

      {!shell && import.meta.env.DEV && activeView === 'home' ? (
        <p className="fixed bottom-6 left-1/2 z-40 max-w-md -translate-x-1/2 px-4 text-center text-xs leading-relaxed text-zinc-600 dark:text-white/45">
          Mock mode: tap the microphone to exercise idle → listening →
          transcribing. Open settings to resize the Electron shell when packaged.
        </p>
      ) : null}

      {shell && import.meta.env.DEV && activeView === 'home' ? (
        <p className="pointer-events-none fixed left-1/2 top-2 z-40 max-w-md -translate-x-1/2 px-3 text-center text-[11px] text-white/35">
          Python drives status in this shell · Alt/Option+Space still fires global
          listening events
        </p>
      ) : null}
    </div>
  )
}
