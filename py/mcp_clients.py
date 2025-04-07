import json
import asyncio
import locale
import logging
import os
from typing import Dict, List, Any, Optional
import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json
from typing import Any, Dict, List, Tuple
import shutil
import nest_asyncio
from dotenv import load_dotenv
from contextlib import AsyncExitStack
load_dotenv() 
nest_asyncio.apply()
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
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.server_name = None
        self.tools = []
        self.tools_list = []
        self.disabled = False

    async def initialize(self, server_name, server_config):
        """Connect to an MCP server
        
        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        self.server_name = server_name
        command = server_config.get('command', 'uv')
        server_params = StdioServerParameters(
            command = get_command_path(command),
            args=server_config.get('args', []),
            env=server_config.get('env', None)
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        self.tools = response.tools
        for tool in self.tools:
            self.tools_list.append(tool.name)
        print("\nConnected to server with tools:", [tool.name for tool in self.tools])

    async def get_openai_functions(self):
        response = await self.session.list_tools()
        tools = []
        if self.disabled:
            return tools
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
        tool = next((tool for tool in self.tools if tool.name == tool_name), None)
        if tool is None:
            return None
        response = await self.session.call_tool(tool_name, tool_params)
        return response
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()