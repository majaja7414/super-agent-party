const remoteMain = require('@electron/remote/main')
const { app, BrowserWindow, ipcMain, screen, shell, dialog, Tray, Menu } = require('electron')
const { clipboard, nativeImage } = require('electron')
const { autoUpdater } = require('electron-updater')
const path = require('path')
const { spawn } = require('child_process')
const fs = require('fs')
const os = require('os')
const net = require('net') // 添加 net 模块用于端口检测

let pythonExec;
let isQuitting = false;

// 判断操作系统
if (os.platform() === 'win32') {
  // Windows
  pythonExec = path.join('.venv', 'Scripts', 'python.exe');
} else {
  // macOS / Linux
  pythonExec = path.join('.venv', 'bin', 'python3');
}

let mainWindow
let loadingWindow
let tray = null
let updateAvailable = false
let backendProcess = null
const HOST = '127.0.0.1'
let PORT = 3456 // 改为 let，允许修改
const DEFAULT_PORT = 3456 // 保存默认端口
const isDev = process.env.NODE_ENV === 'development'
const locales = {
  'zh-CN': {
    show: '显示窗口',
    exit: '退出',
    cut: '剪切',
    copy: '复制',
    paste: '粘贴',
    copyImage: '复制图片',
    copyImageLink: '复制图片链接',
    supportedFiles: '支持的文件',
    allFiles: '所有文件',
    supportedimages: '支持的图片',
  },
  'en-US': {
    show: 'Show Window',
    exit: 'Exit',
    cut: 'Cut',
    copy: 'Copy',
    paste: 'Paste',
    copyImage: 'Copy Image',
    copyImageLink: 'Copy Image Link',
    supportedFiles: 'Supported Files',
    allFiles: 'All Files',
    supportedimages: 'Supported Images',
  }
};
const ALLOWED_EXTENSIONS = [
  // 办公文档
  'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'pdf', 'pages', 
  'numbers', 'key', 'rtf', 'odt',
  
  // 编程开发
  'js', 'ts', 'py', 'java', 'c', 'cpp', 'h', 'hpp', 'go', 'rs',
  'swift', 'kt', 'dart', 'rb', 'php', 'html', 'css', 'scss', 'less',
  'vue', 'svelte', 'jsx', 'tsx', 'json', 'xml', 'yml', 'yaml', 
  'sql', 'sh',
  
  // 数据配置
  'csv', 'tsv', 'txt', 'md', 'log', 'conf', 'ini', 'env', 'toml'
  ];
const ALLOWED_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'];
let currentLanguage = 'zh-CN';

// 构建菜单项
let menu;

// 配置日志文件路径
const logDir = path.join(app.getPath('userData'), 'logs')
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true })
}

// 获取配置文件路径
function getConfigPath() {
  return path.join(app.getPath('userData'), 'config.json');
}

// 加载环境变量
function loadEnvVariables() {
  const configPath = getConfigPath();
  if (fs.existsSync(configPath)) {
    const rawData = fs.readFileSync(configPath);
    const config = JSON.parse(rawData);
    for (const key in config) {
      process.env[key] = config[key];
    }
  }
}

loadEnvVariables();

// 新增：检测端口是否可用
function isPortAvailable(port) {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.listen(port, HOST, () => {
      server.once('close', () => resolve(true))
      server.close()
    })
    server.on('error', () => resolve(false))
  })
}

// 新增：查找可用端口
async function findAvailablePort(startPort = DEFAULT_PORT, maxAttempts = 10) {
  for (let i = 0; i < maxAttempts; i++) {
    const port = startPort + i
    if (await isPortAvailable(port)) {
      return port
    }
  }
  throw new Error(`无法找到可用端口，已尝试 ${startPort} 到 ${startPort + maxAttempts - 1}`)
}

const networkVisible = process.env.networkVisible === 'global';
const BACKEND_HOST = networkVisible ? '0.0.0.0' : HOST
// 保存环境变量
function saveEnvVariable(key, value) {
  const configPath = getConfigPath();
  let config = {};
  if (fs.existsSync(configPath)) {
    const rawData = fs.readFileSync(configPath);
    config = JSON.parse(rawData);
  }
  config[key] = value;
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  
  // 更新当前进程中的环境变量
  process.env[key] = value;
}


