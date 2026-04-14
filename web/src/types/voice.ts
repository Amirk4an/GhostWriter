/** Состояние кнопки записи в UI (синхронизируется с бэкендом в режиме Electron). */
export type VoiceCaptureState =
  | 'idle'
  | 'recording'
  | 'processing'
  | 'error'
