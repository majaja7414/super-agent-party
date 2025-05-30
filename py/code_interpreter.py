from e2b_code_interpreter import Sandbox
import asyncio
from concurrent.futures import ThreadPoolExecutor
from py.get_setting import load_settings

async def e2b_code_async(code: str, language: str = "Python") -> str:
    settings = await load_settings()
    e2b_api_key = settings["codeSettings"]["e2b_api_key"]
    executor = ThreadPoolExecutor()
    def run_in_sandbox():
        with Sandbox(api_key=e2b_api_key) as sandbox:
            execution = sandbox.run_code(code,language=language)
            return execution.logs

    # 使用线程池执行同步代码，防止阻塞事件循环
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, run_in_sandbox)
    return str(result)

e2b_code_tool = {
    "type": "function",
    "function": {
        "name": "e2b_code_async",
        "description": "执行Python代码",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "需要执行的代码，例如：print('Hello, World!')，不要包含markdown的代码块标记！只有输入可运行的代码字符串。工具只会返回stdout和stderr。请将你要查看的答案放在print()中，不要放在其他地方。",
                },
                "language": {
                    "type": "string",
                    "description": "代码语言，目前仅支持Python/JavaScript/Java/Bash/R，默认为Python",
                }
            },
            "required": ["code"],
        },
    },
}