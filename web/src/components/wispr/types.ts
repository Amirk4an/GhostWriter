export type WisprState = 'idle' | 'listening' | 'processing' | 'command'

export const WISPR_STATE_ORDER: WisprState[] = [
  'idle',
  'listening',
  'processing',
  'command',
]

export function nextWisprState(current: WisprState): WisprState {
  const i = WISPR_STATE_ORDER.indexOf(current)
  return WISPR_STATE_ORDER[(i + 1) % WISPR_STATE_ORDER.length]
}
