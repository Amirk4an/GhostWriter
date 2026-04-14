const {
  app,
  BrowserWindow,
  globalShortcut,
  ipcMain,
  screen,
} = require('electron')
const path = require('path')
const net = require('net')
const fs = require('fs')
const readline = require('readline')
const { spawn } = require('child_process')
const { randomUUID } = require('crypto')

/** Alt+Space = Option+Space на macOS в Electron */
const GLOBAL_SHORTCUT = 'Alt+Space'

let panelWindow = null
let widgetWindow = null
let pythonChild = null
let statusServer = null
let statusSocket = null
let appIsQuitting = false
/** Режим главной панели при переключении через IPC (резерв). */
let shellLayoutMode = 'settings'
/** Последние сообщения до готовности окон */
const statusBacklog = []
const BACKLOG_MAX = 32
/** Очередь команд UI->backend до установления TCP-сокета статуса */
const controlBacklog = []
const CONTROL_BACKLOG_MAX = 32
/** Ожидание ответов бэкенда по request_id (list/set микрофона и т.д.) */
const pendingUiReplies = new Map()
/** Главное окно: сайдбар + контент. */
const PANEL_WIDTH = 1080
const PANEL_HEIGHT = 700
/** Отдельная капсула записи. */
const WIDGET_WIDTH = 140
const WIDGET_HEIGHT = 56
const OVERLAY_POSITION_FILE = 'overlay-compact-position.json'

let widgetPositionSaveTimer = null

/** Зарегистрированный accelerator dictation (если есть) */
let registeredDictationAccelerator = null
/** Таймер авто-release для press-to-talk в Electron globalShortcut */
let dictateAutoUpTimer = null
/** latch для hands-free режима (toggle по каждому срабатыванию accelerator) */
let dictateHandsFreeOpen = false
/** Временная метка последнего принятого срабатывания hotkey (anti-repeat) */
let lastDictationShortcutTs = 0

// #region agent log
function agentDebugLog(hypothesisId, location, message, data) {
  fetch('http://127.0.0.1:7479/ingest/ce775ce2-ad04-4795-95d0-f5a1b0a206ce', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': 'edce00' },
    body: JSON.stringify({
      sessionId: 'edce00',
      runId: process.env.GHOST_DEBUG_RUN_ID || 'run1',
      hypothesisId,
      location,
      message,
      data,
      timestamp: Date.now(),
    }),
  }).catch(() => {})
}
// #endregion

// #region agent log
agentDebugLog('H7', 'web/electron/main.cjs:boot', 'Electron main process boot', {
  electronPid: process.pid,
  argvHead: process.argv.slice(0, 6),
})
// #endregion

function projectRoot() {
  return path.join(__dirname, '..', '..')
}

function resolvePythonExe(rootDir) {
  if (process.env.GHOST_WRITER_PYTHON) {
    return process.env.GHOST_WRITER_PYTHON
  }
  if (process.platform === 'win32') {
    const v = path.join(rootDir, '.venv', 'Scripts', 'python.exe')
    return fs.existsSync(v) ? v : 'python'
  }
  const v = path.join(rootDir, '.venv', 'bin', 'python3')
  return fs.existsSync(v) ? v : 'python3'
}

function deliverGhostStatus(msg) {
  if (panelWindow && !panelWindow.isDestroyed()) {
    panelWindow.webContents.send('ghost:status', msg)
  }
  if (widgetWindow && !widgetWindow.isDestroyed()) {
    widgetWindow.webContents.send('ghost:status', msg)
  }
}

function forwardGhostStatus(msg) {
  const hasTarget =
    (panelWindow && !panelWindow.isDestroyed()) ||
    (widgetWindow && !widgetWindow.isDestroyed())
  if (hasTarget) {
    deliverGhostStatus(msg)
    return
  }
  statusBacklog.push(msg)
  while (statusBacklog.length > BACKLOG_MAX) {
    statusBacklog.shift()
  }
}

