import { ArrowLeft, Moon, Sun } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import type { GhostAppSettings, SettingsTabId } from '../../types/settings'
import { SETTINGS_TABS } from './tabs'
import { Button, Card, Select, Toggle } from '../ui'
import { ghostIpc } from '../../services/ipc'

export type SettingsLayoutProps = {
  initialSettings: GhostAppSettings
  onClose: () => void
  onSettingsUpdated?: (next: GhostAppSettings) => void
}

export function SettingsLayout({
  initialSettings,
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

  return (
    <div
      data-wispr-hit-target
      className="flex h-full min-h-0 flex-col gap-3 text-zinc-900 dark:text-white/90"
    >
      <header className="app-region-drag flex shrink-0 items-center gap-3 rounded-2xl border border-zinc-200/60 bg-white/50 px-3 py-2 shadow-sm shadow-zinc-900/5 backdrop-blur-xl dark:border-white/10 dark:bg-zinc-950/45 dark:shadow-black/20">
        <Button
          variant="ghost"
          className="app-region-no-drag rounded-xl px-2 py-1.5"
          onClick={onClose}
          aria-label="Back to home"
        >
          <ArrowLeft className="size-4" strokeWidth={2} />
        </Button>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500 dark:text-white/40">
            Ghost Writer
          </p>
          <p className="truncate text-sm font-semibold">Settings</p>
        </div>
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
            aria-label="Toggle theme"
          >
            {settings.theme === 'dark' ? (
              <Sun className="size-4 text-amber-300" strokeWidth={2} />
            ) : (
              <Moon className="size-4 text-indigo-500" strokeWidth={2} />
            )}
          </Button>
        </div>
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
                <Toggle
                  label="Show shortcut overlay hints"
                  description="Surfaces non-intrusive reminders while dictating."
                  checked={settings.shortcutsShowOverlay}
                  onChange={(e) => {
                    void persist({ shortcutsShowOverlay: e.target.checked })
                  }}
                  disabled={saving}
                />
                <p className="text-xs text-zinc-500 dark:text-white/40">
                  {saving ? 'Saving…' : 'Changes sync through the mock IPC layer.'}
                </p>
              </Card>
            ) : null}

            {activeTab === 'stt' ? (
              <Card interactive className="space-y-4">
                <Select
                  label="Speech-to-text provider"
                  hint="OpenAI path is a stub until backend keys are wired."
                  value={settings.sttProvider}
                  onChange={(e) => {
                    void persist({
                      sttProvider: e.target.value as GhostAppSettings['sttProvider'],
                    })
                  }}
                  disabled={saving}
                >
                  <option value="whisper_local">Whisper (local)</option>
                  <option value="openai">OpenAI</option>
                </Select>
              </Card>
            ) : null}

            {activeTab === 'llm' ? (
              <Card interactive className="space-y-4">
                <Toggle
                  label="Enable LLM post-processing"
                  description="Runs a lightweight model pass after transcription."
                  checked={settings.llmEnabled}
                  onChange={(e) => {
                    void persist({ llmEnabled: e.target.checked })
                  }}
                  disabled={saving}
                />
                <Select
                  label="Model"
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
                  Prompt packs for Slack, Mail, and Notes will land here. For now
                  this panel reserves layout space for future form controls.
                </p>
              </Card>
            ) : null}

            {activeTab === 'shortcuts' ? (
              <Card interactive>
                <p className="text-sm text-zinc-600 dark:text-white/55">
                  Global shortcuts editor placeholder. Hook Electron accelerator
                  metadata here when the main process exposes it.
                </p>
              </Card>
            ) : null}
          </div>
        </main>
      </div>
    </div>
  )
}
