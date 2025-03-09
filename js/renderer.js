const { ipcRenderer } = require('electron');
const marked = require('marked');
// 创建Vue应用
const app = Vue.createApp({
  data() {
    return {
      isCollapse: true,
      activeMenu: 'home',
      isMaximized: false,
      settings: {
        model: '',
        base_url: '',
        api_key: '',
        temperature: 0.7,  // 默认温度值
        max_tokens: 4096,    // 默认最大输出长度
        max_rounds: 10,    // 默认最大轮数
      },
      ws: null,
      messages: [],
      userInput: '',
      isTyping: false,
      currentMessage: '',
      models: [],
      modelsLoading: false,
      modelsError: null,
      toolsSettings: {
        time: {
          enabled: false,
          timezone: 'Asia/Shanghai'
        },
        knowledge: {
          enabled: false,
          model: '',
          file_path: ''
        },
        network: {
          enabled: false,
          search_engine: 'duckduckgo'
        }
      },
      expandedSections: {
        time: false,
        knowledge: false,
        network: false
      },
      timezones: [
        { key: "Etc/GMT+12", label: "UTC-12:00" }, // 国际日期变更线西侧
        { key: "Pacific/Midway", label: "UTC-11:00 Pacific/Midway" },
        { key: "America/Adak", label: "UTC-10:00 America/Adak" },
        { key: "America/Anchorage", label: "UTC-09:00 America/Anchorage" },
        { key: "America/Los_Angeles", label: "UTC-08:00 America/Los_Angeles" },
        { key: "America/Denver", label: "UTC-07:00 America/Denver" },
        { key: "America/Chicago", label: "UTC-06:00 America/Chicago" },
        { key: "America/New_York", label: "UTC-05:00 America/New_York" },
        { key: "America/Caracas", label: "UTC-04:00 America/Caracas" },
        { key: "America/Buenos_Aires", label: "UTC-03:00 America/Buenos_Aires" },
        { key: "Atlantic/South_Georgia", label: "UTC-02:00 Atlantic/South_Georgia" },
        { key: "Atlantic/Azores", label: "UTC-01:00 Atlantic/Azores" },
        { key: "Europe/London", label: "UTC+00:00 Europe/London" },
        { key: "Europe/Paris", label: "UTC+01:00 Europe/Paris" },
        { key: "Europe/Athens", label: "UTC+02:00 Europe/Athens" },
        { key: "Europe/Moscow", label: "UTC+03:00 Europe/Moscow" },
        { key: "Asia/Dubai", label: "UTC+04:00 Asia/Dubai" },
        { key: "Asia/Kolkata", label: "UTC+05:30 Asia/Kolkata" },
        { key: "Asia/Dhaka", label: "UTC+06:00 Asia/Dhaka" },
        { key: "Asia/Jakarta", label: "UTC+07:00 Asia/Jakarta" },
        { key: "Asia/Shanghai", label: "UTC+08:00 Asia/Shanghai" },
        { key: "Japan", label: "UTC+09:00 Japan" },
        { key: "Australia/Brisbane", label: "UTC+10:00 Australia/Brisbane" },
        { key: "Pacific/Nauru", label: "UTC+12:00 Pacific/Nauru" }
      ],
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

    // 格式化消息，使用marked渲染markdown
    formatMessage(content) {
      // 使用正则表达式查找<think>...</think>标签内的内容
      const thinkTagRegexWithClose = /<think>([\s\S]*?)<\/think>/g;
      const thinkTagRegexOpenOnly = /<think>[\s\S]*$/;
      
      // 情况2: 同时存在<think>和</think>
      let formattedContent = content.replace(thinkTagRegexWithClose, match => {
        // 获取<think>...</think>之间的内容
        const thinkContent = match.replace(/<\/?think>/g, '').trim();
        // 将内容转换为引用格式
        return thinkContent.split('\n').map(line => `> ${line}`).join('\n');
      });

      // 情况1: 只有<think>，没有</think>，将<think>之后的所有内容变为引用
      if (!thinkTagRegexWithClose.test(formattedContent)) {
        formattedContent = formattedContent.replace(thinkTagRegexOpenOnly, match => {
          // 移除<think>标签
          const openThinkContent = match.replace('<think>', '').trim();
          // 将内容转换为引用格式
          return openThinkContent.split('\n').map(line => `> ${line}`).join('\n');
        });
      }

      // 使用marked解析Markdown内容
      return marked.parse(formattedContent);
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
      this.ws = new WebSocket('ws://localhost:3456/ws');
      
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
            model: data.data.model || '',
            base_url: data.data.base_url || '',
            api_key: data.data.api_key || '',
            temperature: data.data.temperature || 0.7,
            max_tokens: data.data.max_tokens || 4096,
            max_rounds: data.data.max_rounds || 10,
          };
          this.toolsSettings = data.data.tools || {
            time: { enabled: false },
            knowledge: { enabled: false },
            network: { enabled: false }
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

    handleKeydown(event) {
      if (event.key === 'Enter') {
        if (event.shiftKey) {
          // 如果同时按下了Shift键，则不阻止默认行为，允许换行
          return;
        } else {
          // 阻止默认行为，防止表单提交或新行插入
          event.preventDefault();
          this.sendMessage();
        }
      }
    },

    // 发送消息
    async sendMessage() {
      if (!this.userInput.trim() || this.isTyping) return;
      
      const userInput = this.userInput.trim();
      // 添加用户消息
      this.messages.push({
        role: 'user',
        content: userInput
      });
      
      let max_rounds = this.settings.max_rounds || 10;
      let messages;
      
      if (max_rounds === 0) {
        // 如果 max_rounds 是 0, 映射所有消息
        messages = this.messages.map(msg => ({
          role: msg.role,
          content: msg.content
        }));
      } else {
        // 准备发送的消息历史（保留最近 max_rounds 条消息）
        messages = this.messages.slice(-max_rounds).map(msg => ({
          role: msg.role,
          content: msg.content
        }));
      }

      
      this.userInput = '';
      
      try {
        // 请求参数需要与后端接口一致
        const response = await fetch('http://127.0.0.1:3456/v1/chat/completions', {  // 修改端点路径
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            // 添加API密钥验证（如果配置了api_key）
            // 'Authorization': `Bearer ${YOUR_API_KEY}`  
          },
          body: JSON.stringify({
            messages: messages,
            stream: true,
          })
        });
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error?.message || '请求失败');
        }
        
        this.isTyping = true;
        this.messages.push({
          role: 'assistant',
          content: ''
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          buffer += decoder.decode(value, { stream: true });
          
          // 处理可能包含多个事件的情况
          while (buffer.includes('\n\n')) {
            const eventEndIndex = buffer.indexOf('\n\n');
            const eventData = buffer.slice(0, eventEndIndex);
            buffer = buffer.slice(eventEndIndex + 2);
            
            if (eventData.startsWith('data: ')) {
              const jsonStr = eventData.slice(6).trim();
              if (jsonStr === '[DONE]') {
                this.isTyping = false;
                break;
              }
              
              try {
                const parsed = JSON.parse(jsonStr);
                if (parsed.choices?.[0]?.delta?.content) {
                  const lastMessage = this.messages[this.messages.length - 1];
                  lastMessage.content += parsed.choices[0].delta.content;
                  this.scrollToBottom();
                }
                // 处理错误响应
                if (parsed.error) {  
                  ElMessage.error(parsed.error.message);
                  this.isTyping = false;
                  break;
                }
              } catch (e) {
                console.error('解析错误:', e);
              }
            }
          }
        }
      } catch (error) {
        ElMessage.error(`错误: ${error.message}`);
        this.isTyping = false;
        // 恢复用户输入
        this.userInput = userInput;  
      }
      
      this.isTyping = false;
      this.scrollToBottom();
    },

    // 自动保存设置
    autoSaveSettings() {
      const payload = {
        ...this.settings,
        tools: this.toolsSettings
      }
      this.ws.send(JSON.stringify({
        type: 'save_settings',
        data: payload
      }));
    },

    // 修改后的fetchModels方法
    async fetchModels() {
      this.modelsLoading = true;
      try {
        const response = await fetch('http://127.0.0.1:3456/v1/models');
        const result = await response.json();
        
        // 双重解构获取数据
        const { data } = result;
        
        this.models = data.map(item => ({
          id: item.id,
          created: new Date(item.created * 1000).toLocaleDateString(),
        }));
        
      } catch (error) {
        console.error('获取模型数据失败:', error);
        this.modelsError = error.message;
        this.models = []; // 确保清空数据
      } finally {
        this.modelsLoading = false;
      }
    },

    // 修改copyEndpoint方法
    copyEndpoint() {
      navigator.clipboard.writeText('http://127.0.0.1:3456/v1')
        .then(() => {
          showNotification('API地址已复制');
        })
        .catch(() => {
          showNotification('复制失败，请手动复制', 'error');
        });
    },

    copyModelId(modelId) {
      navigator.clipboard.writeText(modelId)
        .then(() => {
          showNotification('模型ID已复制');
        })
        .catch(() => {
          showNotification('复制失败，请手动复制', 'error');
        });
    },

    handleSelect(key) {
      this.activeMenu = key;
      if (key === 'api') {
        this.fetchModels();
      }
    },

    toggleSection(section) {
      this.expandedSections[section] = !this.expandedSections[section]
      this.autoSaveSettings()
    },
    
    // 新增点击头部的处理
    handleHeaderClick(section) {
      this.toggleSection(section)
    }
  }
});

function showNotification(message, type = 'success') {
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.textContent = message;
  document.body.appendChild(notification);
  
  // 强制重绘确保动画生效
  void notification.offsetWidth;
  
  notification.classList.add('show');
  
  setTimeout(() => {
    notification.classList.remove('show');
    notification.classList.add('hide');
    setTimeout(() => notification.remove(), 400);
  }, 2000);
};

// 修改图标注册方式（完整示例）
app.use(ElementPlus);

// 正确注册所有图标（一次性循环注册）
const Icons = Object.entries(ElementPlusIconsVue).filter(
  ([key]) => !key.endsWith('Outline') // 排除轮廓图标（按需选择）
);

for (const [key, component] of Icons) {
  app.component(key, component);
}


// 挂载应用
app.mount('#app');
