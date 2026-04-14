import type { ReactNode, SelectHTMLAttributes } from 'react'

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string
  hint?: string
  children: ReactNode
}

export function Select({
  label,
  hint,
  id,
  className = '',
  children,
  ...rest
}: SelectProps) {
  const selectId = id ?? label.replace(/\s+/g, '-').toLowerCase()

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label
        htmlFor={selectId}
        className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-white/45"
      >
        {label}
      </label>
      <select
        id={selectId}
        data-wispr-hit-target
        className="app-region-no-drag w-full appearance-none rounded-xl border border-zinc-200/80 bg-white/90 px-3 py-2 text-sm text-zinc-900 shadow-sm shadow-zinc-900/5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/45 dark:border-white/10 dark:bg-zinc-950/60 dark:text-white/90 dark:shadow-none"
        {...rest}
      >
        {children}
      </select>
      {hint ? (
        <p className="text-xs leading-relaxed text-zinc-500 dark:text-white/40">
          {hint}
        </p>
      ) : null}
    </div>
  )
}
