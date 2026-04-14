import type { ButtonHTMLAttributes, ReactNode } from 'react'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  children: ReactNode
}

const variantClass: Record<ButtonVariant, string> = {
  primary:
    'bg-emerald-500/90 text-white shadow-sm shadow-emerald-900/20 hover:bg-emerald-500 dark:bg-emerald-500/85 dark:hover:bg-emerald-400/90',
  secondary:
    'bg-zinc-200/90 text-zinc-900 hover:bg-zinc-100 dark:bg-white/10 dark:text-white dark:hover:bg-white/15',
  ghost:
    'bg-transparent text-zinc-700 hover:bg-zinc-950/5 dark:text-white/80 dark:hover:bg-white/10',
  danger:
    'bg-red-500/90 text-white hover:bg-red-500 dark:bg-red-600/85 dark:hover:bg-red-500/90',
}

export function Button({
  variant = 'secondary',
  className = '',
  type = 'button',
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      data-wispr-hit-target
      type={type}
      className={`app-region-no-drag inline-flex items-center justify-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-zinc-950 disabled:pointer-events-none disabled:opacity-45 ${variantClass[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}