function flushStatusBacklog() {
  if (statusBacklog.length === 0) return
  const pending = statusBacklog.splice(0, statusBacklog.length)
  for (const msg of pending) {
    deliverGhostStatus(msg)
  }
}

function flushControlBacklog() {
  if (controlBacklog.length === 0) return
  if (!statusSocket || statusSocket.destroyed) return
  const pending = controlBacklog.splice(0, controlBacklog.length)
  for (const line of pending) {
    try {
      statusSocket.write(line)
    } catch (e) {
      console.warn('[ghost-writer] не удалось отправить команду backend:', e)
    }
  }
}

function enqueueControlLine(line) {
  controlBacklog.push(line)
  while (controlBacklog.length > CONTROL_BACKLOG_MAX) {
    controlBacklog.shift()
  }
}

/**
 * @param {Record<string, unknown>} payload полезная нагрузка без request_id
 * @param {number} [timeoutMs]
 * @returns {Promise<Record<string, unknown>>}
 */
function sendToBackendAndWait(payload, timeoutMs = 12000) {
  return new Promise((resolve, reject) => {
    const request_id = randomUUID()
    const timer = setTimeout(() => {
      pendingUiReplies.delete(request_id)
      reject(new Error('Таймаут ответа бэкенда'))
    }, timeoutMs)
    pendingUiReplies.set(request_id, (msg) => {
      clearTimeout(timer)
      resolve(msg)
    })
    const line = JSON.stringify({ ...payload, request_id }) + '\n'
    if (statusSocket && !statusSocket.destroyed) {
      try {
        statusSocket.write(line)
      } catch (e) {
        clearTimeout(timer)
        pendingUiReplies.delete(request_id)
        reject(e)
      }
    } else {
      clearTimeout(timer)
      pendingUiReplies.delete(request_id)
      reject(new Error('Бэкенд не подключён'))
    }
  })
}

function sendDictateEdgeToBackend(pressed) {
  const payload = JSON.stringify({
    type: 'dictate_edge',
    pressed: Boolean(pressed),
    ts: Date.now(),
  })
  const line = `${payload}\n`
  if (statusSocket && !statusSocket.destroyed) {
    try {
      statusSocket.write(line)
    } catch (e) {
      console.warn('[ghost-writer] write dictate_edge failed:', e)
      enqueueControlLine(line)
    }
  } else {
    enqueueControlLine(line)
  }
}

function loadDictationHotkeySpec() {
  try {
    const cfgPath = app.isPackaged
      ? path.join(process.resourcesPath, 'ghost_backend', 'config', 'config.json')
      : path.join(projectRoot(), 'config', 'config.json')
    if (!fs.existsSync(cfgPath)) {
      console.warn('[ghost-writer] config.json не найден:', cfgPath)
      return { hotkey: 'f8', handsFreeEnabled: true }
    }
    const raw = fs.readFileSync(cfgPath, 'utf8')
    const cfg = JSON.parse(raw)
    const hotkey = typeof cfg.hotkey === 'string' && cfg.hotkey.trim() ? cfg.hotkey.trim() : 'f8'
    const handsFreeEnabled = cfg.hands_free_enabled !== false
    return { hotkey, handsFreeEnabled }
  } catch (e) {
    console.warn('[ghost-writer] не удалось прочитать hotkey из config.json:', e)
    return { hotkey: 'f8', handsFreeEnabled: true }
  }
}

