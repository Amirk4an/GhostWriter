import { AnimatePresence, motion } from 'framer-motion'
import { Loader2, Mic, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { shellClassNames } from './constants'
import { nextWisprState, type WisprState } from './types'
import { VoiceWave } from './VoiceWave'

export type WisprWidgetProps = {
  className?: string
  initialState?: WisprState
  onStateChange?: (state: WisprState) => void
  processingLabel?: string
  /** Space cycles states; 1–4 jump to idle / listening / processing / command */
  enableDebugShortcuts?: boolean
  /** Режим Electron+Python: виджет только отображает бэкенд, без локального цикла */
  backendControlled?: boolean
  backendState?: WisprState
  /** Подпись при processing (транскрипт, «Вставка…» и т.д.) */
  backendDetail?: string | null
}

const springLayout = {
  type: 'spring' as const,
  stiffness: 420,
  damping: 32,
  mass: 0.85,
}

export function WisprWidget({
  className = '',
  initialState = 'idle',
  onStateChange,
  processingLabel = 'Обработка...',
  enableDebugShortcuts = false,
  backendControlled = false,
  backendState = 'idle',
  backendDetail = null,
}: WisprWidgetProps) {
  const [internalState, setInternalState] = useState<WisprState>(initialState)
  const state = backendControlled ? backendState : internalState
  const onStateChangeRef = useRef(onStateChange)

  useEffect(() => {
    onStateChangeRef.current = onStateChange
  }, [onStateChange])

  useEffect(() => {
    if (backendControlled) return
    const api = window.wisprShell
    if (!api?.onGlobalListening) return

    return api.onGlobalListening(() => {
      setInternalState(() => {
        onStateChangeRef.current?.('listening')
        return 'listening'
      })
    })
  }, [backendControlled])

  useEffect(() => {
    if (backendControlled || !enableDebugShortcuts) return

    const direct: WisprState[] = [
      'idle',
      'listening',
      'processing',
      'command',
    ]

    const onKeyDown = (e: globalThis.KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      const tag = t?.tagName
      const editable =
        t?.isContentEditable ||
        tag === 'INPUT' ||
        tag === 'TEXTAREA' ||
        tag === 'SELECT'

      if (editable) return

      if (e.code === 'Space') {
        e.preventDefault()
        setInternalState((s) => {
          const n = nextWisprState(s)
          onStateChangeRef.current?.(n)
          return n
        })
        return
      }

      if (e.key >= '1' && e.key <= '4') {
        const n = direct[Number(e.key) - 1]
        setInternalState(() => {
          onStateChangeRef.current?.(n)
          return n
        })
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [backendControlled, enableDebugShortcuts])

  const showWave = state === 'listening' || state === 'command'
  const showLabel = state === 'processing'
  const processingText =
    state === 'processing' && backendDetail?.trim()
      ? backendDetail.trim()
      : processingLabel

  const cycleFromInteraction = () => {
    if (backendControlled) return
    setInternalState((s) => {
      const n = nextWisprState(s)
      onStateChangeRef.current?.(n)
      return n
    })
  }

  return (
    <div
      data-wispr-hit-target
      className={`fixed bottom-8 left-1/2 z-50 -translate-x-1/2 ${className}`}
    >
      <motion.div
        layout
        role="status"
        aria-live="polite"
        aria-label={`Голосовой виджет: ${state}`}
        className={`group flex select-none items-center outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 ${shellClassNames(state)} ${
          backendControlled ? 'cursor-default' : 'cursor-pointer'
        } ${state === 'idle' ? 'p-3' : 'gap-3 px-4 py-2.5'}`}
        transition={{ layout: springLayout }}
        whileHover={
          backendControlled ? undefined : { scale: state === 'idle' ? 1.03 : 1.01 }
        }
        whileTap={backendControlled ? undefined : { scale: 0.98 }}
        onClick={backendControlled ? undefined : cycleFromInteraction}
        onKeyDown={
          backendControlled
            ? undefined
            : (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  cycleFromInteraction()
                }
              }
        }
        tabIndex={backendControlled ? -1 : 0}
      >
        <motion.div layout className="flex shrink-0 items-center justify-center">
          <AnimatePresence mode="wait" initial={false}>
            {state === 'processing' ? (
              <motion.div
                key="loader"
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.85 }}
                transition={{ duration: 0.2 }}
              >
                <Loader2
                  className="size-5 animate-spin text-emerald-300/90"
                  strokeWidth={2}
                />
              </motion.div>
            ) : state === 'command' ? (
              <motion.div
                key="sparkles"
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.85 }}
                transition={{ duration: 0.2 }}
              >
                <Sparkles
                  className="size-5 text-amber-300"
                  strokeWidth={2}
                />
              </motion.div>
            ) : (
              <motion.div
                key="mic"
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.85 }}
                transition={{ duration: 0.2 }}
              >
                <Mic
                  className={`size-5 transition-colors duration-200 ${
                    state === 'listening'
                      ? 'text-sky-400'
                      : 'text-white/50 group-hover:text-white/80'
                  }`}
                  strokeWidth={2}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        <AnimatePresence initial={false}>
          {showWave && (
            <motion.div
              key="wave"
              layout
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: 'auto' }}
              exit={{ opacity: 0, width: 0 }}
              transition={{ ...springLayout, opacity: { duration: 0.2 } }}
              className="overflow-hidden"
            >
              <VoiceWave
                variant={state === 'command' ? 'command' : 'listening'}
              />
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence initial={false}>
          {showLabel && (
            <motion.span
              key="label"
              layout
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -6 }}
              transition={{ duration: 0.2 }}
              className="whitespace-nowrap text-sm font-medium text-white/90"
            >
              {processingText}
            </motion.span>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
