![image](static/source/agent_party.png)

<div align="center">
  <a href="./README_ZH.md"><img src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README.md"><img src="https://img.shields.io/badge/English-d9d9d9"></a>
</div>

## Introduction

🚀 Zero-invasive, ultra-simple extension, and empower LLM API with enterprise-level capabilities without modifying a single line of code. Seamlessly attach knowledge bases, real-time internet access, MCP, A2A, deep thinking control, in-depth research, and custom tools to your LLM interface, creating a plug-and-play LLM enhancement platform.

![image](doc/image/demo.png)

## Why Choose Us?
- ✅ Efficient development: Supports streaming output, does not affect the original API's response speed, and no code changes are required
- ✅ Quick access: Avoids repeated access to multiple service providers for a single function, pre-configured with mainstream LLM manufacturer/intelligent body protocol adapters, compatible with OpenAI/Ollama/MCP/A2A, and experience the next-generation LLM middleware instantly
- ✅ High customization: Supports custom knowledge base, real-time networking, MCP, A2A, deep thinking control, in-depth research, custom tools, and other advanced intelligent body functions, creating a pluggable LLM enhancement platform. Customized intelligent bodies can be saved as snapshots for convenient use next time. Snapshotted intelligent bodies can be called directly using the OpenAI API.
- ✅ Data security: Supports local knowledge base and local model access, ensuring data is not leaked and enterprise data security is maintained. All files will be cached locally and will not be uploaded anywhere.
- ✅ Team collaboration: Supports team collaboration, multi-person sharing of knowledge base, model services, tools, MCP, A2A, and other resources, improving team collaboration efficiency. Chat records or files and images in the knowledge base are stored locally and can be used as a local file bed or image bed.

## Installation Method

### Windows Desktop Installation

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.1.3/Super-Agent-Party-Setup-0.1.3.exe)

⭐ Note! Choose to install only for the current user during installation, otherwise, administrator privileges will be required to start.

### Linux Desktop Installation

We provide two mainstream Linux installation package formats for your convenience in different scenarios.

#### 1. Install using `.AppImage` (Recommended)

`.AppImage` is a Linux application format that does not require installation and can be used immediately. Suitable for most Linux distributions.

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.1.3/Super-Agent-Party-0.1.3-Linux.AppImage)

#### 2. Install using `.deb` package (Suitable for Ubuntu/Debian systems)

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.1.3/Super-Agent-Party-0.1.3-Linux.deb)

### Docker Deployment (Recommended)

- Two commands to install this project:
  ```shell
  docker pull ailm32442/super-agent-party:latest
  docker run -d -p 3456:3456 -v ./super-agent-data:/app/data ailm32442/super-agent-party:latest
  ```

- ⭐Note! `./super-agent-data` can be replaced with any local folder, after Docker starts, all data will be cached in this local folder and will not be uploaded anywhere.

- Plug and play: access http://localhost:3456/

### Source Code Deployment

- Windows:
  ```shell
  git clone https://github.com/heshengtao/super-agent-party.git
  cd super-agent-party
  uv sync
  npm install
  start_with_dev.bat
  ```

- Linux or Mac:
  ```shell
  git clone https://github.com/heshengtao/super-agent-party.git
  cd super-agent-party
  uv sync
  npm install
  chmod +x start_with_dev.sh
  ./start_with_dev.sh
  ```

For detailed deployment methods, please refer to the [Deployment and Usage Documentation](doc/install_config_ZH.md)

## Usage

- Desktop: Click the desktop icon to use immediately.

- Web: Access http://localhost:3456/ after startup.

- API call: Developer-friendly, perfectly compatible with OpenAI format, can output in real-time, and does not affect the original API's response speed. No need to modify the calling code:

  ```python
  from openai import OpenAI
  client = OpenAI(
    api_key="super-secret-key",
    base_url="http://localhost:3456/v1"
  )
  response = client.chat.completions.create(
    model="super-model",
    messages=[
        {"role": "user", "content": "What is Super Agent Party?"}
    ]
  )
  print(response.choices[0].message.content)
  ```

## Recently updated

The following content has been merged into the main branch, but has not yet been included in the release version.

