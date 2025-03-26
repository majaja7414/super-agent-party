import json
import subprocess
import os
from langchain_openai import ChatOpenAI
from browser_use import Agent,Browser,BrowserConfig
import asyncio
from dotenv import load_dotenv
load_dotenv()
import sys
SETTINGS_FILE = 'config/settings.json'
SETTINGS_TEMPLATE_FILE = 'config/settings_template.json'
def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # 创建config文件夹
        os.makedirs('config', exist_ok=True)
        # 加载settings_template.json文件
        with open(SETTINGS_TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            default_settings = json.load(f)
        # 创建settings.json文件，并写入默认设置
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, ensure_ascii=False, indent=2)
        return default_settings

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
        raise Exception("未找到谷歌浏览器安装路径，请手动指定路径")
    
async def browser_task(task: str):
    chrome_instance_path = get_chrome_path()
    settings = load_settings()
    model = settings['browser']['model'] or 'gpt-4o-mini'
    api_key = settings['browser']['api_key'] or ''
    base_url = settings['browser']['base_url'] or 'https://api.openai.com/v1'
    agent = Agent(
        task=task,
        browser=Browser(config=BrowserConfig(chrome_instance_path=chrome_instance_path)),
        llm=ChatOpenAI(model=model,api_key=api_key,base_url=base_url),
    )
    result = await agent.run()
    return result

if __name__ == "__main__":
    asyncio.run(browser_task())