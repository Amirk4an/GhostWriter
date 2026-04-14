import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import type { AppRoute } from '../../types/app_route'

export type AppShellProps = {
  appTitle: string
  activeRoute: AppRoute
  onNavigate: (route: AppRoute) => void
  theme: 'light' | 'dark'
  onToggleTheme: () => void
  children: ReactNode
}

/**
 * Двухколоночный каркас: сайдбар и прокручиваемая область контента.
 * Перетаскивание окна — полоса над контентом и шапка сайдбара, не вся правая колонка (иначе ломается scroll).
 */
export function AppShell({
  appTitle,
  activeRoute,
  onNavigate,
  theme,
  onToggleTheme,
  children,
}: AppShellProps) {
  return (
    <div className="flex h-full min-h-0 w-full overflow-hidden rounded-[20px] border border-zinc-200/50 bg-zinc-50/80 shadow-2xl shadow-zinc-900/15 ring-1 ring-zinc-950/5 dark:border-white/10 dark:bg-zinc-950/70 dark:shadow-black/40 dark:ring-white/5">
      <Sidebar
        appTitle={appTitle}
        activeRoute={activeRoute}
        onNavigate={onNavigate}
        theme={theme}
        onToggleTheme={onToggleTheme}
      />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div
          className="app-region-drag h-9 shrink-0 border-b border-zinc-200/40 bg-white/30 dark:border-white/10 dark:bg-zinc-900/30"
          aria-hidden
        />
        <main className="app-region-no-drag min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
          {children}
        </main>
      </div>
    </div>
  )
}
