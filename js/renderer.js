// 检查是否在Electron环境中
const isElectron = typeof process !== 'undefined' && process.versions && process.versions.electron;
let ipcRenderer;
let clipboardInstance = null; // 全局剪贴板实例
const HOST = '127.0.0.1'
const PORT = 3456
if (isElectron) {
  const { shell } = require('electron');
  ipcRenderer = require('electron').ipcRenderer;
  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href]');
    if (!link) return;
    const href = link.getAttribute('href');
    
    try {
      const url = new URL(href);
      
      // 特殊处理上传文件链接
      if (url.hostname === HOST && 
          url.port === PORT &&
          url.pathname.startsWith('/uploaded_files/')) {
        event.preventDefault();
        
        // 转换网络路径为本地文件路径
        const filename = url.pathname.split('/uploaded_files/')[1];
        const filePath = require('path').join(
          require('electron').app.getAppPath(), 
          'uploaded_files', 
          filename
        );
        
        // 用默认程序打开文件
        shell.openPath(filePath).then(err => {
          if (err) console.error('打开文件失败:', err);
        });
        
        return;
      }
      
      // 原有网络协议处理
      if (url.protocol === 'http:' || url.protocol === 'https:') {
        event.preventDefault();
        shell.openExternal(href);
      }
      
    } catch {
      // 处理相对路径
      event.preventDefault();
      window.location.href = href;
    }
  });
}

const md = window.markdownit({
  html: true,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext';
    try {
      return `<pre class="code-block"><div class="code-header"><span class="code-lang">${language}</span><button class="copy-button">复制</button></div><code class="hljs language-${language}">${hljs.highlight(str, { language }).value}</code></pre>`;
    } catch (__) {
      return `<pre class="code-block"><div class="code-header"><span class="code-lang">${language}</span><button class="copy-button">复制</button></div><code class="hljs">${md.utils.escapeHtml(str)}</code></pre>`;
    }
  }
});

