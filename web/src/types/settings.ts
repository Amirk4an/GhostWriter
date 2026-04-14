export type SettingsTabId =
  | 'general'
  | 'stt'
  | 'llm'
  | 'prompts'
  | 'shortcuts'

export type SttProviderMode = 'whisper_local' | 'openai'

export type GhostAppSettings = {
  theme: 'dark' | 'light'
  sttProvider: SttProviderMode
  openaiApiKeyPlaceholder: string
  llmEnabled: boolean
  llmModel: string
  shortcutsShowOverlay: boolean
}

export const defaultGhostAppSettings: GhostAppSettings = {
  theme: 'dark',
  sttProvider: 'whisper_local',
  openaiApiKeyPlaceholder: '',
  llmEnabled: false,
  llmModel: 'gpt-4o-mini',
  shortcutsShowOverlay: true,
}
