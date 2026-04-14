import type { SettingsTabId } from '../../types/settings'

export type SettingsTabDef = {
  id: SettingsTabId
  label: string
  description: string
}

export const SETTINGS_TABS: readonly SettingsTabDef[] = [
  {
    id: 'general',
    label: 'General',
    description: 'Appearance, startup behavior, and defaults.',
  },
  {
    id: 'stt',
    label: 'STT Providers',
    description: 'Whisper on-device vs cloud transcription.',
  },
  {
    id: 'llm',
    label: 'LLM Post-processing',
    description: 'Optional cleanup and formatting after STT.',
  },
  {
    id: 'prompts',
    label: 'App Prompts',
    description: 'Context packs for Slack, Mail, and more.',
  },
  {
    id: 'shortcuts',
    label: 'Shortcuts',
    description: 'Global hotkeys and overlay visibility.',
  },
] as const
