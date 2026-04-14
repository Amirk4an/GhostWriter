const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('wisprShell', {
  platform: process.platform,

  /** Список микрофонов (PortAudio) через Python-бэкенд */
  listAudioInputs: () => ipcRenderer.invoke('ghost:list-audio-inputs'),

  /**
   * Сохраняет индекс микрофона в config.json и применяет в бэкенде.
   * @param {number | null} deviceIndex индекс или null = вход по умолчанию ОС
   */
  setAudioInputDevice: (deviceIndex) =>
    ipcRenderer.invoke('ghost:set-audio-input-device', deviceIndex),

  /**
   * Глобальный шорткат (Alt+Space / Option+Space) — переключение в режим listening.
   * @param {() => void} callback
   * @returns {() => void} unsubscribe
   */
  onGlobalListening: (callback) => {
    const handler = () => {
      callback()
    }
    ipcRenderer.on('wispr:global-listening', handler)
    return () => {
      ipcRenderer.removeListener('wispr:global-listening', handler)
    }
  },

  /**
   * true = клики «проходят» сквозь текущее окно (прозрачная область).
   * false = обычный hit-test. Main-процесс применяет к окну-отправителю (панель или капсула).
   * @param {boolean} enabled
   */
  setWindowPassthrough: (enabled) => {
    ipcRenderer.send('wispr:set-window-passthrough', enabled)
  },

  /**
   * Статусы с Python-бэкенда (Recording / Processing / Idle / Error + detail).
   * @param {(msg: { status: string; detail: string | null }) => void} callback
   */
  onGhostStatus: (callback) => {
    const handler = (_e, msg) => {
      callback(msg)
    }
    ipcRenderer.on('ghost:status', handler)
    return () => {
      ipcRenderer.removeListener('ghost:status', handler)
    }
  },

  /**
   * Resize / hit-test mode for frameless shell: compact overlay vs settings panel.
   * @param {'compact' | 'settings'} mode
   */
  setShellLayout: (mode) => {
    ipcRenderer.send('ghost:set-shell-layout', { mode })
  },
})
