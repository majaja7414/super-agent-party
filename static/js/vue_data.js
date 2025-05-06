const isElectron = window.electronAPI ? true : false;
// 事件监听改造
if (isElectron) {
    document.addEventListener('contextmenu', ev => {
      // 阻止默认行为
      ev.preventDefault();
      // 获取鼠标位置
      const client = {
        x: ev.clientX,
        y: ev.clientY
      };
      // 把鼠标位置发送到主进程
      window.electronAPI.showContextMenu(client);
    });
  
    HOST = "127.0.0.1"
    PORT = 3456
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
  else {
    HOST = window.location.hostname
    PORT = window.location.port
  }

let vue_data = {
    system_prompt: ' ',
    isdocker: false,
    isExpanded: true,
    isElectron: isElectron,
    isCollapse: true,
    isBtnCollapse: false,
    activeMenu: 'home',
    isMaximized: false,
    hasUpdate: false,
    updateSuccess: false,
    settings: {
      model: '',
      base_url: '',
      api_key: '',
      temperature: 0.7,  // 默认温度值
      max_tokens: 4096,    // 默认最大输出长度
      max_rounds: 0,    // 默认最大轮数
      selectedProvider: null,
      top_p: 1,
      extra_params: [], // 额外参数
    },
    reasonerSettings: {
      enabled: false, // 默认不启用
      model: '',
      base_url: '',
      api_key: '',
      selectedProvider: null,
      temperature: 0.7,  // 默认温度值
    },
    paramTypes: [
      { value: 'string', label: 'string' },
      { value: 'integer', label: 'integer' },
      { value: 'float', label: 'float' },
      { value: 'boolean', label: 'boolean' }
    ],
    ws: null,
    messages: [],
    userInput: '',
    isTyping: false,
    currentMessage: '',
    conversationId: null, // 当前对话ID
    conversations: [], // 对话历史记录
    showHistoryDialog: false,
    showLLMToolsDialog: false,
    deletingConversationId: null, // 正在被删除的对话ID
    models: [],
    modelsLoading: false,
    modelsError: null,
    isThinkOpen: false,
    showEditDialog: false,
    editContent: '',
    editType: 'system', // 或 'message'
    editIndex: null,
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
      },
      pollinations: {
        enabled: false, // 默认不启用
      }
    },
    mcpServers: {},
    showAddMCPDialog: false,
    showMCPConfirm: false,
    deletingMCPName: null,
    newMCPJson: '',
    newMCPType: 'stdio', // 新增类型字段
    currentMCPExample: '',
    mcpExamples: {
      stdio: `{
"mcpServers": {
  "echo-server": {
    "command": "node",
    "args": [
      "path/to/echo-mcp/build/index.js"
    ],
    "disabled": false
  }
}
}`,
      sse: `{
"mcpServers": {
  "sse-server": {
    "url": "http://localhost:8000/sse",
    "disabled": false
  }
}
}`,
      ws: `{
"mcpServers": {
  "websocket-server": {
    "url": "ws://localhost:8000/ws",
    "disabled": false
  }
}
}`
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
    showMCPServerDialog: false,
    a2aServers: {},
    showA2AServerDialog: false,
    showAddA2ADialog: false,
    newA2AUrl: '',
    activeCollapse: [],
    newKb: {
      name: '',
      introduction: '',
      providerId: null,
      model: '',
      base_url: '',
      api_key: '',
      chunk_size: 2048,
      chunk_overlap: 512,
      chunk_k: 5,
      processingStatus: 'processing',
    },
    newKbFiles: [],
    systemSettings: {
      language: 'zh-CN',
      theme: 'light',
    },
    agents: {},
    showAgentForm: false,
    editingAgent: null,
    showAgentDialog: false,
    mainAgent: 'super-model',
    newAgent: {
      id: '',
      name: '',
      system_prompt: ''
    },
    editingAgent: false,
    currentLanguage: 'zh-CN',
    translations: translations,
    themeValues: ['light', 'dark'],
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
      settingsAdvanced: true,
      reasonerAdvanced: true,
      knowledgeAdvanced: false,
    },
    abortController: null, // 用于中断请求的控制器
    isSending: false, // 是否正在发送
    showAddDialog: false,
    modelProviders: [],
    // 更新相关
    updateAvailable: false,
    updateInfo: null,
    updateDownloaded: false,
    downloadProgress: 0,
    fileLinks: [],
    subMenu: 'agents', // 新增子菜单状态
    agentTiles: [
      { 
        id: 'agents',
        title: 'agents',
        icon: 'fa-solid fa-robot'
      },
      {
        id: 'mcp',
        title: 'mcpServers', 
        icon: 'fa-solid fa-server'
      },
      {
        id: 'a2a',
        title: 'a2aServers',
        icon: 'fa-solid fa-plug'
      },
      {
        id: 'llmTool',
        title: 'llmTools',
        icon: 'fa-solid fa-network-wired'
      }
    ],
    vendorValues: [
      'custom', 'OpenAI', 'Ollama', 'Deepseek', 'Volcano',
      'siliconflow', 'aliyun', 'ZhipuAI', 'moonshot', 'minimax',
      'LMstudio', 'Gemini','Anthropic', 'Grok', 'mistral', 'lingyi',
      'baichuan', 'qianfan', 'hunyuan', 'stepfun', 'o3',
      'aihubmix', 'ocoolai', 'Github', 'dmxapi', 'openrouter',
      'together', 'fireworks', '360', 'Nvidia', 'hyperbolic',
      'jina', 'gitee', 'ppinfra', 'perplexity', 'infini',
      'modelscope', 'tencent'
    ],
    newProviderTemp: {
      vendor: '',
      url: '',
      apiKey: '',
      modelId: ''
    },
    systemlanguageOptions:[
      { value: 'zh-CN', label: '中文' }, 
      { value: 'en-US', label: 'English' },
    ],
    toneValues: [
      'normal', 'formal', 'friendly', 'humorous', 'professional',
      'sarcastic', 'ironic', 'flirtatious', 'tsundere', 'coquettish',
      'angry', 'sad', 'excited', 'refutational'
    ],
    showUploadDialog: false,
    agentTabActive: 'knowledge',
    files: [],
    selectedCodeLang: 'python',
    previewClickHandler: null,
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
    llmTools: [],
    showLLMForm: false,
    editingLLM: null,
    newLLMTool: {
      name: '',
      type: 'openai',
      description: '',
      base_url: '',
      api_key: '',
      model: '',
      enabled: true
    },
    llmInterfaceTypes: [
      { value: 'openai', label: 'OpenAI' },
      { value: 'ollama', label: 'Ollama' }
    ],
    modelOptions: []
};