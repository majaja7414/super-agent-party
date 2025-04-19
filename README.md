![image](static/source/agent_party.png)

<div align="center">
  <a href="./README_ZH.md"><img src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README.md"><img src="https://img.shields.io/badge/English-d9d9d9"></a>
</div>

## Introduction

If you want to transform a large model into an intelligent agent that can access knowledge bases, connect to the internet, utilize MCP services, perform deep thinking and in-depth research, and also be usable via OpenAI API calls or directly through web and desktop applications, then this project is for you.

![image](static/source/image.png)

## Features

1. Knowledge Base: Enables large models to answer based on information within the knowledge base. If there are multiple knowledge bases, the model will proactively query the relevant one based on the question.
2. Internet Connectivity: Allows large models to proactively search for information online based on question requirements. Currently supports:
- [duckduckgo](https://duckduckgo.com/) (completely free, not accessible in China's network environment)
- [searxng](https://github.com/searxng/searxng) (can be deployed locally with Docker)
- [tavily](https://tavily.com/) (requires applying for an API key)
- [jina](https://github.com/jina-ai/jina) (can be used without an API key for web scraping)
- [crawl4ai](https://github.com/unclecode/crawl4ai) (can be deployed locally with Docker for web scraping).
3. [MCP](https://modelcontextprotocol.io/introduction) Services: Enable large models to proactively call MCP services based on question requirements. Currently supports two calling methods: standard input/output and Server-Sent Events (SSE).
4. Deep Thinking: Transplants the reasoning capabilities of reasoning models into tool-invoking or multimodal models so that large models can use reasoning models for analysis before invoking tools. For example, if deepseek-V3 can invoke tools but the reasoning model deepseek-R1 cannot, the reasoning capability of deepseek-R1 can be transplanted into deepseek-V3 to allow it to reason using deepseek-R1 before invoking tools.
5. In-depth Research: Converts user questions into tasks, gradually analyzes and reasons, invokes tools, checks the output results, and continues analyzing and invoking tools until the task is completed.

## Usage

### Windows Desktop Installation

If you are using a Windows system, you can directly [click here to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.1.0/Super.Agent.Party-Setup-0.1.0.exe) the Windows desktop version and follow the prompts to install.

### Docker Deployment

1. Obtain Docker Image (choose one):
- Pull the official image from DockerHub:
```shell
docker pull ailm32442/super-agent-party:latest
docker run -d -p 3456:3456 ailm32442/super-agent-party:latest
```

- Generate image from source code:
```shell
git clone https://github.com/heshengtao/super-agent-party.git
cd super-agent-party
docker pull python:3.12-slim 
docker build -t super-agent-party . 
docker run -d -p 3456:3456 super-agent-party:latest
```

2. Access at http://localhost:3456/

### Source Code Deployment

1. Download Repository:
```shell
git clone https://github.com/heshengtao/super-agent-party.git
cd super-agent-party
```

2. Install Dependencies (choose one):
- Windows: Click `install.bat` script
- MacOS/Linux: Click `install.sh` script
- Or manually execute the following commands to install dependencies:
```shell
python -m venv super
super\Scripts\activate # Windows
# source super/bin/activate # MacOS/Linux
pip install -r requirements.txt
npm install
```

## Configuration
1. Click on the System Settings in the left sidebar to set language options, system themes, and open this application in web mode.
2. Navigate to the Model Services Interface in the left sidebar to configure the cloud service providers you need to call, such as OpenAI, DeepSeek, etc. Select a model service provider and fill in the corresponding API key, then click the magnifying glass button at the top right corner to fetch the model list from that provider, choose your desired model to complete the configuration.
3. Access the Primary Model and Inference Model interfaces in the left sidebar for more precise model configurations. By default, it selects the first model from the model service provider. You can also choose other models. Note! The primary model needs to have tool invocation capabilities (most inference models do not have tool capabilities), while inference models need to have inference capabilities.
4. Go to the MCP Service Interface in the left sidebar to configure MCP services. Currently, two calling methods are supported: standard input/output and Server-Sent Events (SSE). The standard input/output method requires configuring various parameters of the MCP server; if errors occur, ensure that the local environment has the necessary package managers installed (e.g., uv, npm, etc.). The SSE method requires configuring the MCP server's address.
5. Click on the Internet Function Interface in the left sidebar to configure internet functions. Currently, it supports three search engines and two web-to-markdown tools: DuckDuckGo, SearXNG, Tavily, Jina, Crawl4AI. DuckDuckGo does not require configuration; SearXNG requires configuring the Docker image address; Tavily requires an API key; Jina does not require configuration; Crawl4AI requires configuring the Docker image address.
6. Access the Knowledge Base Interface in the left sidebar to configure the knowledge base. Before configuring the knowledge base, you need to complete the configuration of the word embedding model in the Model Services Interface.

## Disclaimer:
This open-source project and its contents (hereinafter referred to as the "Project") are provided for reference only and do not imply any explicit or implicit warranty. Project contributors are not responsible for the completeness, accuracy, reliability, or applicability of the Project. Any reliance on the content of the Project is undertaken at your own risk. Under no circumstances will the project contributors be liable for any indirect, special, or consequential damages arising out of the use of the Project content.

## Support:

### Join Community
If there are issues with the plugin or if you have other questions, feel free to join our community.

1. QQ Group: `931057213`

<div style="display: flex; justify-content: center;">
    <img src="doc/image/Q群.jpg" style="width: 48%;" />
</div>

2. WeChat Group: `we_glm` (Join the group after adding the assistant's WeChat)

3. Discord:[Discord Link](https://discord.gg/f2dsAKKr2V)

### Follow Us
1. To stay updated with the latest features of this project, follow the Bilibili account: [派酱](https://space.bilibili.com/26978344)

### Donate Support
If my work has brought you value, please consider buying me a coffee! Your support not only energizes the project but also warms the creator's heart.☕💖 Every cup counts!
<div style="display:flex; justify-content:space-between;">
    <img src="doc/image/zhifubao.jpg" style="width: 48%;" />
    <img src="doc/image/wechat.jpg" style="width: 48%;" />
</div> 