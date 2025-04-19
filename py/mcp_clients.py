import json
import asyncio
import locale
import logging
import os
from typing import Dict, List, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
import shutil
import nest_asyncio
from dotenv import load_dotenv
from contextlib import AsyncExitStack

load_dotenv() 
nest_asyncio.apply()

def get_command_path(command_name, default_command='uv'):
    """Find the full path of a command on the system PATH."""
    command_path = shutil.which(command_name)
    if command_path is None:
        print(f"Command '{command_name}' not found in PATH. Using default: {default_command}")
        command_path = shutil.which(default_command)
        if command_path is None:
            raise FileNotFoundError(f"Neither '{command_name}' nor '{default_command}' were found in PATH.")
    return command_path

class McpClient:
    def __init__(self):
        self.session: ClientSession = None
        self.exit_stack = AsyncExitStack()
        self.server_name = None
        self.server_config = None
        self.tools = []
        self.tools_list = []
        self.disabled = False
        self.max_retries = 5
        self.retry_delay = 2  # 初始延迟为2秒，可根据需要调整
        self.monitor_task = None

    async def initialize(self, server_name, server_config):
        retries = 0
        while retries < self.max_retries and not self.disabled:
            try:
                await self._connect(server_name, server_config)
                print("成功连接到服务器")
                # 启动监控
                await self.start_monitoring()
                break
            except Exception as e:
                logging.error(f"连接失败: {e}, 尝试重连...")
                retries += 1
                if retries <= self.max_retries:
                    await asyncio.sleep(self.retry_delay * retries)  # 增加重试等待时间
                else:
                    logging.error("超过最大重试次数，无法连接到服务器")
                    self.disabled = True

    async def _connect(self, server_name, server_config):
        self.server_name = server_name
        self.server_config = server_config
        command = server_config.get('command', '')
        if not command:
            server_url = server_config.get('url', '')
            if not server_url:
                self.disabled = True
                return
            else:
                stream = await self.exit_stack.enter_async_context(sse_client(server_url))
                self.stdio, self.write = stream
                self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        else:
            server_params = StdioServerParameters(
                command=get_command_path(command),
                args=server_config.get('args', []),
                env=server_config.get('env', None)
            )
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()
        response = await self.session.list_tools()
        self.tools = response.tools
        for tool in self.tools:
            self.tools_list.append(tool.name)
        print("\nConnected to server with tools:", [tool.name for tool in self.tools])

    async def monitor_connection(self):
        while not self.disabled:
            if not await self.check_connection():
                print("检测到连接丢失，尝试重新连接...")
                await self.initialize(self.server_name, self.server_config)  # 根据实际情况修改server_config
            await asyncio.sleep(10)  # 每隔10秒检查一次连接状态

    async def check_connection(self):
        try:
            # 这里根据你的具体需求来检查连接有效性，例如发送一个测试请求
            response = await self.session.list_tools()  # 需要替换为实际的ping方法
            if response.tools:
                return True
            return False
        except Exception as e:
            logging.error(f"检查连接时出错: {e}")
            return False

    async def start_monitoring(self):
        """启动监控任务"""
        self.monitor_task = asyncio.create_task(self.monitor_connection())

    async def stop_monitoring(self):
        """停止监控任务"""
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

    async def get_openai_functions(self):
        if self.disabled:
            return []
        response = await self.session.list_tools()
        tools = []
        for tool in response.tools:
            function = {
                "type": "function",
                "function": {
                    "name": tool.name, 
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            }
            tools.append(function)
        return tools

    async def call_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Any:
        if self.disabled:
            return None
        tool = next((tool for tool in self.tools if tool.name == tool_name), None)
        if tool is None:
            return None
        response = await self.session.call_tool(tool_name, tool_params)
        return response

    async def close(self):
        await self.stop_monitoring()
        await self.exit_stack.aclose()