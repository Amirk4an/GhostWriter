import { useCallback, useEffect, useState } from 'react'
import { AppShell } from './components/layout/AppShell'
import { SettingsLayout } from './components/Settings/SettingsLayout'
import { RouteStubView } from './components/views/AppRouteStubs'
import { TranscriptionView } from './components/views/TranscriptionView'
import { useGhostVoiceSession } from './hooks/useGhostVoiceSession'
import {
  ghostIpc,
  GHOST_UI_SETTINGS_STORAGE_KEY,
} from './services/ipc'
import type { AppRoute } from './types/app_route'
import type { GhostAppSettings } from './types/settings'
import { defaultGhostAppSettings } from './types/settings'

export default function App() {
  const [shell] = useState(
    () => typeof window !== 'undefined' && window.wisprShell != null,
  )
  const [activeRoute, setActiveRoute] = useState<AppRoute>('transcription')
  const [ghostSettings, setGhostSettings] =
    useState<GhostAppSettings>(defaultGhostAppSettings)

  const {
    voiceState,
    errorMessage,
    handleMicActivate,
    statusText,
  } = useGhostVoiceSession({ shell })

  useEffect(() => {
    void ghostIpc.getSettings().then(setGhostSettings)
  }, [])

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== GHOST_UI_SETTINGS_STORAGE_KEY || !e.newValue) return
      try {
        const parsed = JSON.parse(e.newValue) as GhostAppSettings
        setGhostSettings({ ...defaultGhostAppSettings, ...parsed })
      } catch {
        /* ignore */
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

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
    window.wisprShell.setShellLayout('settings')
  }, [shell])

  useEffect(() => {
    if (activeRoute !== 'settings') return
    void ghostIpc.getSettings().then(setGhostSettings)
  }, [activeRoute])

  const handleToggleTheme = useCallback(() => {
    const nextTheme = ghostSettings.theme === 'dark' ? 'light' : 'dark'
    void ghostIpc.saveSettings({ theme: nextTheme }).then(setGhostSettings)
  }, [ghostSettings.theme])

  const greetingName =
    ghostSettings.displayName.trim() || 'друг'

  const mainColumn = (() => {
    switch (activeRoute) {
      case 'transcription':
        return (
          <TranscriptionView
            userDisplayName={greetingName}
            state={voiceState}
            statusText={statusText}
            errorMessage={errorMessage}
            onMicActivate={handleMicActivate}
            showRecordingCapsule={!shell}
          />
        )
      case 'settings':
        return (
          <SettingsLayout
            variant="embedded"
            initialSettings={ghostSettings}
            onSettingsUpdated={setGhostSettings}
          />
        )
      case 'llm':
      case 'contexts':
      case 'history':
      case 'help':
        return <RouteStubView route={activeRoute} />
    }
  })()

  return (
    <div
      className={
        shell
          ? 'relative box-border h-full w-full overflow-hidden bg-transparent text-zinc-900 dark:text-white'
          : 'relative box-border min-h-svh overflow-hidden bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-white'
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

      <div
        className={
          shell
            ? 'relative box-border h-full min-h-0 p-2'
            : 'relative mx-auto flex min-h-svh max-w-[1200px] flex-col p-4'
        }
      >
        <AppShell
          appTitle={ghostSettings.appTitle}
          activeRoute={activeRoute}
          onNavigate={setActiveRoute}
          theme={ghostSettings.theme}
          onToggleTheme={handleToggleTheme}
        >
          {mainColumn}
        </AppShell>
      </div>

      {!shell && import.meta.env.DEV ? (
        <p className="fixed bottom-4 left-1/2 z-40 max-w-lg -translate-x-1/2 px-4 text-center text-xs leading-relaxed text-zinc-600 dark:text-white/45">
          Режим разработки: микрофон на этом экране. В Electron запись — в
          отдельной капсуле.
        </p>
      ) : null}
    </div>
  )
}
