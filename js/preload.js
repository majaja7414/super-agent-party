// preload.js
const { contextBridge, shell } = require('electron');

contextBridge.exposeInMainWorld(
  'api', {
    openPath: (path) => shell.openPath(path)
  }
);