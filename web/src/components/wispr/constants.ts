import type { WisprState } from './types'

/** Base glass pill — matches spec: rounded-full, dark glass, blur, hairline border, levitation shadow */
export const SHELL_BASE =
  'rounded-full border border-white/10 bg-[#1A1A1A]/80 backdrop-blur-md font-[system-ui,sans-serif]'

/** Deep levitation + optional neon (single shadow layer list so utilities do not fight) */
export const SHELL_SHADOW: Record<WisprState, string> = {
  idle:
    'shadow-[0_25px_50px_-12px_rgba(0,0,0,0.5)] hover:border-white/20 hover:shadow-[0_28px_56px_-12px_rgba(0,0,0,0.55)]',
  listening:
    'shadow-[0_25px_50px_-12px_rgba(0,0,0,0.5),0_0_20px_rgba(59,130,246,0.5)]',
  processing:
    'shadow-[0_25px_50px_-12px_rgba(0,0,0,0.5),0_0_22px_rgba(34,197,94,0.45)]',
  command:
    'shadow-[0_25px_50px_-12px_rgba(0,0,0,0.5),0_0_22px_rgba(250,204,21,0.45)]',
}

export function shellClassNames(state: WisprState): string {
  return `${SHELL_BASE} ${SHELL_SHADOW[state]}`
}

/**
 * Состояния компактного оверлея (голосовой UI) — маппинг на «wispr»-стекло и тени.
 * recording → подсветка как у listening (синий неон), error → красный акцент.
 */
export type OverlayVoiceState =
  | 'idle'
  | 'recording'
  | 'processing'
  | 'error'

export function overlayPillClassNames(state: OverlayVoiceState): string {
  if (state === 'error') {
    return `${SHELL_BASE} border-red-400/35 shadow-[0_25px_50px_-12px_rgba(0,0,0,0.55),0_0_22px_rgba(248,113,113,0.38)]`
  }
  const wispr: WisprState =
    state === 'recording'
      ? 'listening'
      : state === 'processing'
        ? 'processing'
        : 'idle'
  return `${SHELL_BASE} ${SHELL_SHADOW[wispr]}`
}
