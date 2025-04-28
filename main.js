const remoteMain = require('@electron/remote/main')
const { app, BrowserWindow, ipcMain, screen, shell, dialog, Tray, Menu } = require('electron')
const { autoUpdater } = require('electron-updater')
const path = require('path')
const { spawn } = require('child_process')
const fs = require('fs')

let mainWindow
let loadingWindow
let tray = null
let updateAvailable = false
let backendProcess = null
const HOST = '127.0.0.1'
const PORT = 3456
const isDev = process.env.NODE_ENV === 'development'
const locales = {
  'zh-CN': {
    show: '显示窗口',
    exit: '退出'
  },
  'en-US': {
    show: 'Show Window',
    exit: 'Exit'
  }
};
let currentLanguage = 'zh-CN';

// 配置日志文件路径
const logDir = path.join(app.getPath('userData'), 'logs')
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true })
}

function createLoadingWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize
  loadingWindow = new BrowserWindow({
    width: 600,
    height: 500,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    icon: 'static/source/icon.png',
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      devTools: false
    }
  })
  
  // 加载本地等待页面
  loadingWindow.loadFile(path.join(__dirname, 'static/loading.html'))
}

function startBackend() {
  const spawnOptions = {
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
    shell: false,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      NODE_ENV: isDev ? 'development' : 'production'
    }
  }

  if (isDev) {
    // 开发模式使用Python启动
    const backendScript = path.join(__dirname, 'server.py')
    backendProcess = spawn('./.venv/Scripts/python.exe', [
      'server.py',
      '--port', PORT.toString(),
      '--host', HOST,
    ], spawnOptions)
  } else {
    // 生产模式使用编译后的可执行文件
    let serverExecutable
    switch (process.platform) {
      case 'win32':
        serverExecutable = 'server.exe'
        break
      case 'darwin':
        serverExecutable = 'server'
        break
      case 'linux':
        serverExecutable = 'server'
        break
      default:
        throw new Error(`Unsupported platform: ${process.platform}`)
    }

    const exePath = path.join(
      process.env.PORTABLE_EXECUTABLE_DIR || app.getAppPath(),
      '../server',
      serverExecutable
    ).replace('app.asar', 'app.asar.unpacked')
    
    spawnOptions.env.UV_THREADPOOL_SIZE = '4'
    spawnOptions.env.NODE_OPTIONS = '--max-old-space-size=4096'

    // 设置可执行权限(仅在 Unix 系统)
    if (process.platform !== 'win32') {
      try {
        fs.chmodSync(exePath, '755')
      } catch (err) {
        console.error('Failed to set executable permissions:', err)
      }
    }
    
    backendProcess = spawn(exePath, [], {
      ...spawnOptions,
      cwd: path.dirname(exePath)
    })
  }

  // 日志处理
  const logStream = fs.createWriteStream(
    path.join(logDir, `backend-${Date.now()}.log`),
    { flags: 'a' }
  )
  
  backendProcess.stdout.on('data', (data) => {
    logStream.write(`[INFO] ${data}`)
    if (loadingWindow) {
      loadingWindow.webContents.send('log', data.toString())
    }
  })
  
  backendProcess.stderr.on('data', (data) => {
    logStream.write(`[ERROR] ${data}`)
    if (loadingWindow) {
      loadingWindow.webContents.send('error', data.toString())
    }
  })

  backendProcess.on('error', (err) => {
    logStream.write(`Process error: ${err.message}`)
    if (loadingWindow) {
      loadingWindow.webContents.send('error', err.message)
    }
  })

  backendProcess.on('close', (code) => {
    logStream.end(`\nProcess exited with code ${code}\n`)
  })
}

async function waitForBackend() {
  const MAX_RETRIES = 30
  const RETRY_INTERVAL = 1000
  let retries = 0

  const updateProgress = (progress) => {
    if (loadingWindow && !loadingWindow.isDestroyed()) {
      loadingWindow.webContents.send('progress-update', {
        progress: Math.min(progress, 95)
      })
    }
  }

  while (retries < MAX_RETRIES) {
    try {
      const response = await fetch(`http://${HOST}:${PORT}/health`)
      if (response.ok) {
        updateProgress(100)
        return
      }
    } catch (err) {
      retries++
      updateProgress((retries / MAX_RETRIES) * 90)
      await new Promise(resolve => setTimeout(resolve, RETRY_INTERVAL))
    }
  }
  throw new Error('Backend failed to start')
}

// 配置自动更新
function setupAutoUpdater() {
  // 检查更新出错
  autoUpdater.on('error', (err) => {
    mainWindow.webContents.send('update-error', err.message)
  })

  // 检查到新版本
  autoUpdater.on('update-available', (info) => {
    updateAvailable = true
    mainWindow.webContents.send('update-available', info)
  })

  // 没有新版本
  autoUpdater.on('update-not-available', () => {
    updateAvailable = false
    mainWindow.webContents.send('update-not-available')
  })

  // 下载进度
  autoUpdater.on('download-progress', (progressObj) => {
    mainWindow.webContents.send('download-progress', progressObj)
  })

  // 下载完成
  autoUpdater.on('update-downloaded', () => {
    mainWindow.webContents.send('update-downloaded')
  })
}

// 确保只运行一个实例
const gotTheLock = app.requestSingleInstanceLock()

if (!gotTheLock) {
  app.quit()
} else {
  app.on('second-instance', (event, commandLine, workingDirectory) => {
    // 当运行第二个实例时，显示主窗口
    if (mainWindow) {
      if (!mainWindow.isVisible()) {
        mainWindow.show()
      }
      if (mainWindow.isMinimized()) {
        mainWindow.restore()
      }
      mainWindow.focus()
    }
  })
}

