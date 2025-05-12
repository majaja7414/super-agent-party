## Complete Installation and Usage Guide

### Windows Desktop Installation

If you are using a Windows system, you can directly [download](https://github.com/heshengtao/super-agent-party/releases/download/v0.1.1/Super.Agent.Party-Setup-0.1.1.exe) the Windows desktop version and follow the prompts to install.

### Docker Deployment (Recommended)

1. Get the Docker image (choose one of the following options):
- Pull the official image from Docker Hub:
```shell
docker pull ailm32442/super-agent-party:latest
docker run -d -p 3456:3456 -v ./super-agent-data:/app/data ailm32442/super-agent-party:latest
```

- Build the image from the source code:
```shell
git clone https://github.com/heshengtao/super-agent-party.git
cd super-agent-party
docker pull python:3.12-slim 
docker build -t super-agent-party . 
docker run -d -p 3456:3456 -v ./super-agent-data:/app/data super-agent-party:latest
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
1. Clicking the system settings on the left sidebar allows you to set language options and system themes.
2. Clicking the model configuration - model service interface on the left sidebar configures the cloud service provider you need to call, such as openai, deepseek, etc. Select the model service provider and fill in the corresponding API key, then click the magnifying glass button in the upper right corner to get the model list of the service provider, select the model you need, and complete the configuration.
3. Clicking the model configuration - main model and model configuration - inference model interface on the left sidebar allows you to configure your model more accurately. By default, the first model of the model service provider is selected, and you can also choose other models. Note! The main model needs to have tool calling ability (most inference models do not have tool ability), and the inference model needs to have inference ability.
4. Clicking the model configuration - visual model interface on the left sidebar configures the visual model, allowing models without visual ability to have visual ability and caching sent images to save tokens.
5. Clicking the intelligent body suite interface on the left sidebar, then selecting the following secondary interfaces:
    - Intelligent body interface, which can configure the system prompt words of the intelligent body. The system prompt words determine the behavior of the intelligent body, and you can modify them according to your needs. When you create it, the intelligent body will snapshot all your current configurations, including model services, knowledge bases, internet functions, MCP services, tools, and system prompt words.
    - MCP service interface, which can configure MCP services. Currently, two calling methods are supported: standard input/output and server-sent events (SSE). The standard input/output method requires configuring various parameters of the MCP server. If an error occurs, please note whether the corresponding package manager (such as uv, npm, etc.) is installed locally. The SSE method requires configuring the address of the MCP server.
    - A2A service interface, which can configure A2A services. After configuring the address of the A2A server, you can use it.
    - LLM tool interface, currently supports other ollama formats or openai formats for custom intelligent body access and uses them as tools.
6. Clicking the tool suite - tool interface on the left sidebar can configure some small tools, including current time, in-depth research, and pseudo-inference ability. If you want to fix the language used by the intelligent body, you can configure it here.
7. Clicking the tool suite - internet function interface on the left sidebar can configure internet functions. Currently, three search engines and two web-to-markdown tools are supported: duckduckgo, searxng, tavily, jina, and crawl4ai. Duckduckgo does not require configuration, searxng requires configuring the docker image address, tavily requires configuring the API key, jina does not require configuration, and crawl4ai requires configuring the docker image address.
8. Clicking the tool suite - knowledge base interface on the left sidebar can configure the knowledge base. Before configuring the knowledge base, you need to complete the configuration of the word embedding model in the model service interface on the left sidebar.
9. Clicking the calling method interface on the left sidebar allows you to call the intelligent body created by this application in openai format. If the model name is `super-model`, it will call the currently configured intelligent body. If the model name is the intelligent body ID or intelligent body name you created in the intelligent body interface, it will call the intelligent body you created.