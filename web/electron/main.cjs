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

let mainWindow = null
let pythonChild = null
let statusServer = null
let statusSocket = null
let appIsQuitting = false
/** Последние сообщения до готовности окна */
const statusBacklog = []
const BACKLOG_MAX = 32

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

function forwardGhostStatus(msg) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('ghost:status', msg)
  } else {
    statusBacklog.push(msg)
    while (statusBacklog.length > BACKLOG_MAX) {
      statusBacklog.shift()
    }
  }
}

function flushStatusBacklog() {
  if (!mainWindow || mainWindow.isDestroyed()) return
  for (const msg of statusBacklog) {
    mainWindow.webContents.send('ghost:status', msg)
  }
  statusBacklog.length = 0
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
  const rootDir = projectRoot()
  const mainPy = path.join(rootDir, 'main.py')
  if (!fs.existsSync(mainPy)) {
    console.error('[ghost-writer] main.py не найден:', mainPy)
    return
  }
  const py = resolvePythonExe(rootDir)
  const env = {
    ...process.env,
    GHOST_WRITER_ELECTRON_UI: '1',
    GHOST_WRITER_PUSH_STATUS_HOST: '127.0.0.1',
    GHOST_WRITER_PUSH_STATUS_PORT: String(port),
  }
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

function placeWidgetWindow(win) {
  const { width: sw, height: sh, x: sx, y: sy } =
    screen.getPrimaryDisplay().workArea
  const ww = 560
  const wh = 168
  const gx = Math.round(sx + (sw - ww) / 2)
  const gy = Math.round(sy + sh - wh - 20)
  win.setBounds({ x: gx, y: gy, width: ww, height: wh })
}

/** Centered panel for settings — not always-on-top so it behaves like a normal window. */
function placeSettingsPanel(win) {
  const { width: sw, height: sh, x: sx, y: sy } =
    screen.getPrimaryDisplay().workArea
  const ww = 920
  const wh = 640
  const gx = Math.round(sx + (sw - ww) / 2)
  const gy = Math.round(sy + (sh - wh) / 2)
  win.setBounds({ x: gx, y: gy, width: ww, height: wh })
}

/** @param {import('electron').BrowserWindow | null} win */
function applyGhostShellLayout(win, mode) {
  if (!win || win.isDestroyed()) return
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

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 560,
    height: 168,
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

  placeWidgetWindow(mainWindow)

  if (process.platform === 'darwin') {
    mainWindow.setVisibleOnAllWorkspaces(true, {
      visibleOnFullScreen: true,
    })
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    mainWindow.setIgnoreMouseEvents(true, { forward: true })
  })

  mainWindow.webContents.once('did-finish-load', () => {
    flushStatusBacklog()
  })

  const devUrl =
    process.env.VITE_DEV_SERVER_URL || 'http://127.0.0.1:5173'

  const useViteDevServer =
    process.env.ELECTRON_DEV === '1' && !app.isPackaged

  if (useViteDevServer) {
    mainWindow.loadURL(devUrl).catch((err) => {
      console.error('Failed to load dev URL:', devUrl, err)
    })
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

function registerGlobalShortcut() {
  const ok = globalShortcut.register(GLOBAL_SHORTCUT, () => {
    if (!mainWindow || mainWindow.isDestroyed()) return
    mainWindow.webContents.send('wispr:global-listening')
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

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })

  registerGlobalShortcut()

  ipcMain.on('wispr:set-window-passthrough', (_, enabled) => {
    if (!mainWindow || mainWindow.isDestroyed()) return
    if (enabled) {
      mainWindow.setIgnoreMouseEvents(true, { forward: true })
    } else {
      mainWindow.setIgnoreMouseEvents(false)
    }
  })

  ipcMain.on('ghost:set-shell-layout', (_, payload) => {
    const mode = payload && payload.mode === 'settings' ? 'settings' : 'compact'
    applyGhostShellLayout(mainWindow, mode)
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  appIsQuitting = true
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
  globalShortcut.unregisterAll()
})
