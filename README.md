![image](static/source/agent_party.png)

<div align="center">
  <a href="./README_ZH.md"><img src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README.md"><img src="https://img.shields.io/badge/English-d9d9d9"></a>
</div>

## Introduction

🚀 Zero-invasive, ultra-simple extension, and empower LLM API with enterprise-level capabilities without modifying a single line of code. Seamlessly attach knowledge bases, real-time internet access, permanent memory, MCP, A2A, deep thinking control, in-depth research, and custom tools to your LLM interface, creating a plug-and-play LLM enhancement platform.

![image](doc/image/demo.png)

## Why Choose Us?
- ✅ Efficient development: Supports streaming output, does not affect the original API's response speed, and no code changes are required
- ✅ Quick access: Avoids repeated access to multiple service providers for a single function, pre-configured with mainstream LLM manufacturer/intelligent body protocol adapters, compatible with OpenAI/Ollama/MCP/A2A, and experience the next-generation LLM middleware instantly
- ✅ High customization: Supports custom knowledge base, real-time networking, MCP, A2A, deep thinking control, in-depth research, custom tools, and other advanced intelligent body functions, creating a pluggable LLM enhancement platform. Customized intelligent bodies can be saved as snapshots for convenient use next time. Snapshotted intelligent bodies can be called directly using the OpenAI API.
- ✅ Data security: Supports local knowledge base and local model access, ensuring data is not leaked and enterprise data security is maintained. All files will be cached locally and will not be uploaded anywhere.
- ✅ Team collaboration: Supports team collaboration, multi-person sharing of knowledge base, model services, tools, MCP, A2A, and other resources, improving team collaboration efficiency. Chat records or files and images in the knowledge base are stored locally and can be used as a local file bed or image bed.

## Quick Start

### Windows Desktop Installation

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.1.5/Super-Agent-Party-Setup-0.1.5.exe)

⭐ Note! Choose to install only for the current user during installation, otherwise, administrator privileges will be required to start.

### Linux Desktop Installation

We provide two mainstream Linux installation package formats for your convenience in different scenarios.

#### 1. Install using `.AppImage` (Recommended)

`.AppImage` is a Linux application format that does not require installation and can be used immediately. Suitable for most Linux distributions.

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.1.5/Super-Agent-Party-0.1.5-Linux.AppImage)

#### 2. Install using `.deb` package (Suitable for Ubuntu/Debian systems)

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.1.5/Super-Agent-Party-0.1.5-Linux.deb)

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

- Web or docker: Access http://localhost:3456/ after startup.

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

- MCP call: After starting, you can invoke the local MCP service by writing the following content in the configuration file:

  ```json
  {
    "mcpServers": {
      "super-agent-party": {
        "url": "http://127.0.0.1:3456/mcp",
      }
    }
  }
  ```

## Features

0. Switch from the sidebar to the call method to see how to invoke Agent Party through OpenAI API, MCP server, docker, and the web interface. The OpenAI interface has added the following switch parameters:
  - enable_thinking: The default is False, whether to enable the thinking mode.
  - enable_deep_research: The default is False, whether to enable the deep research mode.
  - enable_web_search: The default is False, whether to enable web search.
1. Knowledge base, allowing the large model to answer questions based on the information in the knowledge base. And it supports the following functions:
  - If there are multiple knowledge bases, the model will actively query the corresponding knowledge base according to the question requirements.
  - You can choose the timing of retrieval, and you can choose to actively retrieve or passively retrieve the knowledge base.
  - We have supported the rerank model, which can improve the retrieval effect of the knowledge base.
  - Support mixed search function, which allows you to choose the proportion between keyword search and semantic search.
