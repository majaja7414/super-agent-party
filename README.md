![image](static/source/agent_party.png)

<div align="center">
  <a href="./README_ZH.md"><img src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README.md"><img src="https://img.shields.io/badge/English-d9d9d9"></a>
</div>

## Introduction

If you want to transform a large model into an intelligent agent that can access knowledge bases, connect to the internet, utilize MCP services, perform deep thinking and in-depth research, and also be usable via OpenAI API calls or directly through web and desktop applications, then this project is for you.

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