// 创建骨架屏窗口
function createSkeletonWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize
  mainWindow = new BrowserWindow({
    width: width,
    height: height,
    frame: false,
    titleBarStyle: 'hiddenInset', // macOS 特有：隐藏标题栏但仍显示原生按钮
    trafficLightPosition: { x: 10, y: 12 }, // 自定义按钮位置（可选）
    show: true,
    icon: 'static/source/icon.png',
    webPreferences: {
      preload: path.join(__dirname, 'static/js/preload.js'),
      nodeIntegration: false,
      sandbox: false,
      contextIsolation: true,
      enableRemoteModule: false,
      webSecurity: false,
      devTools: isDev,
      partition: 'persist:main-session',
    }
  })

  remoteMain.enable(mainWindow.webContents)
  
  // 加载骨架屏页面
  mainWindow.loadFile(path.join(__dirname, 'static/skeleton.html'))
  
  // 设置自动更新
  setupAutoUpdater()
  
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
}

// 修改后的启动后端函数
async function startBackend() {
  try {
    // 查找可用端口
    const availablePort = await findAvailablePort(DEFAULT_PORT)
    PORT = availablePort
    
    // 如果端口不是默认端口，记录变更
    if (PORT !== DEFAULT_PORT) {
      console.log(`默认端口 ${DEFAULT_PORT} 被占用，已切换到端口 ${PORT}`)
    }
    
    const spawnOptions = {
      stdio: ['ignore', 'ignore', 'ignore'],
      shell: false,
      env: {
        ...process.env,
        NODE_ENV: isDev ? 'development' : 'production',
        PYTHONIOENCODING: 'utf-8'
      }
    }

    // Windows 特殊处理
    if (process.platform === 'win32') {
      spawnOptions.windowsHide = true
      spawnOptions.detached = false
      spawnOptions.shell = false
      spawnOptions.windowsVerbatimArguments = false
      spawnOptions.stdio = ['ignore', 'ignore', 'ignore']
    }

    const networkVisible = process.env.networkVisible === 'global';
    const BACKEND_HOST = networkVisible ? '0.0.0.0' : HOST

    if (isDev) {
      // 开发模式
      backendProcess = spawn(pythonExec, [
        'server.py',
        '--port', PORT.toString(),
        '--host', BACKEND_HOST,
      ], spawnOptions);
    } else {
      // 生产模式
      let serverExecutable = process.platform === 'win32' ? 'server.exe' : 'server'
      const resourcesPath = process.resourcesPath || path.join(process.execPath, '..', 'resources')
      const exePath = path.join(resourcesPath, 'server', serverExecutable)
      
      console.log(`Starting backend from: ${exePath}`)
      
      backendProcess = spawn(exePath, [
        '--port', PORT.toString(),
        '--host', BACKEND_HOST,
      ], {
        ...spawnOptions,
        cwd: path.dirname(exePath)
      })
    }

    // 简化日志处理
    if (isDev) {
      const logStream = fs.createWriteStream(
        path.join(logDir, `backend-${Date.now()}.log`),
        { flags: 'a' }
      )
      
      backendProcess.stdout?.on('data', (data) => {
        logStream.write(`[INFO] ${data}`)
      })
      
      backendProcess.stderr?.on('data', (data) => {
        logStream.write(`[ERROR] ${data}`)
      })
    }

    backendProcess.on('error', (err) => {
      console.error('Backend process error:', err)
    })

    backendProcess.on('close', (code) => {
      console.log(`Backend process exited with code ${code}`)
    })

    return PORT // 返回实际使用的端口
  } catch (error) {
    console.error('启动后端服务失败:', error)
    throw error
  }
}



// 修改等待后端函数
async function waitForBackend() {
  const MAX_RETRIES = 30
  const RETRY_INTERVAL = 500
  let retries = 0

  while (retries < MAX_RETRIES) {
    try {
      const response = await fetch(`http://${HOST}:${PORT}/health`)
      if (response.ok) {
        // 后端服务准备就绪，通知骨架屏页面
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('backend-ready', { port: PORT })
        }
        return
      }
    } catch (err) {
      retries++
      await new Promise(resolve => setTimeout(resolve, RETRY_INTERVAL))
    }
  }
  throw new Error('Backend failed to start')
}

