import { MicLauncherButton } from '../voice/MicLauncherButton'
import { Button, Card } from '../ui'
import { KeyboardKey } from '../ui/KeyboardKey'
import type { VoiceCaptureState } from '../../types/voice'

export type TranscriptionViewProps = {
  userDisplayName: string
  state: VoiceCaptureState
  statusText: string
  errorMessage?: string | null
  onMicActivate: () => void
  /**
   * false в Electron-панели: запись только в отдельном виджете-капсуле.
   * true в браузере / однооконном режиме: микрофон на этом экране.
   */
  showRecordingCapsule: boolean
}

const MOCK_TODAY = [
  { time: '09:12', text: 'Раз-раз, проверка.' },
  { time: '11:47', text: 'Нужно отправить черновик до обеда.' },
  { time: '14:03', text: 'Запиши встреку на завтра в десять.' },
]

/**
 * Главный экран: приветствие, шорткат, опционально микрофон, сводные карточки.
 */
export function TranscriptionView({
  userDisplayName,
  state,
  statusText,
  errorMessage,
  onMicActivate,
  showRecordingCapsule,
}: TranscriptionViewProps) {
  const micDisabled = state === 'processing'
  const statusHint = showRecordingCapsule
    ? state === 'idle'
      ? 'Нажмите на микрофон, чтобы начать запись'
      : state === 'recording'
        ? 'Нажмите снова, чтобы остановить'
        : state === 'processing'
          ? 'Подождите…'
          : state === 'error'
            ? 'Нажмите на иконку, чтобы сбросить'
            : statusText
    : 'Запись — в плавающей капсуле на экране (рядом с этим окном). Статус ниже синхронизируется с бэкендом.'

  return (
    <div className="flex min-h-0 flex-col gap-6 p-6 pb-10">
      <header className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-white/95 sm:text-3xl">
          Привет, {userDisplayName}. Снова в поток с{' '}
          <span className="inline-flex flex-wrap items-center gap-1.5 align-middle">
            <KeyboardKey label="F8" />
          </span>
        </h1>
        <p className="max-w-xl text-sm leading-relaxed text-zinc-500 dark:text-white/45">
          Глобальный хоткей:{' '}
          <span className="inline-flex items-center gap-1 font-medium text-zinc-700 dark:text-white/70">
            <KeyboardKey label="F8" />
          </span>
          . Можно изменить в `config/config.json` через поле `hotkey`.
        </p>
      </header>

      {showRecordingCapsule ? (
        <Card className="flex flex-col items-center gap-5 px-6 py-10 sm:px-10">
          <MicLauncherButton
            state={state}
            micDisabled={micDisabled}
            onMicActivate={onMicActivate}
          />
          <div className="space-y-1 text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500 dark:text-white/40">
              Статус
            </p>
            <p className="text-sm font-medium text-zinc-800 dark:text-white/85">
              {statusText}
            </p>
            <p className="text-xs text-zinc-500 dark:text-white/45">{statusHint}</p>
            {state === 'error' && errorMessage ? (
              <p className="text-xs text-red-600 dark:text-red-300/90">
                {errorMessage}
              </p>
            ) : null}
          </div>
          {state === 'error' ? (
            <Button variant="secondary" className="min-w-40" onClick={onMicActivate}>
              Повторить
            </Button>
          ) : null}
        </Card>
      ) : (
        <Card className="space-y-3 px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500 dark:text-white/40">
            Запись
          </p>
          <p className="text-sm text-zinc-700 dark:text-white/75">{statusHint}</p>
          <div className="rounded-xl border border-zinc-200/70 bg-zinc-50/80 px-4 py-3 dark:border-white/10 dark:bg-zinc-900/50">
            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-white/40">
              Статус бэкенда
            </p>
            <p className="mt-1 text-sm font-medium text-zinc-900 dark:text-white/90">
              {statusText}
            </p>
            {errorMessage ? (
              <p className="mt-2 text-xs text-red-600 dark:text-red-300/90">
                {errorMessage}
              </p>
            ) : null}
          </div>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card interactive className="lg:col-span-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-white/40">
            Сегодня
          </p>
          <ul className="mt-4 divide-y divide-zinc-200/80 dark:divide-white/10">
            {MOCK_TODAY.map((row) => (
              <li
                key={row.time}
                className="flex gap-4 py-3 first:pt-0 last:pb-0"
              >
                <span className="w-14 shrink-0 font-mono text-xs text-zinc-400 dark:text-white/35">
                  {row.time}
                </span>
                <span className="text-sm text-zinc-800 dark:text-white/80">
                  {row.text}
                </span>
              </li>
            ))}
          </ul>
        </Card>

        <Card interactive>
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-white/40">
            Статистика
          </p>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500 dark:text-white/45">Слов в минуту</dt>
              <dd className="font-semibold tabular-nums text-zinc-900 dark:text-white/90">
                142
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500 dark:text-white/45">Всего слов</dt>
              <dd className="font-semibold tabular-nums text-zinc-900 dark:text-white/90">
                12 480
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500 dark:text-white/45">За неделю</dt>
              <dd className="font-semibold tabular-nums text-zinc-900 dark:text-white/90">
                3 902
              </dd>
            </div>
          </dl>
        </Card>

        <Card interactive>
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-white/40">
            Челлендж: 100 слов в день
          </p>
          <p className="mt-2 text-sm text-zinc-600 dark:text-white/55">
            Сегодня: 67 из 100 слов
          </p>
          <div
            className="mt-4 h-2 overflow-hidden rounded-full bg-zinc-200/90 dark:bg-white/10"
            role="progressbar"
            aria-valuenow={67}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400 dark:from-emerald-400 dark:to-teal-300"
              style={{ width: '67%' }}
            />
          </div>
        </Card>
      </div>
    </div>
  )
}
