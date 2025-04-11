const remoteMain = require('@electron/remote/main')
const { app, BrowserWindow, ipcMain, screen, shell, dialog } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const fs = require('fs')

let mainWindow
let loadingWindow
let backendProcess = null
const HOST = '127.0.0.1'
const PORT = 3456
const isDev = process.env.NODE_ENV === 'development'

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
    backendProcess = spawn('./super/Scripts/python.exe', [
      '-m',
      'uvicorn',
      'server:app',
      '--port', PORT.toString(),
      '--host', HOST,
      '--no-access-log'
    ], spawnOptions)
  } else {
    // 生产模式使用编译后的可执行文件
    const exePath = path.join(
      process.env.PORTABLE_EXECUTABLE_DIR || app.getAppPath(),
      '../server/server.exe'
    ).replace('app.asar', 'app.asar.unpacked')
    
    spawnOptions.env.UV_THREADPOOL_SIZE = '4'
    spawnOptions.env.NODE_OPTIONS = '--max-old-space-size=4096'
    
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

app.whenReady().then(async () => {
  try {
    createLoadingWindow()

    // 并行处理后端启动和预加载
    const [_, preloadComplete] = await Promise.allSettled([
      (async () => {
        startBackend()
        await waitForBackend()
      })(),
      (async () => {
        remoteMain.initialize()
        await new Promise(resolve => setTimeout(resolve, 500)) // 模拟预加载
      })()
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
        cache: true
      }
    })

    remoteMain.enable(mainWindow.webContents)
    
    // 加载主页面
    await mainWindow.loadURL(`http://${HOST}:${PORT}`)
    mainWindow.show()

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

    // 其他IPC处理...
    ipcMain.on('open-external', (event, url) => {
      shell.openExternal(url)
        .then(() => console.log(`Opened ${url} in the default browser.`))
        .catch(err => console.error(`Error opening ${url}:`, err))
    })

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

if (isDev) {
  app.commandLine.appendSwitch('disable-http-cache')
}