app.whenReady().then(async () => {
  try {
    createLoadingWindow()

    // 并行处理后端启动和预加载
    const [_, preloadComplete] = await Promise.allSettled([
      (async () => {
        startBackend()
        await waitForBackend()
      })(),
    ])

    // 关闭加载窗口
    if (loadingWindow && !loadingWindow.isDestroyed()) {
      loadingWindow.close()
      loadingWindow = null
    }

    // 创建主窗口
    console.log('Creating main window...')
    const { width, height } = screen.getPrimaryDisplay().workAreaSize
    mainWindow = new BrowserWindow({
      width: width,
      height: height,
      frame: false,
      show: false,
      icon: 'static/source/icon.png',
      webPreferences: {
        preload: path.join(__dirname, 'static/js/preload.js'),
        nodeIntegration: false,
        sandbox: false,
        contextIsolation: true,
        enableRemoteModule: false,
        webSecurity: false,
        devTools: isDev, // 开发模式下启用开发者工具，但是不默认展开
        partition: 'persist:main-session',
      }
    })

    remoteMain.enable(mainWindow.webContents)
    // 设置自动更新
    setupAutoUpdater()

    // 检查更新IPC
    ipcMain.handle('check-for-updates', () => {
      if (isDev) {
        console.log('Auto updates are disabled in development mode.')
        return
      }
      return autoUpdater.checkForUpdates()
    })

    // 下载更新IPC
    ipcMain.handle('download-update', () => {
      if (updateAvailable) {
        return autoUpdater.downloadUpdate()
      }
    })

    // 安装更新IPC
    ipcMain.handle('quit-and-install', () => {
      autoUpdater.quitAndInstall()
    })
            
    // 加载主页面
    await mainWindow.loadURL(`http://${HOST}:${PORT}`)
    mainWindow.show()
    ipcMain.on('set-language', (_, lang) => {
      currentLanguage = lang;
      updateTrayMenu();
    });
    // 创建系统托盘
    createTray()

    // 窗口控制事件
    ipcMain.handle('window-action', (_, action) => {
      switch (action) {
        case 'minimize':
          mainWindow.minimize()
          break
        case 'maximize':
          mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize()
          break
        case 'close':
          mainWindow.close()
          break
      }
    })

    // 窗口状态同步
    mainWindow.on('maximize', () => {
      mainWindow.webContents.send('window-state', 'maximized')
    })
    mainWindow.on('unmaximize', () => {
      mainWindow.webContents.send('window-state', 'normal')
    })
    
    // 窗口关闭事件处理 - 最小化到托盘而不是退出
    mainWindow.on('close', (event) => {
      if (!app.isQuitting) {
        event.preventDefault()
        mainWindow.hide()
        return false
      }
      return true
    })

    // 其他IPC处理...
    ipcMain.on('open-external', (event, url) => {
      shell.openExternal(url)
        .then(() => console.log(`Opened ${url} in the default browser.`))
        .catch(err => console.error(`Error opening ${url}:`, err))
    })
    ipcMain.handle('readFile', async (_, path) => {
      return fs.promises.readFile(path);
    });
    // 文件对话框处理器
    ipcMain.handle('open-file-dialog', async (options) => {
      const result = await dialog.showOpenDialog({
        properties: ['openFile', 'multiSelections'],
        filters: [
          { name: '所有文件', extensions: ['*'] }
        ]
      })
      return result
    })

    ipcMain.handle('check-path-exists', (_, path) => {
      return fs.existsSync(path)
    })

  } catch (err) {
    console.error('启动失败:', err)
    if (loadingWindow && !loadingWindow.isDestroyed()) {
      loadingWindow.close()
    }
    dialog.showErrorBox('启动失败', `服务启动失败: ${err.message}`)
    app.quit()
  }
})

// 应用退出处理
app.on('before-quit', () => {
  app.isQuitting = true
  if (backendProcess) {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', backendProcess.pid, '/f', '/t'])
    } else {
      backendProcess.kill('SIGKILL')
    }
  }
})

// 自动退出处理
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// 处理渲染进程崩溃
app.on('render-process-gone', (event, webContents, details) => {
  console.error('渲染进程崩溃:', details)
  dialog.showErrorBox('应用崩溃', `渲染进程异常: ${details.reason}`)
})

// 处理主进程未捕获异常
process.on('uncaughtException', (err) => {
  console.error('未捕获异常:', err)
  if (loadingWindow && !loadingWindow.isDestroyed()) {
    loadingWindow.close()
  }
  dialog.showErrorBox('致命错误', `未捕获异常: ${err.message}`)
  app.quit()
})

function createTray() {
  const iconPath = path.join(__dirname, 'static/source/icon.png');
  if (!tray) {
    tray = new Tray(iconPath);
    tray.setToolTip('Super Agent Party');
    tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        if (mainWindow.isMinimized()) mainWindow.restore();
          mainWindow.focus();
        } else {
          mainWindow.show();
        }
      }
    });
  }
  updateTrayMenu();
}
function updateTrayMenu() {
  const contextMenu = Menu.buildFromTemplate([
    {
      label: locales[currentLanguage].show,
      click: () => {
        if (mainWindow) {
          mainWindow.show()
          mainWindow.focus()
        }
      }
    },
    { type: 'separator' },
    {
      label: locales[currentLanguage].exit,
      click: () => {
        app.isQuitting = true
        app.quit()
      }
    }
  ])
  
  tray.setContextMenu(contextMenu);
}

app.commandLine.appendSwitch('disable-http-cache')
