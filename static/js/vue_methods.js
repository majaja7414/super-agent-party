const md = window.markdownit({
    html: true,
    linkify: true,
    typographer: true,
    highlight: function (str, lang) {
    let language = lang && hljs.getLanguage(lang) ? lang : 'plaintext';
    const isPotentialMermaid = (code) => {
    // 检测标准语法特征
    const mermaidPatterns = [
        // 检测图表类型声明
        /^\s*(graph|sequenceDiagram|gantt|classDiagram|pie|stateDiagram|gitGraph|journey|flowchart|mindmap|quadrantChart|erDiagram|requirementDiagram|gitGraph|C4Context|timeline|zenuml|sankey-beta|xychart-beta|block-beta|packet-beta|kanban|architecture-beta|radar-beta)\b/i,
        // 检测节点关系语法
        /-->|==>|:::|\|\|/,
        // 检测样式配置语法
        /^style\s+[\w]+\s+/im,
        // 检测注释语法
        /%%\{.*\}\n?/
    ];
    
    return mermaidPatterns.some(pattern => pattern.test(code));
    };
    // 自动升级普通文本中的 Mermaid 内容
    if (language === 'plaintext' && isPotentialMermaid(str)) {
    language = 'mermaid';
    };
    const previewable = ['html', 'mermaid'].includes(language);
    const downloadButton = previewable ? 
    `<button class="download-button" data-lang="${language}"><i class="fa-solid fa-download"></i></button>` : '';
    // 添加预览按钮
    const previewButton = previewable ? 
    `<button class="preview-button" data-lang="${language}"><i class="fa-solid fa-eye"></i></button>` : '';
    try {
    return `<pre class="code-block"><div class="code-header"><span class="code-lang">${language}</span><div class="code-actions">${previewButton}${downloadButton}<button class="copy-button"><i class="fa-solid fa-copy"></i></button></div></div><div class="code-content"><code class="hljs language-${language}">${hljs.highlight(str, { language }).value}</code></div></pre>`;
    } catch (__) {
    return `<pre class="code-block"><div class="code-header"><span class="code-lang">${language}</span><div class="code-actions">${previewButton}${downloadButton}<button class="copy-button"><i class="fa-solid fa-copy"></i></button></div></div><div class="code-content"><code class="hljs">${md.utils.escapeHtml(str)}</code></div></pre>`;
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

// 图片上传相关配置
const ALLOWED_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'];
const IMAGE_MIME_WHITELIST = [
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
  'image/bmp'
];

let vue_methods = {
  handleUpdateAction() {
    if (this.updateDownloaded) {
      window.electronAPI.quitAndInstall();
    } else if (this.updateAvailable) {
      window.electronAPI.downloadUpdate();
    }
  },
  formatFileUrl(originalUrl) {
    if (!this.isElectron) {
      try {
        const url = new URL(originalUrl);
        // 替换0.0.0.0为当前域名
        if (url.hostname === '0.0.0.0' || url.hostname === 'localhost' || url.hostname === '127.0.0.1') {
          url.hostname = window.location.hostname;
          // 如果需要强制使用HTTPS可以添加：
          url.protocol = window.location.protocol;
          url.port = window.location.port;
        }
        return url.toString();
      } catch(e) {
        return originalUrl;
      }
    }
    return originalUrl;
  },
  async resetMessage(index) {
    this.messages[index].content = this.t('defaultSystemPrompt');
    this.system_prompt = this.t('defaultSystemPrompt');
    await this.autoSaveSettings();
  },

  async deleteMessage(index) {
    this.messages.splice(index, 1);
    await this.autoSaveSettings();
  },

  openEditDialog(type, content, index = null) {
    this.editType = type;
    this.editContent = content;
    this.editIndex = index;
    this.showEditDialog = true;
  },
  async saveEdit() {
    if (this.editType === 'system') {
      this.system_prompt = this.editContent;
    }
    if (this.editIndex !== null) {
      this.messages[this.editIndex].content = this.editContent;
    }
    await this.autoSaveSettings();
    this.showEditDialog = false;
  },
    async addParam() {
      this.settings.extra_params.push({
        name: '',
        type: 'string',  // 默认类型
        value: ''        // 根据类型自动初始化
      });
      await this.autoSaveSettings();
    },
    async addLorebook() {
      // 如果this.newMemory.lorebook未定义，则初始化为空数组
      if (!this.newMemory.lorebook) {
        this.newMemory.lorebook = [];
      }
      // 在this.newMemory.lorebook的object中添加一个新的键值对
      this.newMemory.lorebook.push({
        name: '',
        value: ''        // 根据类型自动初始化
      });
      this.isWorldviewSettingsExpanded = true;
      await this.autoSaveSettings();
    },
    async removeLorebook(index) {
      if (index === 0) return; // 禁止删除第一个记忆
      this.newMemory.lorebook.splice(index, 1);
      await this.autoSaveSettings();
    },
    async addRandom(){
      // 如果this.newMemory.random未定义，则初始化为空数组
      if (!this.newMemory.random) {
        this.newMemory.random = [];
      }
      this.newMemory.random.push({
        value: ''        // 根据类型自动初始化
      });
      this.isRandomSettingsExpanded = true;
      await this.autoSaveSettings();
    },
    async removeRandom(index) {
      if (index === 0) return; // 禁止删除第一个随机记忆
      this.newMemory.random.splice(index, 1);
      await this.autoSaveSettings();
    },
    async updateParamType(index) {
      const param = this.settings.extra_params[index];
      // 根据类型初始化值
      switch(param.type) {
        case 'boolean':
          param.value = false;
          break;
        case 'integer':
        case 'float':
          param.value = 0;
          break;
        default:
          param.value = '';
      }
      await this.autoSaveSettings();
    },
    async removeParam(index) {
      this.settings.extra_params.splice(index, 1);
      await this.autoSaveSettings();
    },
    switchTollmTools() {
      this.activeMenu = 'agent_group';
      this.subMenu = 'llmTool';
    },
    cancelLLMTool() {
      this.showLLMForm = false
      this.resetForm()
    },
    handleTypeChange(val) {
      this.newLLMTool.base_url = this.defaultBaseURL
      this.newLLMTool.api_key = this.defaultApikey
      this.fetchModelsForType(val)
    },
    changeImgHost(val) {
      this.BotConfig.img_host = val;
      this.autoSaveSettings()
    },
    // 获取模型列表
    async fetchModelsForType(type) {
      try {
        const response = await fetch(`http://${HOST}:${PORT}/llm_models`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type: type,
            base_url: this.newLLMTool.base_url,
            api_key: this.newLLMTool.api_key
          })
        })
        
        const { data } = await response.json()
        this.modelOptions = data.models || []
      } catch (error) {
        console.error('Failed to fetch models:', error)
      }
    },
    // 保存工具
    saveLLMTool() {
      const tool = { ...this.newLLMTool }
      // 添加工具ID
      tool.id = uuid.v4();
      if (this.editingLLM) {
        this.llmTools[this.editingLLM] = tool
      } else {
        this.llmTools.push(tool)
      }
      this.showLLMForm = false
      this.resetForm()
      this.autoSaveSettings()
    },
    // 删除工具
    removeLLMTool(index) {
      this.llmTools.splice(index, 1)
      this.autoSaveSettings()
    },
    // 重置表单
    resetForm() {
      this.newLLMTool = {
        name: '',
        type: 'openai',
        description: '',
        base_url: '',
        api_key: '',
        model: '',
        enabled: true
      }
      this.editingLLM = null
    },
    // 类型标签转换
    toolTypeLabel(type) {
      const found = this.llmInterfaceTypes.find(t => t.value === type)
      return found ? found.label : type
    },
    // 检查更新
    async checkForUpdates() {
      if (isElectron) {
        try {
          await window.electronAPI.checkForUpdates();
        } catch (err) {
          showNotification(err.message, 'error');
        }
      }
    },

    // 下载更新
    async downloadUpdate() {
      if (isElectron && this.updateAvailable) {
        try {
          await window.electronAPI.downloadUpdate();
        } catch (err) {
          showNotification(err.message, 'error');
        }
      }
    },

    // 安装更新
    async installUpdate() {
      if (isElectron && this.updateDownloaded) {
        await window.electronAPI.quitAndInstall();
      }
    },

    // 处理更新按钮点击
    async handleUpdate() {
      if (!this.updateSuccess) {
        try {
          await this.downloadUpdate();
          this.updateSuccess = true;
          setTimeout(() => {
            this.installUpdate();
          }, 1000);
        } catch (err) {
          showNotification(err.message, 'error');
        }
      } else {
        await this.installUpdate();
      }
    },

    generateConversationTitle(messages) {
      const lastUserMessage = [...messages].reverse().find(m => m.role === 'user');
      
      if (lastUserMessage) {
        let textContent;
        
        // 判断 content 是否为字符串还是对象数组
        if (typeof lastUserMessage.content === 'string') {
          textContent = lastUserMessage.content;
        } else if (Array.isArray(lastUserMessage.content)) {
          // 提取所有文本类型的内容并拼接
          textContent = lastUserMessage.content.filter(item => item.type === 'text')
                           .map(item => item.text).join(' ');
        } else {
          // 如果既不是字符串也不是对象数组，设置为空字符串或其他默认值
          textContent = '';
        }
    
        // 拼接 fileLinks_content 部分，如果有
        const fullContent = textContent + (lastUserMessage.fileLinks_content ?? '');
        
        return fullContent.substring(0, 30) + (fullContent.length > 30 ? '...' : '');
      }
      
      return this.t('newChat');
    },
    async confirmDeleteConversation(convId) {
      if (convId === this.conversationId) {
        this.messages = [{ role: 'system', content: this.system_prompt }];
      }
      
      this.conversations = this.conversations.filter(c => c.id !== convId);
      await this.autoSaveSettings();
    },
    async loadConversation(convId) {
      const conversation = this.conversations.find(c => c.id === convId);
      if (conversation) {
        this.conversationId = convId;
        this.messages = [...conversation.messages];
        this.fileLinks = conversation.fileLinks;
        this.mainAgent = conversation.mainAgent;
        this.showHistoryDialog = false;
        this.system_prompt = conversation.system_prompt;
      }
      else {
        this.system_prompt = this.t('defaultSystemPrompt');
        this.messages = [{ role: 'system', content: this.system_prompt }];
      }
      this.scrollToBottom();
      await this.autoSaveSettings();
    },
    switchToagents() {
      this.activeMenu = 'agent_group';
      this.subMenu = 'agents';
    },
    switchToa2aServers() {
      this.activeMenu = 'agent_group';
      this.subMenu = 'a2a';
    },
    async syncProviderConfig(targetConfig) {
      // 当有选中供应商时执行同步
      if (targetConfig.selectedProvider) {
        // 在供应商列表中查找匹配项
        const provider = this.modelProviders.find(
          p => p.id === targetConfig.selectedProvider && !p.disabled
        );
        if (provider) {
          // 同步核心配置
          const shouldUpdate = 
            targetConfig.model !== provider.modelId ||
            targetConfig.base_url !== provider.url ||
            targetConfig.api_key !== provider.apiKey;
          if (shouldUpdate) {
            targetConfig.model = provider.modelId || '';
            targetConfig.base_url = provider.url || '';
            targetConfig.api_key = provider.apiKey || '';
            console.log(`已同步 ${provider.vendor} 配置`);
          }
        } else {
          // 清理无效的供应商选择
          console.warn('找不到匹配的供应商，已重置配置');
          targetConfig.selectedProvider = null;
          targetConfig.model = '';
          targetConfig.base_url = '';
          targetConfig.api_key = '';
        }
        await this.autoSaveSettings();
      }
    },
    updateMCPExample() {
      this.currentMCPExample = this.mcpExamples[this.newMCPType];
    },
    
    toggleMCPServer(name, status) {
      this.mcpServers[name].disabled = !status
      this.autoSaveSettings()
    },
    switchTomcpServers() {
      this.activeMenu = 'agent_group';
      this.subMenu = 'mcp'
    },
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
      if (key === 'agent_group') {
        this.activeMenu = 'agent_group';
        this.subMenu = 'agents'; // 默认显示第一个子菜单
      }
      else if (key === 'model-config') {
        this.activeMenu = 'model-config';
        this.subMenu = 'service'; // 默认显示第一个子菜单
      }
      else if (key === 'toolkit') {
        this.activeMenu = 'toolkit';
        this.subMenu = 'tools'; // 默认显示第一个子菜单
      }
      else if (key === 'api-group') {
        this.activeMenu = 'api-group';
        this.subMenu = 'openai'; // 默认显示第一个子菜单
      }
      else if (key === 'storage') {
        this.activeMenu = 'storage';
        this.subMenu = 'text'; // 默认显示第一个子菜单
      }
      else if (key === 'deploy-bot') {
        this.activeMenu = 'deploy-bot';
        this.subMenu = 'qq_bot'; // 默认显示第一个子菜单
      }
      else {
        this.activeMenu = key;
      }
      this.activeMenu = key;
    }, 
    toggleIcon() {
      this.isExpanded = !this.isExpanded; // 点击时切换状态
      this.maximizeWindow();
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
          .then(() => {
            this.initCopyButtons();
            this.initPreviewButtons();
          })
          .catch(console.error);
      });

      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = rendered;
      // 处理链接标签
      const links = tempDiv.getElementsByTagName('a');
      for (const link of links) {
        const originalHref = link.getAttribute('href');
        if (originalHref) {
          link.setAttribute('href', this.formatFileUrl(originalHref));
        }
      }
      return tempDiv.innerHTML;
    },
    copyLink(uniqueFilename) {
      const url = `${this.partyURL}/uploaded_files/${uniqueFilename}`
      navigator.clipboard.writeText(url)
        .then(() => {
          showNotification(this.t('copy_success'))
        })
        .catch(() => {
          showNotification(this.t('copy_failed'), 'error')
        })
    },
    
    previewImage(img) {
      this.previewImageUrl = `${this.partyURL}/uploaded_files/${img.unique_filename}`
      this.previewVisible = true
      console.log(this.previewImageUrl)
    },
    copyMessageContent(message) {
      // 获取原始内容（用户消息直接复制，AI消息复制原始markdown）
      let content = message.role === 'user' 
        ? message.content 
        : message.rawContent || message.content;
      // 处理文件链接
      if (message.fileLinks?.length) {
        content += '\n\n' + message.fileLinks.map(link => `[${link.name}](${link.path})`).join('\n');
      }
      navigator.clipboard.writeText(content)
        .then(() => showNotification(this.t('copy_success')))
        .catch(() => showNotification(this.t('copy_failed'), 'error'));
    },
    initPreviewButtons() {
      // 清理旧事件监听器
      if (this._previewEventHandler) {
        document.body.removeEventListener('click', this._previewEventHandler);
      }
      // 主事件处理器
      this._previewEventHandler = (e) => {
        const button = e.target.closest('.preview-button');
        if (!button) return;
        e.preventDefault();
        e.stopPropagation();
        console.debug('🏁 预览按钮触发:', button);
        // 获取代码上下文
        const codeBlock = button.closest('.code-block');
        if (!codeBlock) {
          console.error('❌ 未找到代码块容器');
          return;
        }
        // 获取代码内容
        const lang = button.dataset.lang;
        const codeContent = codeBlock.querySelector('code')?.textContent?.trim();
        if (!codeContent) {
          console.warn('⚠️ 空代码内容', codeBlock);
          this.showErrorToast('代码内容为空');
          return;
        }
        // codeBlock中查找/创建预览容器
        let previewContainer = codeBlock.querySelector('.preview-container');
        const isNewContainer = !previewContainer;
        
        if (isNewContainer) {
          previewContainer = document.createElement('div');
          previewContainer.className = 'preview-container loading';
          codeBlock.appendChild(previewContainer);
        }
        // 状态切换逻辑
        if (previewContainer.classList.contains('active')) {
          this.collapsePreview(previewContainer, button);
        } else {
          this.expandPreview({ previewContainer, button, lang, codeContent });
        }
      };
      // 绑定事件监听
      document.body.addEventListener('click', this._previewEventHandler);
      //console.log('🔧 预览按钮事件监听已初始化');
    },
    // 展开预览面板
    expandPreview({ previewContainer, button, lang, codeContent }) {
      console.log('🔼 展开预览:', { lang, length: codeContent.length });
      
      const codeBlock = button.closest('.code-block');
  
      // 检查是否已有预览
      const existingPreview = codeBlock.querySelector('.preview-container.active');
      if (existingPreview) {
        this.collapsePreview(existingPreview, button);
        return;
      }
      // 标记代码块状态
      codeBlock.dataset.previewActive = "true";
      
      // 隐藏代码内容
      const codeContentDiv = codeBlock.querySelector('.code-content');
      codeContentDiv.style.display = 'none';
      
      // 更新按钮状态
      button.innerHTML = '<i class="fa-solid fa-eye-slash"></i>';
      
      previewContainer.classList.add('active', 'loading');
      // 渲染内容
      requestAnimationFrame(() => {
        try {
          if (lang === 'html') {
            this.renderHtmlPreview(previewContainer, codeContent);
            // 动态调整iframe高度
            const iframe = previewContainer.querySelector('iframe');
            iframe.onload = () => {
              iframe.style.height = iframe.contentWindow.document.body.scrollHeight + 'px';
            };
          } else if (lang === 'mermaid') {
            this.renderMermaidPreview(previewContainer, codeContent).then(() => {
              // Mermaid渲染完成后调整高度
              const svg = previewContainer.querySelector('svg');
              if (svg) {
                previewContainer.style.minHeight = svg.getBBox().height + 50 + 'px';
              }
            });
          }
          previewContainer.classList.remove('loading');
        } catch (err) {
          console.error('🚨 预览渲染失败:', err);
          this.showPreviewError(previewContainer, err);
        }
      });
    },
    // 修改 collapsePreview 方法
    collapsePreview(previewContainer, button) {
      console.log('🔽 收起预览');
      
      const codeBlock = previewContainer.parentElement;
  
      // 重置代码块状态
      delete codeBlock.dataset.previewActive;
      
      // 显示代码内容
      const codeContentDiv = codeBlock.querySelector('.code-content');
      codeContentDiv.style.display = 'block';
      
      // 移除预览容器
      previewContainer.remove();
      
      // 重置按钮状态
      button.innerHTML = '<i class="fa-solid fa-eye"></i>';
    },
    // HTML渲染器
    renderHtmlPreview(container, code) {
      console.log('🌐 渲染HTML预览');
      
      const sandbox = document.createElement('iframe');
      sandbox.srcdoc = `<!DOCTYPE html>
        <html>
          <head>
            <base href="http://${HOST}:${PORT}/">
            <link rel="stylesheet" href="/css/styles.css">
            <style>body { margin: 0; padding: 15px; }</style>
          </head>
          <body>${code}</body>
        </html>`;
      
      sandbox.style.cssText = `
        width: 100%;
        height: 800px;
        border: 1px solid #ddd;
        border-radius: 4px;
        background: white;
      `;
      
      container.replaceChildren(sandbox);
    },
    // Mermaid渲染器（带重试机制）
    async renderMermaidPreview(container, code) {
      console.log('📊 渲染Mermaid图表');
      
      const diagramContainer = document.createElement('div');
      diagramContainer.className = 'mermaid-diagram';
      container.replaceChildren(diagramContainer);
      // 异步渲染逻辑
      let retryCount = 0;
      const maxRetries = 3;
      
      const attemptRender = async () => {
        try {
          diagramContainer.textContent = code;
          await mermaid.run({
            nodes: [diagramContainer],
            suppressErrors: false
          });
          console.log('✅ Mermaid渲染成功');
        } catch (err) {
          if (retryCount < maxRetries) {
            retryCount++;
            console.warn(`🔄 重试渲染 (${retryCount}/${maxRetries})`);
            diagramContainer.innerHTML = '';
            await new Promise(resolve => setTimeout(resolve, 500 * retryCount));
            await attemptRender();
          } else {
            throw new Error(`Mermaid渲染失败: ${err.message}`);
          }
        }
      };
      await attemptRender();
    },
    // 错误处理
    showPreviewError(container, error) {
      container.classList.add('error');
      container.innerHTML = `
        <div class="error-alert">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <div>
            <h4>预览渲染失败</h4>
            <code>${error.message}</code>
          </div>
        </div>
      `;
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
    initDownloadButtons() {
        document.body.addEventListener('click', async (e) => {
            const button = e.target.closest('.download-button');
            if (!button) return;
            const lang = button.dataset.lang;
            const codeBlock = button.closest('.code-block');
            const previewButton = codeBlock.querySelector('.preview-button');
            const existingPreview = codeBlock.querySelector('.preview-container.active');
            // 如果previewButton不在预览状态，则执行预览操作
            if (!existingPreview) {
                // 触发预览按钮的点击事件
                previewButton.click();
                // 等待预览完成
                await new Promise(resolve => setTimeout(resolve, 500)); // 根据实际情况调整延时
            }
            const previewContainer = codeBlock.querySelector('.preview-container');
            try {
                if (lang === 'mermaid') {
                    // 使用html2canvas来截图
                    html2canvas(previewContainer, {
                        // 如果Mermaid图表面板有滚动条，你可能需要设置宽度和高度
                        width: previewContainer.offsetWidth,
                        height: previewContainer.offsetHeight,
                    }).then(canvas => {
                        canvas.toBlob(blob => {
                            this.triggerDownload(blob, 'mermaid-diagram.png');
                        });
                    }).catch(error => {
                        console.error('截图失败:', error);
                        showNotification('截图失败，请检查控制台', 'error');
                    });
                }
                else if (lang === 'html') {
                    const iframe = previewContainer.querySelector('iframe');
                    const canvas = await html2canvas(iframe.contentDocument.body);
                    canvas.toBlob(blob => {
                        this.triggerDownload(blob, 'html-preview.png');
                    });
                }
            } catch (error) {
                console.error('下载失败:', error);
                showNotification('下载失败，请检查控制台', 'error');
            }
        });
    },

    triggerDownload(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },
    
    handleCopy(event) {
      const button = event.target.closest('.copy-button')
      if (button) {
        const codeBlock = button.closest('.code-block')
        const codeContent = codeBlock?.querySelector('code')?.textContent || ''
        
        navigator.clipboard.writeText(codeContent).then(() => {
          showNotification(this.t('copy_success'))
        }).catch(() => {
          showNotification(this.t('copy_failed'), 'error')
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
          const threshold = 200; // 阈值可以根据实际情况调整
          const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight <= threshold;
    
          if (isAtBottom) {
            // 如果接近底部，则滚动到底部
            container.scrollTop = container.scrollHeight;
          }
          // 如果不是接近底部，则不执行任何操作
        }
      });
    },
    changeMainAgent(agent) {
      this.mainAgent = agent;
      if (agent === 'super-model') {
        this.system_prompt = this.t('defaultSystemPrompt')
      }
      else {
        this.system_prompt = this.agents[agent].system_prompt;
        console.log(this.system_prompt);
      }
      this.syncSystemPromptToMessages(this.system_prompt);
    },
    async changeQQAgent(agent) {
      this.qqBotConfig.QQAgent = agent;
      await this.autoSaveSettings();
    },
    // WebSocket相关
    initWebSocket() {
      const http_protocol = window.location.protocol;
      const ws_protocol = http_protocol === 'https:' ? 'wss:' : 'ws:';
      const ws_url = `${ws_protocol}//${window.location.host}/ws`;

      this.ws = new WebSocket(ws_url);

      // 设置心跳间隔和重连间隔（单位：毫秒）
      const HEARTBEAT_INTERVAL = 10000; // 每10秒发送一次 ping
      const RECONNECT_INTERVAL = 5000;  // 断开后每5秒尝试重连一次

      let heartbeatTimer = null;
      let reconnectTimer = null;

      const startHeartbeat = () => {
        heartbeatTimer = setInterval(() => {
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            try {
              this.ws.send(JSON.stringify({ type: 'ping' })); // 发送心跳包
            } catch (e) {
              console.error('Failed to send ping:', e);
            }
          }
        }, HEARTBEAT_INTERVAL);
      };

      const stopHeartbeat = () => {
        if (heartbeatTimer) {
          clearInterval(heartbeatTimer);
          heartbeatTimer = null;
        }
      };

      const scheduleReconnect = () => {
        stopHeartbeat();
        if (!reconnectTimer) {
          reconnectTimer = setTimeout(() => {
            console.log('Reconnecting WebSocket...');
            this.initWebSocket(); // 重新初始化
            reconnectTimer = null;
          }, RECONNECT_INTERVAL);
        }
      };

      // WebSocket 打开事件
      this.ws.onopen = () => {
        console.log('WebSocket connection established');
        stopHeartbeat(); // 防止重复心跳
        startHeartbeat();
      };

      // 接收消息
      this.ws.onmessage = (event) => {
        let data;
        try {
          data = JSON.parse(event.data);
        } catch (e) {
          console.log('Message from server:', event.data);
          return;
        }

      if (data.type === 'pong') {
        // 可以在这里处理 pong 回复，比如记录状态
        console.log('Received pong from server.');
      } 
      else if (data.type === 'settings') {
          this.isdocker = data.data.isdocker || false;
          this.settings = {
            model: data.data.model || '',
            base_url: data.data.base_url || '',
            api_key: data.data.api_key || '',
            temperature: data.data.temperature || 0.7,
            max_tokens: data.data.max_tokens || 4096,
            max_rounds: data.data.max_rounds || 0,
            selectedProvider: data.data.selectedProvider || '',
            top_p: data.data.top_p || 1,
            extra_params: data.data.extra_params || [],
          };
          this.system_prompt = data.data.system_prompt || '';
          this.conversations = data.data.conversations || this.conversations;
          this.conversationId = data.data.conversationId || this.conversationId;
          this.agents = data.data.agents || this.agents;
          this.mainAgent = data.data.mainAgent || this.mainAgent;
          this.qqBotConfig = data.data.qqBotConfig || this.qqBotConfig;
          this.BotConfig = data.data.BotConfig || this.BotConfig;
          this.toolsSettings = data.data.tools || this.toolsSettings;
          this.llmTools = data.data.llmTools || this.llmTools;
          this.reasonerSettings = data.data.reasoner || this.reasonerSettings;
          this.visionSettings = data.data.vision || this.visionSettings;
          this.webSearchSettings = data.data.webSearch || this.webSearchSettings;
          this.codeSettings = data.data.codeSettings || this.codeSettings;
          this.KBSettings = data.data.KBSettings || this.KBSettings;
          this.textFiles = data.data.textFiles || this.textFiles;
          this.imageFiles = data.data.imageFiles || this.imageFiles;
          this.videoFiles = data.data.videoFiles || this.videoFiles;
          this.knowledgeBases = data.data.knowledgeBases || this.knowledgeBases;
          this.modelProviders = data.data.modelProviders || this.modelProviders;
          this.systemSettings = data.data.systemSettings || this.systemSettings;
          this.currentLanguage = this.systemSettings.language || 'zh-CN';
          this.mcpServers = data.data.mcpServers || this.mcpServers;
          this.a2aServers = data.data.a2aServers || this.a2aServers;
          this.memories = data.data.memories || this.memories;
          this.memorySettings = data.data.memorySettings || this.memorySettings;
          this.text2imgSettings = data.data.text2imgSettings || this.text2imgSettings;
          this.comfyuiServers = data.data.comfyuiServers || this.comfyuiServers;
          this.comfyuiAPIkey = data.data.comfyuiAPIkey || this.comfyuiAPIkey;
          this.workflows = data.data.workflows || this.workflows;
          this.customHttpTools = data.data.custom_http || this.customHttpTools;
          this.loadConversation(this.conversationId);
        } 
        else if (data.type === 'settings_saved') {
          if (!data.success) {
            showNotification(this.t('settings_save_failed'), 'error');
          }
        }
      };

      // WebSocket 关闭事件
      this.ws.onclose = (event) => {
        console.log('WebSocket connection closed:', event.reason);
        stopHeartbeat();
        scheduleReconnect();
      };

      // WebSocket 错误事件
      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.ws.close(); // 主动关闭连接，触发 onclose 事件
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
    async syncSystemPromptToMessages(newPrompt) {
      // 情况 1: 新提示词为空
      if (!newPrompt) {
        if (this.messages.length > 0 && this.messages[0].role === 'system') {
          this.messages.splice(0, 1); // 删除系统消息
        }
        return;
      }
  
      // 情况 2: 已有系统消息
      if (this.messages[0]?.role === 'system') {
        // 更新系统消息内容
        this.messages[0].content = newPrompt;
        console.log('Updated system message:', this.messages[0]);
        return;
      }
  
      // 情况 3: 没有系统消息
      this.messages.unshift({
        role: 'system',
        content: newPrompt
      });
      console.log('Added system message:', this.messages[0]);
      await this.autoSaveSettings();
    },
    // 发送消息
    async sendMessage() { 
      if (!this.userInput.trim() || this.isTyping) return;
      const userInput = this.userInput.trim();
      let fileLinks = this.files || [];
      if (fileLinks.length > 0){
        const formData = new FormData();
        
        // 使用 'files' 作为键名，而不是 'file'
        for (const file of fileLinks) {
            if (file.file instanceof Blob) { // 确保 file.file 是一个有效的文件对象
                formData.append('files', file.file, file.name); // 添加第三个参数为文件名
            } else {
                console.error("Invalid file object:", file);
                showNotification(this.t('invalid_file'), 'error');
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
                showNotification(this.t('file_upload_failed'), 'error');
                return;
            }
            const data = await response.json();
            if (data.success) {
                fileLinks = data.fileLinks;
                // data.textFiles 添加到 this.textFiles
                this.textFiles = [...this.textFiles, ...data.textFiles];
                await this.autoSaveSettings();
            } else {
                showNotification(this.t('file_upload_failed'), 'error');
            }
          } catch (error) {
              console.error('Error during file upload:', error);
              showNotification(this.t('file_upload_failed'), 'error');
          }
        }
        let imageLinks = this.images || [];
        if (imageLinks.length > 0){
          const formData = new FormData();
          
          // 使用 'files' 作为键名，而不是 'file'
          for (const file of imageLinks) {
              if (file.file instanceof Blob) { // 确保 file.file 是一个有效的文件对象
                  formData.append('files', file.file, file.name); // 添加第三个参数为文件名
              } else {
                  console.error("Invalid file object:", file);
                  showNotification(this.t('invalid_file'), 'error');
                  return;
              }
          }
      
          try {
              console.log('Uploading images...');
              const response = await fetch(`http://${HOST}:${PORT}/load_file`, {
                  method: 'POST',
                  body: formData
              });
              if (!response.ok) {
                  const errorText = await response.text();
                  console.error('Server responded with an error:', errorText);
                  showNotification(this.t('file_upload_failed'), 'error');
                  return;
              }
              const data = await response.json();
              if (data.success) {
                imageLinks = data.fileLinks;
                // data.imageFiles 添加到 this.imageFiles
                this.imageFiles = [...this.imageFiles, ...data.imageFiles];
                await this.autoSaveSettings();
              } else {
                showNotification(this.t('file_upload_failed'), 'error');
              }
          } catch (error) {
              console.error('Error during file upload:', error);
              showNotification(this.t('file_upload_failed'), 'error');
          }
        }
      const fileLinks_content = fileLinks.map(fileLink => `\n[文件名：${fileLink.name}\n文件链接: ${fileLink.path}]`).join('\n') || '';
      const fileLinks_list = Array.isArray(fileLinks) ? fileLinks.map(fileLink => fileLink.path).flat() : []
      // fileLinks_list添加到self.filelinks
      this.fileLinks = this.fileLinks.concat(fileLinks_list)
      const escapedContent = this.escapeHtml(userInput.trim());
      // 添加用户消息
      this.messages.push({
        role: 'user',
        content: escapedContent,
        fileLinks: fileLinks,
        fileLinks_content: fileLinks_content,
        imageLinks: imageLinks || []
      });
      this.files = [];
      this.images = [];
      let max_rounds = this.settings.max_rounds || 0;
      let messages;
      // 把窗口滚动到底部
      this.$nextTick(() => {
        const container = this.$refs.messagesContainer;
        container.scrollTop = container.scrollHeight;
      });
      if (max_rounds === 0) {
        // 如果 max_rounds 是 0, 映射所有消息
        messages = this.messages.map(msg => {
          // 提取HTTP/HTTPS图片链接
          const httpImageLinks = msg.imageLinks?.filter(imageLink => 
            imageLink.path.startsWith('http')
          ) || [];
          
          // 构建图片URL文本信息
          const imageUrlsText = httpImageLinks.length > 0 
            ? '\n\n图片链接:\n' + httpImageLinks.map(link => link.path).join('\n')
            : '';
          
          return {
            role: msg.role,
            content: (msg.imageLinks && msg.imageLinks.length > 0)
              ? [
                  {
                    type: "text",
                    text: msg.content + (msg.fileLinks_content ?? '') + imageUrlsText
                  },
                  ...msg.imageLinks.map(imageLink => ({
                    type: "image_url",
                    image_url: { url: imageLink.path }
                  }))
                ]
              : msg.content + (msg.fileLinks_content ?? '') + imageUrlsText
          };
        });
      } else {
        // 准备发送的消息历史（保留最近 max_rounds 条消息）
        messages = this.messages
          .slice(-max_rounds)
          .map(msg => {
            // 提取HTTP/HTTPS图片链接
            const httpImageLinks = msg.imageLinks?.filter(imageLink => 
              imageLink.path.startsWith('http://') || imageLink.path.startsWith('https://')
            ) || [];
            
            // 构建图片URL文本信息
            const imageUrlsText = httpImageLinks.length > 0 
              ? '\n\n图片链接:\n' + httpImageLinks.map(link => link.path).join('\n')
              : '';
            
            return {
              role: msg.role,
              content: msg.imageLinks.length > 0
                ? [
                    {
                      type: "text",
                      text: msg.content + (msg.fileLinks_content ?? '') + imageUrlsText
                    },
                    ...msg.imageLinks.map(imageLink => ({
                      type: "image_url",
                      image_url: { url: imageLink.path }
                    }))
                  ]
                : msg.content + (msg.fileLinks_content ?? '') + imageUrlsText
            };
          });
      }

      

      
      this.userInput = '';
      this.isSending = true;
      this.abortController = new AbortController(); 
      // 如果conversationId为null
      if (this.conversationId === null) {
        //创建一个新的对话
        this.conversationId = uuid.v4();
        const newConv = {
          id: this.conversationId,
          title: this.generateConversationTitle(messages),
          mainAgent: this.mainAgent,
          timestamp: Date.now(),
          messages: this.messages,
          fileLinks: this.fileLinks,
          system_prompt: this.system_prompt,
        };
        this.conversations.unshift(newConv);
      }
      // 如果conversationId不为null
      else {
        // 更新现有对话
        const conv = this.conversations.find(conv => conv.id === this.conversationId);
        if (conv) {
          conv.messages = this.messages;
          conv.mainAgent = this.mainAgent;
          conv.timestamp = Date.now();
          conv.title = this.generateConversationTitle(messages);
          conv.fileLinks = this.fileLinks;
          conv.system_prompt = this.system_prompt;
        }
      }
      await this.autoSaveSettings();
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
            model: this.mainAgent,
            messages: messages,
            stream: true,
            fileLinks: this.fileLinks,
          }),
          signal: this.abortController.signal
        });
        
        if (!response.ok) {
          const errorData = await response.json();
          // throw new Error(errorData.error?.message || this.t('error_unknown'));
          showNotification(errorData.error?.message || this.t('error_unknown'), 'error');
          throw new Error(errorData.error?.message || this.t('error_unknown')); // 抛出错误以停止执行
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
                showNotification(e, 'error');
              }
            }
          }
        }
      } catch (error) {
        if (error.name === 'AbortError') {
          showNotification(this.t('message.stopGenerate'), 'info');
        } else {
          showNotification(error.message, 'error');
        }
      } finally {
        // 如果conversationId为null
        if (this.conversationId === null) {
          //创建一个新的对话
          this.conversationId = uuid.v4();
          const newConv = {
            id: this.conversationId,
            title: this.generateConversationTitle(messages),
            mainAgent: this.mainAgent,
            timestamp: Date.now(),
            messages: this.messages,
            fileLinks: this.fileLinks,
            system_prompt: this.system_prompt,
          };
          this.conversations.unshift(newConv);
        }
        // 如果conversationId不为null
        else {
          // 更新现有对话
          const conv = this.conversations.find(conv => conv.id === this.conversationId);
          if (conv) {
            conv.messages = this.messages;
            conv.mainAgent = this.mainAgent;
            conv.timestamp = Date.now();
            conv.title = this.generateConversationTitle(messages);
            conv.fileLinks = this.fileLinks;
            conv.system_prompt = this.system_prompt;
          }
        }
        this.isThinkOpen = false;
        this.isSending = false;
        this.isTyping = false;
        this.abortController = null;
        await this.autoSaveSettings();
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
            if (lastMessage.content && !lastMessage.content.endsWith(this.t('message.stopGenerate'))) {
              lastMessage.content += '\n\n'+this.t('message.stopGenerate');
            }
          }
        }
      }
      this.isThinkOpen = false;
      this.isSending = false;
      this.isTyping = false;
      this.abortController = null;
    },
    async autoSaveSettings() {
      return new Promise((resolve, reject) => {
        // 构造 payload（保持原有逻辑）
        const payload = {
          ...this.settings,
          system_prompt: this.system_prompt,
          agents: this.agents,
          mainAgent: this.mainAgent,
          qqBotConfig : this.qqBotConfig,
          BotConfig: this.BotConfig,
          tools: this.toolsSettings,
          llmTools: this.llmTools,
          conversations: this.conversations,
          conversationId: this.conversationId,
          reasoner: this.reasonerSettings,
          vision: this.visionSettings,
          webSearch: this.webSearchSettings, 
          codeSettings: this.codeSettings,
          KBSettings: this.KBSettings,
          textFiles: this.textFiles,
          imageFiles: this.imageFiles,
          videoFiles: this.videoFiles,
          knowledgeBases: this.knowledgeBases,
          modelProviders: this.modelProviders,
          systemSettings: this.systemSettings,
          mcpServers: this.mcpServers,
          a2aServers: this.a2aServers,
          isdocker: this.isdocker,
          memories: this.memories,
          memorySettings: this.memorySettings,
          text2imgSettings: this.text2imgSettings,
          comfyuiServers: this.comfyuiServers,
          comfyuiAPIkey: this.comfyuiAPIkey,
          workflows: this.workflows,
          custom_http: this.customHttpTools,
        };
        const correlationId = uuid.v4();
        // 发送保存请求
        this.ws.send(JSON.stringify({
          type: 'save_settings',
          data: payload,
          correlationId: correlationId // 添加唯一请求 ID
        }));
        // 设置响应监听器
        const handler = (event) => {
          const response = JSON.parse(event.data);
          
          // 匹配对应请求的确认消息
          if (response.type === 'settings_saved' && 
              response.correlationId === correlationId) {
            this.ws.removeEventListener('message', handler);
            resolve();
          }
          
          // 错误处理（根据后端实现）
          if (response.type === 'save_error') {
            this.ws.removeEventListener('message', handler);
            reject(new Error('保存失败'));
          }
        };
        // 设置 5 秒超时
        const timeout = setTimeout(() => {
          this.ws.removeEventListener('message', handler);
          reject(new Error('保存超时'));
        }, 5000);
        this.ws.addEventListener('message', handler);
      });
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
          showNotification(this.t('copy_success'), 'success');
        })
        .catch(() => {
          showNotification(this.t('copy_fail'), 'error');
        });
    },

    copyMCPEndpoint(){
      navigator.clipboard.writeText(`http://${HOST}:${PORT}/mcp`)
        .then(() => {
          showNotification(this.t('copy_success'), 'success');
        })
        .catch(() => {
          showNotification(this.t('copy_fail'), 'error');
        });
    },

    copyModel() {
      navigator.clipboard.writeText('super-model')
        .then(() => {
          showNotification(this.t('copy_success'));
        })
        .catch(() => {
          showNotification(this.t('copy_fail'), 'error');
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
    async clearMessages() {
      this.stopGenerate();
      this.messages = [{ role: 'system', content: this.system_prompt }];
      this.conversationId = null;
      this.fileLinks = [];
      this.isThinkOpen = false; // 重置思考模式状态
      this.scrollToBottom();    // 触发界面更新
      await this.autoSaveSettings();
    },
    async sendFiles() {
      this.showUploadDialog = true;
      // 设置文件上传专用处理
      this.currentUploadType = 'file';
    },
    async sendImages() {
      this.showUploadDialog = true;
      // 设置图片上传专用处理
      this.currentUploadType = 'image';
    },
    browseFiles() {
      if (this.currentUploadType === 'image') {
        this.browseImages();
      } else {
        this.browseDocuments();
      }
    },
    // 专门处理图片选择
    async browseImages() {
      if (!this.isElectron) {
        const input = document.createElement('input')
        input.type = 'file'
        input.multiple = true
        input.accept = ALLOWED_IMAGE_EXTENSIONS.map(ext => `.${ext}`).join(',')
        
        input.onchange = (e) => {
          const files = Array.from(e.target.files)
          const validFiles = files.filter(this.isValidImageType)
          this.handleFiles(validFiles)
        }
        input.click()
      } else {
        const result = await window.electronAPI.openImageDialog();
        if (!result.canceled) {
          // 转换Electron文件路径为File对象
          const files = await Promise.all(
            result.filePaths
              .filter(path => {
                const ext = path.split('.').pop()?.toLowerCase() || '';
                return ALLOWED_IMAGE_EXTENSIONS.includes(ext);
              })
              .map(async path => {
                // 读取文件内容并转换为File对象
                const buffer = await window.electronAPI.readFile(path);
                const blob = new Blob([buffer]);
                return new File([blob], path.split(/[\\/]/).pop());
              })
          );
          this.handleFiles(files);
        }
      }
    },

    // 文件选择处理方法
    async browseDocuments() {
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
          // 转换Electron文件路径为File对象
          const files = await Promise.all(
            result.filePaths
              .filter(path => {
                const ext = path.split('.').pop()?.toLowerCase() || '';
                return ALLOWED_EXTENSIONS.includes(ext);
              })
              .map(async path => {
                // 读取文件内容并转换为File对象
                const buffer = await window.electronAPI.readFile(path);
                const blob = new Blob([buffer]);
                return new File([blob], path.split(/[\\/]/).pop());
              })
          );
          this.handleFiles(files);
        }
      }
    },
    // 文件验证方法
    isValidFileType(file) {
      if (this.currentUploadType === 'image') {
        return this.isValidImageType(file);
      }
      const ext = (file.name.split('.').pop() || '').toLowerCase()
      return ALLOWED_EXTENSIONS.includes(ext) || MIME_WHITELIST.some(mime => file.type.includes(mime))
    },
    isValidImageType(file) {
      const ext = (file.name.split('.').pop() || '').toLowerCase()
      return ALLOWED_IMAGE_EXTENSIONS.includes(ext) || IMAGE_MIME_WHITELIST.some(mime => file.type.includes(mime))
    },
    // 统一处理文件
    async handleFiles(files) {
      const allowedExtensions = this.currentUploadType === 'image' ? ALLOWED_IMAGE_EXTENSIONS : ALLOWED_EXTENSIONS;
      
      const validFiles = files.filter(file => {
        try {
          // 安全获取文件扩展名
          const filename = file.name || (file.path && file.path.split(/[\\/]/).pop()) || '';
          const ext = filename.split('.').pop()?.toLowerCase() || '';
          return allowedExtensions.includes(ext);
        } catch (e) {
          console.error('文件处理错误:', e);
          return false;
        }
      });
      if (validFiles.length > 0) {
        this.addFiles(validFiles, this.currentUploadType);
      } else {
        this.showErrorAlert(this.currentUploadType);
      }
    },
    removeItem(index, type) {
      if (type === 'file') {
        this.files.splice(index, 1);
      } else {
        // 如果是图片，则从图片列表中删除，考虑this.files长度
        index = index - this.files.length;
        this.images.splice(index, 1);
      }
    },
    // 错误提示
    showErrorAlert(type = 'file') {
      const fileTypes = {
        file: this.t('file_type_error'),
        image: this.t('image_type_error')
      };
      showNotification(fileTypes[type], 'error');
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
      this.activeMenu = 'model-config';
      this.subMenu = 'service';
    },

    // 添加文件到列表
    addFiles(files, type = 'file') {
      const targetArray = type === 'image' ? this.images : this.files;
  
      const newFiles = files.map(file => ({
        path: URL.createObjectURL(file),
        name: file.name,
        file: file,
      }));
      targetArray.push(...newFiles);
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
    async addProvider() {
      this.modelProviders.push({
        id: Date.now(),
        vendor: this.newProviderTemp.vendor,
        url: this.newProviderTemp.url,
        apiKey: '',
        modelId: '',
        isNew: true
      });
      this.newProviderTemp = { vendor: '', url: '', apiKey: '', modelId: '' };
      await this.autoSaveSettings();
    },
    async fetchModelsForProvider(provider) {
      try {
        const response = await fetch(`http://${HOST}:${PORT}/v1/providers/models`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            url: provider.url,
            api_key: provider.apiKey
          })
        });
        if (!response.ok) {
          throw new Error('Failed to fetch models');
        }
        const data = await response.json();
        provider.models = data.data;
      } catch (error) {
        showNotification(this.t('fetch_models_failed'), 'error');
      }
    },
    // 找到原有的 removeProvider 方法，替换为以下代码
    async removeProvider(index) {
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
      await this.autoSaveSettings();
    },
    confirmAddProvider() {
      if (!this.newProviderTemp.vendor) {
        showNotification(this.t('vendor_required'), 'warning')
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
        'Ollama': this.isdocker ? 'http://host.docker.internal:11434/v1' : 'http://127.0.0.1:11434/v1',
        'Vllm': 'http://127.0.0.1:8000/v1',
        'LMstudio': 'http://127.0.0.1:1234/v1',
        'Gemini': 'https://generativelanguage.googleapis.com/v1beta/openai',
        'Anthropic': 'https://api.anthropic.com/v1',
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
      if (value === 'Vllm') {
        this.newProviderTemp.apiKey = 'Vllm'
      }
    },
    // rerank供应商
    async selectRankProvider(providerId) {
      const provider = this.modelProviders.find(p => p.id === providerId);
      if (provider) {
        this.KBSettings.model = provider.modelId;
        this.KBSettings.base_url = provider.url;
        this.KBSettings.api_key = provider.apiKey;
        await this.autoSaveSettings();
      }
    },

    // 主模型供应商选择
    async selectMainProvider(providerId) {
      const provider = this.modelProviders.find(p => p.id === providerId);
      if (provider) {
        this.settings.model = provider.modelId;
        this.settings.base_url = provider.url;
        this.settings.api_key = provider.apiKey;
        await this.autoSaveSettings();
      }
    },

    // 推理模型供应商选择
    async selectReasonerProvider(providerId) {
      const provider = this.modelProviders.find(p => p.id === providerId);
      if (provider) {
        this.reasonerSettings.model = provider.modelId;
        this.reasonerSettings.base_url = provider.url;
        this.reasonerSettings.api_key = provider.apiKey;
        await this.autoSaveSettings();
      }
    },
    async selectVisionProvider(providerId) {
      const provider = this.modelProviders.find(p => p.id === providerId);
      if (provider) {
        this.visionSettings.model = provider.modelId;
        this.visionSettings.base_url = provider.url;
        this.visionSettings.api_key = provider.apiKey;
        await this.autoSaveSettings();
      }
    },
    async selectText2imgProvider(providerId) {
      const provider = this.modelProviders.find(p => p.id === providerId);
      if (provider) {
        this.text2imgSettings.model = provider.modelId;
        this.text2imgSettings.base_url = provider.url;
        this.text2imgSettings.api_key = provider.apiKey;
        this.text2imgSettings.vendor = provider.vendor;
        if (this.text2imgSettings.vendor === 'siliconflow') {
          this.text2imgSettings.size = '1024x1024';
        }
        else {
          this.text2imgSettings.size = 'auto';
        }
        await this.autoSaveSettings();
      }
    },

    handleText2imgProviderVisibleChange(visible) {
      if (!visible) {
        this.selectText2imgProvider(this.text2imgSettings.selectedProvider);
      }
    },

    handleRankProviderVisibleChange(visible) {
      if (!visible) {
        this.selectRankProvider(this.KBSettings.selectedProvider);
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
    handleVisionProviderVisibleChange(visible) {
      if (!visible) {
        this.selectVisionProvider(this.visionSettings.selectedProvider);
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
                showNotification(this.t('invalid_file'), 'error');
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
                showNotification(this.t('file_upload_failed'), 'error');
                return;
              }
  
              const data = await response.json();
              if (data.success) {
                uploadedFiles = data.fileLinks; // 获取上传后的文件链接
                // data.textFiles 添加到 this.textFiles
                this.textFiles = [...this.textFiles, ...data.textFiles];
                await this.autoSaveSettings();
              } else {
                showNotification(this.t('file_upload_failed'), 'error');
                return;
              }
            } catch (error) {
              console.error('Error during file upload:', error);
              showNotification(this.t('file_upload_failed'), 'error');
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
                showNotification(this.t('file_upload_failed'), 'error');
                return;
              }
  
              const data = await response.json();
              if (data.success) {
                uploadedFiles = data.fileLinks; // 获取上传后的文件链接
                // data.textFiles 添加到 this.textFiles
                this.textFiles = [...this.textFiles, ...data.textFiles];
                await this.autoSaveSettings();
              } else {
                showNotification(this.t('file_upload_failed'), 'error');
                return;
              }
            } catch (error) {
              console.error('上传错误:', error);
              showNotification(this.t('file_upload_failed'), 'error');
              return;
            }
          }
        }
  
        // 生成唯一的 ID
        const kbId = uuid.v4();
  
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
          weight: this.newKb.weight,
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
        await this.autoSaveSettings();
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
            try {
              const statusResponse = await fetch(`http://${HOST}:${PORT}/kb_status/${kbId}`);
              
              // 处理 HTTP 错误状态
              if (!statusResponse.ok) {
                console.error('状态检查失败:', statusResponse.status);
                return 'failed'; // 返回明确的失败状态
              }
              const data = await statusResponse.json();
              return data.status || 'unknown'; // 防止 undefined
            } catch (error) {
              console.error('状态检查异常:', error);
              return 'failed';
            }
          };
          // 修改轮询逻辑
          const interval = setInterval(async () => {
            try {
              const status = await checkStatus() || ''; // 确保有默认值
              
              const targetKb = this.knowledgeBases.find(k => k.id === kbId);
              if (!targetKb) {
                clearInterval(interval);
                return;
              }
              // 安全的状态判断
              if (status === 'completed') {
                clearInterval(interval);
                targetKb.processingStatus = 'completed';
                showNotification(this.t('kb_created_successfully'), 'success');
                await this.autoSaveSettings();
              } else if (typeof status === 'string' && status.startsWith('failed')) { // 安全判断
                clearInterval(interval);
                this.knowledgeBases = this.knowledgeBases.filter(k => k.id !== kbId);
                showNotification(this.t('kb_creation_failed'), 'error');
                await this.autoSaveSettings();
              }
            } catch (error) {
              console.error('轮询异常:', error);
              clearInterval(interval);
            }
          }, 2000);
        } catch (error) {
          console.error('知识库创建失败:', error);
          showNotification(this.t('kb_creation_failed'), 'error');
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
          chunk_k: 5,
          weight: 0.5,
        };
        this.newKbFiles = [];
      } catch (error) {
        console.error('知识库创建失败:', error);
        showNotification(this.t('kb_creation_failed'), 'error');
      }
    },

    // 删除知识库
    async removeKnowledgeBase(kb) {
      try {
        // 从 settings 中过滤掉要删除的 knowledgeBase
        this.knowledgeBases = this.knowledgeBases.filter(
          item => item.id !== kb.id
        );
        let kbId = kb.id
        //手动触发modelProviders更新，从而能够实时与后端同步
        this.modelProviders = this.modelProviders
        const Response = await fetch(`http://${HOST}:${PORT}/remove_kb`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kbId }),
        });

        if (!Response.ok) throw new Error('删除失败');

        // 保存 settings
        await this.autoSaveSettings();

        showNotification(this.t('kb_deleted_successfully'), 'success');
      } catch (error) {
        console.error('知识库删除失败:', error);
        showNotification(this.t('kb_deletion_failed'), 'error');
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
          await this.autoSaveSettings();
          showNotification(this.t('kb')+` ${kb.name} ${kb.enabled ? this.t('enabled')  : this.t('disabled')}`, 'success');
        }
      } catch (error) {
        console.error('切换知识库状态失败:', error);
        showNotification(this.t('kb_status_change_failed'), 'error');
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
      this.activeMenu = 'toolkit';  // 根据你的菜单项配置的实际值设置
      this.subMenu = 'document';   // 根据你的子菜单项配置的实际值设置
    },
    // 在 methods 中添加
    t(key) {
      return this.translations[this.currentLanguage][key] || key;
    },
    async handleSystemLanguageChange(val) {
      this.currentLanguage = val;
      this.systemSettings.language = val;
      await this.autoSaveSettings();
      this.$forceUpdate();
    },
    // renderer.js 增强方法
    async handleThemeChange(val) {
      // 更新根属性
      document.documentElement.setAttribute('data-theme', val);
      
      this.systemSettings.theme = val;

      await this.autoSaveSettings();
    },
    async handleNetworkChange(val) {
      this.systemSettings.network = val;
      await window.electronAPI.setNetworkVisibility(val);
      this.showRestartDialog = true;
      await this.autoSaveSettings();
    },

    restartApp() {
      window.electronAPI.restartApp();
    },

    // 方法替换为：
    launchBrowserMode() {
      this.isBrowserOpening = true;
      
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
        }, 2000);
      }, 500);
    },

    // 在methods中添加
    async addMCPServer() {
      try {
        const input = this.newMCPJson.trim();
        const parsed = JSON.parse(input.startsWith('{') ? input : `{${input}}`);
        const servers = parsed.mcpServers || parsed;
        
        // 将服务器name作为ID
        const mcpId = Object.keys(servers)[0];
        
        // 添加临时状态
        this.mcpServers = {
          ...this.mcpServers,
          [mcpId]: {
            ...servers[Object.keys(servers)[0]],
            processingStatus: 'initializing', // 新增状态字段
            disabled:true,
            type: this.newMCPType,
            input: input
          }
        };
        
        this.showAddMCPDialog = false;
        this.newMCPJson = '';
        await this.autoSaveSettings();
        // 触发后台任务
        const response = await fetch(`http://${HOST}:${PORT}/create_mcp`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mcpId })
        });
        
        // 启动状态轮询
        const checkStatus = async () => {
          const statusRes = await fetch(`http://${HOST}:${PORT}/mcp_status/${mcpId}`);
          return statusRes.json();
        };
        
        const interval = setInterval(async () => {
          const { status } = await checkStatus();
          
          if (status === 'ready') {
            clearInterval(interval);
            this.mcpServers[mcpId].processingStatus = 'ready';
            this.mcpServers[mcpId].disabled = false;
            await this.autoSaveSettings();
            showNotification(this.t('mcpAdded'), 'success');
          } else if (status.startsWith('failed')) {
            clearInterval(interval);
            this.mcpServers[mcpId].processingStatus = 'server_error';
            this.mcpServers[mcpId].disabled = true;
            await this.autoSaveSettings();
            showNotification(this.t('mcpCreationFailed'), 'error');
          }
        }, 2000);
        
        await this.autoSaveSettings();
      } catch (error) {
        console.error('MCP服务器添加失败:', error);
        showNotification(error.message, 'error');
      }
      await this.autoSaveSettings();
    },

    async editMCPServer(name) {
      this.newMCPJson =  this.mcpServers[name].input
      this.newMCPType = this.mcpServers[name].type
      this.showAddMCPDialog = true
    },
  
    async removeMCPServer(name) {
      this.deletingMCPName = name
      this.showMCPConfirm = true
    },
    // 新增确认方法
    async confirmDeleteMCP() {
      try {
        const response = await fetch(`http://${HOST}:${PORT}/api/remove_mcp`, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            serverName: this.deletingMCPName
          })
        });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || '删除失败');
        }
        const name = this.deletingMCPName
        const newServers = { ...this.mcpServers }
        delete newServers[name]
        this.mcpServers = newServers
        
        this.$nextTick(async () => {
          await this.autoSaveSettings();
        })
        
        showNotification(this.t('mcpDeleted'), 'success')
      } catch (error) {
        console.error('Error:', error.message)
        showNotification(this.t('mcpDeleteFailed'), 'error')
      } finally {
        this.showMCPConfirm = false
      }
    },
      // 保存智能体
    truncatePrompt(text) {
      return text.length > 100 ? text.substring(0, 100) + '...' : text;
    },
    async saveAgent() {
      const payload = {
        type: 'save_agent',
        data: {
          name: this.newAgent.name,
          system_prompt: this.newAgent.system_prompt
        }
      };
      this.ws.send(JSON.stringify(payload));
      this.showAgentForm = false;
      this.newAgent = {
        id: '',
        name: '',
        system_prompt: ''
      };
    },
    copyAgentId(id) {
      navigator.clipboard.writeText(id)
      showNotification(`Agent ID: ${id} copyed`, 'success');
    },
    copyAgentName(name) {
      navigator.clipboard.writeText(name)
      showNotification(`Agent Name: ${name} copyed`, 'success');
    },
    async removeAgent(id) {
      if (this.agents.hasOwnProperty(id)) {
        delete this.agents[id]
        this.agents = { ...this.agents }
        try {
          // 向/delete_file发送请求
          const response = await fetch(`http://${HOST}:${PORT}/remove_agent`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ agentId: id })
          });
          // 处理响应
          if (response.ok) {
            console.log('Agent deleted successfully');
            showNotification(this.t('AgentDeleted'), 'success');
          }
        } catch (error) {
          console.error('Error:', error);
          showNotification(this.t('AgentDeleteFailed'), 'error');
        }
      }
      await this.autoSaveSettings();
    },
    isValidUrl(url) {
      try {
        new URL(url);
        return true;
      } catch {
        return false;
      }
    },
    async addA2AServer() {
      try {
        this.showAddA2ADialog = false;
        const newurl = this.newA2AUrl;
        this.newA2AUrl = '';
        this.a2aServers = {
          ...this.a2aServers,
          [newurl]: {
            status: 'initializing',
          }
        };
        await this.autoSaveSettings();
        const response = await fetch(`http://${HOST}:${PORT}/a2a/initialize`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: newurl })
        });
        
        const data = await response.json();
        this.a2aServers[newurl] = {
          ...this.a2aServers[newurl],
          ...data
        }

        await this.autoSaveSettings();
      } catch (error) {
        console.error('A2A初始化失败:', error);
        this.a2aServers = Object.fromEntries(Object.entries(this.a2aServers).filter(([k]) => k !== newurl));
        await this.autoSaveSettings();
        showNotification(this.t('a2aInitFailed'), 'error');
      }
    },
    async removeA2AServer(url) {
      this.a2aServers = Object.fromEntries(Object.entries(this.a2aServers).filter(([k]) => k !== url));
      await this.autoSaveSettings();
    },
    formatDate(date) {
      // 时间戳转日期
      return new Date(date).toLocaleString();
    },
    async deleteFile(file) {
      console.log('deleteFile:', file);
      this.textFiles = this.textFiles.filter(f => f !== file);
      await this.autoSaveSettings();
      fileName = file.unique_filename
      try {
        // 向/delete_file发送请求
        const response = await fetch(`http://${HOST}:${PORT}/delete_file`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fileName: fileName })
        });
        // 处理响应
        if (response.ok) {
          console.log('File deleted successfully');
          showNotification(this.t('fileDeleted'), 'success');
        }
      } catch (error) {
        console.error('Error:', error);
        showNotification(this.t('fileDeleteFailed'), 'error');
      }
    },
    async deleteImage(img) {
      this.imageFiles = this.imageFiles.filter(i => i !== img);
      await this.autoSaveSettings();
      fileName = img.unique_filename
      try {
        // 向/delete_file发送请求
        const response = await fetch(`http://${HOST}:${PORT}/delete_file`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fileName: fileName })
        });
        // 处理响应
        if (response.ok) {
          console.log('File deleted successfully');
          showNotification(this.t('fileDeleted'), 'success');
        }
      } catch (error) {
        console.error('Error:', error);
        showNotification(this.t('fileDeleteFailed'), 'error');
      }
    },
    getVendorLogo(vendor) {
      return this.vendorLogoList[vendor] || "";
    },
    handleSelectVendor(vendor) {
      this.newProviderTemp.vendor = vendor;
      this.handleVendorChange(vendor);
    },

    selectMemoryProvider(providerId) {
      const provider = this.modelProviders.find(p => p.id === providerId);
      if (provider) {
        this.newMemory.model = provider.modelId;
        this.newMemory.base_url = provider.url;
        this.newMemory.api_key = provider.apiKey;
      }
    },
    async addMemory() {
      if (this.newMemory.id === null){
        const newMem = {
          id: uuid.v4(),
          name: this.newMemory.name,
          providerId: this.newMemory.providerId,
          model:this.newMemory.model,
          api_key: this.newMemory.api_key,
          base_url: this.newMemory.base_url,
          vendor:this.modelProviders.find(p => p.id === this.newMemory.providerId).vendor,
          lorebook: this.newMemory.lorebook,
          random: this.newMemory.random,
          basic_character: this.newMemory.basic_character,
        };
        this.memories.push(newMem);
        if (this.memorySettings.selectedMemory === null){
          this.memorySettings.selectedMemory = newMem.id;
        }
      }
      else {
        const memory = this.memories.find(m => m.id === this.newMemory.id);
        if (memory) {
          memory.name = this.newMemory.name;
          memory.providerId = this.newMemory.providerId;
          memory.model = this.newMemory.model;
          memory.api_key = this.newMemory.api_key;
          memory.base_url = this.newMemory.base_url;
          memory.vendor = this.modelProviders.find(p => p.id === this.newMemory.providerId).vendor;
          memory.lorebook = this.newMemory.lorebook;
          memory.random = this.newMemory.random;
          memory.basic_character = this.newMemory.basic_character;
        }
      }

      await this.autoSaveSettings();
      this.showAddMemoryDialog = false;
      this.newMemory = { 
        id: null,
        name: '', 
        providerId: null,
        model: '',
        api_key: '',
        base_url: '',
        vendor: '',
        lorebook: [{ name: '', value: '' }], // 默认至少一个条目
        random: [{ value: '' }], // 默认至少一个条目
        basic_character: "",
       };
    },
    
    async removeMemory(id) {
      this.memories = this.memories.filter(m => m.id !== id);
      if (this.memorySettings.selectedMemory === id){
        this.memorySettings.selectedMemory = null;
      }
      try {
        // 向/delete_file发送请求
        const response = await fetch(`http://${HOST}:${PORT}/remove_memory`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ memoryId: id })
        });
        // 处理响应
        if (response.ok) {
          console.log('memory deleted successfully');
          showNotification(this.t('memoryDeleted'), 'success');
        }
      } catch (error) {
        console.error('Error:', error);
        showNotification(this.t('memoryDeleteFailed'), 'error');
      }
      await this.autoSaveSettings();
    },
    editMemory(id) {
      const memory = this.memories.find(m => m.id === id);
      if (memory) {
        this.newMemory = { ...memory };
        this.showAddMemoryDialog = true;
      }
    },

    
    getVendorName(providerId) {
      const provider = this.modelProviders.find(p => p.id === providerId);
      return provider ? `${this.t("model")}:${provider.modelId}` : '';
    },
    async saveCustomHttpTool() {
      const toolData = { ...this.newCustomHttpTool };
      
      if (this.editingCustomHttpTool) {
        // 更新现有工具
        const index = this.customHttpTools.findIndex(tool => tool.id === toolData.id);
        if (index !== -1) {
          this.customHttpTools.splice(index, 1, toolData);
        }
      } else {
        // 添加新工具
        toolData.id = uuid.v4();
        this.customHttpTools.push(toolData);
      }
      
      // 与后端同步数据
      await this.autoSaveSettings();
      
      // 重置表单
      this.newCustomHttpTool = {
        enabled: true,
        name: '',
        description: '',
        url: '',
        method: 'GET',
        headers: '',
        body: ''
      };
      this.showCustomHttpToolForm = false;
      this.editingCustomHttpTool = false;
    },
    editCustomHttpTool(id) {
      const tool = this.customHttpTools.find(tool => tool.id === id);
      if (tool) {
        this.newCustomHttpTool = { ...tool };
        this.showCustomHttpToolForm = true;
        this.editingCustomHttpTool = true;
      }
    },
    async removeCustomHttpTool(id) {
      this.customHttpTools = this.customHttpTools.filter(tool => tool.id !== id);
      await this.autoSaveSettings();
    },
  // 启动QQ机器人
  async startQQBot() {
    this.isStarting = true;
    
    try {
      // 显示连接中的提示
      showNotification('正在连接QQ机器人...', 'info');
      
      const response = await fetch(`http://${HOST}:${PORT}/start_qq_bot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.qqBotConfig)
      });

      const result = await response.json();
      
      if (result.success) {
        this.isQQBotRunning = true;
        showNotification('QQ机器人已成功启动并就绪', 'success');
      } else {
        // 显示具体错误信息
        const errorMessage = result.message || '启动失败，请检查配置';
        showNotification(`启动失败: ${errorMessage}`, 'error');
        
        // 如果是超时错误，给出更具体的提示
        if (errorMessage.includes('超时')) {
          showNotification('提示：请检查网络连接和机器人配置是否正确', 'warning');
        }
      }
    } catch (error) {
      console.error('启动QQ机器人时出错:', error);
      showNotification('启动QQ机器人失败: 网络错误或服务器未响应', 'error');
    } finally {
      this.isStarting = false;
    }
  },

  // 停止QQ机器人
  async stopQQBot() {
    this.isStopping = true;
    
    try {
      const response = await fetch(`http://${HOST}:${PORT}/stop_qq_bot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const result = await response.json();
      
      if (result.success) {
        this.isQQBotRunning = false;
        showNotification('QQ机器人已成功停止', 'success');
      } else {
        const errorMessage = result.message || '停止失败';
        showNotification(`停止失败: ${errorMessage}`, 'error');
      }
    } catch (error) {
      console.error('停止QQ机器人时出错:', error);
      showNotification('停止QQ机器人失败: 网络错误或服务器未响应', 'error');
    } finally {
      this.isStopping = false;
    }
  },

  // 重载QQ机器人配置
  async reloadQQBotConfig() {
    this.isReloading = true;
    
    try {
      const response = await fetch(`http://${HOST}:${PORT}/reload_qq_bot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.qqBotConfig)
      });

      const result = await response.json();
      
      if (result.success) {
        if (result.config_changed) {
          showNotification('QQ机器人配置已重载并重新启动', 'success');
        } else {
          showNotification('QQ机器人配置已更新', 'success');
        }
      } else {
        const errorMessage = result.message || '重载失败';
        showNotification(`重载失败: ${errorMessage}`, 'error');
      }
    } catch (error) {
      console.error('重载QQ机器人配置时出错:', error);
      showNotification('重载QQ机器人配置失败: 网络错误或服务器未响应', 'error');
    } finally {
      this.isReloading = false;
    }
  },
  
  // 添加状态检查方法
  async checkQQBotStatus() {
    try {
      const response = await fetch(`http://${HOST}:${PORT}/qq_bot_status`);
      const status = await response.json();
      
      // 更新机器人运行状态
      this.isQQBotRunning = status.is_running;
      
      // 如果机器人正在运行但前端状态不一致，更新状态
      if (status.is_running && !this.isQQBotRunning) {
        this.isQQBotRunning = true;
      }
    } catch (error) {
      console.error('检查机器人状态失败:', error);
    }
  },

    // 新增的方法：供主进程请求关闭机器人
    async requestStopQQBotIfRunning() {
      try {
        const response = await fetch(`http://${HOST}:${PORT}/qq_bot_status`)
        const status = await response.json()

        if (status.is_running) {
          // 调用 stopQQBot 来关闭机器人
          await this.stopQQBot()
          console.log('机器人已关闭')
        }
      } catch (error) {
        console.error('检查或停止机器人失败:', error)
      }
    },
    async handleSeparatorChange(val) {
      this.qqBotConfig.separators = val.map(s => 
        s.replace(/\\n/g, '\n').replace(/\\t/g, '\t')
      );
      await this.autoSaveSettings();
    },
    formatSeparator(s) {
      return s.replace(/\n/g, '\\n')
              .replace(/\t/g, '\\t')
              .replace(/\r/g, '\\r');
    },
    // 新增创建分隔符处理方法
    async handleCreateSeparator(newSeparator) {
      const processed = this.escapeSeparator(newSeparator)
      if (!this.qqBotConfig.separators.includes(processed)) {
        this.qqBotConfig.separators.push(processed)
        await this.autoSaveSettings()
      }
    },

    // 处理回车键冲突
    handleEnter(e) {
      if (e.target.value) {
        e.stopPropagation()
      }
    },

    escapeSeparator(s) {
      return s.replace(/\\n/g, '\n').replace(/\\t/g, '\t')
    },
    clearParam(index) {
      this.newMemory.lorebook[index].name = "";
      this.newMemory.lorebook[index].value = "";
      this.autoSaveSettings();
    },
    clearRandom(index) {
      this.newMemory.random[index].value = "";
      this.autoSaveSettings();
    },
    copyExistingMemoryData(selectedId) {
      const existingMemory = this.memories.find(memory => memory.id === selectedId);
      if (existingMemory) {
        this.newMemory = { ...existingMemory };
        this.newMemory.id = null; // 确保新记忆的ID为null，以便在创建时生成新的ID
      } else {
        this.newMemory = { 
          id: null,
          name: '', 
          providerId: null,
          model: '',
          base_url: '',
          api_key: '',
          vendor: '',
          lorebook: [{ name: '', value: '' }], // 默认至少一个条目
          random: [{ value: '' }], // 默认至少一个条目
          basic_character: '',
        };
      }
    },
    colorBlend(color1, color2, ratio) {
        // 确保ratio在0-1范围内
        ratio = Math.max(0, Math.min(1, ratio));
        
        // 解析十六进制颜色值
        const parseHex = (hex) => {
          hex = hex.replace(/^#/, '');
          // 处理3位简写格式
          if (hex.length === 3) {
            hex = hex.split('').map(char => char + char).join('');
          }
          return {
            r: parseInt(hex.substring(0, 2), 16),
            g: parseInt(hex.substring(2, 4), 16),
            b: parseInt(hex.substring(4, 6), 16)
          };
        };

        // 转换为两位十六进制字符串
        const toHex = (value) => {
          const hex = Math.round(value).toString(16);
          return hex.length === 1 ? '0' + hex : hex;
        };

        const rgb1 = parseHex(color1);
        const rgb2 = parseHex(color2);

        // 计算混合后的RGB值
        const r = rgb1.r * ratio + rgb2.r * (1 - ratio);
        const g = rgb1.g * ratio + rgb2.g * (1 - ratio);
        const b = rgb1.b * ratio + rgb2.b * (1 - ratio);

        // 组合成十六进制颜色
        return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
      },
      toggleInputExpand() {
        this.isInputExpanded = !this.isInputExpanded
    },
    checkMobile() {
      this.isMobile = window.innerWidth <= 768;
      if(this.isMobile) this.sidebarVisible = false;
    },
    // 添加ComfyUI服务器
    addComfyUIServer() {
      this.comfyuiServers.push('http://localhost:8188')
      this.autoSaveSettings()
    },

    // 移除服务器
    removeComfyUIServer(index) {
      if (this.comfyuiServers.length > 1) {
        this.comfyuiServers.splice(index, 1)
        this.autoSaveSettings()
      }
    },

    // 连接服务器
    async connectComfyUI() {
      this.isConnecting = true
      try {
        const url = this.comfyuiServers[0]
        const response = await fetch(`${url}/history`, {
          method: 'HEAD',
          mode: 'cors'
        })
        if (response.ok) {
          this.activeComfyUIUrl = url
          showNotification('服务器连接成功')
        }
      } catch (e) {
        showNotification('无法连接ComfyUI服务器', 'error')
      }
      this.isConnecting = false
    },
    // 浏览文件
    browseWorkflowFile() {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.json';
      input.onchange = (event) => {
        const files = event.target.files;
        if (files.length > 0) {
          this.workflowFile = files[0];
          this.loadWorkflowFile(this.workflowFile); // 确保在文件已选择后调用
        }
      };
      input.click();
    },
    // 移除文件
    removeWorkflowFile() {
      this.workflowFile = null;
    },
    // 删除工作流
    async deleteWorkflow(filename) {
      try {
        const response = await fetch(`/delete_workflow/${filename}`, {
          method: 'DELETE',
        });
        const data = await response.json();
        if (data.success) {
          this.workflows = this.workflows.filter(file => file.unique_filename !== filename);
          await this.autoSaveSettings();
          showNotification('删除成功');
        } else {
          this.workflows = this.workflows.filter(file => file.unique_filename !== filename);
          await this.autoSaveSettings();
          showNotification('删除失败', 'error');
        }
      } catch (error) {
        console.error('删除失败:', error);
       showNotification('删除失败', 'error');
      }
    },
      // 处理文件拖拽
  handleWorkflowDrop(event) {
    event.preventDefault();
    const files = event.dataTransfer.files;
    if (files.length > 0) {
      this.workflowFile = files[0];
      this.loadWorkflowFile(this.workflowFile); // 加载工作流文件以生成选择项
    }
  },
  
  // 加载工作流文件
  async loadWorkflowFile(file) {
    const reader = new FileReader();
    reader.onload = (event) => {
      const workflowJson = JSON.parse(event.target.result);
      this.populateInputOptions(workflowJson);
    };
    reader.readAsText(file);
  },

  // 填充输入选择项
  populateInputOptions(workflowJson) {
    this.textInputOptions = [];
    this.imageInputOptions = [];
    
    for (const nodeId in workflowJson) {
      const node = workflowJson[nodeId];
      if (!node.inputs) continue;
      
      // 查找所有包含text/value/prompt的文本输入字段
      const textInputKeys = Object.keys(node.inputs).filter(key => 
        (key.includes('text') || key.includes('value') || key.includes('prompt')) &&
        typeof node.inputs[key] === 'string' // 确保值是字符串类型
      );
      
      // 为每个符合条件的字段创建选项
      textInputKeys.forEach(key => {
        this.textInputOptions.push({
          label: `${node._meta.title} - ${key} (ID: ${nodeId})`,
          value: { nodeId, inputField: key, id : `${nodeId}-${key}` },
        });
      });
      
      // 查找图片输入字段
      if (node.class_type === 'LoadImage') {
        const imageKeys = Object.keys(node.inputs).filter(key => 
          key.includes('image') && 
          typeof node.inputs[key] === 'string' // 确保值是字符串类型
        );
        
        imageKeys.forEach(key => {
          this.imageInputOptions.push({
            label: `${node._meta.title} - ${key} (ID: ${nodeId})`,
            value: { nodeId, inputField: key, id : `${nodeId}-${key}` },
          });
        });
      }
    }
  },

    // 上传文件
    async uploadWorkflow() {
      if (!this.workflowFile) return;

      const formData = new FormData();
      formData.append('file', this.workflowFile);

      // 记录所选的输入位置
      const workflowData = {
        textInput: this.selectedTextInput,
        textInput2: this.selectedTextInput2,
        imageInput: this.selectedImageInput,
        imageInput2: this.selectedImageInput2,
        description: this.workflowDescription,
      };

      // 发送 JSON 字符串作为普通字段
      formData.append('workflow_data', JSON.stringify(workflowData));

      try {
        const response = await fetch('/add_workflow', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) { // 检查响应状态
          const errorText = await response.text(); // 获取错误文本
          console.error("Server error:", errorText); // 输出错误信息
          throw new Error("Server error");
        }

        const data = await response.json();
        if (data.success) {
          this.workflows.push(data.file);
          this.showWorkflowUploadDialog = false;
          this.workflowFile = null;
          this.selectedTextInput = null; // 重置选中
          this.selectedImageInput = null; // 重置选中
          this.selectedTextInput2 = null; // 重置选中
          this.selectedImageInput2 = null; // 重置选中
          this.workflowDescription = ''; // 清空描述
          await this.autoSaveSettings();
          showNotification('上传成功');
        } else {
          showNotification('上传失败', 'error');
        }
      } catch (error) {
        console.error('上传失败:', error);
        showNotification('上传失败', 'error');
      }
    },
    cancelWorkflowUpload() {
      this.showWorkflowUploadDialog = false;
      this.workflowFile = null;
      this.selectedTextInput = null; // 重置选中
      this.selectedImageInput = null; // 重置选中
      this.selectedTextInput2 = null; // 重置选中
      this.selectedImageInput2 = null; // 重置选中
      this.workflowDescription = ''; // 清空描述
    },
}