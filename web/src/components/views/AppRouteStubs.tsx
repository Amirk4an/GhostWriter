import { Card } from '../ui'
import type { AppRoute } from '../../types/app_route'

const TITLES: Record<Exclude<AppRoute, 'transcription' | 'settings'>, string> = {
  llm: 'Постобработка LLM',
  contexts: 'Контексты',
  history: 'История',
  help: 'Справка',
}

const COPY: Record<Exclude<AppRoute, 'transcription' | 'settings'>, string> = {
  llm: 'Здесь появятся правила постобработки текста после распознавания: модель, температура и пресеты.',
  contexts: 'Сохранённые сценарии диктовки (почта, код, заметки) будут настраиваться в этом разделе.',
  history: 'Лента последних транскрипций с поиском и фильтрами подключится к бэкенду на следующем этапе.',
  help: 'Краткие инструкции, горячие клавиши и ссылки на документацию появятся здесь.',
}

export type RouteStubViewProps = {
  route: Exclude<AppRoute, 'transcription' | 'settings'>
}

/**
 * Заглушка контента для второстепенных разделов сайдбара.
 */
export function RouteStubView({ route }: RouteStubViewProps) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-6">
      <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-white/95">
        {TITLES[route]}
      </h1>
      <Card className="mt-6 max-w-2xl">
        <p className="text-sm leading-relaxed text-zinc-600 dark:text-white/55">
          {COPY[route]}
        </p>
      </Card>
    </div>
  )
}
