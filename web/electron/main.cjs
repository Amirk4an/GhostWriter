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
/** Главное окно: сайдбар + контент. */
const PANEL_WIDTH = 1080
const PANEL_HEIGHT = 700
/** Отдельная капсула записи. */
const WIDGET_WIDTH = 140
const WIDGET_HEIGHT = 56
const OVERLAY_POSITION_FILE = 'overlay-compact-position.json'

let widgetPositionSaveTimer = null

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
          forwardGhostStatus(msg)
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
    const resourcesPath = process.resourcesPath
    const backendName =
      process.platform === 'win32' ? 'ghost_backend.exe' : 'ghost_backend'
    const backendPath = path.join(resourcesPath, backendName)
    if (!fs.existsSync(backendPath)) {
      console.error('[ghost-writer] бинарник бэкенда не найден:', backendPath)
      return
    }
    pythonChild = spawn(backendPath, [], {
      cwd: resourcesPath,
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

  pythonChild.on('exit', (code, signal) => {
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

  if (!ok) {
    console.warn(
      `[wispr] Не удалось зарегистрировать глобальный шорткат "${GLOBAL_SHORTCUT}".`,
    )
  }
}

app.whenReady().then(async () => {
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
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  appIsQuitting = true
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