// 配置自动更新
function setupAutoUpdater() {
  autoUpdater.autoDownload = false; // 先禁用自动下载
  if (isDev) {
    autoUpdater.on('error', (err) => {
      mainWindow.webContents.send('update-error', err.message);
    });
  }
  autoUpdater.on('update-available', (info) => {
    updateAvailable = true;
    // 显示更新按钮并开始下载
    mainWindow.webContents.send('update-available', info);
    autoUpdater.downloadUpdate(); // 自动开始下载
  });
  autoUpdater.on('download-progress', (progressObj) => {
    mainWindow.webContents.send('download-progress', {
      percent: progressObj.percent.toFixed(1),
      transferred: (progressObj.transferred / 1024 / 1024).toFixed(2),
      total: (progressObj.total / 1024 / 1024).toFixed(2)
    });
  });
  autoUpdater.on('update-downloaded', () => {
    mainWindow.webContents.send('update-downloaded');
  });
}

// 确保只运行一个实例
const gotTheLock = app.requestSingleInstanceLock()

if (!gotTheLock) {
  // 如果无法获得锁（说明已经有一个实例在运行），我们不应该显示错误
  // 因为第一个实例会处理显示窗口
  setTimeout(() => {
    app.quit()
  }, 0)
  return
}

// 监听第二个实例的启动
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

