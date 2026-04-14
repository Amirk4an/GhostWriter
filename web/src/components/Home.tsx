import { AnimatePresence, motion } from 'framer-motion'
import { AlertCircle, Loader2, Mic, Settings } from 'lucide-react'
import { Button } from './ui'

export type HomeVoiceState = 'idle' | 'recording' | 'processing' | 'error'

export type HomeProps = {
  /** Tighter layout for the small Electron overlay window */
  compact?: boolean
  state: HomeVoiceState
  statusText: string
  errorMessage?: string | null
  onOpenSettings: () => void
  onMicActivate: () => void
}

export function Home({
  compact = false,
  state,
  statusText,
  errorMessage,
  onOpenSettings,
  onMicActivate,
}: HomeProps) {
  const micDisabled = state === 'processing'

  return (
    <div className="relative flex h-full min-h-0 flex-col">
      <div
        className={`app-region-drag shrink-0 rounded-t-3xl ${compact ? 'h-3' : 'h-8'}`}
        aria-hidden
      />

      <div
        className={`relative flex min-h-0 flex-1 flex-col items-center justify-center px-3 ${compact ? 'pb-2 pt-1' : 'px-4 pb-6 pt-2'}`}
      >
        <button
          type="button"
          data-wispr-hit-target
          onClick={onOpenSettings}
          className={`app-region-no-drag absolute z-20 inline-flex items-center justify-center rounded-full border border-zinc-200/60 bg-white/60 text-zinc-600 shadow-sm shadow-zinc-900/5 transition-colors hover:bg-white/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/45 dark:border-white/10 dark:bg-zinc-950/50 dark:text-white/70 dark:shadow-black/30 dark:hover:bg-zinc-900/60 ${
            compact
              ? 'right-2 top-0 size-8'
              : 'right-3 top-1 size-10'
          }`}
          aria-label="Open settings"
        >
          <Settings className={compact ? 'size-3.5' : 'size-4'} strokeWidth={2} />
        </button>

        <div
          data-wispr-hit-target
          className={`relative flex w-full flex-col items-center rounded-3xl border border-zinc-200/60 bg-white/55 shadow-xl shadow-zinc-900/10 ring-1 ring-zinc-950/5 backdrop-blur-2xl dark:border-white/10 dark:bg-zinc-950/50 dark:shadow-black/40 dark:ring-white/10 ${
            compact
              ? 'max-w-[min(100%,420px)] gap-3 px-4 py-3'
              : 'max-w-sm gap-6 px-8 py-10'
          }`}
        >
          <div
            className={`flex flex-col items-center ${compact ? 'gap-2' : 'gap-5'}`}
          >
            <motion.button
              type="button"
              aria-pressed={state === 'recording'}
              aria-label={
                state === 'recording' ? 'Stop recording' : 'Start recording'
              }
              disabled={micDisabled}
              onClick={onMicActivate}
              className={`relative flex items-center justify-center rounded-full border border-zinc-200/70 bg-gradient-to-b from-white to-zinc-100 text-zinc-700 shadow-inner shadow-white/60 ring-1 ring-zinc-950/5 transition-transform focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:from-zinc-900 dark:to-zinc-950 dark:text-white dark:shadow-inner dark:shadow-black/40 dark:ring-white/10 ${
                compact ? 'size-16' : 'size-28'
              }`}
              whileTap={micDisabled ? undefined : { scale: 0.96 }}
            >
              {state === 'recording' ? (
                <motion.span
                  className="absolute inset-2 rounded-full bg-emerald-400/15 dark:bg-emerald-300/10"
                  animate={{ opacity: [0.45, 0.9, 0.45], scale: [0.92, 1.05, 0.92] }}
                  transition={{
                    duration: 1.8,
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
                      className={`${compact ? 'size-6' : 'size-10'} animate-spin text-emerald-500 dark:text-emerald-300`}
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
                      className={`${compact ? 'size-6' : 'size-10'} text-red-500 dark:text-red-400`}
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
                          : { scale: 1, opacity: 1 }
                      }
                      transition={
                        state === 'recording'
                          ? { duration: 1.4, repeat: Infinity, ease: 'easeInOut' }
                          : { duration: 0.2 }
                      }
                    >
                      <Mic
                        className={`${compact ? 'size-6' : 'size-10'} ${
                          state === 'recording'
                            ? 'text-emerald-500 dark:text-emerald-300'
                            : 'text-zinc-500 dark:text-white/60'
                        }`}
                        strokeWidth={1.75}
                      />
                    </motion.span>
                  </motion.span>
                )}
              </AnimatePresence>
            </motion.button>

            <div className="space-y-0.5 text-center">
              <p
                className={`font-semibold uppercase tracking-[0.2em] text-zinc-500 dark:text-white/40 ${
                  compact ? 'text-[9px]' : 'text-xs'
                }`}
              >
                Status
              </p>
              <p
                className={`font-medium text-zinc-800 dark:text-white/85 ${
                  compact ? 'text-xs' : 'text-sm'
                }`}
              >
                {statusText}
              </p>
              {state === 'error' && errorMessage ? (
                <p className="text-xs text-red-600 dark:text-red-300/90">
                  {errorMessage}
                </p>
              ) : null}
            </div>
          </div>

          {state === 'error' ? (
            <Button
              variant="secondary"
              className="w-full"
              onClick={onMicActivate}
            >
              Try again
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
