// main.js
const { app, BrowserWindow, ipcMain, screen, shell, dialog } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const fs = require('fs')
let mainWindow
let backendProcess = null

// 配置日志文件路径
const logDir = path.join(app.getPath('userData'), 'logs')
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true })
}

function startBackend() {
  const backendScript = path.join(__dirname, 'server.py')
  
  // 配置跨平台启动参数
  const spawnOptions = {
    cwd: __dirname,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
    shell: false
  }

  // Windows系统特殊配置
  if (process.platform === 'win32') {
    spawnOptions.detached = true
    spawnOptions.creationFlags = 0x08000000  // CREATE_NO_WINDOW
  }

  // 启动后端进程
  backendProcess = spawn('python', [
    '-m',
    'uvicorn',
    'server:app',
    '--port', '3456',
    '--host', '0.0.0.0'
  ], spawnOptions)

  // 日志文件处理
  const logStream = fs.createWriteStream(
    path.join(logDir, `backend-${Date.now()}.log`),
    { flags: 'a' }
  )

  // 处理输出
  backendProcess.stdout.on('data', (data) => {
    logStream.write(`[INFO] ${data}`)
  })

  backendProcess.stderr.on('data', (data) => {
    logStream.write(`[ERROR] ${data}`)
  })

  backendProcess.on('error', (err) => {
    logStream.write(`Process error: ${err.message}`)
  })

  backendProcess.on('close', (code) => {
    logStream.end(`\nProcess exited with code ${code}\n`)
  })
}

app.whenReady().then(() => {
  // 启动后端服务
  startBackend()

  // 创建无边框窗口
  const { width, height } = screen.getPrimaryDisplay().workAreaSize
  mainWindow = new BrowserWindow({
    width: width,
    height: height,
    frame: false,
    show: false, // 初始隐藏窗口
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false, 
      webSecurity: false,
      devTools: true, // 开发者工具
    }
  })

  // 加载页面
  mainWindow.loadURL('http://localhost:3456')
    .then(() => {
      // 页面加载完成后显示窗口
      mainWindow.show()
      if (process.env.NODE_ENV === 'development') {
        mainWindow.webContents.openDevTools()
      }
    })
    .catch(err => {
      console.error('Failed to load URL:', err)
      app.quit()
    })

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

    // 窗口状态同步（保持不变）
    mainWindow.on('maximize', () => {
      mainWindow.webContents.send('window-state', 'maximized')
    })
    mainWindow.on('unmaximize', () => {
      mainWindow.webContents.send('window-state', 'normal')
    })

    ipcMain.on('open-external', (event, url) => {
      shell.openExternal(url)
        .then(() => console.log(`Opened ${url} in the default browser.`))
        .catch(err => console.error(`Error opening ${url}:`, err));
    });

    // 文件类型分类配置
    const FILE_FILTERS = [
      { 
        name: '办公文档', 
        extensions: ['doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'pdf', 'pages', 'numbers', 'key', 'rtf', 'odt'] 
      },
      { 
        name: '编程开发', 
        extensions: [
          'js', 'ts', 'py', 'java', 'c', 'cpp', 'h', 'hpp', 'go', 'rs',
          'swift', 'kt', 'dart', 'rb', 'php', 'html', 'css', 'scss',
          'less', 'vue', 'svelte', 'jsx', 'tsx', 'json', 'xml', 'yml',
          'yaml', 'sql', 'sh'
        ]
      },
      {
        name: '数据配置',
        extensions: ['csv', 'tsv', 'txt', 'md', 'log', 'conf', 'ini', 'env', 'toml']
      }
    ]
    // 文件对话框处理器
    ipcMain.handle('open-file-dialog', async (event, options) => {
      const result = await dialog.showOpenDialog({
        properties: ['openFile', 'multiSelections'],
        filters: [
          ...FILE_FILTERS,
          { name: '所有文件', extensions: ['*'] }
        ]
      })
      return result
    })
    ipcMain.handle('check-path-exists', (_, path) => {
      return fs.existsSync(path);
    });
})

// 应用退出处理
app.on('before-quit', () => {
  if (backendProcess) {
    // 跨平台进程终止
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

// 禁用缓存
app.commandLine.appendSwitch('disable-http-cache')