function hotkeyToElectronAccelerator(raw) {
  const parts = String(raw || '')
    .replace(/\s+/g, '')
    .split('+')
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => p.toLowerCase())
  if (parts.length === 0) return null
  const mods = parts.slice(0, -1)
  const key = parts[parts.length - 1]

  const outMods = []
  for (const m of mods) {
    if (m === 'cmd' || m === 'super' || m === 'win') {
      outMods.push(process.platform === 'darwin' ? 'Command' : 'Super')
    } else if (m === 'ctrl' || m === 'control') {
      outMods.push('Control')
    } else if (m === 'alt' || m === 'option') {
      outMods.push(process.platform === 'darwin' ? 'Option' : 'Alt')
    } else if (m === 'shift') {
      outMods.push('Shift')
    } else {
      return null
    }
  }

  let keyAcc = null
  if (key.length === 1) {
    keyAcc = key.toUpperCase()
  } else if (key.startsWith('f') && /^f\d{1,2}$/.test(key)) {
    keyAcc = `F${key.slice(1)}`
  } else {
    const map = {
      space: 'Space',
      tab: 'Tab',
      enter: 'Enter',
      return: 'Enter',
      esc: 'Escape',
      escape: 'Escape',
      backspace: 'Backspace',
      delete: 'Delete',
      up: 'Up',
      down: 'Down',
      left: 'Left',
      right: 'Right',
    }
    keyAcc = map[key] || null
  }
  if (!keyAcc) return null
  return [...outMods, keyAcc].join('+')
}

function startStatusServer() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer((sock) => {
      if (statusSocket && !statusSocket.destroyed) {
        statusSocket.destroy()
      }
      statusSocket = sock
      const rl = readline.createInterface({ input: sock, crlfDelay: Infinity })
      rl.on('line', (line) => {
        const trimmed = line.trim()
        if (!trimmed) return
        try {
          const msg = JSON.parse(trimmed)
          if (msg && typeof msg === 'object' && msg.request_id != null) {
            const rid = String(msg.request_id)
            const cb = pendingUiReplies.get(rid)
            if (cb) {
              pendingUiReplies.delete(rid)
              cb(msg)
              return
            }
          }
          if (msg && typeof msg === 'object' && 'status' in msg) {
            forwardGhostStatus(msg)
            return
          }
        } catch (e) {
          console.warn('[ghost-writer] bad status JSON:', trimmed.slice(0, 120))
        }
      })
      sock.on('close', () => {
        rl.close()
        if (statusSocket === sock) statusSocket = null
      })
      sock.on('error', () => {
        rl.close()
        if (statusSocket === sock) statusSocket = null
      })

      flushControlBacklog()
    })
    srv.on('error', reject)
    srv.listen(0, '127.0.0.1', () => {
      resolve(srv)
    })
  })
}

