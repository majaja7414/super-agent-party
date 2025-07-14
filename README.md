![image](static/source/agent_party.png)

<div align="center">
  <a href="./README_ZH.md"><img src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README.md"><img src="https://img.shields.io/badge/English-d9d9d9"></a>
</div>

<div align="center">
  <a href="https://space.bilibili.com/26978344">B站</a> ·
  <a href="https://www.youtube.com/@LLM-party">youtube</a> ·
  <a href="https://gcnij7egmcww.feishu.cn/wiki/DPRKwdetCiYBhPkPpXWcugujnRc">中文文档</a> ·
  <a href="https://temporal-lantern-7e8.notion.site/super-agent-party-211b2b2cb6f180c899d1c27a98c4965d">English doc</a> 
</div>

## Introduction

### 🚀 **A 3D AI desktop pet with endless possibilities!**  

- ✅Empower LLM APIs with enterprise-level capabilities without modifying a single line of code. Seamlessly enhance your LLM interfaces with advanced features such as knowledge bases, real-time internet connectivity, permanent memory, code execution tools, deep thought control, in-depth research, visual capabilities, drawing abilities, auditory functions, speech capabilities, and custom tools—creating a plug-and-play LLM enhancement platform.  
- ✅At the same time, deploy your agent configurations to any frontend with just one click (already implemented for classic chat interfaces, QQ official bots, and VRM desktop pets).  
- ✅You can also use other agents, smart tools, and intelligent workflows as tools for agent-party agents (already implemented for ComfyUI, MCP, and A2A).  
- ✅Multi-platform support: Windows, macOS, Linux, Docker, Web.

![image](doc/image/demo.png)

## Software Screenshots

### Multi-Vendor Support: Supports both locally deployed engines and cloud vendor interfaces  
![image](doc/image/model.jpeg)  

### Massive tools: support asynchronous calls without blocking agent replies
![image](doc/image/tool.jpeg)

### VRM Desktop Pet: Supports uploading custom VRM models to create a personalized desktop pet  
![image](doc/image/vrmbot.jpeg)  

### Memory Module: Supports permanent memory and lorebook world-building  
![image](doc/image/memory.jpeg)  

### QQ Bot: Supports one-click deployment to the official QQ bot, enabling users to access the agent anytime, anywhere  
![image](doc/image/qqbot.jpeg)  

### Developer-Friendly: Open OpenAI API and MCP interfaces, allowing external agent integration  
![image](doc/image/API.jpeg)  

### ComfyUI Integration: Converts ComfyUI workflows into agent tools with multi-ComfyUI server load balancing  
![image](doc/image/comfyui.jpeg)

## Quick Start

### Windows Desktop Installation

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.2.3/Super-Agent-Party-Setup-0.2.2.exe)

⭐ Note! Choose to install only for the current user during installation, otherwise, administrator privileges will be required to start.

### MacOS Desktop Installation (beta test)

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.2.3/Super-Agent-Party-0.2.2-Mac.dmg)

⭐ Note! After downloading, drag the app file from the dmg file to the `/Applications` directory. Then open the Terminal and execute the following command, entering the root password when prompted, to remove the Quarantine attribute added due to being downloaded from the internet:

  ```shell
  sudo xattr -dr com.apple.quarantine /Applications/Super-Agent-Party.app
  ```

### Linux Desktop Installation

We provide two mainstream Linux installation package formats for your convenience in different scenarios.

#### 1. Install using `.AppImage` (Recommended)

`.AppImage` is a Linux application format that does not require installation and can be used immediately. Suitable for most Linux distributions.

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.2.3/Super-Agent-Party-0.2.2-Linux.AppImage)

#### 2. Install using `.deb` package (Suitable for Ubuntu/Debian systems)

  👉 [Click to download](https://github.com/heshengtao/super-agent-party/releases/download/v0.2.3/Super-Agent-Party-0.2.2-Linux.deb)

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

Please refer to the following document for the main functions:
  - 👉 [Chinese document](https://gcnij7egmcww.feishu.cn/wiki/DPRKwdetCiYBhPkPpXWcugujnRc)
  - 👉 [English document](https://temporal-lantern-7e8.notion.site/super-agent-party-211b2b2cb6f180c899d1c27a98c4965d)

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