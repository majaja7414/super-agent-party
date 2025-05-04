## Complete Installation and Usage Guide

### Windows Desktop Installation

If you are using a Windows system, you can directly [download](https://github.com/heshengtao/super-agent-party/releases/download/v0.1.1/Super.Agent.Party-Setup-0.1.1.exe) the Windows desktop version and follow the prompts to install.

### Docker Deployment (Recommended)

1. Get the Docker image (choose one of the following options):
- Pull the official image from Docker Hub:
```shell
docker pull ailm32442/super-agent-party:latest
docker run -d -p 3456:3456 ailm32442/super-agent-party:latest
```

- Build the image from the source code:
```shell
git clone https://github.com/heshengtao/super-agent-party.git
cd super-agent-party
docker pull python:3.12-slim 
docker build -t super-agent-party . 
docker run -d -p 3456:3456 super-agent-party:latest
```

2. Access http://localhost:3456/

### Source Code Deployment

1. Download the repository:
```shell
git clone https://github.com/heshengtao/super-agent-party.git
cd super-agent-party
```

2. Install dependencies (choose one of the following options):
- Windows: Click the `install.bat` script
- macOS/Linux: Click the `install.sh` script
- Or use pip and npm to install dependencies:
```shell
python -m venv .venv
.venv\Scripts\activate # windows
# source .venv/bin/activate # macos/linux
pip install -r requirements.txt
npm install
```
- Or use uv and npm to install dependencies:
```shell
uv sync
npm install
```

3. Start the service (choose one of the following options):
- Windows: Click the `start_with_dev.bat` script
- macOS/Linux: Click the `start_with_dev.sh` script
- Or manually execute the following command to start the service:
```shell
.venv\Scripts\activate # windows
# source .venv/bin/activate # macos/linux
npm run dev
```

## How to Use
1. Click on the system settings in the left sidebar to set language options and system themes.
2. Click on the tool interface in the left sidebar to configure some small tools, including the current time, in-depth research, and pseudo-reasoning abilities. If you want to fix the language used by the intelligent body, you can configure it here.
3. Click on the model service interface in the left sidebar to configure the cloud service provider you need to call, such as OpenAI or DeepSeek. Select the model service provider and fill in the corresponding API key, then click the magnifying glass button in the upper right corner to get the model list of the service provider. Select the model you need to complete the configuration.
4. Click on the intelligent body interface in the left sidebar to configure the system prompt words of the intelligent body. The system prompt words determine the behavior of the intelligent body, and you can modify them according to your needs. When you create it, the intelligent body will snapshot all your current configurations, including model services, knowledge bases, internet functionality, MCP services, tools, and system prompt words.
5. Click on the main model and reasoning model interfaces in the left sidebar to configure your model more accurately. By default, the first model of the model service provider will be selected, but you can also choose other models. Note that the main model needs to have tool calling ability (most reasoning models do not have tool capabilities), and the reasoning model needs to have reasoning ability.
6. Click on the MCP service interface in the left sidebar to configure the MCP service. Currently, two calling methods are supported: standard input/output and server-sent events (SSE). The standard input/output method requires configuring the MCP server's parameters, and if an error occurs, please note whether the corresponding package manager (such as uv or npm) is installed locally. The SSE method requires configuring the MCP server's address.
7. Click on the internet functionality interface in the left sidebar to configure internet functionality. Currently, three search engines and two web-to-markdown tools are supported: DuckDuckGo, Searxng, Tavily, Jina, and Crawl4ai. DuckDuckGo does not require configuration, Searxng requires configuring the Docker image address, Tavily requires configuring the API key, Jina does not require configuration, and Crawl4ai requires configuring the Docker image address.
8. Click on the knowledge base interface in the left sidebar to configure the knowledge base. Before configuring the knowledge base, you need to complete the configuration of the word embedding model in the model service interface.
9. Click on the calling method interface in the left sidebar, and you can use the OpenAI format to call the intelligent body created by this application. If the model name is `super-model`, it will call the currently configured intelligent body. If the model name is the ID of the intelligent body you created in the intelligent body interface, it will call the intelligent body you created.
10. Click on the A2A service interface in the left sidebar to configure the A2A service. After configuring the A2A server address, you can use it.
11. Click on the LLM tool interface in the left sidebar. Currently, it supports other OLLAMA formats or OpenAI formats for custom intelligent body access as a tool.