// main.js
const remoteMain = require('@electron/remote/main')
const { app, BrowserWindow, ipcMain, screen, shell, dialog } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const fs = require('fs')
let mainWindow
let backendProcess = null
const HOST = '127.0.0.1'
const PORT = 3456
// 配置日志文件路径
const logDir = path.join(app.getPath('userData'), 'logs')
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true })
}

function startBackend() {
  const backendScript = path.join(__dirname, 'server.py')
  const spawnOptions = {
    cwd: __dirname,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
    shell: false
  }
  
  // 启动后端进程
  backendProcess = spawn('./super/Scripts/python.exe', [
    '-m',
    'uvicorn',
    'server:app',
    '--port', '3456',
    '--host', HOST
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

// main.js 修改部分
async function waitForBackend() {
  const MAX_RETRIES = 30; // 最大重试次数
  const RETRY_INTERVAL = 1000; // 每次重试间隔 1 秒
  const HEALTH_CHECK_URL = `http://${HOST}:${PORT}/health`;
  console.log(`Please wait a moment, the service is starting...`);
  for (let i = 0; i < MAX_RETRIES; i++) {
    try {
      const response = await fetch(HEALTH_CHECK_URL);
      // 接收到{"status": "ok"}
      if (response.ok) {
        const data = await response.json();
        if (data.status === 'ok') {
          return; // 后端已启动
        }
      }
    } catch (err) {
      //console.log(`${i + 1}/${MAX_RETRIES}`);
    }
    await new Promise(resolve => setTimeout(resolve, RETRY_INTERVAL));
  }
  throw new Error('Backend failed to start');
}


app.whenReady().then(async () => {
  try {
    startBackend();
    await waitForBackend();
    console.log(`Please wait a moment, the window is being created...`);
    remoteMain.initialize();
    // 创建无边框窗口
    const { width, height } = screen.getPrimaryDisplay().workAreaSize
    mainWindow = new BrowserWindow({
      width: width,
      height: height,
      frame: false,
      show: false, // 初始隐藏窗口
      icon: 'static/source/icon.png',
      webPreferences: {
        preload: path.join(__dirname,'static/js/preload.js'),
        nodeIntegration: false,
        sandbox: false, 
        contextIsolation: true, // 保持启用
        enableRemoteModule: false, // 显式禁用旧版 remote
        webSecurity: false,
        devTools: true, // 开发者工具
      }
    })
    remoteMain.enable(mainWindow.webContents)
    // 加载页面
    mainWindow.loadURL(`http://${HOST}:${PORT}`)
      .then(() => {
        // 页面加载完成后显示窗口
        mainWindow.show()
        console.log(`APP run on http://${HOST}:${PORT}`);
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
            { name: '所有文件', extensions: ['*'] }
          ]
        })
        return result
      })
      ipcMain.handle('check-path-exists', (_, path) => {
        return fs.existsSync(path);
      });
    } catch (err) {
      console.error('Failed to start backend:', err);
      dialog.showErrorBox('启动失败', '后端服务启动失败，请检查日志');
      app.quit();
    }
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
