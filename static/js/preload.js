const { contextBridge, shell, ipcRenderer } = require('electron');
const path = require('path');
const { remote } = require('@electron/remote/main')


// 暴露安全接口
contextBridge.exposeInMainWorld('electronAPI', {
  // 系统功能
  openExternal: (url) => shell.openExternal(url),
  openPath: (filePath) => shell.openPath(filePath),
  getAppPath: () => app.getAppPath(),
  getPath: () => remote.app.getPath('downloads'),
  // 窗口控制
  windowAction: (action) => ipcRenderer.invoke('window-action', action),
  onWindowState: (callback) => ipcRenderer.on('window-state', callback),

  // 文件对话框
  openFileDialog: () => ipcRenderer.invoke('open-file-dialog'),
  openImageDialog: () => ipcRenderer.invoke('open-image-dialog'),
  readFile: (filePath) => ipcRenderer.invoke('readFile', filePath),
  // 路径处理
  pathJoin: (...args) => path.join(...args),
  sendLanguage: (lang) => ipcRenderer.send('set-language', lang),
  // 环境检测
  isElectron: true,

  // 自动更新
  checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
  downloadUpdate: () => ipcRenderer.invoke('download-update'),
  quitAndInstall: () => ipcRenderer.invoke('quit-and-install'),
  onUpdateAvailable: (callback) => ipcRenderer.on('update-available', callback),
  onUpdateNotAvailable: (callback) => ipcRenderer.on('update-not-available', callback),
  onUpdateError: (callback) => ipcRenderer.on('update-error', callback),
  onDownloadProgress: (callback) => ipcRenderer.on('download-progress', callback),
  onUpdateDownloaded: (callback) => ipcRenderer.on('update-downloaded', callback),
  showContextMenu: (menu) => ipcRenderer.invoke('show-context-menu', menu),
});
