import { AnimatePresence, motion } from 'framer-motion'
import { AlertCircle, Loader2, Mic } from 'lucide-react'
import type { VoiceCaptureState } from '../../types/voice'

export type MicLauncherButtonProps = {
  /** Узкая капсула для оверлея (сейчас не используется в основном окне). */
  compact?: boolean
  state: VoiceCaptureState
  micDisabled: boolean
  onMicActivate: () => void
}

/**
 * Крупная круглая кнопка записи с анимацией ожидания и записи.
 */
export function MicLauncherButton({
  compact = false,
  state,
  micDisabled,
  onMicActivate,
}: MicLauncherButtonProps) {
  const btnSize = compact ? 'size-10' : 'size-28'
  const iconSize = compact ? 'size-5' : 'size-10'
  const pulseInset = compact ? 'inset-1.5' : 'inset-2'

  const glassBase = compact
    ? 'border-0 bg-transparent shadow-none ring-0 text-white/70 hover:bg-white/[0.08] hover:text-white/90'
    : 'border border-zinc-200/70 bg-gradient-to-b from-white to-zinc-100 text-zinc-700 shadow-inner shadow-white/60 ring-1 ring-zinc-950/5 dark:border-white/10 dark:from-zinc-900 dark:to-zinc-950 dark:text-white dark:shadow-inner dark:shadow-black/40 dark:ring-white/10'

  const showReadyPulse = state === 'idle' && !micDisabled

  return (
    <motion.button
      type="button"
      data-wispr-hit-target
      aria-pressed={state === 'recording'}
      aria-label={
        state === 'recording' ? 'Остановить запись' : 'Начать запись'
      }
      disabled={micDisabled}
      onClick={onMicActivate}
      className={`app-region-no-drag relative flex ${btnSize} cursor-pointer items-center justify-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/45 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent disabled:cursor-not-allowed disabled:opacity-55 ${glassBase}`}
      whileTap={micDisabled ? undefined : { scale: 0.96 }}
    >
      {state === 'recording' ? (
        <motion.span
          className={`absolute ${pulseInset} rounded-full ${compact ? 'bg-sky-500/20' : 'bg-emerald-400/15 dark:bg-emerald-300/10'}`}
          animate={{ opacity: [0.45, 0.9, 0.45], scale: [0.92, 1.05, 0.92] }}
          transition={{
            duration: 1.8,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      ) : null}

      {showReadyPulse ? (
        <motion.span
          className={`pointer-events-none absolute ${pulseInset} rounded-full ${compact ? 'bg-white/10' : 'bg-emerald-500/10 dark:bg-emerald-400/8'}`}
          animate={{ opacity: [0.35, 0.65, 0.35], scale: [0.96, 1.02, 0.96] }}
          transition={{
            duration: 2.4,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      ) : null}

      <AnimatePresence mode="wait" initial={false}>
        {state === 'processing' ? (
          <motion.span
            key="processing"
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.85 }}
            transition={{ duration: 0.2 }}
            className="relative"
          >
            <Loader2
              className={`${iconSize} animate-spin ${compact ? 'text-emerald-400' : 'text-emerald-500 dark:text-emerald-300'}`}
              strokeWidth={1.75}
            />
          </motion.span>
        ) : state === 'error' ? (
          <motion.span
            key="error"
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.85 }}
            transition={{ duration: 0.2 }}
            className="relative"
          >
            <AlertCircle
              className={`${iconSize} ${compact ? 'text-red-400' : 'text-red-500 dark:text-red-400'}`}
              strokeWidth={1.75}
            />
          </motion.span>
        ) : (
          <motion.span
            key="mic"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.2 }}
            className="relative"
          >
            <motion.span
              animate={
                state === 'recording'
                  ? { scale: [1, 1.06, 1], opacity: [0.85, 1, 0.85] }
                  : showReadyPulse
                    ? { scale: [1, 1.03, 1], opacity: [0.88, 1, 0.88] }
                    : { scale: 1, opacity: 1 }
              }
              transition={
                state === 'recording'
                  ? { duration: 1.4, repeat: Infinity, ease: 'easeInOut' }
                  : showReadyPulse
                    ? { duration: 2.2, repeat: Infinity, ease: 'easeInOut' }
                    : { duration: 0.2 }
              }
            >
              <Mic
                className={`${iconSize} ${
                  state === 'recording'
                    ? compact
                      ? 'text-sky-400'
                      : 'text-emerald-500 dark:text-emerald-300'
                    : compact
                      ? 'text-white/60'
                      : 'text-zinc-500 dark:text-white/60'
                }`}
                strokeWidth={1.75}
              />
            </motion.span>
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  )
}
