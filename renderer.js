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
      ws: null,
      messages: [],
      userInput: '',
      isTyping: false,
      currentMessage: '',
      eventSource: null
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

    // 格式化消息，将换行符转换为<br>标签
    formatMessage(content) {
      return content.replace(/\n/g, '<br>');
    },

    // 滚动到最新消息
    scrollToBottom() {
      this.$nextTick(() => {
        const container = this.$refs.messagesContainer;
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      });
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

    // 发送消息
    async sendMessage() {
      if (!this.userInput.trim() || this.isTyping) return;
      
      // 添加用户消息
      this.messages.push({
        role: 'user',
        content: this.userInput
      });
      
      // 准备发送的消息历史
      const messages = this.messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }));
      
      // 清空输入框
      const userInput = this.userInput;
      this.userInput = '';
      
      try {
        // 关闭之前的EventSource连接
        if (this.eventSource) {
          this.eventSource.close();
        }
        
        // 发送消息并获取流式响应
        const response = await fetch('http://localhost:3456/chat/completions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            messages: messages,
            model: this.settings.modelName || 'gpt-3.5-turbo'
          })
        });
        
        if (!response.ok) {
          throw new Error('请求失败');
        }
        
        // 创建新的EventSource来接收流式响应
        this.isTyping = true;
        this.messages.push({
          role: 'assistant',
          content: ''
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') {
                this.isTyping = false;
                break;
              }
              
              try {
                const parsed = JSON.parse(data);
                if (parsed.content) {
                  const lastMessage = this.messages[this.messages.length - 1];
                  lastMessage.content += parsed.content;
                  this.scrollToBottom();
                } else if (parsed.error) {
                  ElMessage.error(parsed.error);
                  this.isTyping = false;
                }
              } catch (e) {
                console.error('解析响应失败:', e);
              }
            }
          }
        }
      } catch (error) {
        ElMessage.error('发送消息失败');
        this.isTyping = false;
        // 恢复输入内容
        this.userInput = userInput;
      }
      
      this.scrollToBottom();
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
