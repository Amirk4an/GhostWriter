export {}

export type GhostStatusPayload = {
  status: string
  detail: string | null
}

export type GhostShellLayoutMode = 'compact' | 'settings'

declare global {
  interface Window {
    /** Публикуется из `electron/preload.cjs` только в десктопной оболочке */
    wisprShell?: {
      platform: NodeJS.Platform
      onGlobalListening: (callback: () => void) => () => void
      setWindowPassthrough: (enabled: boolean) => void
      onGhostStatus: (callback: (msg: GhostStatusPayload) => void) => () => void
      setShellLayout?: (mode: GhostShellLayoutMode) => void
    }
  }
}