// 只有在获得锁（第一个实例）时才执行初始化
app.whenReady().then(async () => {
  try {
    // 创建骨架屏窗口
    createSkeletonWindow()
    
    // 启动后端服务（现在会自动查找可用端口）
    const actualPort = await startBackend()
    
    // 等待后端服务准备就绪
    await waitForBackend()
    
    // 后端服务准备就绪后，加载完整内容
    console.log(`Backend server is running at http://${HOST}:${PORT}`)

    // 添加获取端口信息的 IPC 处理
    ipcMain.handle('get-server-info', () => {
      return {
        port: PORT,
        defaultPort: DEFAULT_PORT,
        isDefaultPort: PORT === DEFAULT_PORT
      }
    })

    ipcMain.handle('set-env', async (event, arg) => {
      saveEnvVariable(arg.key, arg.value);
    });
    //重启应用
    ipcMain.handle('restart-app', () => {
      app.relaunch();
      app.exit();
    })
    // 检查更新IPC
    ipcMain.handle('check-for-updates', async () => {
      if (isDev) {
        console.log('Auto updates are disabled in development mode.')
        return { updateAvailable: false }
      }
      try {
        const result = await autoUpdater.checkForUpdates()
        // 只返回必要的可序列化数据
        return {
          updateAvailable: updateAvailable,
          updateInfo: result ? {
            version: result.updateInfo.version,
            releaseDate: result.updateInfo.releaseDate
          } : null
        }
      } catch (error) {
        console.error('检查更新出错:', error)
        return { 
          updateAvailable: false, 
          error: error.message 
        }
      }
    })

    // 下载更新IPC
    ipcMain.handle('download-update', () => {
      if (updateAvailable) {
        return autoUpdater.downloadUpdate()
      }
    })

    // 安装更新IPC
    ipcMain.handle('quit-and-install', () => {
      setTimeout(() => autoUpdater.quitAndInstall(), 500);
    });
            
    // 加载主页面
    await mainWindow.loadURL(`http://${HOST}:${PORT}`)
    ipcMain.on('set-language', (_, lang) => {
      currentLanguage = lang;
      updateTrayMenu();
      updatecontextMenu();
    });
    // 创建系统托盘
    createTray();
    updatecontextMenu();
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
    // 修改 show-context-menu 的 IPC 处理
    ipcMain.handle('show-context-menu', async (event, { menuType, data }) => {
      let menuTemplate;
      
      if (menuType === 'image') {
        menuTemplate = [
          {
            label: locales[currentLanguage].copyImageLink,
            click: () => clipboard.writeText(data.src)
          },
          {
            label: locales[currentLanguage].copyImage,
            click: async () => {
              try {
                // 处理网络图片
                if (data.src.startsWith('http')) {
                  const response = await fetch(data.src);
                  const blob = await response.blob();
                  const buffer = await blob.arrayBuffer();
                  const image = nativeImage.createFromBuffer(Buffer.from(buffer));
                  clipboard.writeImage(image);
                }
                // 处理本地图片
                else {
                  const image = nativeImage.createFromPath(data.src);
                  clipboard.writeImage(image);
                }
              } catch (error) {
                console.error('复制图片失败:', error);
              }
            }
          }
        ];
      } else {
        // 原有基础菜单
        menuTemplate = [
          { label: locales[currentLanguage].cut, role: 'cut' },
          { label: locales[currentLanguage].copy, role: 'copy' },
          { label: locales[currentLanguage].paste, role: 'paste' }
        ];
      }

      menu = Menu.buildFromTemplate(menuTemplate);
      menu.popup(BrowserWindow.fromWebContents(event.sender));
    });
    // 监听关闭事件
    ipcMain.handle('request-stop-qqbot', async (event) => {
      const win = BrowserWindow.getAllWindows()[0]; // 获取主窗口
      if (win && !win.isDestroyed()) {
        // 通过webContents执行渲染进程方法
        await win.webContents.executeJavaScript(`
          window.stopQQBotHandler && window.stopQQBotHandler()
        `);
      }
    });
    let vrmWindow = null;

    ipcMain.handle('start-vrm-window', async () => {
      if (vrmWindow) {
        vrmWindow.focus();
        return;
      }

      const { width, height } = screen.getPrimaryDisplay().workAreaSize;
      
      vrmWindow = new BrowserWindow({
        width: 540,
        height: 960,
        x: width - 560,  // 右边距 20px
        y: height - 900, // 下边距 20px
        transparent: true,
        frame: false,
        resizable: false,
        alwaysOnTop: true,
        skipTaskbar: true,
        hasShadow: false,
        focusable: false,
        acceptFirstMouse: true,
        backgroundColor: 'rgba(0, 0, 0, 0)',
        webPreferences: {
          contextIsolation: true,
          nodeIntegration: true,
          enableRemoteModule: true,
          sandbox: false,
          webgl: true, // 启用 WebGL
          devTools: isDev,
          webAudio: true,
          autoplayPolicy: 'no-user-gesture-required', // 允许自动播放
          preload: path.join(__dirname, 'static/js/preload.js')
        }
      });

      // 加载页面
      await vrmWindow.loadURL(`http://${HOST}:${PORT}/vrm.html`);

      // 窗口关闭处理
      vrmWindow.on('closed', () => {
        vrmWindow = null;
      });

    });

    // 停止VRM窗口
    ipcMain.handle('stop-vrm-window', () => {
      if (vrmWindow && !vrmWindow.isDestroyed()) {
        vrmWindow.close();
        vrmWindow = null;
      }
    });

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
          { name: locales[currentLanguage].supportedFiles, extensions: ALLOWED_EXTENSIONS },
          { name: locales[currentLanguage].allFiles, extensions: ['*'] }
        ]
      })
      return result
    })
    ipcMain.handle('open-image-dialog', async () => {
      const result = await dialog.showOpenDialog({
        properties: ['openFile'],
        filters: [
          { name: locales[currentLanguage].supportedimages, extensions: ALLOWED_IMAGE_EXTENSIONS },
          { name: locales[currentLanguage].allFiles, extensions: ['*'] }
        ]
      })
      // 返回包含文件名和路径的对象数组
      return result
    });
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
app.on('before-quit', async (event) => {
  // 防止重复处理退出事件
  if (isQuitting) return;
  
  // 标记退出状态并阻止默认退出行为
  isQuitting = true;
  event.preventDefault();
  
  try {
    const mainWindow = BrowserWindow.getAllWindows()[0];
    
    // 1. 尝试停止QQ机器人
    if (mainWindow && !mainWindow.isDestroyed()) {
      await mainWindow.webContents.executeJavaScript(`
        if (window.stopQQBotHandler) {
          window.stopQQBotHandler();
        }
      `);
      
      // 等待机器人停止（最多1秒）
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    // 2. 停止后端进程
    if (backendProcess) {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', backendProcess.pid, '/f', '/t']);
      } else {
        backendProcess.kill('SIGKILL');
      }
      backendProcess = null;
    }
  } catch (error) {
    console.error('退出时发生错误:', error);
  } finally {
    // 3. 最终退出应用
    app.exit(0);
  }
});

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
  const iconPath = path.join(__dirname, 'static/source/icon_tray.png');
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

function updatecontextMenu() {
  menu = Menu.buildFromTemplate([
    {
      label: locales[currentLanguage].cut,
      role: 'cut'
    },
    {
      label: locales[currentLanguage].copy,
      role: 'copy'
    },
    {
      label: locales[currentLanguage].paste,
      role: 'paste'
    }
  ]);
}

app.on('web-contents-created', (e, webContents) => {
  webContents.on('new-window', (event, url) => {
  event.preventDefault();
  shell.openExternal(url);
  });
});

app.commandLine.appendSwitch('disable-http-cache')
