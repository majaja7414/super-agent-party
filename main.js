const { app, BrowserWindow, ipcMain, screen } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

process.env.ELECTRON_DISABLE_SECURITY_WARNINGS = true;

let mainWindow;
let backendProcess;

function startBackend() {
  // 使用虚拟环境中的 Python 解释器
  const pythonPath = path.join(__dirname, '../super/Scripts/python.exe');
  
  backendProcess = spawn(pythonPath, [
    '-m', 'uvicorn',
    'server:app',
    '--port', '3456',
    '--host', '0.0.0.0',
    '--reload' // 保留开发时的热重载功能
  ], {
    stdio: 'pipe',
    cwd: __dirname,
    env: {
      ...process.env,
      VIRTUAL_ENV: path.join(__dirname, 'super')
    }
  });

  // 处理输出
  backendProcess.stdout.on('data', (data) => {
    console.log(`[后端] ${data}`);
    if (data.includes('Application startup complete') && mainWindow) {
      mainWindow.loadURL('http://localhost:3456');
    }
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[后端错误] ${data}`);
  });

  backendProcess.on('error', (err) => {
    console.error('后端启动失败:', err);
    app.quit();
  });
}

app.on('ready', () => {
  startBackend();

  // 延迟创建窗口确保后端就绪
  const createWindow = () => {
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.workAreaSize;
    
    mainWindow = new BrowserWindow({
      width: width,
      height: height,
      frame: false,
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false,
        webSecurity: false
      },
      show: false // 先隐藏窗口
    });

    // 监听后端准备就绪
    mainWindow.once('ready-to-show', () => {
      mainWindow.show();
    });

    // 其他 IPC 监听代码...
  };

  // 3秒后创建窗口（替代原 timeout）
  setTimeout(createWindow, 3000);
});

app.on('before-quit', () => {
  if (backendProcess) {
    // Windows 系统使用 taskkill 确保终止
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', backendProcess.pid, '/f', '/t']);
    } else {
      backendProcess.kill('SIGTERM');
    }
  }
});

// 其他原有代码...