function spawnPythonBackend(port) {
  const env = {
    ...process.env,
    GHOST_WRITER_ELECTRON_UI: '1',
    GHOST_WRITER_PUSH_STATUS_HOST: '127.0.0.1',
    GHOST_WRITER_PUSH_STATUS_PORT: String(port),
  }

  if (app.isPackaged) {
    const backendDir = path.join(process.resourcesPath, 'ghost_backend')
    const backendName =
      process.platform === 'win32' ? 'ghost_backend.exe' : 'ghost_backend'
    const backendPath = path.join(backendDir, backendName)
    if (!fs.existsSync(backendPath)) {
      console.error('[ghost-writer] бинарник бэкенда не найден:', backendPath)
      return
    }
    pythonChild = spawn(backendPath, [], {
      cwd: backendDir,
      env,
      stdio: ['ignore', 'ignore', 'pipe'],
    })
    pythonChild.stderr?.on('data', (buf) => {
      process.stderr.write(`[python] ${buf}`)
    })
  } else {
    const rootDir = projectRoot()
    const mainPy = path.join(rootDir, 'main.py')
    if (!fs.existsSync(mainPy)) {
      console.error('[ghost-writer] main.py не найден:', mainPy)
      return
    }
    const py = resolvePythonExe(rootDir)
    pythonChild = spawn(py, [mainPy], {
      cwd: rootDir,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    pythonChild.stdout?.on('data', (buf) => {
      process.stdout.write(`[python] ${buf}`)
    })
    pythonChild.stderr?.on('data', (buf) => {
      process.stderr.write(`[python] ${buf}`)
    })
  }

  // #region agent log
  if (pythonChild) {
    agentDebugLog('H5', 'web/electron/main.cjs:spawnPythonBackend', 'Electron spawn python backend', {
      electronPid: process.pid,
      pythonChildPid: pythonChild.pid ?? null,
      packaged: app.isPackaged,
    })
  }
  // #endregion

  pythonChild.on('exit', (code, signal) => {
    // #region agent log
    agentDebugLog('H8', 'web/electron/main.cjs:python-exit', 'Python child exited', {
      electronPid: process.pid,
      code: code ?? null,
      signal: signal ?? null,
      appIsQuitting,
    })
    // #endregion
    pythonChild = null
    console.warn('[ghost-writer] Python завершился', { code, signal })
    if (!appIsQuitting) {
      app.quit()
    }
  })
}

function killPythonChild() {
  if (pythonChild && !pythonChild.killed) {
    try {
      pythonChild.kill('SIGTERM')
    } catch (e) {
      console.warn('[ghost-writer] kill python:', e)
    }
  }
  pythonChild = null
}

function overlayPositionPath() {
  return path.join(app.getPath('userData'), OVERLAY_POSITION_FILE)
}

/** @returns {{ x: number, y: number } | null} */
function loadCompactOverlayPosition() {
  try {
    const p = overlayPositionPath()
    if (!fs.existsSync(p)) return null
    const raw = JSON.parse(fs.readFileSync(p, 'utf8'))
    if (typeof raw.x !== 'number' || typeof raw.y !== 'number') return null
    return { x: raw.x, y: raw.y }
  } catch (e) {
    console.warn('[ghost-writer] не удалось прочитать позицию виджета:', e)
    return null
  }
}

/**
 * Отбрасывает сохранённые координаты от старых багов (например позиция главной панели):
 * виджет должен быть в нижней части рабочей области и примерно по горизонтальному центру.
 * @param {{ x: number, y: number }} saved
 * @param {Electron.Rectangle} wa
 * @param {number} ww
 * @param {number} wh
 */
function isSavedWidgetPositionPlausible(saved, wa, ww, wh) {
  const { x, y } = saved
  const minY = wa.y + wa.height * 0.4
  if (y < minY) return false
  const widgetCenterX = x + ww / 2
  const workMidX = wa.x + wa.width / 2
  if (Math.abs(widgetCenterX - workMidX) > wa.width * 0.48) return false
  return true
}

function saveCompactOverlayPosition(win) {
  if (!win || win.isDestroyed()) return
  if (win !== widgetWindow) return
  try {
    const b = win.getBounds()
    fs.mkdirSync(path.dirname(overlayPositionPath()), { recursive: true })
    fs.writeFileSync(
      overlayPositionPath(),
      JSON.stringify({ x: b.x, y: b.y }, null, 0),
      'utf8',
    )
  } catch (e) {
    console.warn('[ghost-writer] не удалось сохранить позицию виджета:', e)
  }
}

function scheduleSaveCompactOverlayPosition(win) {
  if (!win || win.isDestroyed() || win !== widgetWindow) return
  if (widgetPositionSaveTimer) clearTimeout(widgetPositionSaveTimer)
  widgetPositionSaveTimer = setTimeout(() => {
    widgetPositionSaveTimer = null
    saveCompactOverlayPosition(win)
  }, 350)
}

/**
 * Ограничивает левый верхний угол компактного окна рамкой рабочей области дисплея.
 * @param {number} x
 * @param {number} y
 * @param {number} ww
 * @param {number} wh
 * @param {Electron.Rectangle} wa
 */
function clampCompactTopLeft(x, y, ww, wh, wa) {
  const margin = 24
  const minX = wa.x - ww + margin
  const maxX = wa.x + wa.width - margin
  const minY = wa.y
  const maxY = wa.y + wa.height - margin
  return {
    x: Math.round(Math.min(Math.max(x, minX), maxX)),
    y: Math.round(Math.min(Math.max(y, minY), maxY)),
    width: ww,
    height: wh,
  }
}

/** Отступ от нижнего края рабочей области (док / панель). */
const WIDGET_BOTTOM_GAP = 16

function placeWidgetWindow(win) {
  const wa = screen.getPrimaryDisplay().workArea
  const ww = WIDGET_WIDTH
  const wh = WIDGET_HEIGHT
  const defaultX = Math.round(wa.x + (wa.width - ww) / 2)
  const defaultY = Math.round(wa.y + wa.height - wh - WIDGET_BOTTOM_GAP)
  const saved = loadCompactOverlayPosition()
  let gx = defaultX
  let gy = defaultY
  if (saved && isSavedWidgetPositionPlausible(saved, wa, ww, wh)) {
    gx = saved.x
    gy = saved.y
  }
  win.setBounds(clampCompactTopLeft(gx, gy, ww, wh, wa))
}

/** Центрированная панель приложения (сайдбар + область контента). */
function placeSettingsPanel(win) {
  const { width: sw, height: sh, x: sx, y: sy } =
    screen.getPrimaryDisplay().workArea
  const ww = PANEL_WIDTH
  const wh = PANEL_HEIGHT
  const gx = Math.round(sx + (sw - ww) / 2)
  const gy = Math.round(sy + (sh - wh) / 2)
  win.setBounds({ x: gx, y: gy, width: ww, height: wh })
}

/** @param {import('electron').BrowserWindow | null} win */
function applyGhostShellLayout(win, mode) {
  if (!win || win.isDestroyed()) return
  shellLayoutMode = mode === 'settings' ? 'settings' : 'compact'
  if (mode === 'settings') {
    win.setAlwaysOnTop(false)
    win.setResizable(true)
    placeSettingsPanel(win)
    win.setIgnoreMouseEvents(false)
    return
  }
  win.setResizable(false)
  win.setAlwaysOnTop(true)
  placeWidgetWindow(win)
  win.setIgnoreMouseEvents(true, { forward: true })
}

function loadUrlInto(win, isWidget) {
  const devUrl =
    process.env.VITE_DEV_SERVER_URL || 'http://127.0.0.1:5173'

  const useViteDevServer =
    process.env.ELECTRON_DEV === '1' && !app.isPackaged

  if (useViteDevServer) {
    const url = isWidget ? `${devUrl}#ghostSurface=widget` : devUrl
    win.loadURL(url).catch((err) => {
      console.error('Failed to load dev URL:', url, err)
    })
  } else if (isWidget) {
    win.loadFile(path.join(__dirname, '../dist/index.html'), {
      hash: 'ghostSurface=widget',
    })
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

function createPanelWindow() {
  panelWindow = new BrowserWindow({
    width: PANEL_WIDTH,
    height: PANEL_HEIGHT,
    show: false,
    transparent: true,
    frame: false,
    resizable: true,
    maximizable: true,
    fullscreenable: false,
    alwaysOnTop: false,
    skipTaskbar: false,
    hasShadow: true,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  shellLayoutMode = 'settings'
  placeSettingsPanel(panelWindow)
  panelWindow.setAlwaysOnTop(false)
  panelWindow.setIgnoreMouseEvents(false)

  if (process.platform === 'darwin') {
    panelWindow.setVisibleOnAllWorkspaces(true, {
      visibleOnFullScreen: true,
    })
  }

  panelWindow.on('closed', () => {
    panelWindow = null
    if (widgetWindow && !widgetWindow.isDestroyed()) {
      widgetWindow.close()
    }
  })

  panelWindow.once('ready-to-show', () => {
    panelWindow.show()
    panelWindow.setIgnoreMouseEvents(false)
  })

  panelWindow.webContents.once('did-finish-load', () => {
    flushStatusBacklog()
  })

  loadUrlInto(panelWindow, false)
}

function createWidgetWindow() {
  widgetWindow = new BrowserWindow({
    width: WIDGET_WIDTH,
    height: WIDGET_HEIGHT,
    show: false,
    transparent: true,
    frame: false,
    resizable: false,
    maximizable: false,
    fullscreenable: false,
    alwaysOnTop: true,
    skipTaskbar: false,
    hasShadow: false,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  placeWidgetWindow(widgetWindow)
  widgetWindow.setAlwaysOnTop(true)
  widgetWindow.setIgnoreMouseEvents(true, { forward: true })

  if (process.platform === 'darwin') {
    widgetWindow.setVisibleOnAllWorkspaces(true, {
      visibleOnFullScreen: true,
    })
  }

  widgetWindow.on('closed', () => {
    widgetWindow = null
  })

  widgetWindow.on('move', () => {
    scheduleSaveCompactOverlayPosition(widgetWindow)
  })

  widgetWindow.once('ready-to-show', () => {
    widgetWindow.show()
    widgetWindow.setIgnoreMouseEvents(true, { forward: true })
  })

  widgetWindow.webContents.once('did-finish-load', () => {
    flushStatusBacklog()
  })

  loadUrlInto(widgetWindow, true)
}

function createWindows() {
  createPanelWindow()
  createWidgetWindow()
}

function registerGlobalShortcut() {
  const ok = globalShortcut.register(GLOBAL_SHORTCUT, () => {
    for (const win of BrowserWindow.getAllWindows()) {
      if (!win.isDestroyed()) {
        win.webContents.send('wispr:global-listening')
      }
    }
  })
  // #region agent log
  agentDebugLog('H16', 'web/electron/main.cjs:registerGlobalShortcut', 'register Alt+Space', {
    ok,
    electronPid: process.pid,
  })
  // #endregion

  if (!ok) {
    console.warn(
      `[wispr] Не удалось зарегистрировать глобальный шорткат "${GLOBAL_SHORTCUT}".`,
    )
  }

  const spec = loadDictationHotkeySpec()
  const acc = hotkeyToElectronAccelerator(spec.hotkey)
  if (registeredDictationAccelerator) {
    try {
      globalShortcut.unregister(registeredDictationAccelerator)
    } catch (e) {
      /* ignore */
    }
    registeredDictationAccelerator = null
  }
  if (!acc) {
    console.warn('[ghost-writer] Не удалось сопоставить hotkey с Electron accelerator:', spec.hotkey)
    return
  }

  const okDict = globalShortcut.register(acc, () => {
    const now = Date.now()
    if (now - lastDictationShortcutTs < 350) {
      // #region agent log
      agentDebugLog(
        'H17',
        'web/electron/main.cjs:dictationShortcutIgnored',
        'dictation accelerator ignored by debounce',
        {
          accelerator: acc,
          deltaMs: now - lastDictationShortcutTs,
          electronPid: process.pid,
        },
      )
      // #endregion
      return
    }
    lastDictationShortcutTs = now

    // #region agent log
    agentDebugLog('H17', 'web/electron/main.cjs:dictationShortcut', 'dictation accelerator fired', {
      accelerator: acc,
      handsFreeEnabled: spec.handsFreeEnabled,
      electronPid: process.pid,
    })
    // #endregion

    if (dictateAutoUpTimer) {
      clearTimeout(dictateAutoUpTimer)
      dictateAutoUpTimer = null
    }

    if (spec.handsFreeEnabled) {
      dictateHandsFreeOpen = !dictateHandsFreeOpen
      sendDictateEdgeToBackend(dictateHandsFreeOpen)
      return
    }

    // press-to-talk: globalShortcut не даёт release, эмулируем короткое удержание
    sendDictateEdgeToBackend(true)
    dictateAutoUpTimer = setTimeout(() => {
      sendDictateEdgeToBackend(false)
      dictateAutoUpTimer = null
    }, 220)
  })

  // #region agent log
  agentDebugLog('H17', 'web/electron/main.cjs:registerGlobalShortcut', 'register dictation accelerator', {
    ok: okDict,
    accelerator: acc,
    rawHotkey: spec.hotkey,
    handsFreeEnabled: spec.handsFreeEnabled,
    electronPid: process.pid,
  })
  // #endregion

  if (!okDict) {
    console.warn('[ghost-writer] Не удалось зарегистрировать dictation accelerator:', acc)
    return
  }
  registeredDictationAccelerator = acc
}

app.whenReady().then(async () => {
  // #region agent log
  agentDebugLog('H7', 'web/electron/main.cjs:whenReady', 'app.whenReady reached', {
    electronPid: process.pid,
    alreadyHasPythonChild: Boolean(pythonChild),
  })
  agentDebugLog('H13', 'web/electron/main.cjs:dock-state', 'dock state at startup', {
    electronPid: process.pid,
    platform: process.platform,
    dockVisible:
      process.platform === 'darwin' && app.dock && typeof app.dock.isVisible === 'function'
        ? app.dock.isVisible()
        : null,
  })
  // #endregion
  const skipPython = process.env.GHOST_WRITER_UI_ONLY === '1'

  if (!skipPython) {
    try {
      statusServer = await startStatusServer()
      const addr = statusServer.address()
      const port = typeof addr === 'object' && addr ? addr.port : 0
      spawnPythonBackend(port)
    } catch (err) {
      console.error('[ghost-writer] TCP сервер статуса не поднялся:', err)
    }
  } else {
    console.warn('[ghost-writer] GHOST_WRITER_UI_ONLY=1 — Python не запускается')
  }

  createWindows()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindows()
  })

  registerGlobalShortcut()

  ipcMain.on('wispr:set-window-passthrough', (event, raw) => {
    const enabled =
      typeof raw === 'boolean' ? raw : raw && raw.enabled !== undefined
        ? Boolean(raw.enabled)
        : true
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win || win.isDestroyed()) return
    if (enabled) {
      win.setIgnoreMouseEvents(true, { forward: true })
    } else {
      win.setIgnoreMouseEvents(false)
    }
  })

  ipcMain.on('ghost:set-shell-layout', (_, payload) => {
    const mode = payload && payload.mode === 'settings' ? 'settings' : 'compact'
    if (panelWindow && !panelWindow.isDestroyed()) {
      applyGhostShellLayout(panelWindow, mode)
    }
  })

  ipcMain.handle('ghost:list-audio-inputs', async () => {
    const msg = await sendToBackendAndWait({ type: 'list_audio_inputs' })
    if (!msg || !msg.ok) {
      throw new Error(typeof msg?.error === 'string' ? msg.error : 'Не удалось получить список микрофонов')
    }
    return {
      devices: Array.isArray(msg.devices) ? msg.devices : [],
      defaultIndex: msg.default_index == null ? null : Number(msg.default_index),
      currentIndex: msg.current_index == null ? null : Number(msg.current_index),
    }
  })

  ipcMain.handle('ghost:set-audio-input-device', async (_evt, deviceIndex) => {
    const msg = await sendToBackendAndWait({
      type: 'set_audio_input_device',
      device: deviceIndex === undefined ? null : deviceIndex,
    })
    if (!msg || !msg.ok) {
      throw new Error(typeof msg?.error === 'string' ? msg.error : 'Не удалось сохранить микрофон')
    }
    return { currentIndex: msg.current_index == null ? null : Number(msg.current_index) }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

// #region agent log
app.on('second-instance', (_event, argv) => {
  agentDebugLog('H7', 'web/electron/main.cjs:second-instance', 'second app instance detected', {
    electronPid: process.pid,
    argvHead: Array.isArray(argv) ? argv.slice(0, 6) : [],
  })
})
// #endregion

app.on('before-quit', () => {
  appIsQuitting = true
  if (dictateAutoUpTimer) {
    clearTimeout(dictateAutoUpTimer)
    dictateAutoUpTimer = null
  }
  if (registeredDictationAccelerator) {
    try {
      globalShortcut.unregister(registeredDictationAccelerator)
    } catch (e) {
      /* ignore */
    }
    registeredDictationAccelerator = null
  }
  if (widgetPositionSaveTimer) {
    clearTimeout(widgetPositionSaveTimer)
    widgetPositionSaveTimer = null
  }
  if (widgetWindow && !widgetWindow.isDestroyed()) {
    saveCompactOverlayPosition(widgetWindow)
  }
  killPythonChild()
  if (statusServer) {
    try {
      statusServer.close()
    } catch (e) {
      /* ignore */
    }
    statusServer = null
  }
})

app.on('will-quit', () => {
  killPythonChild()
  globalShortcut.unregisterAll()
})
