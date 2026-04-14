export {}

export type GhostStatusPayload = {
  status: string
  detail: string | null
}

export type GhostShellLayoutMode = 'compact' | 'settings'

export type GhostAudioInputDevice = {
  index: number
  name: string
  is_default: boolean
}

export type GhostAudioInputsPayload = {
  devices: GhostAudioInputDevice[]
  defaultIndex: number | null
  currentIndex: number | null
}

declare global {
  interface Window {
    /** Публикуется из `electron/preload.cjs` только в десктопной оболочке */
    wisprShell?: {
      platform: NodeJS.Platform
      onGlobalListening: (callback: () => void) => () => void
      setWindowPassthrough: (enabled: boolean) => void
      onGhostStatus: (callback: (msg: GhostStatusPayload) => void) => () => void
      setShellLayout?: (mode: GhostShellLayoutMode) => void
      listAudioInputs?: () => Promise<GhostAudioInputsPayload>
      setAudioInputDevice?: (
        deviceIndex: number | null,
      ) => Promise<{ currentIndex: number | null }>
    }
  }
}
