import type { HTMLAttributes, ReactNode } from 'react'

export type CardProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode
  /** When true, surface receives hit-target marker for Electron passthrough regions */
  interactive?: boolean
}

export function Card({
  children,
  className = '',
  interactive = false,
  ...rest
}: CardProps) {
  return (
    <div
      data-wispr-hit-target={interactive ? true : undefined}
      className={`rounded-2xl border border-zinc-200/70 bg-white/70 p-4 shadow-lg shadow-zinc-900/5 ring-1 ring-zinc-950/5 backdrop-blur-xl dark:border-white/10 dark:bg-zinc-950/55 dark:shadow-black/25 dark:ring-white/10 ${className}`}
      {...rest}
    >
      {children}
    </div>
  )
}
