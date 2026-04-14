import type { GhostAppSettings } from '../types/settings'
import { defaultGhostAppSettings } from '../types/settings'

const delay = (ms: number) =>
  new Promise<void>((resolve) => {
    setTimeout(resolve, ms)
  })

/** Общее хранилище между окнами Electron (два renderer-процесса). */
export const GHOST_UI_SETTINGS_STORAGE_KEY = 'ghost_writer_ui_settings_v1'

function readStoredSettings(): GhostAppSettings {
  try {
    if (typeof localStorage !== 'undefined') {
      const raw = localStorage.getItem(GHOST_UI_SETTINGS_STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<GhostAppSettings>
        return { ...defaultGhostAppSettings, ...parsed }
      }
    }
  } catch {
    /* ignore */
  }
  return { ...defaultGhostAppSettings }
}

function writeStoredSettings(next: GhostAppSettings): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(GHOST_UI_SETTINGS_STORAGE_KEY, JSON.stringify(next))
    }
  } catch {
    /* ignore */
  }
}

let memorySettings: GhostAppSettings = readStoredSettings()

/**
 * Mock IPC: replace internals с `ipcRenderer.invoke` при подключении main-процесса.
 * Настройки дублируются в `localStorage`, чтобы панель и виджет-капсула читали одно состояние.
 */
export const ghostIpc = {
  async startRecording(): Promise<{ ok: true }> {
    await delay(320 + Math.random() * 400)
    return { ok: true }
  },

  async stopRecording(): Promise<{ ok: true; detail: string | null }> {
    await delay(480 + Math.random() * 520)
    return { ok: true, detail: 'Здесь появился бы распознанный текст.' }
  },

  async getSettings(): Promise<GhostAppSettings> {
    await delay(280 + Math.random() * 220)
    memorySettings = { ...defaultGhostAppSettings, ...readStoredSettings() }
    return { ...defaultGhostAppSettings, ...memorySettings }
  },

  async saveSettings(
    partial: Partial<GhostAppSettings>,
  ): Promise<GhostAppSettings> {
    await delay(360 + Math.random() * 280)
    memorySettings = {
      ...defaultGhostAppSettings,
      ...memorySettings,
      ...partial,
    }
    writeStoredSettings(memorySettings)
    return { ...memorySettings }
  },
}
