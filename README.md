![image](static/source/agent_party.png)

<div align="center">
  <a href="./README_ZH.md"><img src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README.md"><img src="https://img.shields.io/badge/English-d9d9d9"></a>
</div>

## Introduction

🚀 Zero Intrusion · Minimalist Expansion · Empower LLM APIs with Enterprise-Grade Capabilities without modifying a single line of code, seamlessly add advanced features to your LLM interfaces, including knowledge base integration, real-time internet access, permanent memory, code execution tools, MCP, A2A, deep thinking control, in-depth research, visual understanding, image generation, custom tools, and more. Build a plug-and-play LLM enhancement middleware platform. At the same time, you can deploy your agent configuration to social platforms with just one click (official QQ bot is already supported).

![image](doc/image/demo.png)

## Why Choose Us?
- ✅ Efficient development: Supports streaming output, does not affect the original API's response speed, and no code changes are required
- ✅ Quick access: Avoids repeated access to multiple service providers for a single function, pre-configured with mainstream LLM manufacturer/intelligent body protocol adapters, compatible with OpenAI/Ollama/MCP/A2A, and experience the next-generation LLM middleware instantly
- ✅ High customization: Supports advanced agent features such as custom knowledge base, real-time internet access, permanent memory, code execution tools, MCP, A2A, deep thinking control, in-depth research, visual capabilities, image generation, and custom tools, allowing you to build a plug-and-play LLM enhancement middleware platform.  
Customized agents can be saved as snapshots for easy reuse in the future. The snapshot agents can be directly called using the OpenAI API.
- ✅ Data security: Supports local knowledge base and local model access, ensuring data is not leaked and enterprise data security is maintained. All files will be cached locally and will not be uploaded anywhere.
- ✅ Team collaboration: Supports team collaboration, multi-person sharing of knowledge base, model services, tools, MCP, A2A, and other resources, improving team collaboration efficiency. Chat records or files and images in the knowledge base are stored locally and can be used as a local file bed or image bed.
- ✅One-click deployment: Supports one-click deployment to social software, such as QQ, making it convenient for users to use the intelligent entity anytime and anywhere.

## Quick Start

### Windows Desktop Installation

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.2.0/Super-Agent-Party-Setup-0.2.0.exe)

⭐ Note! Choose to install only for the current user during installation, otherwise, administrator privileges will be required to start.

### MacOS Desktop Installation (beta test)

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.2.0/Super-Agent-Party-0.2.0-Mac.dmg)

⭐ Note! After downloading, drag the app file from the dmg file to the `/Applications` directory. Then open the Terminal and execute the following command, entering the root password when prompted, to remove the Quarantine attribute added due to being downloaded from the internet:

  ```shell
  sudo xattr -dr com.apple.quarantine /Applications/Super-Agent-Party.app
  ```

### Linux Desktop Installation

We provide two mainstream Linux installation package formats for your convenience in different scenarios.

#### 1. Install using `.AppImage` (Recommended)

`.AppImage` is a Linux application format that does not require installation and can be used immediately. Suitable for most Linux distributions.

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.2.0/Super-Agent-Party-0.2.0-Linux.AppImage)

