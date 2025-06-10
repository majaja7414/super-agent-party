import json
import asyncio
import logging
import shutil
from typing import Dict, List, Any, AsyncIterator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.websocket import websocket_client
from mcp.client.streamable_http import streamablehttp_client
from contextlib import AsyncExitStack, asynccontextmanager
import nest_asyncio
from dotenv import load_dotenv

load_dotenv()
nest_asyncio.apply()

def get_command_path(command_name, default_command='uv'):
    """获取可执行文件路径"""
    path = shutil.which(command_name) or shutil.which(default_command)
    if not path:
        raise FileNotFoundError(f"未找到 {command_name} 或 {default_command}")
    return path

class ConnectionManager:
    def __init__(self):
        self._exit_stack = AsyncExitStack()
        self.session: ClientSession = None
        self.stdio = None
        self.write = None
        self.tools = []

    @asynccontextmanager
    async def connect(self, config: dict) -> AsyncIterator['ConnectionManager']:
        """安全连接上下文管理器"""
        try:
            # 清理旧连接
            await self._exit_stack.aclose()
            self._exit_stack = AsyncExitStack()

            # 建立新连接
            if 'command' in config:
                server_params = StdioServerParameters(
                    command=get_command_path(config['command']),
                    args=config.get('args', []),
                    env=config.get('env', None)
                )
                transport = await self._exit_stack.enter_async_context(stdio_client(server_params))
            else:
                mcptype = config.get('type', 'ws')
                client_map = {
                    'ws': websocket_client,
                    'sse': sse_client,
                    'streamablehttp': streamablehttp_client
                }
                transport = await self._exit_stack.enter_async_context(client_map[mcptype](config['url']))

            self.stdio, self.write = transport
            self.session = await self._exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
            
            # 初始化会话
            await self.session.initialize()
            tools = await self.session.list_tools()
            self.tools = [tool.name for tool in tools.tools]
            print(f"Connected to server. Available tools: {self.tools}")
            
            yield self
        finally:
            # 保证在同一个任务中清理
            await self._exit_stack.aclose()
            self.session = None

class McpClient:
    def __init__(self):
        self._conn: ConnectionManager = None
        self._config: dict = None
        self._lock = asyncio.Lock()
        self._monitor_task = None
        self._ping_task = None
        self._active = asyncio.Event()
        self._shutdown = False
        self.disabled = False

    async def initialize(self, server_name: str, server_config: dict):
        """非阻塞初始化"""
        if self._monitor_task:
            self._monitor_task.cancel()

        self._config = server_config
        self._monitor_task = asyncio.create_task(self._connection_monitor())

    async def _check_connection(self) -> bool:
        """综合连接状态检查"""
        try:
            if not self._active.is_set():
                return False
            return await asyncio.wait_for(self._conn.session.send_ping(), timeout=3)
        except:
            return False

    async def close(self):
        """安全关闭连接"""
        self._shutdown = True
        
        # 取消并等待监控任务
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass  # 预期中的任务取消
            
        # 取消心跳任务
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            
        # 清理连接资源
        async with self._lock:
            if self._conn:
                await self._conn._exit_stack.aclose()
                self._conn = None

    async def _connection_monitor(self):
        try:
            while not self._shutdown:
                try:
                    # 将整个连接周期放入锁保护范围
                    async with self._lock:
                        # 创建新连接
                        conn = ConnectionManager()
                        async with conn.connect(self._config) as active_conn:
                            self._conn = active_conn
                            self._active.set()
                            
                            # 将心跳检查放在连接上下文中
                            try:
                                while not self._shutdown:
                                    if not await self._check_connection():
                                        break
                                    await asyncio.sleep(5)
                            finally:
                                self._active.clear()
                                self._conn = None
                                
                    # 连接断开后等待重连
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logging.error(f"连接错误: {e}")
                    await asyncio.sleep(5)
                    
        except asyncio.CancelledError:
            logging.debug("监控任务正常终止")
        finally:
            # 确保资源清理
            async with self._lock:
                if self._conn:
                    await self._conn._exit_stack.aclose()
                    self._conn = None

    async def get_openai_functions(self):
        if self.disabled or not self._conn:
            return []
            
        response = await self._conn.session.list_tools()
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
        if self.disabled or not self._conn:
            return None
        
        response = await self._conn.session.call_tool(tool_name, tool_params)
        return response
