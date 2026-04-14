import {
  BookOpen,
  HelpCircle,
  History,
  Mic,
  Moon,
  Settings,
  Sparkles,
  Sun,
} from 'lucide-react'
import type { AppRoute } from '../../types/app_route'

export type SidebarProps = {
  appTitle: string
  activeRoute: AppRoute
  onNavigate: (route: AppRoute) => void
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}

const NAV: { route: AppRoute; label: string; icon: typeof Mic }[] = [
  { route: 'transcription', label: 'Транскрипция', icon: Mic },
  { route: 'llm', label: 'Постобработка LLM', icon: Sparkles },
  { route: 'contexts', label: 'Контексты', icon: BookOpen },
  { route: 'history', label: 'История', icon: History },
  { route: 'help', label: 'Справка', icon: HelpCircle },
]

/**
 * Левое меню: разделы, настройки и переключатель темы (white-label, без подписок).
 */
export function Sidebar({
  appTitle,
  activeRoute,
  onNavigate,
  theme,
  onToggleTheme,
}: SidebarProps) {
  return (
    <aside className="flex w-[248px] shrink-0 flex-col border-r border-zinc-200/60 bg-white/40 py-4 backdrop-blur-xl dark:border-white/10 dark:bg-zinc-950/40">
      <div className="app-region-drag px-4 pb-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-400 dark:text-white/35">
          Приложение
        </p>
        <p className="mt-1 truncate text-lg font-semibold tracking-tight text-zinc-900 dark:text-white/95">
          {appTitle}
        </p>
      </div>

      <nav className="app-region-no-drag flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-2">
        {NAV.map(({ route, label, icon: Icon }) => {
          const active = activeRoute === route
          return (
            <button
              key={route}
              type="button"
              onClick={() => onNavigate(route)}
              className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/45 ${
                active
                  ? 'bg-emerald-500/15 text-emerald-900 dark:bg-emerald-400/10 dark:text-emerald-100'
                  : 'text-zinc-600 hover:bg-zinc-950/[0.04] dark:text-white/65 dark:hover:bg-white/[0.06]'
              }`}
            >
              <Icon className="size-4 shrink-0 opacity-80" strokeWidth={2} />
              <span className="min-w-0 truncate">{label}</span>
            </button>
          )
        })}
      </nav>

      <div className="app-region-no-drag mt-auto space-y-2 px-3 pt-2">
        <button
          type="button"
          onClick={() => onNavigate('settings')}
          className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/45 ${
            activeRoute === 'settings'
              ? 'bg-emerald-500/15 text-emerald-900 dark:bg-emerald-400/10 dark:text-emerald-100'
              : 'text-zinc-600 hover:bg-zinc-950/[0.04] dark:text-white/65 dark:hover:bg-white/[0.06]'
          }`}
        >
          <Settings className="size-4 shrink-0 opacity-80" strokeWidth={2} />
          Настройки
        </button>

        <button
          type="button"
          onClick={onToggleTheme}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-zinc-200/60 bg-white/50 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-white/80 dark:border-white/10 dark:bg-zinc-900/40 dark:text-white/75 dark:hover:bg-zinc-800/60"
          aria-label="Переключить тему"
        >
          {theme === 'dark' ? (
            <>
              <Sun className="size-4 text-amber-300" strokeWidth={2} />
              Светлая тема
            </>
          ) : (
            <>
              <Moon className="size-4 text-indigo-500" strokeWidth={2} />
              Тёмная тема
            </>
          )}
        </button>
      </div>
    </aside>
  )
}
