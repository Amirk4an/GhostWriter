export type SettingsTabId =
  | 'general'
  | 'stt'
  | 'llm'
  | 'prompts'
  | 'shortcuts'

export type SttProviderMode = 'whisper_local' | 'openai'

export type GhostAppSettings = {
  theme: 'dark' | 'light'
  /** Подпись в сайдбаре и шапке (white-label). */
  appTitle: string
  /** Имя для строки приветствия на главном экране. */
  displayName: string
  sttProvider: SttProviderMode
  openaiApiKeyPlaceholder: string
  llmEnabled: boolean
  llmModel: string
  shortcutsShowOverlay: boolean
}

export const defaultGhostAppSettings: GhostAppSettings = {
  theme: 'dark',
  appTitle: 'Ghost Writer',
  displayName: '',
  sttProvider: 'whisper_local',
  openaiApiKeyPlaceholder: '',
  llmEnabled: false,
  llmModel: 'gpt-4o-mini',
  shortcutsShowOverlay: true,
}
