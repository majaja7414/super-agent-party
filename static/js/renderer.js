// 在页面加载完成后添加 content-loaded 类
document.addEventListener('DOMContentLoaded', function() {
  // 设置一个短暂的延迟，确保所有资源都已加载
  setTimeout(function() {
    document.body.classList.add('content-loaded');
  }, 100);
});

// 创建Vue应用
const app = Vue.createApp({
  data() {
    return vue_data
  },
  mounted() {
    this.isMac = window.electron.isMac;
    this.initWebSocket();
    this.highlightCode();
    this.initDownloadButtons();
    if (isElectron) {
      // 检查更新
      this.checkForUpdates();
      // 监听更新事件
      window.electronAPI.onUpdateAvailable((_, info) => {
        this.updateAvailable = true;
        this.updateInfo = info;
        showNotification(this.t('updateAvailable'), 'info');
      });
      window.electronAPI.onUpdateNotAvailable(() => {
        this.updateAvailable = false;
        this.updateInfo = null;
      });
      window.electronAPI.onUpdateError((_, err) => {
        showNotification(err, 'error');
      });
      window.electronAPI.onDownloadProgress((_, progress) => {
        this.downloadProgress = progress.percent;
        this.updateIcon = 'fa-solid fa-spinner fa-spin';
      });
      window.electronAPI.onUpdateDownloaded(() => {
        this.updateDownloaded = true;
        this.updateIcon = 'fa-solid fa-rocket';
      });
    }
    this.$nextTick(() => {
      this.initPreviewButtons();
    });
    document.documentElement.setAttribute('data-theme', this.systemSettings.theme);
    if (isElectron) {
      window.electronAPI.onWindowState((_, state) => {
        this.isMaximized = state === 'maximized'
      });
    }
  },
  watch: {
    selectedCodeLang() {
      this.highlightCode();
    },
    modelProviders: {
      deep: true,
      handler(newProviders) {
        const existingIds = new Set(newProviders.map(p => p.id));
        // 自动清理无效的 selectedProvider
        [this.settings, this.reasonerSettings,this.visionSettings,this.KBSettings].forEach(config => {
          if (config.selectedProvider && !existingIds.has(config.selectedProvider)) {
            config.selectedProvider = null;
            // 可选项：同时重置相关字段
            config.model = '';
            config.base_url = '';
            config.api_key = '';
          }
          if (!config.selectedProvider && newProviders.length > 0) {
            config.selectedProvider = newProviders[0].id;
          }
        });
        [this.settings, this.reasonerSettings,this.visionSettings,this.KBSettings].forEach(config => {
          if (config.selectedProvider) this.syncProviderConfig(config);
        });
      }
    },
    'systemSettings.theme': {
      handler(newVal) {
        document.documentElement.setAttribute('data-theme', newVal);
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'loose',
          theme: newVal === 'dark' ? 'dark' : 'default'
        });
        // 强制更新 Element Plus 主题
        const themeColor = newVal === 'dark' ? '#1668dc' : '#409eff';
        const root = document.documentElement;
        root.style.setProperty('--el-color-primary', themeColor, 'important');
        if (window.__ELEMENT_PLUS_INSTANCE__) {
          window.__ELEMENT_PLUS_INSTANCE__.config.globalProperties.$ELEMENT.reload();
        }
      },
      immediate: true // 立即执行一次以应用初始值
    },
    'systemSettings.language': {
      handler(newVal) {
        if (this.isElectron) {
          window.electronAPI.sendLanguage(newVal);
        }
      },
      immediate: true
    },
  },
  computed: {
    updateButtonText() {
      if (this.updateDownloaded) return this.t('installNow');
      if (this.downloadProgress > 0) return this.t('downloading');
      return this.t('updateAvailable');
    },
    allItems() {
      return [
        ...this.files.map(file => ({ ...file, type: 'file' })),
        ...this.images.map(image => ({ ...image, type: 'image' }))
      ];
    },
    sortedConversations() {
      return [...this.conversations].sort((a, b) => b.timestamp - a.timestamp);
    },
    iconClass() {
      return this.isExpanded ? 'fa-solid fa-compress' : 'fa-solid fa-expand';
    },
    hasEnabledA2AServers() {
      return Object.values(this.a2aServers).some(server => server.enabled);
    },
    hasEnabledLLMTools() {
      return this.llmTools.some(tool => tool.enabled);
    },
    hasEnabledKnowledgeBases() {
      return this.knowledgeBases.some(kb => kb.enabled)
    },
    hasEnabledMCPServers() {
      // 检查this.mcpServers中的sever中是否有disable为false的
      return Object.values(this.mcpServers).some(server => !server.disabled);
    },
    hasFiles() {
      return this.files.length > 0
    },
    hasImages() {
      return this.images.length > 0
    },
    formValid() {
      return !!this.newLLMTool.name && !!this.newLLMTool.type
    },
    defaultBaseURL() {
      switch(this.newLLMTool.type) {
        case 'openai': 
          return 'https://api.openai.com/v1'
        case 'ollama':
          return this.isdocker ? 
            'http://host.docker.internal:11434' : 
            'http://127.0.0.1:11434'
        default:
          return ''
      }
    },
    defaultApikey() {
      switch(this.newLLMTool.type) {
        case 'ollama':
          return 'ollama'
        default:
          return ''
      }
    },
    validProvider() {
      if (!this.newProviderTemp.vendor) return false
      if (this.newProviderTemp.vendor === 'custom') {
        return this.newProviderTemp.url.startsWith('http')
      }
      return true
    },
    vendorOptions() {
      return this.vendorValues.map(value => ({
        label: this.t(`vendor.${value}`), // 使用统一的翻译键
        value
    }));
    },
    themeOptions() {
      return this.themeValues.map(value => ({
        label: this.t(`theme.${value}`),
        value // 保持原始值（推荐）
      }));
    },
    hasAgentChanges() {
      return this.mainAgent !== 'super-model' || 
        Object.values(this.agents).some(a => a.enabled)
    },
    
  },
  methods: vue_methods
});

function showNotification(message, type = 'success') {
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.textContent = message;
  document.body.appendChild(notification);
  
  // 强制重绘确保动画生效
  void notification.offsetWidth;
  
  notification.classList.add('show');

  // 设置显示时间：错误提示显示5秒，其他提示显示2秒
  const duration = type === 'error' ? 5000 : 2000;

  setTimeout(() => {
    notification.classList.remove('show');
    notification.classList.add('hide');
    setTimeout(() => notification.remove(), 400);
  }, duration);
}

// 修改图标注册方式（完整示例）
app.use(ElementPlus);

// 正确注册所有图标（一次性循环注册）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}


// 挂载应用
app.mount('#app');