// 添加更复杂的临时占位符
const LATEX_PLACEHOLDER_PREFIX = 'LATEX_PLACEHOLDER_';
let latexPlaceholderCounter = 0;

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
]
// MIME类型白名单
const MIME_WHITELIST = [
  'text/plain',
  'application/msword',
  'application/vnd.openxmlformats-officedocument',
  'application/pdf',
  'application/json',
  'text/csv',
  'text/x-python',
  'application/xml',
  'text/x-go',
  'text/x-rust',
  'text/x-swift',
  'text/x-kotlin',
  'text/x-dart',
  'text/x-ruby',
  'text/x-php'
]
// 创建Vue应用
const app = Vue.createApp({
  data() {
    return {
      isElectron: isElectron,
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
        selectedProvider: null,
      },
      reasonerSettings: {
        enabled: false, // 默认不启用
        model: '',
        base_url: '',
        api_key: '',
        selectedProvider: null,
      },
      ws: null,
      messages: [],
      userInput: '',
      isTyping: false,
      currentMessage: '',
      models: [],
      modelsLoading: false,
      modelsError: null,
      isThinkOpen: false,
      toolsSettings: {
        time: {
          enabled: false,
        },
        language: {
          enabled: false, // 默认不启用
          language: 'zh-CN',
          tone: 'normal',
        },
        inference: {
          enabled: false, // 默认不启用
        }
      },
      webSearchSettings: {
        enabled: false,
        engine: 'duckduckgo',
        when: 'before_thinking',
        duckduckgo_max_results: 10, // 默认值
        searxng_url: `http://${HOST}:8080`,
        searxng_max_results: 10, // 默认值
        tavily_max_results: 10, // 默认值
        tavily_api_key: '',
      },
      knowledgeSettings: {
        enabled: true,
        model: '',
        base_url: '',
        api_key: '',
        chunk_size: 512,
        overlap_size: 64,
        score_threshold: 0.7,
        selectedProvider: null
      },
      knowledgeFiles: [],
      expandedSections: {
        settingsBase: true,
        settingsAdvanced: true,
        reasonerConfig: true,
        time: false,
        language: true,
        inference: false,
        superapi: true,
        webSearchConfig: true,
        duckduckgoConfig: true,
        searxngConfig: true,
        tavilyConfig: true,
        knowledgeHeader: true,
      },
      showAddDialog: false,
      modelProviders: [],
      vendorOptions: [
        { label: 'OpenAI', value: 'OpenAI' },
        { label: '深度求索', value: 'Deepseek' },
        { label: '阿里云百炼', value: 'aliyun' },
        { label: '智谱AI', value: 'ZhipuAI' },
        { label: '火山引擎', value: 'Volcano' },
        { label: '月之暗面', value: 'moonshot' },
        { label: 'minimax', value: 'minimax' },
        { label: 'Ollama', value: 'Ollama' },
        { label: 'LM studio', value: 'LMstudio' },
        { label: 'Gemini', value: 'Gemini' },
        { label: 'Grok', value: 'Grok' },
        { label: 'mistral', value: 'mistral' },
        { label: '零一万物', value: 'lingyi' },
        { label: '百川', value: 'baichuan' },
        { label: '百度千帆', value: 'qianfan' },
        { label: '腾讯混元', value: 'hunyuan' },
        { label: '硅基流动', value: 'siliconflow' },
        { label: '阶跃星辰', value: 'stepfun' },
        { label: 'o3', value: 'o3' },
        { label: 'aihubmix', value: 'aihubmix' },
        { label: 'ocoolai', value: 'ocoolai' },
        { label: 'Github', value: 'Github' },
        { label: 'dmxapi', value: 'dmxapi' },
        { label: 'openrouter', value: 'openrouter' },
        { label: 'together', value: 'together' },
        { label: 'fireworks', value: 'fireworks' },
        { label: '360智脑', value: '360' },
        { label: 'Nvidia', value: 'Nvidia' },
        { label: 'hyperbolic', value: 'hyperbolic' },
        { label: 'jina', value: 'jina' },
        { label: 'gitee', value: 'gitee' },
        { label: 'PPIO', value: 'ppinfra' },
        { label: 'perplexity', value: 'perplexity' },
        { label: '无问芯穹', value: 'infini' },
        { label: '魔搭', value: 'modelscope' },
        { label: '腾讯云', value: 'tencent' },
        { label: '自定义', value: 'custom' }
      ],
      newProviderTemp: {
        vendor: '',
        url: '',
        apiKey: '',
        modelId: ''
      },
      languageOptions:[
        { value: 'zh-CN', label: '中文' }, 
        { value: 'en-US', label: 'English' },
        { value: 'ja-JP', label: '日本語' },
        { value: 'ko-KR', label: '한국어' },
        { value: 'fr-FR', label: 'Français' },
        { value: 'es-ES', label: 'Español' },
        { value: 'de-DE', label: 'Deutsch' },
        { value: 'it-IT', label: 'Italiano' },
        { value: 'ru-RU', label: 'Русский' },
        { value: 'pt-BR', label: 'Português' },
        { value: 'ar-AR', label: 'العربية' },
        { value: 'hi-IN', label: 'हिन्दी' },
        { value: 'tr-TR', label: 'Türkçe' },
        { value: 'vi-VN', label: 'Tiếng Việt' },
        { value: 'th-TH', label: 'ไทย' },
        { value: 'id-ID', label: 'Bahasa Indonesia' },
        { value: 'ms-MY', label: 'Bahasa Melayu' },
        { value: 'nl-NL', label: 'Nederlands' },
        { value: 'pl-PL', label: 'Polski' },
        { value: 'cs-CZ', label: 'Čeština' }
      ],// 语言选项
      toneOptions:[
        {value: '正常', label: '正常'},
        {value: '正式', label: '正式'},
        {value: '友好', label: '友好'},
        {value: '幽默', label: '幽默'},
        {value: '专业', label: '专业'},
        {value: '阴阳怪气', label: '阴阳怪气'},
        {value: '讽刺', label: '讽刺'},
        {value: '挑逗', label: '挑逗'},
        {value: '傲娇', label: '傲娇'},
        {value: '撒娇', label: '撒娇'},
        {value: '愤怒', label: '愤怒'},
        {value: '悲伤', label: '悲伤'},
        {value: '兴奋', label: '兴奋'},
        {value: '反驳', label: '反驳'},
      ],
      showUploadDialog: false,
      files: [],
      selectedCodeLang: 'python',
      codeExamples: {
        python: `from openai import OpenAI
client = OpenAI(
    api_key="super-secret-key",
    base_url="http://${HOST}:${PORT}/v1"
)
response = client.chat.completions.create(
    model="super-model",
    messages=[
        {"role": "user", "content": "什么是super agent party？"}
    ]
)
print(response.choices[0].message.content)`,
      javascript: `import OpenAI from 'openai';
const client = new OpenAI({
    apiKey: "super-secret-key",
    baseURL: "http://${HOST}:${PORT}/v1"
});
async function main() {
    const completion = await client.chat.completions.create({
        model: "super-model",
        messages: [
            { role: "user", content: "什么是super agent party？" }
        ]
    });
    console.log(completion.choices[0].message.content);
}
main();`,
      curl: `curl http://${HOST}:${PORT}/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer super-secret-key" \\
  -d '{
    "model": "super-model",
    "messages": [
      {"role": "user", "content": "什么是super agent party？"}
    ]
  }'`
      },  
    };
  },
  mounted() {
    this.initWebSocket();
    this.highlightCode();
    if (isElectron) {
      // 更新事件监听
      ipcRenderer.on('window-state', (_, state) => {
        this.isMaximized = state === 'maximized'
      });
    }
  },
  watch: {
    selectedCodeLang() {
      this.highlightCode();
    }
  },
  computed: {
    validProvider() {
      if (!this.newProviderTemp.vendor) return false
      if (this.newProviderTemp.vendor === 'custom') {
        return this.newProviderTemp.url.startsWith('http')
      }
      return true
    }
  },
  methods: {
    // 窗口控制
    minimizeWindow() {
      if (isElectron) ipcRenderer.invoke('window-action', 'minimize');
    },
    maximizeWindow() {
      if (isElectron) ipcRenderer.invoke('window-action', 'maximize');
    },
    closeWindow() {
      if (isElectron) ipcRenderer.invoke('window-action', 'close');
    },

    // 菜单控制
    handleSelect(key) {
      const url = `http://${HOST}:${PORT}`;

      if (key === 'web') {
        if (isElectron) {
          // 使用 IPC 向主进程发送消息
          require('electron').ipcRenderer.send('open-external', url);
        } else {
          // 如果是在普通浏览器环境中
          window.open(url, '_blank');
        }
      } else {
        // 处理其他菜单选项
        this.activeMenu = key;
      }
    },

    //  使用占位符处理 LaTeX 公式
    formatMessage(content) {
      // 使用正则表达式查找<think>...</think>标签内的内容
      const thinkTagRegexWithClose = /<think>([\s\S]*?)<\/think>/g;
      const thinkTagRegexOpenOnly = /<think>[\s\S]*$/;
      
      // 情况2: 同时存在<think>和</think>
      let formattedContent = content.replace(thinkTagRegexWithClose, match => {
        // 移除开闭标签并清理首尾空白
        const thinkContent = match.replace(/<\/?think>/g, '').trim();
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
      if (formattedContent) {
        // 使用占位符替换 LaTeX 公式
        const latexRegex = /(\$.*?\$)|(\\\[.*?\\\])|(\\\(.*?\))/g;
        let latexPlaceholders = [];
        formattedContent = formattedContent.replace(latexRegex, (match) => {
          const placeholder = LATEX_PLACEHOLDER_PREFIX + latexPlaceholderCounter++;
          latexPlaceholders.push({ placeholder, latex: match });
          return placeholder;
        });

        let rendered = md.render(formattedContent);

        // 恢复 LaTeX 公式
        latexPlaceholders.forEach(({ placeholder, latex }) => {
          rendered = rendered.replace(placeholder, latex);
        });

        this.$nextTick(() => {
          MathJax.typesetPromise()
            .then(() => {
              console.log("LaTeX formulas rendered!");
              this.initCopyButtons(); // 确保复制按钮初始化
            })
            .catch(err => console.log("MathJax typesetting error: " + err.message));
        });
        return rendered;
      }
      return '';
    },
    
    handleCopy(event) {
      const button = event.target.closest('.copy-button')
      if (button) {
        const codeBlock = button.closest('.code-block')
        const codeContent = codeBlock?.querySelector('code')?.textContent || ''
        
        navigator.clipboard.writeText(codeContent).then(() => {
          showNotification('已复制到剪贴板')
        }).catch(() => {
          showNotification('复制失败', 'error')
        })
        
        event.stopPropagation()
        event.preventDefault()
      }
    },
    
    initCopyButtons() {
      // 移除旧的ClipboardJS初始化代码
      document.querySelectorAll('.copy-button').forEach(btn => {
        btn.removeEventListener('click', this.handleCopy)
        btn.addEventListener('click', this.handleCopy)
      })
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
      this.ws = new WebSocket(`ws://${HOST}:${PORT}/ws`);
      
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
          this.toolsSettings = data.data.tools || {};
          this.reasonerSettings = data.data.reasoner || {};
          this.webSearchSettings = data.data.webSearch || {};
          this.knowledgeSettings = data.data.knowledge || {};
          this.knowledgeFiles = data.data.knowledgeFiles || [];
          this.modelProviders = data.data.modelProviders || [];
        } else if (data.type === 'settings_saved') {
          if (!data.success) {
            showNotification('设置保存失败', 'error');
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
      let fileLinks = this.files || [];
      if (fileLinks.length > 0){
        if (!this.isElectron) {
          // 如果不是在Electron环境中，则通过http://127.0.0.1:3456/load_file 接口上传文件，将文件上传到blob对应的链接
          const formData = new FormData();
          
          // 使用 'files' 作为键名，而不是 'file'
          for (const file of fileLinks) {
              if (file.file instanceof Blob) { // 确保 file.file 是一个有效的文件对象
                  formData.append('files', file.file, file.name); // 添加第三个参数为文件名
              } else {
                  console.error("Invalid file object:", file);
                  showNotification('文件上传失败: 文件无效', 'error');
                  return;
              }
          }
      
          try {
              console.log('Uploading files...');
              const response = await fetch(`http://${HOST}:${PORT}/load_file`, {
                  method: 'POST',
                  body: formData
              });
              if (!response.ok) {
                  const errorText = await response.text();
                  console.error('Server responded with an error:', errorText);
                  showNotification(`文件上传失败: ${errorText}`, 'error');
                  return;
              }
              const data = await response.json();
              if (data.success) {
                  fileLinks = data.fileLinks;
              } else {
                  showNotification('文件上传失败', 'error');
              }
          } catch (error) {
              console.error('Error during file upload:', error);
              showNotification('文件上传失败', 'error');
          }
        }
        else {
          // Electron环境处理逻辑
          try {
            console.log('Uploading Electron files...');
            const response = await fetch(`http://${HOST}:${PORT}/load_file`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                files: fileLinks.map(file => ({
                  path: file.path,
                  name: file.name
                }))
              })
            });
            if (!response.ok) {
              const errorText = await response.text();
              console.error('Server error:', errorText);
              showNotification(`文件上传失败: ${errorText}`, 'error');
              return;
            }
            const data = await response.json();
            if (data.success) {
              fileLinks = data.fileLinks;
            } else {
              showNotification('文件上传失败', 'error');
            }
          } catch (error) {
            console.error('上传错误:', error);
            showNotification('文件上传失败', 'error');
          }
        }
      }
      const fileLinks_content = fileLinks.map(fileLink => `\n[文件名：${fileLink.name}\n文件链接: ${fileLink.path}]`).join('\n');
      // 添加用户消息
      this.messages.push({
        role: 'user',
        content: userInput,
        fileLinks: fileLinks,
        fileLinks_content: fileLinks_content
      });
      this.files = [];
      let max_rounds = this.settings.max_rounds || 10;
      let messages;
      
      if (max_rounds === 0) {
        // 如果 max_rounds 是 0, 映射所有消息
        messages = this.messages.map(msg => ({
          role: msg.role,
          content: msg.content + msg.fileLinks_content
        }));
      } else {
        // 准备发送的消息历史（保留最近 max_rounds 条消息）
        messages = this.messages.slice(-max_rounds).map(msg => ({
          role: msg.role,
          content: msg.content + msg.fileLinks_content
        }));
      }

      
      this.userInput = '';

      try {
        console.log('Sending message...');
        // 请求参数需要与后端接口一致
        const response = await fetch(`http://${HOST}:${PORT}/v1/chat/completions`, {  // 修改端点路径
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            // 添加API密钥验证（如果配置了api_key）
            // 'Authorization': `Bearer ${YOUR_API_KEY}`  
          },
          body: JSON.stringify({
            messages: messages,
            stream: true,
            fileLinks: Array.isArray(fileLinks) ? fileLinks.map(fileLink => fileLink.path).flat() : []
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
                
                // 处理 reasoning_content 逻辑
                if (parsed.choices?.[0]?.delta?.reasoning_content) {
                  const lastMessage = this.messages[this.messages.length - 1];
                  let newContent = parsed.choices[0].delta.reasoning_content;
                
                  // 将新内容中的换行符转换为换行+引用符号
                  newContent = newContent.replace(/\n/g, '\n> ');
                
                  if (!this.isThinkOpen) {
                    // 新增思考块时换行并添加 "> " 前缀
                    lastMessage.content += '\n> ' + newContent;
                    this.isThinkOpen = true;
                  } else {
                    // 追加内容时直接拼接
                    lastMessage.content += newContent;
                  }
                  
                  this.scrollToBottom();
                }
                // 处理 content 逻辑
                if (parsed.choices?.[0]?.delta?.content) {
                  const lastMessage = this.messages[this.messages.length - 1];
                  if (this.isThinkOpen) {
                    lastMessage.content += '\n\n';
                    this.isThinkOpen = false; // 重置状态
                  }
                  lastMessage.content += parsed.choices[0].delta.content;
                  this.scrollToBottom();
                }
              } catch (e) {
                console.error(e);
              }
            }
          }
        }
      } catch (error) {
        showNotification(error.message, 'error');
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
        tools: this.toolsSettings,
        reasoner: this.reasonerSettings,
        webSearch: this.webSearchSettings, 
        knowledge: this.knowledgeSettings,
        knowledgeFiles: this.knowledgeFiles,
        modelProviders: this.modelProviders,
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
        const response = await fetch(`http://${HOST}:${PORT}//v1/models`);
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
      navigator.clipboard.writeText(`http://${HOST}:${PORT}/v1`)
        .then(() => {
          showNotification('API端点已复制');
        })
        .catch(() => {
          showNotification('复制失败，请手动复制', 'error');
        });
    },

    copyModel() {
      navigator.clipboard.writeText('super-model')
        .then(() => {
          showNotification('模型ID已复制');
        })
        .catch(() => {
          showNotification('复制失败，请手动复制', 'error');
        });
    },

    toggleSection(section) {
      this.expandedSections[section] = !this.expandedSections[section]
      this.autoSaveSettings()
    },
    
    // 新增点击头部的处理
    handleHeaderClick(section) {
      this.toggleSection(section)
    },
    clearMessages() {
      this.messages = [];
      this.isThinkOpen = false; // 重置思考模式状态
      this.scrollToBottom();    // 触发界面更新
    },
    sendFiles() {
      this.showUploadDialog = true;
    },
    // 文件选择处理方法
    async browseFiles() {
      if (!this.isElectron) {
        const input = document.createElement('input')
        input.type = 'file'
        input.multiple = true
        input.accept = ALLOWED_EXTENSIONS.map(ext => `.${ext}`).join(',')
        
        input.onchange = (e) => {
          const files = Array.from(e.target.files)
          const validFiles = files.filter(this.isValidFileType)
          this.handleFiles(validFiles)
        }
        input.click()
      } else {
        const result = await ipcRenderer.invoke('open-file-dialog')
        if (!result.canceled) {
          const validPaths = result.filePaths
            .filter(path => {
              const ext = path.split('.').pop()?.toLowerCase() || ''
              return ALLOWED_EXTENSIONS.includes(ext)
            })
          this.handleFiles(validPaths)
        }
      }
    },
    // 文件验证方法
    isValidFileType(file) {
      const ext = (file.name.split('.').pop() || '').toLowerCase()
      return ALLOWED_EXTENSIONS.includes(ext) || 
             MIME_WHITELIST.some(mime => file.type.includes(mime))
    },
    // 统一处理文件
    handleFiles(files) {
      if (files.length > 0) {
        this.addFiles(files)
      } else {
        this.showErrorAlert()
      }
    },
    removeFile(index) {
      this.files.splice(index, 1);
    },  
    // 错误提示
    showErrorAlert() {
      const categories = [
        "📄 办公文档：DOC/DOCX/PPT/XLS/PDF等",
        "👨💻 编程文件：JS/TS/PY/Java/C/Go/Rust等",
        "📊 数据文件：CSV/TSV/JSON/XML/YAML",
        "⚙️ 配置文件：CONF/INI/ENV/TOML",
        "📝 文本文件：TXT/MD/LOG"
      ]
      ElMessage.error(`不支持的文件类型，请选择以下类型：\n${categories.join('\n')}`)
    },
    // 拖放处理
    handleDrop(event) {
      event.preventDefault()
      const files = Array.from(event.dataTransfer.files)
        .filter(this.isValidFileType)
      this.handleFiles(files)
    },

    // 添加文件到列表
    addFiles(files) {
      const newFiles = files.map(file => {
        if (typeof file === 'string') { // Electron路径
          return {
            path: file,
            name: file.split(/[\\/]/).pop()
          }
        }
        return { // 浏览器File对象
          path: URL.createObjectURL(file),// 生成临时URL
          name: file.name,
          file: file
        }
      });
      
      this.files = [...this.files, ...newFiles];
      this.showUploadDialog = false;
    },
    highlightCode() {
      this.$nextTick(() => {
        document.querySelectorAll('pre code').forEach(block => {
          hljs.highlightElement(block);
        });
        this.initCopyButtons();
      });
    },
     // 处理知识库文件上传
    async handleKnowledgeFile(file) {
      try {
        const formData = new FormData()
        formData.append('files', file.raw)
        
        const response = await fetch(`http://${HOST}:${PORT}/load_file`, {
          method: 'POST',
          body: formData
        })
        
        const data = await response.json()
        if (data.success) {
          this.knowledgeFiles = [
            ...this.knowledgeFiles,
            ...data.fileLinks.map(link => ({
              ...link,
              localPath: file.raw.path // 保留本地路径供生成使用
            }))
          ]
        }
        this.autoSaveSettings();
      } catch (error) {
        showNotification('文件上传失败', 'error')
      }
    },
    // 删除知识库文件
    removeKnowledgeFile(index) {
      this.knowledgeFiles.splice(index, 1)
      this.autoSaveSettings();
    },
    // 生成知识库
    async generateKnowledgeBase() {
      try {
        const response = await fetch(`http://${HOST}:${PORT}/build_knowledge`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            files: this.knowledgeFiles.map(f => f.localPath),
            config: this.knowledgeSettings
          })
        })
        
        if (response.ok) {
          showNotification('知识库生成成功')
        } else {
          const error = await response.json()
          throw new Error(error.message)
        }
      } catch (error) {
        showNotification(`生成失败: ${error.message}`, 'error')
      }
    },
    addProvider() {
      this.modelProviders.push({
        id: Date.now(),
        vendor: this.newProviderTemp.vendor,
        url: this.newProviderTemp.url,
        apiKey: '',
        modelId: '',
        isNew: true
      });
      this.newProviderTemp = { vendor: '', url: '', apiKey: '', modelId: '' };
      this.autoSaveSettings();
    },
    async fetchModelsForProvider(provider) {
      try {
        const response = await fetch(`${provider.url}/models`, {
          headers: {
            'Authorization': `Bearer ${provider.apiKey}`
          }
        });
        const data = await response.json();
        provider.models = data.data.map(m => m.id);
      } catch (error) {
        showNotification('获取模型列表失败', 'error');
      }
    },
    removeProvider(index) {
      this.modelProviders.splice(index, 1);
      this.autoSaveSettings();
    },
    confirmAddProvider() {
      if (!this.newProviderTemp.vendor) {
        showNotification('请选择供应商类型', 'warning')
        return
      }
      
      const newProvider = {
        id: Date.now(),
        vendor: this.newProviderTemp.vendor,
        url: this.newProviderTemp.url,
        apiKey: '',
        modelId: '',
        models: []
      }
      
      this.modelProviders.push(newProvider)
      this.showAddDialog = false
      this.newProviderTemp = { vendor: '', url: '' }
      this.autoSaveSettings()
    },
    handleVendorChange(value) {
      const defaultUrls = {
        'OpenAI': 'https://api.openai.com/v1',
        'Deepseek': 'https://api.deepseek.com/v1',
        'aliyun': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'ZhipuAI': 'https://open.bigmodel.cn/api/paas/v4',
        'Volcano': 'https://ark.cn-beijing.volces.com/api/v3',
        'moonshot': 'https://api.moonshot.cn/v1',
        'minimax': 'https://api.minimax.chat/v1',
        'Ollama': 'http://127.0.0.1:11434/v1',
        'LMstudio': 'http://127.0.0.1:1234/v1',
        'Gemini': 'https://generativelanguage.googleapis.com/v1beta',
        'Grok': 'https://api.groq.com/openai/v1',
        'mistral': 'https://api.mistral.ai/v1',
        'lingyi': 'https://api.lingyiwanwu.com/v1',
        'baichuan': 'https://api.baichuan-ai.com/v1',
        'qianfan': 'https://qianfan.baidubce.com/v2',
        'hunyuan': 'https://api.hunyuan.cloud.tencent.com/v1',
        'siliconflow': 'https://api.siliconflow.cn/v1',
        'stepfun': 'https://api.stepfun.com/v1',
        'o3': 'https://api.o3.fan/v1',
        'aihubmix': 'https://aihubmix.com/v1',
        'ocoolai': 'https://api.ocoolai.com/v1',
        'Github': 'https://models.inference.ai.azure.com',
        'dmxapi': 'https://www.dmxapi.cn/v1',
        'openrouter': 'https://openrouter.ai/api/v1',
        'together': 'https://api.together.xyz/v1',
        'fireworks': 'https://api.fireworks.ai/inference/v1',
        '360': 'https://api.360.cn/v1',
        'Nvidia': 'https://integrate.api.nvidia.com/v1',
        'hyperbolic': 'https://api.hyperbolic.xyz/v1',
        'jina': 'https://api.jina.ai/v1',
        'gitee': 'https://ai.gitee.com/v1',
        'ppinfra': 'https://api.ppinfra.com/v3/openai/v1',
        'perplexity': 'https://api.perplexity.ai',
        'infini': 'https://cloud.infini-ai.com/maas/v1',
        'modelscope': 'https://api-inference.modelscope.cn/v1',
        'tencent': 'https://api.lkeap.cloud.tencent.com/v1',
      }
      
      if (value !== 'custom') {
        this.newProviderTemp.url = defaultUrls[value] || ''
      }
    },
    // 主模型供应商选择
    selectMainProvider(providerId) {
      const provider = this.modelProviders.find(p => p.id === providerId);
      if (provider) {
        this.settings.model = provider.modelId;
        this.settings.base_url = provider.url;
        this.settings.api_key = provider.apiKey;
        this.autoSaveSettings();
      }
    },

    // 推理模型供应商选择
    selectReasonerProvider(providerId) {
      const provider = this.modelProviders.find(p => p.id === providerId);
      if (provider) {
        this.reasonerSettings.model = provider.modelId;
        this.reasonerSettings.base_url = provider.url;
        this.reasonerSettings.api_key = provider.apiKey;
        this.autoSaveSettings();
      }
    },
    // 在methods中添加
    selectKnowledgeProvider(providerId) {
      const provider = this.modelProviders.find(p => p.id === providerId);
      if (provider) {
        this.knowledgeSettings.model = provider.modelId;
        this.knowledgeSettings.base_url = provider.url;
        this.knowledgeSettings.api_key = provider.apiKey;
        this.autoSaveSettings();
      }
    },
    handleMainProviderVisibleChange(visible) {
      if (!visible) {
        this.selectMainProvider(this.settings.selectedProvider);
      }
    },
    handleReasonerProviderVisibleChange(visible) {
      if (!visible) {
        this.selectReasonerProvider(this.reasonerSettings.selectedProvider);
      }
    },
    
    handleKnowledgeProviderVisibleChange(visible) {
      if (!visible) {
        this.selectKnowledgeProvider(this.knowledgeSettings.selectedProvider);
      }
    },
    
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
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}


// 挂载应用
app.mount('#app');
