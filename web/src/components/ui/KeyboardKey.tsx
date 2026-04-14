/**
 * Визуализация одной клавиши в стиле macOS-подсказок (кэпс).
 */
export type KeyboardKeyProps = {
  label: string
  className?: string
}

export function KeyboardKey({ label, className = '' }: KeyboardKeyProps) {
  return (
    <kbd
      className={`inline-flex min-h-[1.75rem] min-w-[1.75rem] items-center justify-center rounded-lg border border-zinc-300/90 bg-gradient-to-b from-white to-zinc-100 px-2.5 py-1 font-sans text-xs font-semibold tracking-wide text-zinc-700 shadow-[0_1px_0_rgba(255,255,255,0.9)_inset,0_1px_2px_rgba(0,0,0,0.06)] dark:border-white/12 dark:from-zinc-800 dark:to-zinc-900 dark:text-white/90 dark:shadow-[0_1px_0_rgba(255,255,255,0.06)_inset] ${className}`}
    >
      {label}
    </kbd>
  )
}
