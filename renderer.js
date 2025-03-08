const { ipcRenderer } = require('electron');

// Top bar button functionality
document.getElementById('minimize-btn').addEventListener('click', () => {
  ipcRenderer.send('window-minimize');
});

document.getElementById('maximize-btn').addEventListener('click', () => {
  ipcRenderer.send('window-maximize');
});

document.getElementById('close-btn').addEventListener('click', () => {
  ipcRenderer.send('window-close');
});

// Sidebar toggle functionality
const sidebar = document.querySelector('.sidebar');
document.getElementById('home-btn').addEventListener('click', () => {
  switchPage('home');
});

document.getElementById('settings-btn').addEventListener('click', () => {
  switchPage('settings');
});

// Add event listener for toggle-sidebar-btn
document.getElementById('toggle-sidebar-btn').addEventListener('click', () => {
  sidebar.classList.toggle('collapsed');
});

// Ensure the sidebar is always full height
sidebar.style.height = '100%';

// Page switching logic
function switchPage(pageId) {
  document.querySelectorAll('.page').forEach(page => {
    page.classList.remove('active');
  });
  document.getElementById(pageId).classList.add('active');
}

// WebSocket connection to the backend
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  console.log('WebSocket connection established');
};

ws.onmessage = (event) => {
  console.log('Message from server:', event.data);
};

ws.onclose = () => {
  console.log('WebSocket connection closed');
};
