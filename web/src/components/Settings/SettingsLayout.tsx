import { ArrowLeft, Moon, Sun } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import type { GhostAppSettings, SettingsTabId } from '../../types/settings'
import { SETTINGS_TABS } from './tabs'
import { Button, Card, Select, Toggle } from '../ui'
import { ghostIpc } from '../../services/ipc'

const fieldClass =
  'mt-1 w-full rounded-xl border border-zinc-200/80 bg-white/80 px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none transition-colors placeholder:text-zinc-400 focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20 dark:border-white/10 dark:bg-zinc-900/60 dark:text-white/90 dark:placeholder:text-white/35 dark:focus:border-emerald-400/40'

export type SettingsLayoutProps = {
  initialSettings: GhostAppSettings
  /** В режиме `modal` — кнопка «Назад» и отдельный переключатель темы в шапке. */
  variant?: 'modal' | 'embedded'
  onClose?: () => void
  onSettingsUpdated?: (next: GhostAppSettings) => void
}

export function SettingsLayout({
  initialSettings,
  variant = 'embedded',
  onClose,
  onSettingsUpdated,
}: SettingsLayoutProps) {
  const [activeTab, setActiveTab] = useState<SettingsTabId>('general')
  const [settings, setSettings] = useState<GhostAppSettings>(initialSettings)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setSettings(initialSettings)
  }, [initialSettings])

  const persist = useCallback(async (partial: Partial<GhostAppSettings>) => {
    setSaving(true)
    try {
      const next = await ghostIpc.saveSettings(partial)
      setSettings(next)
      onSettingsUpdated?.(next)
    } finally {
      setSaving(false)
    }
  }, [onSettingsUpdated])

  const active = SETTINGS_TABS.find((t) => t.id === activeTab)
  const isModal = variant === 'modal'

  return (
    <div
      data-wispr-hit-target
      className="flex h-full min-h-0 flex-col gap-3 text-zinc-900 dark:text-white/90"
    >
      <header className="app-region-drag flex shrink-0 items-center gap-3 rounded-2xl border border-zinc-200/60 bg-white/50 px-3 py-2 shadow-sm shadow-zinc-900/5 backdrop-blur-xl dark:border-white/10 dark:bg-zinc-950/45 dark:shadow-black/20">
        {isModal ? (
          <Button
            variant="ghost"
            className="app-region-no-drag rounded-xl px-2 py-1.5"
            onClick={onClose}
            aria-label="Назад на главный экран"
          >
            <ArrowLeft className="size-4" strokeWidth={2} />
          </Button>
        ) : (
          <span className="w-9 shrink-0" aria-hidden />
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">Настройки</p>
        </div>
        {isModal ? (
          <div className="app-region-no-drag flex items-center gap-2">
            <Button
              variant="ghost"
              className="rounded-xl px-2 py-1.5"
              type="button"
              onClick={() => {
                void persist({
                  theme: settings.theme === 'dark' ? 'light' : 'dark',
                })
              }}
              aria-label="Переключить тему"
            >
              {settings.theme === 'dark' ? (
                <Sun className="size-4 text-amber-300" strokeWidth={2} />
              ) : (
                <Moon className="size-4 text-indigo-500" strokeWidth={2} />
              )}
            </Button>
          </div>
        ) : (
          <span className="w-9 shrink-0" aria-hidden />
        )}
      </header>

      <div className="flex min-h-0 flex-1 gap-3 overflow-hidden">
        <aside
          data-wispr-hit-target
          className="app-region-no-drag flex w-52 shrink-0 flex-col gap-1 overflow-y-auto rounded-2xl border border-zinc-200/60 bg-white/50 p-2 shadow-sm shadow-zinc-900/5 backdrop-blur-xl dark:border-white/10 dark:bg-zinc-950/45 dark:shadow-black/20"
        >
          {SETTINGS_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              data-wispr-hit-target
              onClick={() => {
                setActiveTab(tab.id)
              }}
              className={`rounded-xl px-3 py-2 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/45 ${
                tab.id === activeTab
                  ? 'bg-emerald-500/15 text-emerald-900 dark:bg-emerald-400/10 dark:text-emerald-100'
                  : 'text-zinc-600 hover:bg-zinc-950/[0.04] dark:text-white/65 dark:hover:bg-white/[0.06]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </aside>

        <main
          data-wispr-hit-target
          className="app-region-no-drag min-h-0 flex-1 overflow-y-auto rounded-2xl border border-zinc-200/60 bg-white/50 p-4 shadow-sm shadow-zinc-900/5 backdrop-blur-xl dark:border-white/10 dark:bg-zinc-950/45 dark:shadow-black/20"
        >
          <div className="mx-auto max-w-xl space-y-4">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">
                {active?.label}
              </h2>
              <p className="mt-1 text-sm text-zinc-600 dark:text-white/50">
                {active?.description}
              </p>
            </div>

            {activeTab === 'general' ? (
              <Card interactive className="space-y-4">
                <div>
                  <label
                    htmlFor="gw-app-title"
                    className="text-sm font-medium text-zinc-800 dark:text-white/85"
                  >
                    Название в интерфейсе
                  </label>
                  <input
                    id="gw-app-title"
                    type="text"
                    className={fieldClass}
                    value={settings.appTitle}
                    onChange={(e) => {
                      void persist({ appTitle: e.target.value })
                    }}
                    disabled={saving}
                    autoComplete="off"
                  />
                  <p className="mt-1 text-xs text-zinc-500 dark:text-white/40">
                    Отображается в сайдбаре (white-label).
                  </p>
                </div>
                <div>
                  <label
                    htmlFor="gw-display-name"
                    className="text-sm font-medium text-zinc-800 dark:text-white/85"
                  >
                    Имя в приветствии
                  </label>
                  <input
                    id="gw-display-name"
                    type="text"
                    className={fieldClass}
                    value={settings.displayName}
                    onChange={(e) => {
                      void persist({ displayName: e.target.value })
                    }}
                    disabled={saving}
                    placeholder="Например, Алекс"
                    autoComplete="name"
                  />
                </div>
                <Toggle
                  label="Подсказки по сочетаниям клавиш"
                  description="Ненавязливые напоминания во время диктовки."
                  checked={settings.shortcutsShowOverlay}
                  onChange={(e) => {
                    void persist({ shortcutsShowOverlay: e.target.checked })
                  }}
                  disabled={saving}
                />
                <p className="text-xs text-zinc-500 dark:text-white/40">
                  {saving
                    ? 'Сохранение…'
                    : 'Изменения синхронизируются через тестовый слой IPC.'}
                </p>
              </Card>
            ) : null}

            {activeTab === 'stt' ? (
              <Card interactive className="space-y-4">
                <Select
                  label="Провайдер распознавания речи"
                  hint="Путь OpenAI — заглушка, пока не подключены ключи бэкенда."
                  value={settings.sttProvider}
                  onChange={(e) => {
                    void persist({
                      sttProvider: e.target.value as GhostAppSettings['sttProvider'],
                    })
                  }}
                  disabled={saving}
                >
                  <option value="whisper_local">Whisper (локально)</option>
                  <option value="openai">OpenAI</option>
                </Select>
              </Card>
            ) : null}

            {activeTab === 'llm' ? (
              <Card interactive className="space-y-4">
                <Toggle
                  label="Включить постобработку LLM"
                  description="Лёгкий проход модели после транскрипции."
                  checked={settings.llmEnabled}
                  onChange={(e) => {
                    void persist({ llmEnabled: e.target.checked })
                  }}
                  disabled={saving}
                />
                <Select
                  label="Модель"
                  value={settings.llmModel}
                  onChange={(e) => {
                    void persist({ llmModel: e.target.value })
                  }}
                  disabled={saving || !settings.llmEnabled}
                >
                  <option value="gpt-4o-mini">gpt-4o-mini</option>
                  <option value="gpt-4o">gpt-4o</option>
                </Select>
              </Card>
            ) : null}

            {activeTab === 'prompts' ? (
              <Card interactive>
                <p className="text-sm text-zinc-600 dark:text-white/55">
                  Здесь появятся наборы промптов для Slack, почты и заметок. Сейчас
                  панель резервирует место под будущие поля формы.
                </p>
              </Card>
            ) : null}

            {activeTab === 'shortcuts' ? (
              <Card interactive>
                <p className="text-sm text-zinc-600 dark:text-white/55">
                  Заглушка редактора глобальных сочетаний: сюда можно подключить
                  метаданные акселераторов Electron, когда main-процесс их отдаст.
                </p>
              </Card>
            ) : null}
          </div>
        </main>
      </div>
    </div>
  )
}
