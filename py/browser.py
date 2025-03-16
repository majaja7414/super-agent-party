import subprocess
import os
from langchain_openai import ChatOpenAI
from browser_use import Agent,Browser,BrowserConfig
import asyncio
from dotenv import load_dotenv
load_dotenv()
import sys
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
    
async def main():
    chrome_instance_path = get_chrome_path()
    agent = Agent(
        task="比较一下GPT4o和deepseek V3的具体价格",
        browser=Browser(config=BrowserConfig(chrome_instance_path=chrome_instance_path)),
        llm=ChatOpenAI(model="gpt-4o"),
    )
    await agent.run()

if __name__ == "__main__":
    # 运行主函数，并且同步打印最新的日志到控制台
    asyncio.run(main())
    print("done")