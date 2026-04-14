import type { SettingsTabId } from '../../types/settings'

export type SettingsTabDef = {
  id: SettingsTabId
  label: string
  description: string
}

export const SETTINGS_TABS: readonly SettingsTabDef[] = [
  {
    id: 'general',
    label: 'Общие',
    description: 'Оформление, поведение при запуске и значения по умолчанию.',
  },
  {
    id: 'stt',
    label: 'Распознавание речи',
    description: 'Whisper на устройстве или облачная транскрипция.',
  },
  {
    id: 'llm',
    label: 'Постобработка LLM',
    description: 'Дополнительная очистка и форматирование после STT.',
  },
  {
    id: 'prompts',
    label: 'Промпты приложений',
    description: 'Контекстные наборы для Slack, почты и других программ.',
  },
  {
    id: 'shortcuts',
    label: 'Сочетания клавиш',
    description: 'Глобальные горячие клавиши и подсказки поверх окон.',
  },
] as const
