## 完整安装使用教程

### windows桌面版安装

如果你是windows系统，可以直接[点击下载](https://github.com/heshengtao/super-agent-party/releases/download/v0.1.1/Super.Agent.Party-Setup-0.1.1.exe)windows桌面版，然后按照提示进行安装。

### docker部署（推荐）

1. 获取docker镜像（二选一）：
- 从dockerhub拉取官网镜像：
```shell
docker pull ailm32442/super-agent-party:latest
docker run -d -p 3456:3456 ailm32442/super-agent-party:latest
```

- 从源码生成镜像：
```shell
git clone https://github.com/heshengtao/super-agent-party.git
cd super-agent-party
docker pull python:3.12-slim 
docker build -t super-agent-party . 
docker run -d -p 3456:3456 super-agent-party:latest
```

2. 访问http://localhost:3456/

### 源码部署

1. 下载仓库：
```shell
git clone https://github.com/heshengtao/super-agent-party.git
cd super-agent-party
```

2. 安装依赖（四选一）：
- windows: 点击脚本`install.bat`
- macos/linux:点击脚本`install.sh`
- 或者使用pip和npm安装依赖：
```shell
python -m venv .venv
.venv\Scripts\activate # windows
# source .venv/bin/activate # macos/linux
pip install -r requirements.txt
npm install
```
- 或者使用uv和npm安装依赖：
```shell
uv sync
npm install
```

3. 启动服务（三选一）：
- windows: 点击脚本`start_with_dev.bat`
- macos/linux:点击脚本`start_with_dev.sh`
- 或者手动执行以下命令以启动服务：
```shell
.venv\Scripts\activate # windows
# source .venv/bin/activate # macos/linux
npm run dev
```

## 怎么使用
1. 点击左侧栏的系统设置，可以设置语言选项、系统主题。
2. 点击左侧栏的模型配置-模型服务界面，配置你需要调用的云服务商，例如：openai、deepseek等。选择模型服务商并填入对应的API key，然后点击右上角的放大镜按钮，可以获取到该服务商的模型列表，选择你需要的模型，即可完成配置。
3. 点击左侧栏的模型配置-主模型、模型配置-推理模型界面，可以更精准的配置你的模型，默认会选择模型服务商中的第一个模型，你也可以选择其他模型。注意！主模型需要有工具调用能力（一般的推理模型都没有工具能力），推理模型需要有推理能力。
4. 点击左侧栏的模型配置-视觉模型界面，可以配置视觉模型。让无视觉能力的模型拥有视觉能力，并缓存已发送过的图片，从而节省token。
5. 点击左侧栏的智能体套件界面，然后选择以下二级界面：
    - 智能体界面，可以配置智能体的系统提示词，系统提示词决定了智能体的行为，你可以根据你的需求进行修改。当你创建时，智能体会快照你的所有当前配置，包括模型服务、知识库、联网功能、MCP服务、工具、系统提示词等。
    - MCP服务界面，可以配置MCP服务，目前支持两种调用方式：标准输入输出和服务器发送事件 (SSE)。标准输入输出方式需要配置MCP服务器的各类参数，如果报错，请注意本地是否安装对应的包管理器（例如：uv、npm等），SSE方式需要配置MCP服务器的地址。
    - A2A服务界面，可以配置A2A服务，配置A2A服务器的地址后即可使用。
    - LLM工具界面，目前以支持其他ollama格式或者openai格式的自定义智能体接入后，作为工具使用。
6. 点击左侧栏的工具套件-工具界面，可以配置一些小工具，包括当前时间、深度研究、伪推理能力。如果你想要固定智能体使用的语言，可以在这里配置。
7. 点击左侧栏的工具套件-联网功能界面，可以配置联网功能，目前支持三种搜索引擎和两种网页转markdown工具：duckduckgo、searxng、tavily、jina、crawl4ai。duckduckgo不需要配置，searxng需要配置docker镜像地址，tavily需要配置api key，jina不需要配置，crawl4ai需要配置docker镜像地址。
8. 点击左侧栏的工具套件-知识库界面，可以配置知识库。在配置知识库之前，需要在左侧栏的模型服务界面完成词嵌入模型的配置。
9. 点击左侧栏的调用方法界面，你可以用openai格式来调用本应用创建的智能体，模型名称如果为`super-model`，就会调用当前配置的智能体，模型名称如果为你在智能体界面创建的智能体ID或者智能体名称，就会调用你创建的智能体。