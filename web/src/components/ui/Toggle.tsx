import type { InputHTMLAttributes } from 'react'

export type ToggleProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'type' | 'role'
> & {
  label: string
  description?: string
}

export function Toggle({
  label,
  description,
  id,
  className = '',
  ...rest
}: ToggleProps) {
  const inputId = id ?? label.replace(/\s+/g, '-').toLowerCase()

  return (
    <label
      htmlFor={inputId}
      data-wispr-hit-target
      className={`app-region-no-drag flex cursor-pointer items-start gap-3 rounded-xl p-2 transition-colors hover:bg-zinc-950/[0.04] dark:hover:bg-white/[0.06] ${className}`}
    >
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium text-zinc-900 dark:text-white/90">
          {label}
        </span>
        {description ? (
          <span className="mt-0.5 block text-xs leading-relaxed text-zinc-500 dark:text-white/45">
            {description}
          </span>
        ) : null}
      </span>
      <span className="relative mt-0.5 inline-flex h-6 w-11 shrink-0 items-center">
        <input
          id={inputId}
          type="checkbox"
          role="switch"
          className="peer absolute inset-0 z-10 cursor-pointer opacity-0"
          {...rest}
        />
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-full bg-zinc-300 transition-colors peer-checked:bg-emerald-500/90 peer-focus-visible:ring-2 peer-focus-visible:ring-emerald-500/50 peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-white dark:bg-white/15 dark:peer-checked:bg-emerald-500/80 dark:peer-focus-visible:ring-offset-zinc-950"
        />
        <span
          aria-hidden
          className="pointer-events-none absolute left-0.5 top-0.5 size-5 rounded-full bg-white shadow-sm transition-transform peer-checked:translate-x-5 dark:bg-zinc-950"
        />
      </span>
    </label>
  )
}
