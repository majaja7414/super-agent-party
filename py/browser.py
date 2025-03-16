from langchain_openai import ChatOpenAI
from browser_use import Agent,Browser,BrowserConfig
import asyncio
from dotenv import load_dotenv
load_dotenv()
import sys
# 不同系统的浏览器路径
if sys.platform() == "win32":
    chrome_instance_path = "C:\Program Files\Google\Chrome\Application\chrome.exe"
elif sys.platform == "darwin":
    chrome_instance_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
else:
    chrome_instance_path = "/usr/bin/google-chrome-stable"
async def main():
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