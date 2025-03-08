const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

// 禁用安全警告（包括 PNG iCCP 配置文件警告）
process.env.ELECTRON_DISABLE_SECURITY_WARNINGS = true;

let mainWindow;

app.on('ready', () => {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    frame: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false
    },
  });

  mainWindow.loadFile('index.html');

  // Handle window minimize, maximize, and close
  ipcMain.on('window-minimize', () => {
    mainWindow.minimize();
  });

  ipcMain.on('window-maximize', () => {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
    mainWindow.webContents.send('window-state-changed', mainWindow.isMaximized());
  });

  // 监听窗口最大化事件
  mainWindow.on('maximize', () => {
    mainWindow.webContents.send('window-state-changed', true);
  });

  // 监听窗口还原事件
  mainWindow.on('unmaximize', () => {
    mainWindow.webContents.send('window-state-changed', false);
  });

  ipcMain.on('window-close', () => {
    mainWindow.close();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
