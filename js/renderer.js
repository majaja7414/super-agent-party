const HOST = '127.0.0.1'
const PORT = 3456
const isElectron = window.electronAPI ? true : false;
// 事件监听改造
if (isElectron) {
  document.addEventListener('click', async (event) => {
    const link = event.target.closest('a[href]');
    if (!link) return;
    const href = link.getAttribute('href');
    
    try {
      const url = new URL(href);
      
      if (url.hostname === HOST && 
          url.port === PORT &&
          url.pathname.startsWith('/uploaded_files/')) {
        event.preventDefault();
        
        // 使用预加载接口处理路径
        const filename = url.pathname.split('/uploaded_files/')[1];
        const filePath = window.electronAPI.pathJoin(
          window.electronAPI.getAppPath(), 
          'uploaded_files', 
          filename
        );
        
        await window.electronAPI.openPath(filePath);
        return;
      }
      if (['http:', 'https:'].includes(url.protocol)) {
        event.preventDefault();
        await window.electronAPI.openExternal(href); // 确保调用electronAPI
        return;
      }
      
    } catch {
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
        temperature: 0.7,  // 默认温度值
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
        },
        deepsearch: {
          enabled: false, // 默认不启用
        },
        formula: {
          enabled: true
        }
      },
      webSearchSettings: {
        enabled: false,
        engine: 'duckduckgo',
        crawler: 'jina',
        when: 'before_thinking',
        duckduckgo_max_results: 10, // 默认值
        searxng_url: `http://${HOST}:8080`,
        searxng_max_results: 10, // 默认值
        tavily_max_results: 10, // 默认值
        tavily_api_key: '',
        jina_api_key: '',
        Crawl4Ai_url: 'http://127.0.0.1:11235',
        Crawl4Ai_api_key: 'test_api_code'
      },
      knowledgeBases: [],
      showAddKbDialog: false,
      showKnowledgeDialog: false,
      activeCollapse: [],
      newKb: {
        name: '',
        introduction: '',
        providerId: null,
        model: '',
        base_url: '',
        api_key: '',
        chunk_size: 1024,
        chunk_overlap: 256,
        chunk_k: 5,
        processingStatus: 'processing',
      },
      newKbFiles: [],
      systemSettings: {
        language: 'zh-CN',
        theme: 'light',
      },
      currentLanguage: 'zh-CN',
      translations: translations,
      themeOptions: [
        { value: 'light', label: '亮色模式' },
        { value: 'dark', label: '暗色模式' }
      ],
      browserBtnColor: '#409EFF',
      isBrowserOpening: false,
      expandedSections: {
        settingsBase: true,
        reasonerConfig: true,
        language: true,
        superapi: true,
        webSearchConfig: true,
        duckduckgoConfig: true,
        searxngConfig: true,
        tavilyConfig: true,
        jinaConfig: true,
        Crawl4AiConfig: true,
        settingsAdvanced: false,
        reasonerAdvanced: false,
        knowledgeAdvanced: false,
      },
      abortController: null, // 用于中断请求的控制器
      isSending: false, // 是否正在发送
      showAddDialog: false,
      modelProviders: [],
      vendorOptions: [
        { label: '自定义OpenAI', value: 'custom' },
        { label: 'OpenAI', value: 'OpenAI' },
        { label: 'Ollama', value: 'Ollama' },
        { label: '深度求索', value: 'Deepseek' },
        { label: '火山引擎', value: 'Volcano' },
        { label: '硅基流动', value: 'siliconflow' },
        { label: '阿里云百炼', value: 'aliyun' },
        { label: '智谱AI', value: 'ZhipuAI' },
        { label: '月之暗面', value: 'moonshot' },
        { label: 'minimax', value: 'minimax' },
        { label: 'LM studio', value: 'LMstudio' },
        { label: 'Gemini', value: 'Gemini' },
        { label: 'Grok', value: 'Grok' },
        { label: 'mistral', value: 'mistral' },
        { label: '零一万物', value: 'lingyi' },
        { label: '百川', value: 'baichuan' },
        { label: '百度千帆', value: 'qianfan' },
        { label: '腾讯混元', value: 'hunyuan' },
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
        { label: '腾讯云', value: 'tencent' }
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
      systemlanguageOptions:[
        { value: 'zh-CN', label: '中文' }, 
        { value: 'en-US', label: 'English' },
      ],
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
        [this.settings, this.reasonerSettings].forEach(config => {
          if (config.selectedProvider && !existingIds.has(config.selectedProvider)) {
            config.selectedProvider = null;
            // 可选项：同时重置相关字段
            config.model = '';
            config.base_url = '';
            config.api_key = '';
          }
        });
      }
    },
    'systemSettings.theme': {
      handler(newVal) {
        document.documentElement.setAttribute('data-theme', newVal);
        // 强制更新 Element Plus 主题
        const themeColor = newVal === 'dark' ? '#1668dc' : '#409eff';
        const root = document.documentElement;
        root.style.setProperty('--el-color-primary', themeColor, 'important');
        if (window.__ELEMENT_PLUS_INSTANCE__) {
          window.__ELEMENT_PLUS_INSTANCE__.config.globalProperties.$ELEMENT.reload();
        }
      },
      immediate: true // 立即执行一次以应用初始值
    }
  },
  computed: {
    hasEnabledKnowledgeBases() {
      return this.knowledgeBases.some(kb => kb.enabled)
    },
    hasFiles() {
      return this.files.length > 0
    },
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
      if (isElectron) window.electronAPI.windowAction('minimize');
    },
    maximizeWindow() {
      if (isElectron) window.electronAPI.windowAction('maximize');
    },
    closeWindow() {
      if (isElectron) window.electronAPI.windowAction('close');
    },
    handleSelect(key) {
      this.activeMenu = key;
    }, 
    //  使用占位符处理 LaTeX 公式
    formatMessage(content) {
      const parts = this.splitCodeAndText(content);
      let latexPlaceholderCounter = 0;
      const latexPlaceholders = [];
      let inUnclosedCodeBlock = false;
    
      let processedContent = parts.map(part => {
        if (part.type === 'code') {
          inUnclosedCodeBlock = !part.closed;
          return part.content; // 直接保留原始代码块内容
        } else if (inUnclosedCodeBlock) {
          // 处理未闭合代码块中的内容
          return part.content
            .replace(/`/g, '\\`') // 转义反引号
            .replace(/\$/g, '\\$'); // 转义美元符号
        } else {
          // 处理非代码内容
          // 处理think标签
          const thinkTagRegexWithClose = /<think>([\s\S]*?)<\/think>/g;
          const thinkTagRegexOpenOnly = /<think>[\s\S]*$/;
          
          let formatted = part.content
            .replace(thinkTagRegexWithClose, (_, p1) => 
              p1.split('\n').map(line => `> ${line}`).join('\n')
            )
            .replace(thinkTagRegexOpenOnly, match => 
              match.replace('<think>', '').split('\n').map(line => `> ${line}`).join('\n')
            );
    
          // 处理LaTeX公式
          const latexRegex = /(\$.*?\$)|(\\\[.*?\\\])|(\\$.*?$)/g;
          return formatted.replace(latexRegex, (match) => {
            const placeholder = `LATEX_PLACEHOLDER_${latexPlaceholderCounter++}`;
            latexPlaceholders.push({ placeholder, latex: match });
            return placeholder;
          });
        }
      }).join('');
    
      // 渲染Markdown
      let rendered = md.render(processedContent);
    
      // 恢复LaTeX占位符
      latexPlaceholders.forEach(({ placeholder, latex }) => {
        rendered = rendered.replace(placeholder, latex);
      });
    
      // 处理未闭合代码块的转义字符
      rendered = rendered.replace(/\\\`/g, '`').replace(/\\\$/g, '$');
    
      this.$nextTick(() => {
        MathJax.typesetPromise()
          .then(() => this.initCopyButtons())
          .catch(console.error);
      });
    
      return rendered;
    },
    // 新增方法：检测未闭合代码块
    hasUnclosedCodeBlock(parts) {
      return parts.some(p => p.type === 'code' && !p.closed);
    },

    splitCodeAndText(content) {
      const codeFenceRegex = /(```[\s\S]*?)(?:```|$)/g; // 修改正则表达式
      const parts = [];
      let lastIndex = 0;
      let hasUnclosed = false;

      // 处理代码块
      let match;
      while ((match = codeFenceRegex.exec(content)) !== null) {
        const textBefore = content.slice(lastIndex, match.index);
        if (textBefore) parts.push({ type: 'text', content: textBefore });

        // 判断是否闭合
        const isClosed = match[0].endsWith('```');
        const codeContent = isClosed ? 
          match[0] : 
          match[0] + '\n```'; // 自动补全闭合

        parts.push({
          type: 'code',
          content: codeContent,
          closed: isClosed
        });

        lastIndex = codeFenceRegex.lastIndex;
        hasUnclosed = !isClosed;
      }

      // 处理剩余内容
      const remaining = content.slice(lastIndex);
      if (remaining) {
        if (hasUnclosed) {
          // 将剩余内容视为代码块
          parts.push({
            type: 'code',
            content: remaining + '\n```',
            closed: false
          });
        } else {
          parts.push({ type: 'text', content: remaining });
        }
      }

      return parts;
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
          // 定义一个阈值，用来判断是否接近底部
          const threshold = 100; // 阈值可以根据实际情况调整
          const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight <= threshold;
    
          if (isAtBottom) {
            // 如果接近底部，则滚动到底部
            container.scrollTop = container.scrollHeight;
          }
          // 如果不是接近底部，则不执行任何操作
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
            selectedProvider: data.data.selectedProvider || '',
          };
          this.toolsSettings = data.data.tools || {};
          this.reasonerSettings = data.data.reasoner || {};
          this.webSearchSettings = data.data.webSearch || {};
          this.knowledgeBases = data.data.knowledgeBases || [];
          this.modelProviders = data.data.modelProviders || [];
          this.systemSettings = data.data.systemSettings || {};
          this.currentLanguage = this.systemSettings.language || 'zh-CN';
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
    escapeHtml(unsafe) {
      return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
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
      const escapedContent = this.escapeHtml(userInput.trim());
      // 添加用户消息
      this.messages.push({
        role: 'user',
        content: escapedContent,
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
      this.isSending = true;
      this.abortController = new AbortController(); 
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
          }),
          signal: this.abortController.signal
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
        if (error.name === 'AbortError') {
          showNotification('已停止生成', 'info');
        } else {
          showNotification(error.message, 'error');
        }
      } finally {
        this.isThinkOpen = false;
        this.isSending = false;
        this.isTyping = false;
        this.abortController = null;
      }
    },
    stopGenerate() {
      if (this.abortController) {
        this.abortController.abort();
        // 保留已生成的内容，仅标记为完成状态
        if (this.messages.length > 0) {
          const lastMessage = this.messages[this.messages.length - 1];
          if (lastMessage.role === 'assistant') {
            // 可选：添加截断标记
            if (lastMessage.content && !lastMessage.content.endsWith('(已停止)')) {
              lastMessage.content += '\n\n(生成已停止)';
            }
          }
        }
      }
      this.isThinkOpen = false;
      this.isSending = false;
      this.isTyping = false;
      this.abortController = null;
    },
    // 自动保存设置
    autoSaveSettings() {
      const payload = {
        ...this.settings,
        tools: this.toolsSettings,
        reasoner: this.reasonerSettings,
        webSearch: this.webSearchSettings, 
        knowledgeBases: this.knowledgeBases,
        modelProviders: this.modelProviders,
        systemSettings: this.systemSettings,
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
      this.stopGenerate();
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
        const result = await window.electronAPI.openFileDialog();
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
    switchToApiBox() {
      // 切换到 API 钥匙箱界面
      this.activeMenu = 'api-box'
      
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
        showNotification('该供应商不支持模型列表获取或未填写API密钥', 'error');
      }
    },
    // 找到原有的 removeProvider 方法，替换为以下代码
    removeProvider(index) {
      // 获取被删除的供应商信息
      const removedProvider = this.modelProviders[index];
      
      // 从供应商列表中移除
      this.modelProviders.splice(index, 1);

      // 清理所有相关配置中的引用
      const providerId = removedProvider.id;
      
      // 主模型配置清理
      if (this.settings.selectedProvider === providerId) {
        this.settings.selectedProvider = null;
        this.settings.model = '';
        this.settings.base_url = '';
        this.settings.api_key = '';
      }

      // 推理模型配置清理
      if (this.reasonerSettings.selectedProvider === providerId) {
        this.reasonerSettings.selectedProvider = null;
        this.reasonerSettings.model = '';
        this.reasonerSettings.base_url = '';
        this.reasonerSettings.api_key = '';
      }

      // 触发自动保存
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
        apiKey: this.newProviderTemp.apiKey || '',
        modelId: this.newProviderTemp.modelId || '',
        models: []
      }
      
      this.modelProviders.push(newProvider)
      this.showAddDialog = false
      this.newProviderTemp = { vendor: '', url: '', apiKey: '', modelId: '' }
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
      if (value === 'Ollama') {
        this.newProviderTemp.apiKey = 'ollama'
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
    // 创建知识库
    async createKnowledgeBase() {
      try {
        // 上传文件
        let uploadedFiles = [];
        if (this.newKbFiles.length > 0) {
          if (!this.isElectron) {
            // 浏览器环境：通过 FormData 上传
            const formData = new FormData();
            for (const file of this.newKbFiles) {
              if (file.file instanceof Blob) {
                formData.append('files', file.file, file.name);
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
                uploadedFiles = data.fileLinks; // 获取上传后的文件链接
              } else {
                showNotification('文件上传失败', 'error');
                return;
              }
            } catch (error) {
              console.error('Error during file upload:', error);
              showNotification('文件上传失败', 'error');
              return;
            }
          } else {
            // Electron 环境：通过 JSON 上传
            try {
              console.log('Uploading Electron files...');
              const response = await fetch(`http://${HOST}:${PORT}/load_file`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                  files: this.newKbFiles.map(file => ({
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
                uploadedFiles = data.fileLinks; // 获取上传后的文件链接
              } else {
                showNotification('文件上传失败', 'error');
                return;
              }
            } catch (error) {
              console.error('上传错误:', error);
              showNotification('文件上传失败', 'error');
              return;
            }
          }
        }
  
        // 生成唯一的 ID
        const kbId = Date.now();
  
        // 构建新的知识库对象，使用上传后的文件链接
        const newKb = {
          id: kbId,
          name: this.newKb.name,
          introduction: this.newKb.introduction,
          providerId: this.newKb.providerId,
          model: this.newKb.model,
          base_url: this.newKb.base_url,
          api_key: this.newKb.api_key,
          enabled: true, // 默认启用
          chunk_size: this.newKb.chunk_size,
          chunk_overlap: this.newKb.chunk_overlap,
          chunk_k: this.newKb.chunk_k,
          files: uploadedFiles.map(file => ({ // 使用服务器返回的文件链接
            name: file.name,
            path: file.path,
          })),
          processingStatus: 'processing', // 设置处理状态为 processing
        };
  
        // 更新 settings 中的 knowledgeBases
        this.knowledgeBases = [...(this.knowledgeBases || []), newKb];
        //手动触发modelProviders更新，从而能够实时与后端同步
        this.modelProviders = this.modelProviders
        // 保存 settings
        this.autoSaveSettings();
        // post kbId to 后端的create_kb端口
        try {
          // 1. 触发任务
          const startResponse = await fetch(`http://${HOST}:${PORT}/create_kb`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kbId }),
          });
          
          if (!startResponse.ok) throw new Error('启动失败');
          // 2. 轮询状态
          const checkStatus = async () => {
            const statusResponse = await fetch(`http://${HOST}:${PORT}/kb_status/${kbId}`);
            const data = await statusResponse.json();
            console.log(data.status);
            return data.status;
          };
          // 3. 每2秒检查一次状态
          const interval = setInterval(async () => {
            const status = await checkStatus();
            
            // 找到对应的知识库对象
            const targetKb = this.knowledgeBases.find(k => k.id === kbId);
            
            if (status === 'completed') {
              clearInterval(interval);
              targetKb.processingStatus = 'completed';
              showNotification('知识库处理完成');
              this.autoSaveSettings();
            } else if (status.startsWith('failed')) {
              clearInterval(interval);
              // 移除失败的知识库
              this.knowledgeBases = this.knowledgeBases.filter(k => k.id !== kbId);
              showNotification(`处理失败: ${status}`, 'error');
              this.autoSaveSettings();
            }
          }, 2000);
        } catch (error) {
          console.error('知识库创建失败:', error);
          showNotification('知识库创建失败', 'error');
        }      
        this.showAddKbDialog = false;
        this.newKb = { 
          name: '', 
          introduction: '',
          providerId: null, 
          model: '', 
          base_url: '', 
          api_key: '',
          chunk_size: 1024,
          chunk_overlap: 256,
          chunk_k: 5
        };
        this.newKbFiles = [];
      } catch (error) {
        console.error('知识库创建失败:', error);
        showNotification('知识库创建失败', 'error');
      }
    },

    // 删除知识库
    async removeKnowledgeBase(kb) {
      try {
        // 从 settings 中过滤掉要删除的 knowledgeBase
        this.knowledgeBases = this.knowledgeBases.filter(
          item => item.id !== kb.id
        );
        //手动触发modelProviders更新，从而能够实时与后端同步
        this.modelProviders = this.modelProviders
        // 保存 settings
        this.autoSaveSettings();

        showNotification('知识库删除成功');
      } catch (error) {
        console.error('知识库删除失败:', error);
        showNotification('知识库删除失败', 'error');
      }
    },

    // 切换知识库启用状态
    async toggleKbEnabled(kb) {
      try {
        // 更新 knowledgeBase 的 enabled 状态
        const kbToUpdateIndex = this.knowledgeBases.findIndex(
          item => item.id === kb.id
        );

        if (kbToUpdateIndex !== -1) {
          this.knowledgeBases[kbToUpdateIndex].enabled = kb.enabled;
          //手动触发modelProviders更新，从而能够实时与后端同步
          this.modelProviders = this.modelProviders
          // 保存 settings
          this.autoSaveSettings();
          showNotification(`知识库 ${kb.name} 已${kb.enabled ? '启用' : '禁用'}`);
        }
      } catch (error) {
        console.error('切换知识库状态失败:', error);
        showNotification('切换知识库状态失败', 'error');
      }
    },
    // 选择供应商
    selectKbProvider(providerId) {
      const provider = this.modelProviders.find(p => p.id === providerId);
      if (provider) {
        this.newKb.model = provider.modelId;
        this.newKb.base_url = provider.url;
        this.newKb.api_key = provider.apiKey;
      }
    },

    // 文件上传相关方法
    async browseKbFiles() {
        if (!this.isElectron) {
          const input = document.createElement('input')
          input.type = 'file'
          input.multiple = true
          input.accept = ALLOWED_EXTENSIONS.map(ext => `.${ext}`).join(',')
          
          input.onchange = (e) => {
            const files = Array.from(e.target.files)
            const validFiles = files.filter(this.isValidFileType)
            this.handleKbFiles(validFiles)
          }
          input.click()
        } else {
          const result = await window.electronAPI.openFileDialog();
          if (!result.canceled) {
            const validPaths = result.filePaths
              .filter(path => {
                const ext = path.split('.').pop()?.toLowerCase() || ''
                return ALLOWED_EXTENSIONS.includes(ext)
              })
            this.handleKbFiles(validPaths)
          }
        }
    },

    handleKbFiles(files) {
        if (files.length > 0) {
          this.addKbFiles(files)
        } else {
          this.showErrorAlert()
        }
    },
      // 添加文件到列表
    addKbFiles(files) {
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
      
      this.newKbFiles = [...this.newKbFiles, ...newFiles];
    },
    async handleKbDrop(event) {
      event.preventDefault();
      const files = Array.from(event.dataTransfer.files)
        .filter(this.isValidFileType);
      this.handleKbFiles(files);
    },
    removeKbFile(index) {
      this.newKbFiles.splice(index, 1);
    },
    switchToKnowledgePage() {
      this.activeMenu = 'document';  // 根据你的菜单项配置的实际值设置
      window.scrollTo(0, 0);
    },
    // 在 methods 中添加
    t(key) {
      return this.translations[this.currentLanguage][key] || key;
    },
    handleSystemLanguageChange(val) {
      this.currentLanguage = val;
      this.systemSettings.language = val;
      this.autoSaveSettings();
      this.$forceUpdate();
    },
    // renderer.js 增强方法
    handleThemeChange(val) {
      // 更新根属性
      document.documentElement.setAttribute('data-theme', val);
      
      this.systemSettings.theme = val;

      this.autoSaveSettings();
    },

    // 方法替换为：
    launchBrowserMode() {
      this.isBrowserOpening = true;
      this.browserBtnColor = '#67c23a'; // 按钮颜色变化
      
      setTimeout(() => {
        const url = `http://${HOST}:${PORT}`;
        if (isElectron) {
          window.electronAPI.openExternal(url);
        } else {
          window.open(url, '_blank');
        }
        
        // 2秒后恢复状态
        setTimeout(() => {
          this.isBrowserOpening = false;
          this.browserBtnColor = '#409EFF';
        }, 2000);
      }, 500);
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
