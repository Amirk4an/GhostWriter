import type { GhostAppSettings } from '../types/settings'
import { defaultGhostAppSettings } from '../types/settings'

const delay = (ms: number) =>
  new Promise<void>((resolve) => {
    setTimeout(resolve, ms)
  })

let memorySettings: GhostAppSettings = { ...defaultGhostAppSettings }

/**
 * Mock IPC: replace internals with `ipcRenderer.invoke` when wiring the real main process.
 */
export const ghostIpc = {
  async startRecording(): Promise<{ ok: true }> {
    await delay(320 + Math.random() * 400)
    return { ok: true }
  },

  async stopRecording(): Promise<{ ok: true; detail: string | null }> {
    await delay(480 + Math.random() * 520)
    return { ok: true, detail: 'Transcribed text would appear here.' }
  },

  async getSettings(): Promise<GhostAppSettings> {
    await delay(280 + Math.random() * 220)
    return { ...memorySettings }
  },

  async saveSettings(
    partial: Partial<GhostAppSettings>,
  ): Promise<GhostAppSettings> {
    await delay(360 + Math.random() * 280)
    memorySettings = { ...memorySettings, ...partial }
    return { ...memorySettings }
  },
}
