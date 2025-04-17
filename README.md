# super-agent-party

## 简介

如果你想要让一个大模型变成一个智能体，接入知识库、联网、MCP服务、深度思考、深度研究，并且还能够通过Openai API调用或web端、桌面端直接使用，那么这个项目就是为你准备的。

## 功能

1. 知识库，让大模型能够根据知识库中的信息进行回答。如果有多个知识库，模型会根据提问需求去主动查询对应的知识库。
2. 联网功能，让大模型能够根据提问需求去主动联网查询信息。目前已支持：
- [duckduckgo](https://duckduckgo.com/)（完全免费，中国网络环境无法访问）
- [searxng](https://github.com/searxng/searxng)（可以docker本地部署）
- [tavily](https://tavily.com/)（需要申请api key）
- [jina](https://github.com/jina-ai/jina)（可以无需api key，用于网页抓取）
- [crawl4ai](https://github.com/unclecode/crawl4ai)（可以docker本地部署，用于网页抓取）。
3. [MCP](https://modelcontextprotocol.io/introduction)服务，让大模型能够根据提问需求去主动调用MCP服务。目前支持两种调用方式：标准输入输出和服务器发送事件 (SSE)。
4. 深度思考，可以将推理模型的推理能力移植到可以工具调用或多模态模型中，让大模型在工具调用之前先利用推理模型进行推理分析。例如：deepseek-V3可以工具调用，但是推理模型deepseek-R1无法工具调用，那么就可以将deepseek-R1的推理能力移植到deepseek-V3中，让deepseek-V3在工具调用之前先利用deepseek-R1进行推理分析。
5. 深度研究，将用户的问题转化成任务，逐步分析推理后调用工具，输出结果后会重新检查任务是否完成，如果任务未完成，则继续分析推理后调用工具，直到任务完成。

## 使用方法

### docker部署

1. 生成docker容器：
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

2. 安装依赖：
- windows: 点击脚本`install.bat`
- macos/linux:点击脚本`install.sh`
- 或者手动执行以下命令以安装依赖：
```shell
python -m venv super
super\Scripts\activate # windows
# source super/bin/activate # macos/linux
pip install -r requirements.txt
npm install
```

3. 启动服务：
- windows: 点击脚本`start_with_dev.bat`
- macos/linux:点击脚本`start_with_dev.sh`
- 或者手动执行以下命令以启动服务：
```shell
npm run dev
```