#### 2. Install using `.deb` package (Suitable for Ubuntu/Debian systems)

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.2.0/Super-Agent-Party-0.2.0-Linux.deb)

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
  - **Search Engine**
    - [duckduckgo](https://duckduckgo.com/) (Completely free, but cannot be accessed in China's online environment)
    - [searxng](https://github.com/searxng/searxng) (can be locally deployed with Docker)
    - [tavily](https://tavily.com/)（需要申请api key）
    - [bing](https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/create-bing-search-service-resource) (need to apply for an API key)
    - [google](https://console.cloud.google.com/apis/credentials) (need to apply for an API key)
    - [Brave](https://brave.com/search/api/) (need to apply for an api key)
    - [exa](https://www.exa.app/) (need to apply for an API key)
    - [serper](https://serper.dev/) (need to apply for an API key)
    - [bochaai](https://bochaai.com/) (need to apply for an API key)
  - **Web scraping**
    - [jina](https://github.com/jina-ai/jina) (can be used for web scraping without an API key)
    - [crawl4ai](https://github.com/unclecode/crawl4ai) (can be locally deployed with Docker, used for web scraping).
3. [MCP](https://modelcontextprotocol.io/introduction) service, which allows large models to actively invoke the MCP service according to the needs of the query. Currently, it supports three invocation methods: standard input and output, server-sent events (SSE), streaming HTTP, and websocket.
4. [A2A](https://github.com/google/A2A) service, which allows large models to actively invoke the A2A service according to the needs of the query.
5. Deep thinking allows us to transplant the reasoning ability of the inference model into tools or multimodal models, so that the large model can use the inference model for reasoning analysis before tool invocation. For example: deepseek-V3 can be invoked by tools, but the inference model deepseek-R1 cannot be invoked by tools. In this case, we can transplant the reasoning ability of deepseek-R1 into deepseek-V3, so that deepseek-V3 can use deepseek-R1 for reasoning analysis before tool invocation.
6. Conduct in-depth research, convert users' problems into tasks, gradually analyze and infer, then invoke tools. After outputting the results, we will recheck whether the task is completed. If the task is not completed, we will continue to analyze and infer, then invoke tools until the task is completed.
7. Custom LLM tools can convert LLM interfaces into LLM tools, and any project that adapts to the Ollama format or the OpenAI interface can be used as a tool.
8. Visual caching, which allows you to configure a visual model separately for recognizing image information. The recognition results will be cached to save tokens. Configuring a visual model can enable some models without visual capabilities (for example, most inference models, etc.) to acquire visual capabilities.
9. Storage space management function, which allows you to view the files and pictures uploaded in chat in the storage space, and they are all cached locally, enhancing the software's function of image and file storage.
10. Added memory module, which can be viewed on the tool interface.
  - To add new memories, you need to add a word embedding model, and the agent will update the memory vector database in real time. Every time you answer, it will automatically search for relevant memories.
  - The memory module can be enabled and disabled in the memory configuration, and the number of results can be adjusted to allow the agent to see more or less relevant memories.
  - The memory configuration is divided into four sections: Auto-update Settings, Role Settings, Worldview Settings, and Random Settings.
11. Added a code execution tool, supporting both cloud-based and local solutions:
  - Cloud-based solution: Invoke the code sandbox from [e2b](https://e2b.dev/), an API key needs to be obtained.
  - Local solution: Use the code sandbox from [bytedance/SandboxFusion](https://github.com/bytedance/SandboxFusion), requires local deployment using Docker.
    ```shell
    docker run -it -p 8080:8080 volcengine/sandbox-fusion:server-20241204
    ```
    For users in mainland China, the following mirror is provided:
    ```shell
    docker run -it -p 8080:8080 vemlp-cn-beijing.cr.volces.com/preset-images/code-sandbox:server-20241204
    ```
12. Implemented widgets: current time, retrieving content from file/image URLs, pseudo reasoning, Pollinations image generation, enhanced rendering of LaTeX formulas, and language tone.
  - Current time: Get the current time.
  - Retrieve the content from the file/image URL: Retrieve the content from the file/image URL.
  - Pseudo-reasoning: Enabling a model that doesn't have reasoning capabilities to acquire them.
  - Pollinations image generation: Call the Pollinations image generation API to generate images. (No API key is needed.)
  - Enhanced latex formula rendering: Control the more stable output of latex formulas in large models.
  - Language tone: Control the more stable output language and tone of the large model.
13. Support for converting custom HTTP requests into agent tools has been added. You can now use any HTTP request as an agent tool, and you can add custom HTTP request tools in the Agent Toolkit interface.
14. Supported one-click deployment for the official QQ bot:  
  - This update implements a QQ bot that allows you to link your configured agent to the official QQ bot, with no risk of account suspension.  
  - The QQ bot supports custom message delimiters; the default delimiters are `["。", "\n", "？", "！"]`, which split the agent's streaming output into individual messages sent to QQ.  
  - The QQ bot supports both private and group chats.  
  - The QQ bot supports viewing text and image messages (images require the model to support vision or have a vision model enabled). You can also enable an image generation model to send images.  
  - Conversation round limit is adjustable, defaulting to 30 rounds. Older conversation records will be gradually discarded to prevent context overflow. You can configure the memory module to maintain fixed character settings and permanent memory.  
  - The QQ bot can return its thinking process and tool-calling process; this feature can be enabled or disabled via configuration.
15. For image generation models, in addition to the previously supported Pollinations, we now also support OpenAI interface models such as: `dall-e-2`, `dall-e-3`, and `gpt-image-1`. It can also integrate with other image generation models compatible with the OpenAI drawing API, for example: Kolors or FLUX on SiliconFlow.  
16. Provided a solution for when the robot sends out images and the return is in base64 format. You can add an image hosting service to the robot's general configuration. In the future, more image hosting options will be provided, currently only [easyimage2](https://github.com/icret/EasyImages2.0) is supported.  

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