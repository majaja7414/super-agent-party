import json
import subprocess
import os
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from browser_use import Agent,Browser,BrowserConfig
import asyncio
from dotenv import load_dotenv
load_dotenv()
import sys
from py.get_setting import load_settings

def get_chrome_path():
    chrome_path = None
    if sys.platform.startswith('win'):
        # Windows系统
        try:
            # 通过注册表查找安装路径
            import winreg
            reg_path = r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe'
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                chrome_path = winreg.QueryValue(key, None)
        except Exception:
            # 注册表查找失败时尝试默认路径
            default_paths = [
                os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
                os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
                os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe')
            ]
            for path in default_paths:
                if os.path.exists(path):
                    chrome_path = path
                    break
    elif sys.platform.startswith('darwin'):
        # macOS系统
        default_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        if os.path.exists(default_path):
            chrome_path = default_path
    elif sys.platform.startswith('linux'):
        # Linux系统
        try:
            chrome_path = subprocess.check_output(['which', 'google-chrome']).decode().strip()
        except subprocess.CalledProcessError:
            try:
                chrome_path = subprocess.check_output(['which', 'chromium-browser']).decode().strip()
            except subprocess.CalledProcessError:
                pass
    if chrome_path and os.path.isfile(chrome_path):
        return chrome_path
    else:
        raise None
    
async def browser_task(task: str):
    settings = load_settings()
    if not settings['browser']['usePlaywright']:
        if settings['browser']['chrome_path']:
            chrome_instance_path = settings['browser']['chrome_path']
        else:
            chrome_instance_path = get_chrome_path()
    else:
        chrome_instance_path = None
    model = settings['browser']['model'] or 'gpt-4o-mini'
    api_key = settings['browser']['api_key'] or ''
    base_url = settings['browser']['base_url'] or 'https://api.openai.com/v1'
    cur_vendor = None
    for provider in settings["modelProviders"]:
        if provider["id"] == settings['browser']['selectedProvider']:
            cur_vendor = provider["vendor"]
            break
    if cur_vendor == "anthropic":
        llm=ChatAnthropic(model=model,api_key=api_key,base_url=base_url)
    else:
        llm=ChatOpenAI(model=model,api_key=api_key,base_url=base_url)
    if chrome_instance_path:
        agent = Agent(
            task=task,
            browser=Browser(config=BrowserConfig(chrome_instance_path=chrome_instance_path)),
            llm=llm,
        )
    else:
        agent = Agent(
            task=task,
            browser=Browser(),
            llm=llm,
        )
    result = await agent.run()
    return result

browser_task_tool = {
    "type": "function",
    "function": {
        "name": "browser_task",
        "description": "用浏览器自动执行你给出的任务的工具，输入任务描述，返回任务执行结果",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "要执行的任务描述"},
            },
            "required": ["task"],
        },
    },
}

if __name__ == "__main__":
    asyncio.run(browser_task("给出deepseekv3和GPT 4o哪个价格的价格对比表"))