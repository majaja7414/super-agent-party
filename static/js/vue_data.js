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
  // 判断协议
  const protocol = window.location.protocol;
let vue_data = {
    isElectron: isElectron,
    partyURL:window.location.port ? `${protocol}//${HOST}:${PORT}` : `${protocol}//${HOST}`,
    downloadProgress: 0,
    updateDownloaded: false,
    updateAvailable: false,
    updateInfo: null,
    updateIcon: 'fa-solid fa-download',
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
    visionSettings: {
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
      getFile: {
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
}`,
    streamablehttp: `{
  "mcpServers": {
    "streamablehttp-server": {
      "url": "http://localhost:8000/streamablehttp",
      "disabled": false
    }
  }
}`
    },
    activeKbTab: 'add', // 默认激活的标签页
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
    codeSettings: {
      enabled: false,
      engine: 'e2b',
      e2b_api_key: '',
    },
    knowledgeBases: [],
    KBSettings: {
      when: 'before_thinking',
      is_rerank: false,
      selectedProvider: null,
      model: '',
      base_url: '',
      api_key: '',
      top_n: 5,
    },
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
      weight: 0.5,
      processingStatus: 'processing',
    },
    newKbFiles: [],
    systemSettings: {
      language: 'zh-CN',
      theme: 'light',
      network:"local",
    },
    networkOptions:[
      { value: 'local', label: 'local' }, 
      { value: 'global', label: 'global' },
    ],
    showRestartDialog: false,
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
    modelTiles: [
      { id: 'service', title: 'modelService', icon: 'fa-solid fa-cloud' },
      { id: 'main', title: 'mainModel', icon: 'fa-solid fa-microchip' },
      { id: 'reasoner', title: 'reasonerModel', icon: 'fa-solid fa-atom' },
      { id: 'vision', title: 'visionModel' , icon: 'fa-solid fa-camera'}
    ],
    toolkitTiles: [
      { id: 'tools', title: 'tools', icon: 'fa-solid fa-screwdriver-wrench' },
      { id: 'websearch', title: 'webSearch', icon: 'fa-solid fa-globe' },
      { id: 'document', title: 'knowledgeBase', icon: 'fa-solid fa-book' },
      { id: 'memory', title: 'memory', icon: 'fa-solid fa-brain'},
      { id: 'interpreter', title: 'interpreter', icon: 'fa-solid fa-code'}
    ],
    apiTiles: [
      { id: 'openai', title: 'openaiStyleAPI', icon: 'fa-solid fa-link' },
      { id: 'mcp', title: 'MCPStyleAPI', icon: 'fa-solid fa-server' },
      { id: 'docker', title: 'docker', icon: 'fa-brands fa-docker'},
      { id: 'browser', title: 'browserMode', icon: 'fa-solid fa-globe' }
    ],
    storageTiles: [
      { id: 'text', icon: 'fa-solid fa-file-lines', title: 'storageText' },
      { id: 'image', icon: 'fa-solid fa-image', title: 'storageImage' },
      { id: 'video', icon: 'fa-solid fa-video', title: 'storageVideo' }
    ],
    activeMemoryTab: 'add',
    memories: [],
    newMemory: { 
      id: null,
      name: '', 
      providerId: null,
      model: '',
      base_url: '',
      api_key: '',
      vendor: '',
      lorebook: [],
      basic_character: '',
    },
    showAddMemoryDialog: false,
    showMemoryDialog: false,
    memorySettings: {
      selectedMemory: null,
      is_memory: false,
      memoryLimit: 3
    },
    textFiles: [],
    imageFiles: [],
    videoFiles: [],
    subMenu: '', // 新增子菜单状态
    agentTiles: [
      { 
        id: 'agents',
        title: 'agentSnapshot',
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
      'custom', 'OpenAI', 'Ollama','Vllm','LMstudio', 'Deepseek', 'Volcano',
      'siliconflow', 'aliyun', 'ZhipuAI', 'moonshot', 'minimax', 'Gemini','Anthropic', 
      'Grok', 'mistral', 'lingyi','baichuan', 'qianfan', 'hunyuan', 'stepfun', 'Github', 
      'openrouter','together', 'fireworks', '360', 'Nvidia',
      'jina', 'gitee', 'perplexity', 'infini',
      'modelscope', 'tencent'
    ],
    vendorLogoList: {
      'custom': 'source/providers/custom.png',
      'OpenAI': 'source/providers/openai.jpeg',
      'Ollama': 'source/providers/ollama.png',
      'Vllm': 'source/providers/vllm.png',
      'LMstudio': 'source/providers/lmstudio.png',
      'Deepseek': 'source/providers/deepseek.png',
      'Volcano': 'source/providers/volcengine.png',
      'siliconflow': 'source/providers/silicon.png',
      'aliyun': 'source/providers/bailian.png',
      'ZhipuAI': 'source/providers/zhipu.png',
      'moonshot': 'source/providers/moonshot.png',
      'minimax': 'source/providers/minimax.png',
      'Gemini': 'source/providers/gemini.png',
      'Anthropic': 'source/providers/anthropic.png',
      'Grok': 'source/providers/grok.png',
      'mistral': 'source/providers/mistral.png',
      'lingyi': 'source/providers/zero-one.png',
      'baichuan': 'source/providers/baichuan.png',
      'qianfan': 'source/providers/baidu-cloud.svg',
      'hunyuan': 'source/providers/hunyuan.png',
      'stepfun': 'source/providers/step.png',
      'Github': 'source/providers/github.png',
      'openrouter': 'source/providers/openrouter.png',
      'together': 'source/providers/together.png',
      'fireworks': 'source/providers/fireworks.png',
      '360': 'source/providers/360.png',
      'Nvidia': 'source/providers/nvidia.png',
      'jina': 'source/providers/jina.png',
      'gitee': 'source/providers/gitee-ai.png',
      'perplexity': 'source/providers/perplexity.png',
      'infini': 'source/providers/infini.png',
      'modelscope': 'source/providers/modelscope.png',
      'tencent': 'source/providers/tencent-cloud-ti.png'
    },
    vendorAPIpage: {
      'OpenAI': 'https://platform.openai.com/api-keys',
      'Ollama': 'https://ollama.com/',
      'Vllm': 'https://docs.vllm.ai/en/latest/',      
      'LMstudio': 'https://lmstudio.ai/docs/app',
      'Deepseek': 'https://platform.deepseek.com/api_keys',
      'Volcano': 'https://www.volcengine.com/experience/ark',
      'siliconflow': 'https://cloud.siliconflow.cn/i/yGxrNlGb',
      'aliyun': 'https://bailian.console.aliyun.com/?tab=model#/api-key',
      'ZhipuAI': 'https://open.bigmodel.cn/usercenter/apikeys',
      'moonshot': 'https://platform.moonshot.cn/console/api-keys',
      'minimax': 'https://platform.minimaxi.com/user-center/basic-information/interface-key',
      'Gemini': 'https://aistudio.google.com/app/apikey',
      'Anthropic': 'https://console.anthropic.com/settings/keys',
      'Grok': 'https://console.x.ai/',
      'mistral': 'https://console.mistral.ai/api-keys/',
      'lingyi': 'https://platform.lingyiwanwu.com/apikeys',
      'baichuan': 'https://platform.baichuan-ai.com/console/apikey',
      'qianfan': 'https://console.bce.baidu.com/iam/#/iam/apikey/list',
      'hunyuan': 'https://console.cloud.tencent.com/hunyuan/api-key',
      'stepfun': 'https://platform.stepfun.com/interface-key',
      'Github': 'https://github.com/settings/tokens',
      'openrouter': 'https://openrouter.ai/settings/keys',
      'together': 'https://api.together.ai/settings/api-keys',
      'fireworks': 'https://fireworks.ai/account/api-keys',
      '360': 'https://ai.360.com/platform/keys',
      'Nvidia': 'https://build.nvidia.com/meta/llama-3_1-405b-instruct',
      'jina': 'https://jina.ai/api-dashboard',
      'gitee': 'https://ai.gitee.com/dashboard/settings/tokens',
      'perplexity': 'https://www.perplexity.ai/settings/api',
      'infini': 'https://cloud.infini-ai.com/iam/secret/key',
      'modelscope': 'https://modelscope.cn/my/myaccesstoken',
      'tencent': 'https://console.cloud.tencent.com/lkeap/api'
    },
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
    images: [],
    currentUploadType: 'file',
    selectedCodeLang: 'python',
    previewClickHandler: null,
    dockerExamples: `docker pull ailm32442/super-agent-party:latest
docker run -d -p 3456:3456 -v ./super-agent-data:/app/data ailm32442/super-agent-party:latest
`,
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
    modelOptions: [],
    previewVisible: false,
    previewImageUrl: ''
};