const { ipcRenderer } = require('electron');

// 创建Vue应用
const app = Vue.createApp({
  data() {
    return {
      isCollapse: true,
      activeMenu: 'home',
      isMaximized: false,
      settings: {
        modelName: '',
        baseURL: '',
        apiKey: ''
      },
      ws: null
    };
  },
  mounted() {
    this.initWebSocket();
    
    // 监听窗口状态变化
    ipcRenderer.on('window-state-changed', (_, isMaximized) => {
      this.isMaximized = isMaximized;
    });
  },
  methods: {
    // 窗口控制
    minimizeWindow() {
      ipcRenderer.send('window-minimize');
    },
    maximizeWindow() {
      ipcRenderer.send('window-maximize');
    },
    closeWindow() {
      ipcRenderer.send('window-close');
    },

    // 菜单处理
    handleSelect(key) {
      this.activeMenu = key;
    },

    // WebSocket相关
    initWebSocket() {
      this.ws = new WebSocket('ws://localhost:8000/ws');
      
      this.ws.onopen = () => {
        console.log('WebSocket connection established');
      };

      this.ws.onmessage = (event) => {
        let data;
        try {
          data = JSON.parse(event.data);
        } catch (e) {
          console.log('Message from server:', event.data);
          return;
        }

        if (data.type === 'settings') {
          this.settings = {
            modelName: data.data.modelName || '',
            baseURL: data.data.baseURL || '',
            apiKey: data.data.apiKey || ''
          };
        } else if (data.type === 'settings_saved') {
          if (!data.success) {
            ElMessage.error('设置保存失败');
          }
        }
      };

      this.ws.onclose = () => {
        console.log('WebSocket connection closed');
      };
    },

    // 自动保存设置
    autoSaveSettings() {
      this.ws.send(JSON.stringify({
        type: 'save_settings',
        data: this.settings
      }));
    }
  }
});

// 使用Element Plus
app.use(ElementPlus);

// 注册图标组件
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component);
}

// 挂载应用
app.mount('#app');
