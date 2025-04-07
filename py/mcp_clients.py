import json
import asyncio
import locale
import os
from typing import Dict, List, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json
from typing import Any, Dict, List, Tuple
import shutil
import nest_asyncio
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
        self.servers = {}  # Store server sessions
        self.all_tools = {}  # Store tool information
        self.is_initialized = False
        
    def load_mcp_servers_from_config(self,config) -> List[tuple]:
        
        servers = []
        for server_name, server_config in config.get('mcpServers', {}).items():
            if server_config.get('disabled', True):
                # 如果服务器被禁用，则跳过
                continue
            command = server_config.get('command', 'uv')
            server_params = StdioServerParameters(
                command = get_command_path(command),
                args=server_config.get('args', []),
                env=server_config.get('env', None)
            )
            servers.append((server_name, server_params))
        
        return servers

    @staticmethod
    def _convert_to_openai_functions(tools: Dict) -> List[Dict]:
        functions = []
        for tool_name, tool_details in tools.items():
            function = {
                "type": "function",
                "function": {
                    "name": tool_name,  # Using prefixed name (server-toolname)
                    "description": tool_details['description'],
                    "parameters": tool_details['input_schema']
                }
            }
            functions.append(function)
        return functions

    async def initialize(self,config):
        self.is_initialized = True
        """Initialize connections to all MCP servers"""
        servers = self.load_mcp_servers_from_config(config)
        
        for server_name, server_params in servers:
            # Create client and session
            client = stdio_client(server_params)
            read, write = await client.__aenter__()
            session = ClientSession(read, write)
            await session.__aenter__()
            
            # Store session
            self.servers[server_name] = {
                'client': client,
                'session': session
            }
            
            # Initialize the connection
            await session.initialize()
            
            # Get tools for this server
            server_tools = await session.list_tools()
            
            # Store tools with server prefix
            if hasattr(server_tools, 'tools'):
                for tool in server_tools.tools:
                    prefixed_tool_name = f"{server_name}-{tool.name}"
                    self.all_tools[prefixed_tool_name] = {
                        'description': tool.description,
                        'input_schema': tool.inputSchema,
                        'server': server_name,
                        'name': tool.name
                    }

    async def get_openai_functions(self) -> List[Dict]:
        """Get OpenAI-compatible function descriptions"""
        return self._convert_to_openai_functions(self.all_tools)

    async def call_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Any:
        """Call a tool using server-toolname format"""
        if tool_name not in self.all_tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        tool_info = self.all_tools[tool_name]
        server_name = tool_info['server']
        
        if server_name not in self.servers:
            raise ValueError(f"Server not connected: {server_name}")
        
        session = self.servers[server_name]['session']
        return await session.call_tool(tool_info['name'], arguments=tool_params)

    async def close(self):
        """Close all server connections"""
        for server_info in self.servers.values():
            await server_info['session'].__aexit__(None, None, None)
            await server_info['client'].__aexit__(None, None, None)
