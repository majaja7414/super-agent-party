import json
import asyncio
import locale
import logging
import os
from typing import Dict, List, Any, Optional
import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
import json
from typing import Any, Dict, List, Tuple
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
        try:
            self.server_name = server_name
            command = server_config.get('command', '')
            if not command:
                server_url = server_config.get('url', '')
                if not server_url:
                    self.disabled = True
                    return
                else:
                    # 初始化SSE客户端
                    stream = await self.exit_stack.enter_async_context(sse_client(server_url))
                    self.stdio, self.write = stream
                    self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
            else:
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
        except Exception as e:
            logging.error(f"Error initializing MCP client: {e}")
            self.disabled = True

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