1. Add storage space management function, which allows you to view the files and images uploaded in the chat in the storage space and save them locally, thus enhancing the software's image and document storage capabilities.
2. Adding a file/image link viewing tool allows the large model to retrieve file/image information based on the URL provided by the user.
3. The agent party's configured intelligent entities can now be invoked using MCP.
4. The openai interface has added the following switch parameters:
- enable_thinking: Default to False, whether to enable the thinking mode.
- enable_deep_research: Defaults to False, whether to enable the deep research mode.
- enable_web_search: Defaulted to False, whether to enable web search.
5. The knowledge base supports the rerank model, which can improve the retrieval results of the knowledge base.
The MCP tool for accessing intelligent entities already supports streaming HTTP.

## Function Introduction

0. Switch to the calling method from the sidebar to view how to call Agent Party in OpenAI API or web mode.
1. Knowledge base, allowing large models to answer based on information in the knowledge base. If there are multiple knowledge bases, the model will actively query the corresponding knowledge base according to the question.
2. Internet access function, allowing large models to actively query information on the internet according to the question. Currently supported:
- [duckduckgo](https://duckduckgo.com/) (completely free, inaccessible in Chinese network environment)
- [searxng](https://github.com/searxng/searxng) (can be deployed locally with Docker)
- [tavily](https://tavily.com/) (requires applying for an API key)
- [jina](https://github.com/jina-ai/jina) (can be used without an API key for web scraping)
- [crawl4ai](https://github.com/unclecode/crawl4ai) (can be deployed locally with Docker for web scraping).
3. [MCP](https://modelcontextprotocol.io/introduction) service, allowing large models to actively call MCP services according to the question. Currently supports three calling methods: standard input/output, server-sent events (SSE),Streaming HTTP, and WebSocket.
4. [A2A](https://github.com/google/A2A) service, allowing large models to actively call A2A services according to the question.
5. Deep thinking, which can transplant the reasoning ability of reasoning models to tool calls or multimodal models, allowing large models to use reasoning models for reasoning analysis before tool calls. For example, deepseek-V3 can be called by tools, but the reasoning model deepseek-R1 cannot be called by tools. Therefore, the reasoning ability of deepseek-R1 can be transplanted to deepseek-V3, allowing deepseek-V3 to use deepseek-R1 for reasoning analysis before tool calls.
6. In-depth research, which converts user questions into tasks, analyzes and reasons step by step, calls tools, and outputs results. If the task is not completed, it will continue to analyze and reason, and call tools until the task is completed.
7. Custom tools, any project that adapts to Ollama format or OpenAI interface can be used as a tool.
8. Visual caching, which can be configured separately with a visual model to recognize image information, and the recognition results will be cached to save tokens. Configuring a visual model can enable some models without visual capabilities (such as most inference models) to acquire visual capabilities.

## Disclaimer:
This open-source project and its content (hereinafter referred to as the "project") are for reference only and do not imply any explicit or implicit warranties. The project contributors do not assume any responsibility for the completeness, accuracy, reliability, or applicability of the project. Any behavior that relies on the project content shall be at the user's own risk. In any case, the project contributors shall not be liable for any indirect, special, or incidental losses or damages arising from the use of the project content.

## License Agreement

This project uses a dual licensing model:
1. By default, this project follows the **GNU Affero General Public License v3.0 (AGPLv3)** license agreement
2. If you need to use this project for closed-source commercial purposes, you must obtain a commercial license from the project administrator

Using this project for closed-source commercial purposes without written authorization is considered a violation of this agreement. The complete text of AGPLv3 can be found in the LICENSE file in the project root directory or at [gnu.org/licenses](https://www.gnu.org/licenses/agpl-3.0.html).

## Support:

### Join the Community
If you have any questions or issues with the project, you are welcome to join our community.

1. QQ Group: `931057213`

<div style="display: flex; justify-content: center;">
    <img src="doc/image/Q群.jpg" style="width: 48%;" />
</div>

2. WeChat Group: `we_glm` (add the assistant's WeChat and join the group)

3. Discord: [Discord link](https://discord.gg/f2dsAKKr2V)

### Follow Us
1. If you want to keep up with the latest features of this project, please follow the Bilibili account: [Pai Jiang](https://space.bilibili.com/26978344)

### Donate
If my work has brought value to you, please consider buying me a cup of coffee! Your support not only injects vitality into the project but also warms the creator's heart. ☕💖 Every cup counts!
<div style="display:flex; justify-content:space-between;">
    <img src="doc/image/zhifubao.jpg" style="width: 48%;" />
    <img src="doc/image/wechat.jpg" style="width: 48%;" />
</div>