2. Networking function, which allows the large model to actively query information online according to the needs of the question. Currently, it supports:
  - [duckduckgo](https://duckduckgo.com/) (Completely free, but cannot be accessed in China's online environment)
  - [searxng](https://github.com/searxng/searxng) (can be locally deployed with Docker)
  - [tavily](https://tavily.com/)（需要申请api key）
  - [jina](https://github.com/jina-ai/jina) (can be used for web scraping without an API key)
  - [crawl4ai](https://github.com/unclecode/crawl4ai) (can be locally deployed with Docker, and is used for web scraping).
3. [MCP](https://modelcontextprotocol.io/introduction) service, which allows large models to actively invoke the MCP service according to the needs of the query. Currently, it supports three invocation methods: standard input and output, server-sent events (SSE), streaming HTTP, and websocket.
4. [A2A](https://github.com/google/A2A) service, which allows large models to actively invoke the A2A service according to the needs of the query.
5. Deep thinking allows us to transplant the reasoning ability of the inference model into tools or multimodal models, so that the large model can use the inference model for reasoning analysis before tool invocation. For example: deepseek-V3 can be invoked by tools, but the inference model deepseek-R1 cannot be invoked by tools. In this case, we can transplant the reasoning ability of deepseek-R1 into deepseek-V3, so that deepseek-V3 can use deepseek-R1 for reasoning analysis before tool invocation.
6. Conduct in-depth research, convert users' problems into tasks, gradually analyze and infer, then invoke tools. After outputting the results, we will recheck whether the task is completed. If the task is not completed, we will continue to analyze and infer, then invoke tools until the task is completed.
7. Custom LLM tools can convert LLM interfaces into LLM tools, and any project that adapts to the Ollama format or the OpenAI interface can be used as a tool.
8. Visual caching, which allows you to configure a visual model separately for recognizing image information. The recognition results will be cached to save tokens. Configuring a visual model can enable some models without visual capabilities (for example, most inference models, etc.) to acquire visual capabilities.
9. Storage space management function, which allows you to view the files and pictures uploaded in chat in the storage space, and they are all cached locally, enhancing the software's function of image and file storage.
10. Added memory module, which can be viewed on the tool interface.
- To add new memories, you need to add a word embedding model, and the agent will update the memory vector database in real time. Every time you answer, it will automatically search for relevant memories.
The memory module can be enabled and disabled in the memory configuration, and the number of results can be adjusted to allow the agent to see more or less relevant memories.
11. Implemented widgets: current time, retrieving content from file/image URLs, pseudo reasoning, Pollinations image generation, enhanced rendering of LaTeX formulas, and language tone.
  - Current time: Get the current time.
  - Retrieve the content from the file/image URL: Retrieve the content from the file/image URL.
  - Pseudo-reasoning: Enabling a model that doesn't have reasoning capabilities to acquire them.
  - Pollinations image generation: Call the Pollinations image generation API to generate images. (No API key is needed.)
  - Enhanced latex formula rendering: Control the more stable output of latex formulas in large models.
  - Language tone: Control the more stable output language and tone of the large model.

## Disclaimer:
This open-source project and its content (hereinafter referred to as the "project") are for reference only and do not imply any explicit or implicit warranties. The project contributors do not assume any responsibility for the completeness, accuracy, reliability, or applicability of the project. Any behavior that relies on the project content shall be at the user's own risk. In any case, the project contributors shall not be liable for any indirect, special, or incidental losses or damages arising from the use of the project content.

## License Agreement

This project uses a dual licensing model:
1. By default, this project follows the **GNU Affero General Public License v3.0 (AGPLv3)** license agreement
2. If you need to use this project for closed-source commercial purposes, you must obtain a commercial license from the project administrator

Using this project for closed-source commercial purposes without written authorization is considered a violation of this agreement. The complete text of AGPLv3 can be found in the LICENSE file in the project root directory or at [gnu.org/licenses](https://www.gnu.org/licenses/agpl-3.0.html).

## Support:

### Follow us
<a href="https://space.bilibili.com/26978344">
  <img src="doc/image/B.png" width="100" height="100" style="border-radius: 80%; overflow: hidden;" alt="octocat"/>
</a>
<a href="https://www.youtube.com/@LLM-party">
  <img src="doc/image/YT.png" width="100" height="100" style="border-radius: 80%; overflow: hidden;" alt="octocat"/>
</a>

### Join the Community
If you have any questions or issues with the project, you are welcome to join our community.

1. QQ Group: `931057213`

<div style="display: flex; justify-content: center;">
    <img src="doc/image/Q群.jpg" style="width: 48%;" />
</div>

2. WeChat Group: `we_glm` (add the assistant's WeChat and join the group)

3. Discord: [Discord link](https://discord.gg/f2dsAKKr2V)

### Donate
If my work has brought value to you, please consider buying me a cup of coffee! Your support not only injects vitality into the project but also warms the creator's heart. ☕💖 Every cup counts!
<div style="display:flex; justify-content:space-between;">
    <img src="doc/image/zhifubao.jpg" style="width: 48%;" />
    <img src="doc/image/wechat.jpg" style="width: 48%;" />
</div>