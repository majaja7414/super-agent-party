# -- coding: utf-8 --
import base64
from io import BytesIO
import os
import sys
import tempfile
import wave
from scipy.io import wavfile
import numpy as np
import websockets
# 在程序最开始设置
if hasattr(sys, '_MEIPASS'):
    # 打包后的程序
    os.environ['PYTHONPATH'] = sys._MEIPASS
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')
import edge_tts
import asyncio
import copy
from functools import partial
import json
import random
import re
import shutil
import signal
from urllib.parse import urlparse
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, WebSocket, Request, WebSocketDisconnect
from fastapi_mcp import FastApiMCP
import logging
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel
from fastapi import status
from fastapi.responses import JSONResponse, StreamingResponse
import uuid
import time
from typing import Any, List, Dict,Optional
import shortuuid
from py.mcp_clients import McpClient
from contextlib import asynccontextmanager,suppress
import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor

import argparse
from mem0 import Memory
from py.qq_bot_manager import QQBotManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
parser = argparse.ArgumentParser(description="Run the ASGI application server.")
parser.add_argument("--host", default="127.0.0.1", help="Host for the ASGI server, default is 127.0.0.1")
parser.add_argument("--port", type=int, default=3456, help="Port for the ASGI server, default is 3456")
args = parser.parse_args()
HOST = args.host
PORT = args.port

os.environ["no_proxy"] = "localhost,127.0.0.1"
local_timezone = None
settings = None
client = None
reasoner_client = None
mcp_client_list = {}
locales = {}
_TOOL_HOOKS = {}
cur_random = []
ALLOWED_EXTENSIONS = [
  # 办公文档
  'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'pdf', 'pages', 
  'numbers', 'key', 'rtf', 'odt',
  
  # 编程开发
  'js', 'ts', 'py', 'java', 'c', 'cpp', 'h', 'hpp', 'go', 'rs',
  'swift', 'kt', 'dart', 'rb', 'php', 'html', 'css', 'scss', 'less',
  'vue', 'svelte', 'jsx', 'tsx', 'json', 'xml', 'yml', 'yaml', 
  'sql', 'sh',
  
  # 数据配置
  'csv', 'tsv', 'txt', 'md', 'log', 'conf', 'ini', 'env', 'toml'
]
ALLOWED_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']

ALLOWED_VIDEO_EXTENSIONS = ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', '3gp', 'm4v']

from py.get_setting import load_settings,save_settings,base_path,configure_host_port,UPLOAD_FILES_DIR,AGENT_DIR,MEMORY_CACHE_DIR,KB_DIR
from py.llm_tool import get_image_base64,get_image_media_type


configure_host_port(args.host, args.port)

@asynccontextmanager
async def lifespan(app: FastAPI): 
    from py.get_setting import init_db
    await init_db()
    global settings, client, reasoner_client, mcp_client_list,local_timezone,logger,locales
    with open(base_path + "/config/locales.json", "r", encoding="utf-8") as f:
        locales = json.load(f)
    from tzlocal import get_localzone
    local_timezone = get_localzone()
    settings = await load_settings()
    if settings:
        client = AsyncOpenAI(api_key=settings['api_key'], base_url=settings['base_url'])
        reasoner_client = AsyncOpenAI(api_key=settings['reasoner']['api_key'],base_url=settings['reasoner']['base_url'])
    else:
        client = AsyncOpenAI()
        reasoner_client = AsyncOpenAI()
    mcp_init_tasks = []
    async def init_mcp_with_timeout(server_name, server_config):
        """带超时处理的异步初始化函数"""
        try:
            mcp_client = McpClient()
            if not server_config['disabled']:
                await asyncio.wait_for(
                    mcp_client.initialize(server_name, server_config),
                    timeout=6
                )
            return server_name, mcp_client, None
        except asyncio.TimeoutError:
            logger.error(f"MCP client {server_name} initialization timeout")
            return server_name, None, "timeout"
        except Exception as e:
            logger.error(f"MCP client {server_name} initialization failed: {str(e)}")
            return server_name, None, "error"
    if settings:
        # 创建所有初始化任务
        for server_name, server_config in settings['mcpServers'].items():
            task = asyncio.create_task(init_mcp_with_timeout(server_name, server_config))
            mcp_init_tasks.append(task)
        # 立即继续执行不等待
        # 通过回调处理结果
        async def check_results():
            """后台收集任务结果"""
            for task in asyncio.as_completed(mcp_init_tasks):
                server_name, mcp_client, error = await task
                if error:
                    settings['mcpServers'][server_name]['disabled'] = True
                    settings['mcpServers'][server_name]['processingStatus'] = 'server_error'
                    mcp_client_list[server_name] = McpClient()
                    mcp_client_list[server_name].disabled = True
                else:
                    mcp_client_list[server_name] = mcp_client
            await save_settings(settings)  # 所有任务完成后统一保存
            await broadcast_settings_update(settings)  # 所有任务完成后统一广播
        # 在后台运行结果收集
        asyncio.create_task(check_results())
    yield
# WebSocket端点增加连接管理
active_connections = []
# 新增广播函数
async def broadcast_settings_update(settings):
    """向所有WebSocket连接推送配置更新"""
    for connection in active_connections:  # 需要维护全局连接列表
        try:
            await connection.send_json({
                "type": "settings",
                "data": settings  # 直接使用内存中的最新配置
            })
        except Exception as e:
            logger.error(f"Broadcast failed: {e}")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def t(text: str) -> str:
    global locales
    settings = await load_settings()
    target_language = settings["systemSettings"]["language"]
    return locales[target_language].get(text, text)


# 全局存储异步工具状态
async_tools = {}
async_tools_lock = asyncio.Lock()

async def execute_async_tool(tool_id: str, tool_name: str, args: dict, settings: dict,user_prompt: str):
    try:
        results = await dispatch_tool(tool_name, args, settings)
        if tool_name in ["query_knowledge_base"] and type(results) == list:
            from py.know_base import rerank_knowledge_base
            if settings["KBSettings"]["is_rerank"]:
                results = await rerank_knowledge_base(user_prompt,results)
            results = json.dumps(results, ensure_ascii=False, indent=4)
        async with async_tools_lock:
            async_tools[tool_id] = {
                "status": "completed",
                "result": results,
                "name": tool_name,
                "parameters": args,
            }
    except Exception as e:
        async with async_tools_lock:
            async_tools[tool_id] = {
                "status": "error",
                "result": str(e),
                "name": tool_name,
                "parameters": args,
            }

async def get_image_content(image_url: str) -> str:
    import hashlib
    settings = await load_settings()
    base64_image = await get_image_base64(image_url)
    media_type = await get_image_media_type(image_url)
    url= f"data:{media_type};base64,{base64_image}"
    image_hash = hashlib.md5(image_url.encode()).hexdigest()
    content = ""
    if settings['vision']['enabled']:
        # 如果uploaded_files/{item['image_url']['hash']}.txt存在，则读取文件内容，否则调用vision api
        if os.path.exists(os.path.join(UPLOAD_FILES_DIR, f"{image_hash}.txt")):
            with open(os.path.join(UPLOAD_FILES_DIR, f"{image_hash}.txt"), "r", encoding='utf-8') as f:
                content += f"\n\n图片(URL:{image_url} 哈希值：{image_hash})信息如下：\n\n"+str(f.read())+"\n\n"
        else:
            images_content = [{"type": "text", "text": "请仔细描述图片中的内容，包含图片中可能存在的文字、数字、颜色、形状、大小、位置、人物、物体、场景等信息。"},{"type": "image_url", "image_url": {"url": url}}]
            client = AsyncOpenAI(api_key=settings['vision']['api_key'],base_url=settings['vision']['base_url'])
            response = await client.chat.completions.create(
                model=settings['vision']['model'],
                messages = [{"role": "user", "content": images_content}],
                temperature=settings['vision']['temperature'],
            )
            content = f"\n\nn图片(URL:{image_url} 哈希值：{image_hash})信息如下：\n\n"+str(response.choices[0].message.content)+"\n\n"
            with open(os.path.join(UPLOAD_FILES_DIR, f"{image_hash}.txt"), "w", encoding='utf-8') as f:
                f.write(str(response.choices[0].message.content))
    else:           
        # 如果uploaded_files/{item['image_url']['hash']}.txt存在，则读取文件内容，否则调用vision api
        if os.path.exists(os.path.join(UPLOAD_FILES_DIR, f"{image_hash}.txt")):
            with open(os.path.join(UPLOAD_FILES_DIR, f"{image_hash}.txt"), "r", encoding='utf-8') as f:
                content += f"\n\nn图片(URL:{image_url} 哈希值：{image_hash})信息如下：\n\n"+str(f.read())+"\n\n"
        else:
            images_content = [{"type": "text", "text": "请仔细描述图片中的内容，包含图片中可能存在的文字、数字、颜色、形状、大小、位置、人物、物体、场景等信息。"},{"type": "image_url", "image_url": {"url": url}}]
            client = AsyncOpenAI(api_key=settings['api_key'],base_url=settings['base_url'])
            response = await client.chat.completions.create(
                model=settings['model'],
                messages = [{"role": "user", "content": images_content}],
                temperature=settings['temperature'],
            )
            content = f"\n\nn图片(URL:{image_url} 哈希值：{image_hash})信息如下：\n\n"+str(response.choices[0].message.content)+"\n\n"
            with open(os.path.join(UPLOAD_FILES_DIR, f"{image_hash}.txt"), "w", encoding='utf-8') as f:
                f.write(str(response.choices[0].message.content))
    return content

async def dispatch_tool(tool_name: str, tool_params: dict,settings: dict) -> str | List | None:
    global mcp_client_list,_TOOL_HOOKS
    from py.web_search import (
        DDGsearch_async, 
        searxng_async, 
        Tavily_search_async,
        Bing_search_async,
        Google_search_async,
        Brave_search_async,
        Exa_search_async,
        Serper_search_async,
        bochaai_search_async,
        jina_crawler_async,
        Crawl4Ai_search_async, 
    )
    from py.know_base import query_knowledge_base
    from py.agent_tool import agent_tool_call
    from py.a2a_tool import a2a_tool_call
    from py.llm_tool import custom_llm_tool
    from py.pollinations import pollinations_image,openai_image,siliconflow_image
    from py.load_files import get_file_content
    from py.code_interpreter import e2b_code_async,local_run_code_async
    from py.custom_http import fetch_custom_http
    from py.comfyui_tool import comfyui_tool_call
    _TOOL_HOOKS = {
        "DDGsearch_async": DDGsearch_async,
        "searxng_async": searxng_async,
        "Tavily_search_async": Tavily_search_async,
        "query_knowledge_base": query_knowledge_base,
        "jina_crawler_async": jina_crawler_async,
        "Crawl4Ai_search_async": Crawl4Ai_search_async,
        "agent_tool_call": agent_tool_call,
        "a2a_tool_call": a2a_tool_call,
        "custom_llm_tool": custom_llm_tool,
        "pollinations_image":pollinations_image,
        "get_file_content":get_file_content,
        "get_image_content": get_image_content,
        "e2b_code_async": e2b_code_async,
        "local_run_code_async": local_run_code_async,
        "openai_image": openai_image,
        "siliconflow_image": siliconflow_image,
        "Bing_search_async": Bing_search_async,
        "Google_search_async": Google_search_async,
        "Brave_search_async": Brave_search_async,
        "Exa_search_async": Exa_search_async,
        "Serper_search_async": Serper_search_async,
        "bochaai_search_async": bochaai_search_async,
        "comfyui_tool_call": comfyui_tool_call,
    }
    if "multi_tool_use." in tool_name:
        tool_name = tool_name.replace("multi_tool_use.", "")
    if "custom_http_" in tool_name:
        tool_name = tool_name.replace("custom_http_", "")
        print(tool_name)
        settings_custom_http = settings['custom_http']
        for custom in settings_custom_http:
            if custom['name'] == tool_name:
                tool_custom_http = custom
                break
        method = tool_custom_http['method']
        url = tool_custom_http['url']
        headers = tool_custom_http['headers']
        result = await fetch_custom_http(method, url, headers, tool_params)
        return str(result)
    if "comfyui_" in tool_name:
        tool_name = tool_name.replace("comfyui_", "")
        text_input = tool_params.get('text_input', None)
        text_input_2 = tool_params.get('text_input_2', None)
        image_input = tool_params.get('image_input', None)
        image_input_2 = tool_params.get('image_input_2', None)
        print(tool_name)
        result = await comfyui_tool_call(tool_name, text_input, image_input,text_input_2,image_input_2)
        return str(result)
    if tool_name not in _TOOL_HOOKS:
        for server_name, mcp_client in mcp_client_list.items():
            if tool_name in mcp_client._conn.tools:
                result = await mcp_client.call_tool(tool_name, tool_params)
                return str(result.model_dump())
        return None
    tool_call = _TOOL_HOOKS[tool_name]
    try:
        ret_out = await tool_call(**tool_params)
        return ret_out
    except Exception as e:
        logger.error(f"Error calling tool {tool_name}: {e}")
        return f"Error calling tool {tool_name}: {e}"


class ChatRequest(BaseModel):
    messages: List[Dict]
    model: str = None
    temperature: float = 0.7
    tools: dict = None
    stream: bool = False
    max_tokens: int = None
    top_p: float = 1
    frequency_penalty: float = 0
    presence_penalty: float = 0
    fileLinks: List[str] = None
    enable_thinking: bool = False
    enable_deep_research: bool = False
    enable_web_search: bool = False
    asyncToolsID: List[str] = None

async def message_without_images(messages: List[Dict]) -> List[Dict]:
    if messages:
        for message in messages:
            if 'content' in message:
                # message['content'] 是一个列表
                if isinstance(message['content'], list):
                    for item in message['content']:
                        if isinstance(item, dict) and item['type'] == 'text':
                            message['content'] = item['text']
                            break
    return messages

async def images_in_messages(messages: List[Dict],fastapi_base_url: str) -> List[Dict]:
    import hashlib
    images = []
    index = 0
    for message in messages:
        image_urls = []
        if 'content' in message:
            # message['content'] 是一个列表
            if isinstance(message['content'], list):
                for item in message['content']:
                    if isinstance(item, dict) and item['type'] == 'image_url':
                        # 如果item["image_url"]["url"]是http或https开头，则转换成base64
                        if item["image_url"]["url"].startswith("http"):
                            image_url = item["image_url"]["url"]
                            # 对image_url分解出baseURL，与fastapi_base_url比较，如果相同，将image_url的baseURL替换成127.0.0.1:PORT
                            if fastapi_base_url in image_url:
                                image_url = image_url.replace(fastapi_base_url, f"http://127.0.0.1:{PORT}/")
                            base64_image = await get_image_base64(image_url)
                            media_type = await get_image_media_type(image_url)
                            item["image_url"]["url"] = f"data:{media_type};base64,{base64_image}"
                            item["image_url"]["hash"] = hashlib.md5(item["image_url"]["url"].encode()).hexdigest()
                        else:
                            item["image_url"]["hash"] = hashlib.md5(item["image_url"]["url"].encode()).hexdigest()

                        image_urls.append(item)
        if image_urls:
            images.append({'index': index, 'images': image_urls})
        index += 1
    return images

async def images_add_in_messages(request_messages: List[Dict], images: List[Dict], settings: dict) -> List[Dict]:
    messages=copy.deepcopy(request_messages)
    if settings['vision']['enabled']:
        for image in images:
            index = image['index']
            if index < len(messages):
                if 'content' in messages[index]:
                    for item in image['images']:
                        # 如果uploaded_files/{item['image_url']['hash']}.txt存在，则读取文件内容，否则调用vision api
                        if os.path.exists(os.path.join(UPLOAD_FILES_DIR, f"{item['image_url']['hash']}.txt")):
                            with open(os.path.join(UPLOAD_FILES_DIR, f"{item['image_url']['hash']}.txt"), "r", encoding='utf-8') as f:
                                messages[index]['content'] += f"\n\nsystem: 用户发送的图片(哈希值：{item['image_url']['hash']})信息如下：\n\n"+str(f.read())+"\n\n"
                        else:
                            images_content = [{"type": "text", "text": "请仔细描述图片中的内容，包含图片中可能存在的文字、数字、颜色、形状、大小、位置、人物、物体、场景等信息。"},{"type": "image_url", "image_url": {"url": item['image_url']['url']}}]
                            client = AsyncOpenAI(api_key=settings['vision']['api_key'],base_url=settings['vision']['base_url'])
                            response = await client.chat.completions.create(
                                model=settings['vision']['model'],
                                messages = [{"role": "user", "content": images_content}],
                                temperature=settings['vision']['temperature'],
                            )
                            messages[index]['content'] += f"\n\nsystem: 用户发送的图片(哈希值：{item['image_url']['hash']})信息如下：\n\n"+str(response.choices[0].message.content)+"\n\n"
                            with open(os.path.join(UPLOAD_FILES_DIR, f"{item['image_url']['hash']}.txt"), "w", encoding='utf-8') as f:
                                f.write(str(response.choices[0].message.content))
    else:           
        for image in images:
            index = image['index']
            if index < len(messages):
                if 'content' in messages[index]:
                    for item in image['images']:
                        # 如果uploaded_files/{item['image_url']['hash']}.txt存在，则读取文件内容，否则调用vision api
                        if os.path.exists(os.path.join(UPLOAD_FILES_DIR, f"{item['image_url']['hash']}.txt")):
                            with open(os.path.join(UPLOAD_FILES_DIR, f"{item['image_url']['hash']}.txt"), "r", encoding='utf-8') as f:
                                messages[index]['content'] += f"\n\nsystem: 用户发送的图片(哈希值：{item['image_url']['hash']})信息如下：\n\n"+str(f.read())+"\n\n"
                        else:
                            messages[index]['content'] = [{"type": "text", "text": messages[index]['content']}]
                            messages[index]['content'].append({"type": "image_url", "image_url": {"url": item['image_url']['url']}})
    return messages

async def tools_change_messages(request: ChatRequest, settings: dict):
    if settings['tools']['time']['enabled']:
        time_message = f"消息发送时间：{local_timezone}  {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n\n"
        request.messages[-1]['content'] = time_message + request.messages[-1]['content']
    if settings['tools']['inference']['enabled']:
        inference_message = "回答用户前请先思考推理，再回答问题，你的思考推理的过程必须放在<think>与</think>之间。\n\n"
        request.messages[-1]['content'] = f"{inference_message}\n\n用户：" + request.messages[-1]['content']
    if settings['tools']['formula']['enabled']:
        latex_message = "\n\n当你想使用latex公式时，你必须是用 ['$', '$'] 作为行内公式定界符，以及 ['$$', '$$'] 作为行间公式定界符。\n\n"
        if request.messages and request.messages[0]['role'] == 'system':
            request.messages[0]['content'] += latex_message
        else:
            request.messages.insert(0, {'role': 'system', 'content': latex_message})
    if settings['tools']['language']['enabled']:
        language_message = f"请使用{settings['tools']['language']['language']}语言推理分析思考，不要使用其他语言推理分析，语气风格为{settings['tools']['language']['tone']}\n\n"
        if request.messages and request.messages[0]['role'] == 'system':
            request.messages[0]['content'] += language_message
        else:
            request.messages.insert(0, {'role': 'system', 'content': language_message})
    if settings["stickerPacks"]:
        for stickerPack in settings["stickerPacks"]:
            if stickerPack["enabled"]:
                sticker_message = f"\n\n图片库名称：{stickerPack['name']}，包含的图片：{json.dumps(stickerPack['stickers'])}\n\n"
                if request.messages and request.messages[0]['role'] == 'system':
                    request.messages[0]['content'] += sticker_message
                else:
                    request.messages.insert(0, {'role': 'system', 'content': sticker_message})
        request.messages[0]['content'] += "\n\n当你需要使用图片时，请将图片的URL放在markdown的图片标签中，例如：![图片名](图片URL)\n\n"
    return request

def get_drs_stage(DRS_STAGE):
    if DRS_STAGE == 1:
        drs_msg = "当前阶段为明确用户需求阶段，你需要分析用户的需求，并给出明确的需求描述。如果用户的需求描述不明确，你可以暂时不完成任务，而是分析需要让用户进一步明确哪些需求。"
    elif DRS_STAGE == 2:
        drs_msg = "当前阶段为查询搜索阶段，利用你的知识库、互联网搜索、数据库查询工具（如果有，这些工具不一定会提供），查询完成任务所需要的所有信息。"
    elif DRS_STAGE == 3:
        drs_msg = "当前阶段为生成结果阶段，根据当前收集到的所有信息，完成任务，生成回答。如果用户要求你生成一个超过2000字的回答，你可以尝试将该任务拆分成多个部分，每次只完成其中一个部分。"
    else:
        drs_msg = "当前阶段为生成结果阶段，根据当前收集到的所有信息，完成任务，生成回答。如果用户要求你生成一个超过2000字的回答，你可以尝试将该任务拆分成多个部分，每次只完成其中一个部分。"
    return drs_msg  

def get_drs_stage_name(DRS_STAGE):
    if DRS_STAGE == 1:
        drs_stage_name = "明确用户需求阶段"
    elif DRS_STAGE == 2:
        drs_stage_name = "查询搜索阶段"
    elif DRS_STAGE == 3:
        drs_stage_name = "生成结果阶段"
    else:
        drs_stage_name = "生成结果阶段"
    return drs_stage_name

def get_drs_stage_system_message(DRS_STAGE,user_prompt,full_content):
    drs_stage_name = get_drs_stage_name(DRS_STAGE)
    if DRS_STAGE == 1:
        search_prompt = f"""
# 当前状态：

## 初始任务：
{user_prompt}

## 当前结果：
{full_content}

## 当前阶段：
{drs_stage_name}

# 深度研究一共有三个阶段：1: 明确用户需求阶段 2: 查询搜索阶段 3: 生成结果阶段

## 当前阶段，请输出json字符串：

### 如果需要用户明确需求，请输出json字符串：
{{
    "status": "need_more_info",
    "unfinished_task": ""
}}

### 如果不需要进一步明确需求，进入并进入查询搜索阶段，请输出json字符串：
{{
    "status": "search",
    "unfinished_task": ""
}}
"""
    elif DRS_STAGE == 2:
        search_prompt = f"""
# 当前状态：

## 初始任务：
{user_prompt}

## 当前结果：
{full_content}

## 当前阶段：
{drs_stage_name}

# 深度研究一共有三个阶段：1: 明确用户需求阶段 2: 查询搜索阶段 3: 生成结果阶段

## 当前阶段，请输出json字符串：

### 如果需要继续查询，请输出json字符串：
{{
    "status": "need_more_search",
    "unfinished_task": "这里填入继续查询的信息"
}}

### 如果不需要进一步明确需求，进入并进入查询搜索阶段，请输出json字符串：
{{
    "status": "answer",
    "unfinished_task": ""
}}
"""    
    else:
        search_prompt = f"""
# 当前状态：

## 初始任务：
{user_prompt}

## 当前结果：
{full_content}

## 当前阶段：
{drs_stage_name}

# 深度研究一共有三个阶段：1: 明确用户需求阶段 2: 查询搜索阶段 3: 生成结果阶段

## 当前阶段，请输出json字符串：

如果初始任务已完成，请输出json字符串：
{{
    "status": "done",
    "unfinished_task": ""
}}

如果初始任务未完成，请输出json字符串：
{{
    "status": "not_done",
    "unfinished_task": "这里填入未完成的任务"
}}
"""    
    return search_prompt

async def generate_stream_response(client,reasoner_client, request: ChatRequest, settings: dict,fastapi_base_url,enable_thinking,enable_deep_research,enable_web_search,async_tools_id):
    global mcp_client_list
    DRS_STAGE = 1 # 1: 明确用户需求阶段 2: 查询搜索阶段 3: 生成结果阶段
    images = await images_in_messages(request.messages,fastapi_base_url)
    request.messages = await message_without_images(request.messages)
    from py.load_files import get_files_content,file_tool,image_tool
    from py.web_search import (
        DDGsearch_async, 
        searxng_async, 
        Tavily_search_async,
        Bing_search_async,
        Google_search_async,
        Brave_search_async,
        Exa_search_async,
        Serper_search_async,
        bochaai_search_async,
        duckduckgo_tool, 
        searxng_tool, 
        tavily_tool, 
        bing_tool,
        google_tool,
        brave_tool,
        exa_tool,
        serper_tool,
        bochaai_tool,
        jina_crawler_tool, 
        Crawl4Ai_tool
    )
    from py.know_base import kb_tool,query_knowledge_base,rerank_knowledge_base
    from py.agent_tool import get_agent_tool
    from py.a2a_tool import get_a2a_tool
    from py.llm_tool import get_llm_tool
    from py.pollinations import pollinations_image_tool,openai_image_tool,siliconflow_image_tool
    from py.code_interpreter import e2b_code_tool,local_run_code_tool
    m0 = None
    memoryId = None
    if settings["memorySettings"]["is_memory"]:
        memoryId = settings["memorySettings"]["selectedMemory"]
        cur_memory = None
        for memory in settings["memories"]:
            if memory["id"] == memoryId:
                cur_memory = memory
                break
        if cur_memory:
            
            config={
                "embedder": {
                    "provider": 'openai',
                    "config": {
                        "model": cur_memory['model'],
                        "api_key": cur_memory['api_key'],
                        "openai_base_url":cur_memory["base_url"],
                        "embedding_dims":1024
                    },
                },
                "llm": {
                    "provider": 'openai',
                    "config": {
                        "model": settings['model'],
                        "api_key": settings['api_key'],
                        "openai_base_url":settings["base_url"]
                    }
                },
                "vector_store": {
                    "provider": "faiss",
                    "config": {
                        "collection_name": "agent-party",
                        "path": os.path.join(MEMORY_CACHE_DIR,memoryId),
                        "distance_strategy": "euclidean",
                        "embedding_model_dims": 1024
                    }
                }
            }
            m0 = Memory.from_config(config)
    open_tag = "<think>"
    close_tag = "</think>"
    try:
        tools = request.tools or []
        if mcp_client_list:
            for server_name, mcp_client in mcp_client_list.items():
                if server_name in settings['mcpServers']:
                    if 'disabled' not in settings['mcpServers'][server_name]:
                        settings['mcpServers'][server_name]['disabled'] = False
                    if settings['mcpServers'][server_name]['disabled'] == False and settings['mcpServers'][server_name]['processingStatus'] == 'ready':
                        function = await mcp_client.get_openai_functions()
                        if function:
                            tools.extend(function)
        get_llm_tool_fuction = await get_llm_tool(settings)
        if get_llm_tool_fuction:
            tools.append(get_llm_tool_fuction)
        get_agent_tool_fuction = await get_agent_tool(settings)
        if get_agent_tool_fuction:
            tools.append(get_agent_tool_fuction)
        get_a2a_tool_fuction = await get_a2a_tool(settings)
        if get_a2a_tool_fuction:
            tools.append(get_a2a_tool_fuction)
        if settings['text2imgSettings']['enabled']:
            if settings['text2imgSettings']['engine'] == 'pollinations':
                tools.append(pollinations_image_tool)
            elif settings['text2imgSettings']['engine'] == 'openai':
                if settings['text2imgSettings']['vendor'] == 'siliconflow':
                    tools.append(siliconflow_image_tool)
                else:
                    tools.append(openai_image_tool)
        if settings['tools']['getFile']['enabled']:
            tools.append(file_tool)
            tools.append(image_tool)
        if settings["codeSettings"]['enabled']:
            if settings["codeSettings"]["engine"] == "e2b":
                tools.append(e2b_code_tool)
            elif settings["codeSettings"]["engine"] == "sandbox":
                tools.append(local_run_code_tool)
        if settings["custom_http"]:
            for custom_http in settings["custom_http"]:
                if custom_http["enabled"]:
                    if custom_http['body'] == "":
                        custom_http['body'] = "{}"
                    custom_http_tool = {
                        "type": "function",
                        "function": {
                            "name": f"custom_http_{custom_http['name']}",
                            "description": f"{custom_http['description']}",
                            "parameters": json.loads(custom_http['body']),
                        },
                    }
                    tools.append(custom_http_tool)
        if settings["workflows"]:
            for workflow in settings["workflows"]:
                if workflow["enabled"]:
                    comfyui_properties = {}
                    comfyui_required = []
                    if workflow["text_input"] is not None:
                        comfyui_properties["text_input"] = {
                            "description": "第一个文字输入，需要输入的提示词，用于生成图片或者视频，如果无特别提示，默认为英文",
                            "type": "string"
                        }
                        comfyui_required.append("text_input")
                    if workflow["text_input_2"] is not None:
                        comfyui_properties["text_input_2"] = {
                            "description": "第二个文字输入，需要输入的提示词，用于生成图片或者视频，如果无特别提示，默认为英文",
                            "type": "string"
                        }
                        comfyui_required.append("text_input_2")
                    if workflow["image_input"] is not None:
                        comfyui_properties["image_input"] = {
                            "description": "第一个图片输入，需要输入的图片，必须是图片URL，可以是外部链接，也可以是服务器内部的URL，例如：https://www.example.com/xxx.png  或者  http://127.0.0.1:3456/xxx.jpg",
                            "type": "string"
                        }
                        comfyui_required.append("image_input")
                    if workflow["image_input_2"] is not None:
                        comfyui_properties["image_input_2"] = {
                            "description": "第二个图片输入，需要输入的图片，必须是图片URL，可以是外部链接，也可以是服务器内部的URL，例如：https://www.example.com/xxx.png  或者  http://127.0.0.1:3456/xxx.jpg",
                            "type": "string"
                        }
                        comfyui_required.append("image_input_2")
                    comfyui_parameters = {
                        "type": "object",
                        "properties": comfyui_properties,
                        "required": comfyui_required
                    }
                    comfyui_tool = {
                        "type": "function",
                        "function": {
                            "name": f"comfyui_{workflow['unique_filename']}",
                            "description": f"{workflow['description']}+\n如果要输入图片提示词或者修改提示词，尽可能使用英语。\n返回的图片结果，请将图片的URL放入![image]()这样的markdown语法中，用户才能看到图片。如果是视频，请将视频的URL放入<video controls> <source src=''></video>的中src中，用户才能看到视频。如果有多个结果，则请用换行符分隔开这几个图片或者视频，用户才能看到多个结果。",
                            "parameters": comfyui_parameters,
                        },
                    }
                    tools.append(comfyui_tool)
        print(tools)
        source_prompt = ""
        if request.fileLinks:
            print("fileLinks",request.fileLinks)
            # 异步获取文件内容
            files_content = await get_files_content(request.fileLinks)
            fileLinks_message = f"\n\n相关文件内容：{files_content}"
            
            # 修复字符串拼接错误
            if request.messages and request.messages[0]['role'] == 'system':
                request.messages[0]['content'] += fileLinks_message
            else:
                request.messages.insert(0, {'role': 'system', 'content': fileLinks_message})
            source_prompt += fileLinks_message
        user_prompt = request.messages[-1]['content']
        if m0:
            lore_content = ""
            assistant_reply = ""
            # 找出request.messages中上次的assistant回复
            for i in range(len(request.messages)-1, -1, -1):
                if request.messages[i]['role'] == 'assistant':
                    assistant_reply = request.messages[i]['content']
                    break
            if cur_memory["lorebook"]:
                for lore in cur_memory["lorebook"]:
                    if lore["name"] != "" and (lore["name"] in user_prompt or lore["name"] in assistant_reply):
                        lore_content = lore_content + "\n\n" + f"{lore['name']}：{lore['value']}"
            global cur_random 
            # 如果request.messages中不包含assistant回复，说明是首次提问，触发随机设定
            if not assistant_reply:
                # 如果 cur_memory 中有 random 条目
                if cur_memory.get("random") and len(cur_memory["random"]) > 0:
                    # 随机选择一个 random 条目
                    random_entry = random.choice(cur_memory["random"])
                    if random_entry.get("value"):
                        lore_content = lore_content + "\n\n" + f"{random_entry['value']}"
                        cur_random.append({"id":memoryId,"value":random_entry["value"]})
                        print("新随机设定：",{"id":memoryId,"value":random_entry["value"]})
            else:
                for item in cur_random:
                    if item["id"] == memoryId:
                        lore_content = lore_content + "\n\n" + f"{item['value']}"
                        print("沿用随机设定：",{"id":memoryId,"value":item['value']})  
                        break 
            memoryLimit = settings["memorySettings"]["memoryLimit"]
            try:
                relevant_memories = m0.search(query=user_prompt, user_id=memoryId, limit=memoryLimit)
                relevant_memories = json.dumps(relevant_memories, ensure_ascii=False)
            except Exception as e:
                print("m0.search error:",e)
                relevant_memories = ""
            if request.messages and request.messages[0]['role'] == 'system':
                request.messages[0]['content'] += "之前的相关记忆：\n\n" + relevant_memories + "\n\n相关结束\n\n"
            else:
                request.messages.insert(0, {'role': 'system', 'content': "之前的相关记忆：\n\n" + relevant_memories + "\n\n相关结束\n\n"})
            if cur_memory["basic_character"]:
                print("添加角色设定：\n\n" + cur_memory["basic_character"] + "\n\n角色设定结束\n\n")
                if request.messages and request.messages[0]['role'] == 'system':
                    request.messages[0]['content'] += "角色设定：\n\n" + cur_memory["basic_character"] + "\n\n角色设定结束\n\n"
                else:
                    request.messages.insert(0, {'role': 'system', 'content': "角色设定：\n\n" + cur_memory["basic_character"] + "\n\n角色设定结束\n\n"})
            if lore_content:
                print("添加世界观设定：\n\n" + lore_content + "\n\n世界观设定结束\n\n")
                if request.messages and request.messages[0]['role'] == 'system':
                    request.messages[0]['content'] += "世界观设定：\n\n" + lore_content + "\n\n世界观设定结束\n\n"
                else:
                    request.messages.insert(0, {'role': 'system', 'content': "世界观设定：\n\n" + lore_content + "\n\n世界观设定结束\n\n"})
        request = await tools_change_messages(request, settings)
        model = settings['model']
        extra_params = settings['extra_params']
        # 移除extra_params这个list中"name"不包含非空白符的键值对
        if extra_params:
            for extra_param in extra_params:
                if not extra_param['name'].strip():
                    extra_params.remove(extra_param)
            # 列表转换为字典
            extra_params = {item['name']: item['value'] for item in extra_params}
        else:
            extra_params = {}
        async def stream_generator(user_prompt,DRS_STAGE):
            try:
                # 处理传入的异步工具ID查询
                if async_tools_id:
                    responses_to_send = []
                    responses_to_wait = []
                    async with async_tools_lock:
                        # 收集已完成的结果并删除条目
                        for tid in list(async_tools.keys()):  # 转成list避免字典修改异常
                            if tid in async_tools_id:
                                if async_tools[tid]["status"] in ("completed", "error"):
                                    responses_to_send.append({
                                        "tool_id": tid,
                                        **async_tools.pop(tid)  # 移除已处理的条目
                                    })
                                elif async_tools[tid]["status"] == "pending":
                                    responses_to_wait.append({
                                        "tool_id": tid,
                                        "name":async_tools[tid]["name"],
                                        "parameters": async_tools[tid]["parameters"]
                                    })
                    for response in responses_to_send:
                        tid = response["tool_id"]
                        if response["status"] == "completed":
                            # 构造文件名
                            filename = f"{tid}.txt"
                            # 将搜索结果写入uploaded_file文件夹下的filename文件
                            with open(os.path.join(UPLOAD_FILES_DIR, filename), "w", encoding='utf-8') as f:
                                f.write(str(response["result"]))            
                            # 将文件链接更新为新的链接
                            fileLink=f"{fastapi_base_url}uploaded_files/{filename}"
                            tool_chunk = {
                                "choices": [{
                                    "delta": {
                                        "tool_content": f"\n\n[{tid}{await t("tool_result")}]({fileLink})\n\n",
                                        "async_tool_id": tid
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(tool_chunk)}\n\n"
                            request.messages.append({
                                "role": "system",
                                "content": f"之前调用的异步工具（{tid}）的结果：\n\n{response['result']}\n\n====结果结束====\n\n请根据工具结果回复未回复的问题或需求。"
                            }) 
                        if response["status"] == "error":
                            # 构造文件名
                            filename = f"{tid}.txt"
                            # 将搜索结果写入uploaded_file文件夹下的filename文件
                            with open(os.path.join(UPLOAD_FILES_DIR, filename), "w", encoding='utf-8') as f:
                                f.write(str(response["result"]))            
                            # 将文件链接更新为新的链接
                            fileLink=f"{fastapi_base_url}uploaded_files/{filename}"
                            tool_chunk = {
                                "choices": [{
                                    "delta": {
                                        "tool_content": f"\n\n[{tid}{await t("tool_result")}]({fileLink})\n\n",
                                        "async_tool_id": tid
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(tool_chunk)}\n\n"
                            request.messages.append({
                                "role": "system",
                                "content": f"之前调用的异步工具（{tid}）发生错误：\n\n{response['result']}\n\n====错误结束====\n\n"
                            }) 
                    for response in responses_to_wait:
                        # 在request.messages倒数第一个元素之前的位置插入一个新元素
                        request.messages.insert(-1, 
                            {
                                "tool_calls": [
                                    {
                                        "id": "agentParty",
                                        "function": {
                                            "arguments": json.dumps(response["parameters"]),
                                            "name": response["name"],
                                        },
                                        "type": "function",
                                    }
                                ],
                                "role": "assistant",
                                "content": "",
                            }
                        )
                        results = f"{response["name"]}工具已成功启动，获取结果需要花费很久的时间。请不要再次调用该工具，因为工具结果将生成后自动发送，再次调用也不能更快的获取到结果。请直接告诉用户，你会在获得结果后回答他的问题。"
                        request.messages.insert(-1, 
                            {
                                "role": "tool",
                                "tool_call_id": "agentParty",
                                "name": response["name"],
                                "content": str(results),
                            }
                        )
                kb_list = []
                if settings["knowledgeBases"]:
                    for kb in settings["knowledgeBases"]:
                        if kb["enabled"] and kb["processingStatus"] == "completed":
                            kb_list.append({"kb_id":kb["id"],"name": kb["name"],"introduction":kb["introduction"]})
                if settings["KBSettings"]["when"] == "before_thinking" or settings["KBSettings"]["when"] == "both":
                    if kb_list:
                        chunk_dict = {
                            "id": "webSearch",
                            "choices": [
                                {
                                    "finish_reason": None,
                                    "index": 0,
                                    "delta": {
                                        "role":"assistant",
                                        "content": "",
                                        "tool_content": f"{await t("KB_search")}\n\n"
                                    }
                                }
                            ]
                        }
                        yield f"data: {json.dumps(chunk_dict)}\n\n"
                        all_kb_content = []
                        # 用query_knowledge_base函数查询kb_list中所有的知识库
                        for kb in kb_list:
                            kb_content = await query_knowledge_base(kb["kb_id"],user_prompt)
                            all_kb_content.extend(kb_content)
                            if settings["KBSettings"]["is_rerank"]:
                                all_kb_content = await rerank_knowledge_base(user_prompt,all_kb_content)
                        if all_kb_content:
                            all_kb_content = json.dumps(all_kb_content, ensure_ascii=False, indent=4)
                            kb_message = f"\n\n可参考的知识库内容：{all_kb_content}"
                            request.messages[-1]['content'] += f"{kb_message}\n\n用户：{user_prompt}"
                                                    # 获取时间戳和uuid
                            timestamp = time.time()
                            uid = str(uuid.uuid4())
                            # 构造文件名
                            filename = f"{timestamp}_{uid}.txt"
                            # 将搜索结果写入UPLOAD_FILES_DIR文件夹下的filename文件
                            with open(os.path.join(UPLOAD_FILES_DIR, filename), "w", encoding='utf-8') as f:
                                f.write(str(all_kb_content))           
                            # 将文件链接更新为新的链接
                            fileLink=f"{fastapi_base_url}uploaded_files/{filename}"
                            tool_chunk = {
                                "choices": [{
                                    "delta": {
                                        "tool_content": f"\n\n[{await t("search_result")}]({fileLink})\n\n",
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(tool_chunk)}\n\n"
                if settings["KBSettings"]["when"] == "after_thinking" or settings["KBSettings"]["when"] == "both":
                    if kb_list:
                        kb_list_message = f"\n\n可调用的知识库列表：{json.dumps(kb_list, ensure_ascii=False)}"
                        if request.messages and request.messages[0]['role'] == 'system':
                            request.messages[0]['content'] += kb_list_message
                        else:
                            request.messages.insert(0, {'role': 'system', 'content': kb_list_message})
                else:
                    kb_list = []
                if settings['webSearch']['enabled'] or enable_web_search:
                    if settings['webSearch']['when'] == 'before_thinking' or settings['webSearch']['when'] == 'both':
                        chunk_dict = {
                            "id": "webSearch",
                            "choices": [
                                {
                                    "finish_reason": None,
                                    "index": 0,
                                    "delta": {
                                        "role":"assistant",
                                        "content": "",
                                        "tool_content": f"{await t("web_search")}\n\n"
                                    }
                                }
                            ]
                        }
                        yield f"data: {json.dumps(chunk_dict)}\n\n"
                        if settings['webSearch']['engine'] == 'duckduckgo':
                            results = await DDGsearch_async(user_prompt)
                        elif settings['webSearch']['engine'] == 'searxng':
                            results = await searxng_async(user_prompt)
                        elif settings['webSearch']['engine'] == 'tavily':
                            results = await Tavily_search_async(user_prompt)
                        elif settings['webSearch']['engine'] == 'bing':
                            results = await Bing_search_async(user_prompt)
                        elif settings['webSearch']['engine'] == 'google':
                            results = await Google_search_async(user_prompt)
                        elif settings['webSearch']['engine'] == 'brave':
                            results = await Brave_search_async(user_prompt)
                        elif settings['webSearch']['engine'] == 'exa':
                            results = await Exa_search_async(user_prompt)
                        elif settings['webSearch']['engine'] == 'serper':
                            results = await Serper_search_async(user_prompt)
                        elif settings['webSearch']['engine'] == 'bochaai':
                            results = await bochaai_search_async(user_prompt)
                        if results:
                            request.messages[-1]['content'] += f"\n\n联网搜索结果：{results}\n\n请根据联网搜索结果组织你的回答，并确保你的回答是准确的。"
                            # 获取时间戳和uuid
                            timestamp = time.time()
                            uid = str(uuid.uuid4())
                            # 构造文件名
                            filename = f"{timestamp}_{uid}.txt"
                            # 将搜索结果写入uploaded_file文件夹下的filename文件
                            with open(os.path.join(UPLOAD_FILES_DIR, filename), "w", encoding='utf-8') as f:
                                f.write(str(results))           
                            # 将文件链接更新为新的链接
                            fileLink=f"{fastapi_base_url}uploaded_files/{filename}"
                            tool_chunk = {
                                "choices": [{
                                    "delta": {
                                        "tool_content": f"\n\n[{await t("search_result")}]({fileLink})\n\n",
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(tool_chunk)}\n\n"
                    if settings['webSearch']['when'] == 'after_thinking' or settings['webSearch']['when'] == 'both':
                        if settings['webSearch']['engine'] == 'duckduckgo':
                            tools.append(duckduckgo_tool)
                        elif settings['webSearch']['engine'] == 'searxng':
                            tools.append(searxng_tool)
                        elif settings['webSearch']['engine'] == 'tavily':
                            tools.append(tavily_tool)
                        elif settings['webSearch']['engine'] == 'bing':
                            tools.append(bing_tool)
                        elif settings['webSearch']['engine'] == 'google':
                            tools.append(google_tool)
                        elif settings['webSearch']['engine'] == 'brave':
                            tools.append(brave_tool)
                        elif settings['webSearch']['engine'] == 'exa':
                            tools.append(exa_tool)
                        elif settings['webSearch']['crawler'] == 'serper':
                            tools.append(serper_tool)
                        elif settings['webSearch']['crawler'] == 'bochaai':
                            tools.append(bochaai_tool)

                        if settings['webSearch']['crawler'] == 'jina':
                            tools.append(jina_crawler_tool)
                        elif settings['webSearch']['crawler'] == 'crawl4ai':
                            tools.append(Crawl4Ai_tool)
                if kb_list:
                    tools.append(kb_tool)
                if settings['tools']['deepsearch']['enabled'] or enable_deep_research: 
                    deepsearch_messages = copy.deepcopy(request.messages)
                    deepsearch_messages[-1]['content'] += "\n\n将用户提出的问题或给出的当前任务拆分成多个步骤，每一个步骤用一句简短的话概括即可，无需回答或执行这些内容，直接返回总结即可，但不能省略问题或任务的细节。如果用户输入的只是闲聊或者不包含任务和问题，直接把用户输入重复输出一遍即可。如果是非常简单的问题，也可以只给出一个步骤即可。一般情况下都是需要拆分成多个步骤的。"
                    response = await client.chat.completions.create(
                        model=model,
                        messages=deepsearch_messages,
                        temperature=0.5,
                        extra_body = extra_params, # 其他参数
                    )
                    user_prompt = response.choices[0].message.content
                    deepsearch_chunk = {
                        "choices": [{
                            "delta": {
                                "tool_content": f"\n\n💖{await t("start_task")}{user_prompt}\n\n",
                            }
                        }]
                    }
                    yield f"data: {json.dumps(deepsearch_chunk)}\n\n"
                    request.messages[-1]['content'] += f"\n\n如果用户没有提出问题或者任务，直接闲聊即可，如果用户提出了问题或者任务，任务描述不清晰或者你需要进一步了解用户的真实需求，你可以暂时不完成任务，而是分析需要让用户进一步明确哪些需求。"
                # 如果启用推理模型
                if settings['reasoner']['enabled'] or enable_thinking:
                    reasoner_messages = copy.deepcopy(request.messages)
                    if settings['tools']['deepsearch']['enabled'] or enable_deep_research: 
                        reasoner_messages[-1]['content'] += f"\n\n可参考的步骤：{user_prompt}\n\n"
                        drs_msg = get_drs_stage(DRS_STAGE)
                        if drs_msg:
                            reasoner_messages[-1]['content'] += f"\n\n{drs_msg}\n\n"
                    if tools:
                        reasoner_messages[-1]['content'] += f"可用工具：{json.dumps(tools)}"
                    for modelProvider in settings['modelProviders']: 
                        if modelProvider['id'] == settings['reasoner']['selectedProvider']:
                            vendor = modelProvider['vendor']
                            break
                    msg = await images_add_in_messages(reasoner_messages, images,settings)
                    if vendor == 'Ollama':
                        # 流式调用推理模型
                        reasoner_stream = await reasoner_client.chat.completions.create(
                            model=settings['reasoner']['model'],
                            messages=msg,
                            stream=True,
                            temperature=settings['reasoner']['temperature']
                        )
                        full_reasoning = ""
                        buffer = ""  # 跨chunk的内容缓冲区
                        in_reasoning = False  # 是否在标签内
                        
                        async for chunk in reasoner_stream:
                            if not chunk.choices:
                                continue
                            chunk_dict = chunk.model_dump()
                            delta = chunk_dict["choices"][0].get("delta", {})
                            if delta:
                                current_content = delta.get("content", "")
                                buffer += current_content  # 累积到缓冲区
                                
                                # 实时处理缓冲区内容
                                while True:
                                    if not in_reasoning:
                                        # 寻找开放标签
                                        start_pos = buffer.find(open_tag)
                                        if start_pos != -1:
                                            # 开放标签前的内容（非思考内容）
                                            non_reasoning = buffer[:start_pos]
                                            buffer = buffer[start_pos+len(open_tag):]
                                            in_reasoning = True
                                        else:
                                            break  # 无开放标签，保留后续处理
                                    else:
                                        # 寻找闭合标签
                                        end_pos = buffer.find(close_tag)
                                        if end_pos != -1:
                                            # 提取思考内容并构造响应
                                            reasoning_part = buffer[:end_pos]
                                            chunk_dict["choices"][0]["delta"] = {
                                                "reasoning_content": reasoning_part,
                                                "content": ""  # 清除非思考内容
                                            }
                                            yield f"data: {json.dumps(chunk_dict)}\n\n"
                                            full_reasoning += reasoning_part
                                            buffer = buffer[end_pos+len(close_tag):]
                                            in_reasoning = False
                                        else:
                                            # 发送未闭合的中间内容
                                            if buffer:
                                                chunk_dict["choices"][0]["delta"] = {
                                                    "reasoning_content": buffer,
                                                    "content": ""
                                                }
                                                yield f"data: {json.dumps(chunk_dict)}\n\n"
                                                full_reasoning += buffer
                                                buffer = ""
                                            break  # 等待更多内容
                    else:
                        # 流式调用推理模型
                        reasoner_stream = await reasoner_client.chat.completions.create(
                            model=settings['reasoner']['model'],
                            messages=msg,
                            stream=True,
                            max_tokens=1, # 根据实际情况调整
                            temperature=settings['reasoner']['temperature']
                        )
                        full_reasoning = ""
                        # 处理推理模型的流式响应
                        async for chunk in reasoner_stream:
                            if not chunk.choices:
                                continue

                            chunk_dict = chunk.model_dump()
                            delta = chunk_dict["choices"][0].get("delta", {})
                            if delta:
                                reasoning_content = delta.get("reasoning_content", "")
                                if reasoning_content:
                                    full_reasoning += reasoning_content
                            yield f"data: {json.dumps(chunk_dict)}\n\n"

                    # 在推理结束后添加完整推理内容到消息
                    request.messages[-1]['content'] += f"\n\n可参考的推理过程：{full_reasoning}"
                # 状态跟踪变量
                in_reasoning = False
                reasoning_buffer = []
                content_buffer = []
                if settings['tools']['deepsearch']['enabled'] or enable_deep_research: 
                    request.messages[-1]['content'] += f"\n\n可参考的步骤：{user_prompt}\n\n"
                    drs_msg = get_drs_stage(DRS_STAGE)
                    if drs_msg:
                        request.messages[-1]['content'] += f"\n\n{drs_msg}\n\n"
                msg = await images_add_in_messages(request.messages, images,settings)
                if tools:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=msg,  # 添加图片信息到消息
                        temperature=request.temperature,
                        tools=tools,
                        stream=True,
                        max_tokens=request.max_tokens or settings['max_tokens'],
                        top_p=request.top_p or settings['top_p'],
                        frequency_penalty=request.frequency_penalty,
                        presence_penalty=request.presence_penalty,
                        extra_body = extra_params, # 其他参数
                    )
                else:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=msg,  # 添加图片信息到消息
                        temperature=request.temperature,
                        stream=True,
                        max_tokens=request.max_tokens or settings['max_tokens'],
                        top_p=request.top_p or settings['top_p'],
                        frequency_penalty=request.frequency_penalty,
                        presence_penalty=request.presence_penalty,
                        extra_body = extra_params, # 其他参数
                    )
                tool_calls = []
                full_content = ""
                search_not_done = False
                search_task = ""
                async for chunk in response:
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    if choice.delta.tool_calls:  # function_calling
                        for idx, tool_call in enumerate(choice.delta.tool_calls):
                            tool = choice.delta.tool_calls[idx]
                            if len(tool_calls) <= idx:
                                tool_calls.append(tool)
                                continue
                            if tool.function.arguments:
                                # function参数为流式响应，需要拼接
                                if tool_calls[idx].function.arguments:
                                    tool_calls[idx].function.arguments += tool.function.arguments
                                else:
                                    tool_calls[idx].function.arguments = tool.function.arguments
                    else:
                        # 创建原始chunk的拷贝
                        chunk_dict = chunk.model_dump()
                        delta = chunk_dict["choices"][0]["delta"]
                        
                        # 初始化必要字段
                        delta.setdefault("content", "")
                        delta.setdefault("reasoning_content", "")
                        
                        # 优先处理 reasoning_content
                        if delta["reasoning_content"]:
                            yield f"data: {json.dumps(chunk_dict)}\n\n"
                            continue

                        # 处理内容
                        current_content = delta["content"]
                        buffer = current_content
                        
                        while buffer:
                            if not in_reasoning:
                                # 寻找开始标签
                                start_pos = buffer.find(open_tag)
                                if start_pos != -1:
                                    # 处理开始标签前的内容
                                    content_buffer.append(buffer[:start_pos])
                                    buffer = buffer[start_pos+len(open_tag):]
                                    in_reasoning = True
                                else:
                                    content_buffer.append(buffer)
                                    buffer = ""
                            else:
                                # 寻找结束标签
                                end_pos = buffer.find(close_tag)
                                if end_pos != -1:
                                    # 处理思考内容
                                    reasoning_buffer.append(buffer[:end_pos])
                                    buffer = buffer[end_pos+len(close_tag):]
                                    in_reasoning = False
                                else:
                                    reasoning_buffer.append(buffer)
                                    buffer = ""
                        
                        # 构造新的delta内容
                        new_content = "".join(content_buffer)
                        new_reasoning = "".join(reasoning_buffer)
                        
                        # 更新chunk内容
                        delta["content"] = new_content.strip("\x00")  # 保留未完成内容
                        delta["reasoning_content"] = new_reasoning.strip("\x00") or None
                        
                        # 重置缓冲区但保留未完成部分
                        if in_reasoning:
                            content_buffer = [new_content.split(open_tag)[-1]] 
                        else:
                            content_buffer = []
                        reasoning_buffer = []
                        
                        yield f"data: {json.dumps(chunk_dict)}\n\n"
                        full_content += delta.get("content", "")
                # 最终flush未完成内容
                if content_buffer or reasoning_buffer:
                    final_chunk = {
                        "choices": [{
                            "delta": {
                                "content": "".join(content_buffer),
                                "reasoning_content": "".join(reasoning_buffer)
                            }
                        }]
                    }
                    yield f"data: {json.dumps(final_chunk)}\n\n"
                    full_content += final_chunk["choices"][0]["delta"].get("content", "")
                if tool_calls:
                    pass
                elif settings['tools']['deepsearch']['enabled'] or enable_deep_research: 
                    search_prompt = get_drs_stage_system_message(DRS_STAGE,user_prompt,full_content)
                    response = await client.chat.completions.create(
                        model=model,
                        messages=[
                            {
                            "role": "system",
                            "content": source_prompt,
                            },
                            {
                            "role": "user",
                            "content": search_prompt,
                            }
                        ],
                        temperature=0.5,
                        extra_body = extra_params, # 其他参数
                    )
                    response_content = response.choices[0].message.content
                    # 用re 提取```json 包裹json字符串 ```
                    if "```json" in response_content:
                        try:
                            response_content = re.search(r'```json(.*?)```', response_content, re.DOTALL).group(1)
                        except:
                            # 用re 提取```json 之后的内容
                            response_content = re.search(r'```json(.*?)', response_content, re.DOTALL).group(1)
                    try:
                        response_content = json.loads(response_content)
                    except json.JSONDecodeError:
                        search_chunk = {
                            "choices": [{
                                "delta": {
                                    "tool_content": f"\n\n❌{await t("task_error")}\n\n",
                                }
                            }]
                        }
                        yield f"data: {json.dumps(search_chunk)}\n\n"
                    if response_content["status"] == "done":
                        search_chunk = {
                            "choices": [{
                                "delta": {
                                    "tool_content": f"\n\n✅{await t("task_done")}\n\n",
                                }
                            }]
                        }
                        yield f"data: {json.dumps(search_chunk)}\n\n"
                        search_not_done = False
                    elif response_content["status"] == "not_done":
                        search_chunk = {
                            "choices": [{
                                "delta": {
                                    "tool_content": f"\n\n❎{await t("task_not_done")}\n\n",
                                }
                            }]
                        }
                        yield f"data: {json.dumps(search_chunk)}\n\n"
                        search_not_done = True
                        search_task = response_content["unfinished_task"]
                        task_prompt = f"请继续完成初始任务中未完成的任务：\n\n{search_task}\n\n初始任务：{user_prompt}\n\n最后，请给出完整的初始任务的最终结果。"
                        request.messages.append(
                            {
                                "role": "assistant",
                                "content": full_content,
                            }
                        )
                        request.messages.append(
                            {
                                "role": "user",
                                "content": task_prompt,
                            }
                        )
                    elif response_content["status"] == "need_more_info":
                        DRS_STAGE = 2
                        search_chunk = {
                            "choices": [{
                                "delta": {
                                    "tool_content": f"\n\n❓{await t("task_need_more_info")}\n\n"
                                }
                            }]
                        }
                        yield f"data: {json.dumps(search_chunk)}\n\n"
                        search_not_done = False
                    elif response_content["status"] == "search":
                        DRS_STAGE = 2
                        search_chunk = {
                            "choices": [{
                                "delta": {
                                    "tool_content": f"\n\n🔍{await t("enter_search_stage")}\n\n"
                                }
                            }]
                        }
                        yield f"data: {json.dumps(search_chunk)}\n\n"
                        search_not_done = True
                        drs_msg = get_drs_stage(DRS_STAGE)
                        request.messages.append(
                            {
                                "role": "assistant",
                                "content": full_content,
                            }
                        )
                        request.messages.append(
                            {
                                "role": "user",
                                "content": drs_msg,
                            }
                        )
                    elif response_content["status"] == "need_more_search":
                        DRS_STAGE = 2
                        search_chunk = {
                            "choices": [{
                                "delta": {
                                    "tool_content": f"\n\n🔍{await t("need_more_search")}\n\n"
                                }
                            }]
                        }
                        yield f"data: {json.dumps(search_chunk)}\n\n"
                        search_not_done = True
                        search_task = response_content["unfinished_task"]
                        task_prompt = f"请继续查询如下信息：\n\n{search_task}\n\n初始任务：{user_prompt}\n\n"
                        request.messages.append(
                            {
                                "role": "assistant",
                                "content": full_content,
                            }
                        )
                        request.messages.append(
                            {
                                "role": "user",
                                "content": task_prompt,
                            }
                        )
                    elif response_content["status"] == "answer":
                        DRS_STAGE = 3
                        search_chunk = {
                            "choices": [{
                                "delta": {
                                    "tool_content": f"\n\n⭐{await t("enter_answer_stage")}\n\n"
                                }
                            }]
                        }
                        yield f"data: {json.dumps(search_chunk)}\n\n"
                        search_not_done = True
                        drs_msg = get_drs_stage(DRS_STAGE)
                        request.messages.append(
                            {
                                "role": "assistant",
                                "content": full_content,
                            }
                        )
                        request.messages.append(
                            {
                                "role": "user",
                                "content": drs_msg,
                            }
                        )
                reasoner_messages = copy.deepcopy(request.messages)
                while tool_calls or search_not_done:
                    full_content = ""
                    if tool_calls:
                        response_content = tool_calls[0].function
                        if response_content.name in  ["DDGsearch_async","searxng_async", "Bing_search_async", "Google_search_async", "Brave_search_async", "Exa_search_async", "Serper_search_async","bochaai_search_async"]:
                            chunk_dict = {
                                "id": "agentParty",
                                "choices": [
                                    {
                                        "finish_reason": None,
                                        "index": 0,
                                        "delta": {
                                            "role":"assistant",
                                            "content": "",
                                            "tool_content": f"\n\n{await t("web_search")}\n\n"
                                        }
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(chunk_dict)}\n\n"
                        elif response_content.name in  ["jina_crawler_async","Crawl4Ai_search_async"]:
                            chunk_dict = {
                                "id": "agentParty",
                                "choices": [
                                    {
                                        "finish_reason": None,
                                        "index": 0,
                                        "delta": {
                                            "role":"assistant",
                                            "content": "",
                                            "tool_content": f"\n\n{await t("web_search_more")}\n\n"
                                        }
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(chunk_dict)}\n\n"
                        elif response_content.name in ["query_knowledge_base"]:
                            chunk_dict = {
                                "id": "agentParty",
                                "choices": [
                                    {
                                        "finish_reason": None,
                                        "index": 0,
                                        "delta": {
                                            "role":"assistant",
                                            "content": "",
                                            "tool_content": f"\n\n{await t("knowledge_base")}\n\n"
                                        }
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(chunk_dict)}\n\n"
                        else:
                            chunk_dict = {
                                "id": "agentParty",
                                "choices": [
                                    {
                                        "finish_reason": None,
                                        "index": 0,
                                        "delta": {
                                            "role":"assistant",
                                            "content": "",
                                            "tool_content": f"\n\n{await t("call")}{response_content.name}{await t("tool")}\n\n"
                                        }
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(chunk_dict)}\n\n"
                        modified_data = '[' + response_content.arguments.replace('}{', '},{') + ']'
                        # 使用json.loads来解析修改后的字符串为列表
                        data_list = json.loads(modified_data)
                        if settings['tools']['asyncTools']['enabled']:
                            tool_id = uuid.uuid4()
                            async_tool_id = f"{response_content.name}_{tool_id}"
                            chunk_dict = {
                                "id": "agentParty",
                                "choices": [
                                    {
                                        "finish_reason": None,
                                        "index": 0,
                                        "delta": {
                                            "role":"assistant",
                                            "content": "",
                                            "async_tool_id": async_tool_id
                                        }
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(chunk_dict)}\n\n"
                            # 启动异步任务并记录状态
                            asyncio.create_task(
                                execute_async_tool(
                                    async_tool_id,
                                    response_content.name,
                                    data_list[0],
                                    settings,
                                    user_prompt
                                )
                            )
                            
                            async with async_tools_lock:
                                async_tools[async_tool_id] = {
                                    "status": "pending",
                                    "result": None,
                                    "name":response_content.name,
                                    "parameters":data_list[0]
                                }
                            results = f"{response_content.name}工具已成功启动，获取结果需要花费很久的时间。请不要再次调用该工具，因为工具结果将生成后自动发送，再次调用也不能更快的获取到结果。请直接告诉用户，你会在获得结果后回答他的问题。"
                        else:
                            results = await dispatch_tool(response_content.name, data_list[0],settings)
                        if results is None:
                            chunk = {
                                "id": "extra_tools",
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "role":"assistant",
                                            "content": "",
                                            "tool_calls":modified_data,
                                        }
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(chunk)}\n\n"
                            break
                        if response_content.name in ["query_knowledge_base"] and type(results) == list:
                            if settings["KBSettings"]["is_rerank"]:
                                results = await rerank_knowledge_base(user_prompt,results)
                            results = json.dumps(results, ensure_ascii=False, indent=4)
                        request.messages.append(
                            {
                                "tool_calls": [
                                    {
                                        "id": tool_calls[0].id,
                                        "function": {
                                            "arguments": json.dumps(data_list[0]),
                                            "name": response_content.name,
                                        },
                                        "type": tool_calls[0].type,
                                    }
                                ],
                                "role": "assistant",
                                "content": str(response_content),
                            }
                        )
                        request.messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_calls[0].id,
                                "name": response_content.name,
                                "content": str(results),
                            }
                        )
                        if (settings['webSearch']['when'] == 'after_thinking' or settings['webSearch']['when'] == 'both') and settings['tools']['asyncTools']['enabled'] is False:
                            request.messages[-1]['content'] += f"\n对于联网搜索的结果，如果联网搜索的信息不足以回答问题时，你可以进一步使用联网搜索查询还未给出的必要信息。如果已经足够回答问题，请直接回答问题。"
                        if settings['tools']['asyncTools']['enabled']:
                            reasoner_messages.append(
                                {
                                    "role": "assistant",
                                    "content": str(response_content),
                                }
                            )
                            reasoner_messages.append(
                                {
                                    "role": "system",
                                    "content": f"{response_content.name}工具已成功启动，获取结果需要花费很久的时间。请不要再次调用该工具，因为工具结果将生成后自动发送，再次调用也不能更快的获取到结果。请直接告诉用户，你会在获得结果后回答他的问题。",
                                }
                            )
                        else:
                            reasoner_messages.append(
                                {
                                    "role": "assistant",
                                    "content": str(response_content),
                                }
                            )
                            reasoner_messages.append(
                                {
                                    "role": "system",
                                    "content": f"{response_content.name}工具结果："+str(results),
                                }
                            )
                            # 获取时间戳和uuid
                            timestamp = time.time()
                            uid = str(uuid.uuid4())
                            # 构造文件名
                            filename = f"{timestamp}_{uid}.txt"
                            # 将搜索结果写入uploaded_file文件夹下的filename文件
                            with open(os.path.join(UPLOAD_FILES_DIR, filename), "w", encoding='utf-8') as f:
                                f.write(str(results))            
                            # 将文件链接更新为新的链接
                            fileLink=f"{fastapi_base_url}uploaded_files/{filename}"
                            tool_chunk = {
                                "choices": [{
                                    "delta": {
                                        "tool_content": f"\n\n[{response_content.name}{await t("tool_result")}]({fileLink})\n\n",
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(tool_chunk)}\n\n"
                    # 如果启用推理模型
                    if settings['reasoner']['enabled'] or enable_thinking:
                        if tools:
                            reasoner_messages[-1]['content'] += f"可用工具：{json.dumps(tools)}"
                        for modelProvider in settings['modelProviders']: 
                            if modelProvider['id'] == settings['reasoner']['selectedProvider']:
                                vendor = modelProvider['vendor']
                                break
                        msg = await images_add_in_messages(reasoner_messages, images,settings)
                        if vendor == 'Ollama':
                            # 流式调用推理模型
                            reasoner_stream = await reasoner_client.chat.completions.create(
                                model=settings['reasoner']['model'],
                                messages=msg,
                                stream=True,
                                temperature=settings['reasoner']['temperature']
                            )
                            full_reasoning = ""
                            buffer = ""  # 跨chunk的内容缓冲区
                            in_reasoning = False  # 是否在标签内
                            
                            async for chunk in reasoner_stream:
                                if not chunk.choices:
                                    continue
                                chunk_dict = chunk.model_dump()
                                delta = chunk_dict["choices"][0].get("delta", {})
                                if delta:
                                    current_content = delta.get("content", "")
                                    buffer += current_content  # 累积到缓冲区
                                    
                                    # 实时处理缓冲区内容
                                    while True:
                                        if not in_reasoning:
                                            # 寻找开放标签
                                            start_pos = buffer.find(open_tag)
                                            if start_pos != -1:
                                                # 开放标签前的内容（非思考内容）
                                                non_reasoning = buffer[:start_pos]
                                                buffer = buffer[start_pos+len(open_tag):]
                                                in_reasoning = True
                                            else:
                                                break  # 无开放标签，保留后续处理
                                        else:
                                            # 寻找闭合标签
                                            end_pos = buffer.find(close_tag)
                                            if end_pos != -1:
                                                # 提取思考内容并构造响应
                                                reasoning_part = buffer[:end_pos]
                                                chunk_dict["choices"][0]["delta"] = {
                                                    "reasoning_content": reasoning_part,
                                                    "content": ""  # 清除非思考内容
                                                }
                                                yield f"data: {json.dumps(chunk_dict)}\n\n"
                                                full_reasoning += reasoning_part
                                                buffer = buffer[end_pos+len(close_tag):]
                                                in_reasoning = False
                                            else:
                                                # 发送未闭合的中间内容
                                                if buffer:
                                                    chunk_dict["choices"][0]["delta"] = {
                                                        "reasoning_content": buffer,
                                                        "content": ""
                                                    }
                                                    yield f"data: {json.dumps(chunk_dict)}\n\n"
                                                    full_reasoning += buffer
                                                    buffer = ""
                                                break  # 等待更多内容
                        else:
                            # 流式调用推理模型
                            reasoner_stream = await reasoner_client.chat.completions.create(
                                model=settings['reasoner']['model'],
                                messages=msg,
                                stream=True,
                                max_tokens=1, # 根据实际情况调整
                                temperature=settings['reasoner']['temperature']
                            )
                            full_reasoning = ""
                            # 处理推理模型的流式响应
                            async for chunk in reasoner_stream:
                                if not chunk.choices:
                                    continue

                                chunk_dict = chunk.model_dump()
                                delta = chunk_dict["choices"][0].get("delta", {})
                                if delta:
                                    reasoning_content = delta.get("reasoning_content", "")
                                    if reasoning_content:
                                        full_reasoning += reasoning_content
                                yield f"data: {json.dumps(chunk_dict)}\n\n"

                        # 在推理结束后添加完整推理内容到消息
                        request.messages[-1]['content'] += f"\n\n可参考的推理过程：{full_reasoning}"
                    msg = await images_add_in_messages(request.messages, images,settings)
                    if tools:
                        response = await client.chat.completions.create(
                            model=model,
                            messages=msg,  # 添加图片信息到消息
                            temperature=request.temperature,
                            tools=tools,
                            stream=True,
                            max_tokens=request.max_tokens or settings['max_tokens'],
                            top_p=request.top_p or settings['top_p'],
                            frequency_penalty=request.frequency_penalty,
                            presence_penalty=request.presence_penalty,
                            extra_body = extra_params, # 其他参数
                        )
                    else:
                        response = await client.chat.completions.create(
                            model=model,
                            messages=msg,  # 添加图片信息到消息
                            temperature=request.temperature,
                            stream=True,
                            max_tokens=request.max_tokens or settings['max_tokens'],
                            top_p=request.top_p or settings['top_p'],
                            frequency_penalty=request.frequency_penalty,
                            presence_penalty=request.presence_penalty,
                            extra_body = extra_params, # 其他参数
                        )
                    tool_calls = []
                    async for chunk in response:
                        if not chunk.choices:
                            continue
                        if chunk.choices:
                            choice = chunk.choices[0]
                            if choice.delta.tool_calls:  # function_calling
                                for idx, tool_call in enumerate(choice.delta.tool_calls):
                                    tool = choice.delta.tool_calls[idx]
                                    if len(tool_calls) <= idx:
                                        tool_calls.append(tool)
                                        continue
                                    if tool.function.arguments:
                                        # function参数为流式响应，需要拼接
                                        if tool_calls[idx].function.arguments:
                                            tool_calls[idx].function.arguments += tool.function.arguments
                                        else:
                                            tool_calls[idx].function.arguments = tool.function.arguments
                            else:
                                # 创建原始chunk的拷贝
                                chunk_dict = chunk.model_dump()
                                delta = chunk_dict["choices"][0]["delta"]
                                
                                # 初始化必要字段
                                delta.setdefault("content", "")
                                delta.setdefault("reasoning_content", "")

                                # 优先处理 reasoning_content
                                if delta["reasoning_content"]:
                                    yield f"data: {json.dumps(chunk_dict)}\n\n"
                                    continue
                                
                                # 处理内容
                                current_content = delta["content"]
                                buffer = current_content
                                
                                while buffer:
                                    if not in_reasoning:
                                        # 寻找开始标签
                                        start_pos = buffer.find(open_tag)
                                        if start_pos != -1:
                                            # 处理开始标签前的内容
                                            content_buffer.append(buffer[:start_pos])
                                            buffer = buffer[start_pos+len(open_tag):]
                                            in_reasoning = True
                                        else:
                                            content_buffer.append(buffer)
                                            buffer = ""
                                    else:
                                        # 寻找结束标签
                                        end_pos = buffer.find(close_tag)
                                        if end_pos != -1:
                                            # 处理思考内容
                                            reasoning_buffer.append(buffer[:end_pos])
                                            buffer = buffer[end_pos+len(close_tag):]
                                            in_reasoning = False
                                        else:
                                            reasoning_buffer.append(buffer)
                                            buffer = ""
                                
                                # 构造新的delta内容
                                new_content = "".join(content_buffer)
                                new_reasoning = "".join(reasoning_buffer)
                                
                                # 更新chunk内容
                                delta["content"] = new_content.strip("\x00")  # 保留未完成内容
                                delta["reasoning_content"] = new_reasoning.strip("\x00") or None
                                
                                # 重置缓冲区但保留未完成部分
                                if in_reasoning:
                                    content_buffer = [new_content.split(open_tag)[-1]] 
                                else:
                                    content_buffer = []
                                reasoning_buffer = []
                                
                                yield f"data: {json.dumps(chunk_dict)}\n\n"
                                full_content += delta.get("content", "")
                    # 最终flush未完成内容
                    if content_buffer or reasoning_buffer:
                        final_chunk = {
                            "choices": [{
                                "delta": {
                                    "content": "".join(content_buffer),
                                    "reasoning_content": "".join(reasoning_buffer)
                                }
                            }]
                        }
                        yield f"data: {json.dumps(final_chunk)}\n\n"
                        full_content += final_chunk["choices"][0]["delta"].get("content", "")
                    if tool_calls:
                        pass
                    elif settings['tools']['deepsearch']['enabled'] or enable_deep_research: 
                        search_prompt = get_drs_stage_system_message(DRS_STAGE,user_prompt,full_content)
                        response = await client.chat.completions.create(
                            model=model,
                            messages=[                        
                                {
                                "role": "system",
                                "content": source_prompt,
                                },
                                {
                                "role": "user",
                                "content": search_prompt,
                                }
                            ],
                            temperature=0.5,
                            extra_body = extra_params, # 其他参数
                        )
                        response_content = response.choices[0].message.content
                        # 用re 提取```json 包裹json字符串 ```
                        if "```json" in response_content:
                            try:
                                response_content = re.search(r'```json(.*?)```', response_content, re.DOTALL).group(1)
                            except:
                                # 用re 提取```json 之后的内容
                                response_content = re.search(r'```json(.*?)', response_content, re.DOTALL).group(1)
                        try:
                            response_content = json.loads(response_content)
                        except json.JSONDecodeError:
                            search_chunk = {
                                "choices": [{
                                    "delta": {
                                        "tool_content": f"\n\n❌{await t("task_error")}\n\n",
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(search_chunk)}\n\n"
                        if response_content["status"] == "done":
                            search_chunk = {
                                "choices": [{
                                    "delta": {
                                        "tool_content": f"\n\n✅{await t("task_done")}\n\n",
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(search_chunk)}\n\n"
                            search_not_done = False
                        elif response_content["status"] == "not_done":
                            search_chunk = {
                                "choices": [{
                                    "delta": {
                                        "tool_content": f"\n\n❎{await t("task_not_done")}\n\n",
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(search_chunk)}\n\n"
                            search_not_done = True
                            search_task = response_content["unfinished_task"]
                            task_prompt = f"请继续完成初始任务中未完成的任务：\n\n{search_task}\n\n初始任务：{user_prompt}\n\n最后，请给出完整的初始任务的最终结果。"
                            request.messages.append(
                                {
                                    "role": "assistant",
                                    "content": full_content,
                                }
                            )
                            request.messages.append(
                                {
                                    "role": "user",
                                    "content": task_prompt,
                                }
                            )
                        elif response_content["status"] == "need_more_info":
                            DRS_STAGE = 2
                            search_chunk = {
                                "choices": [{
                                    "delta": {
                                        "tool_content": f"\n\n❓{await t("task_need_more_info")}\n\n"
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(search_chunk)}\n\n"
                            search_not_done = False
                        elif response_content["status"] == "search":
                            DRS_STAGE = 2
                            search_chunk = {
                                "choices": [{
                                    "delta": {
                                        "tool_content": f"\n\n🔍{await t("enter_search_stage")}\n\n"
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(search_chunk)}\n\n"
                            search_not_done = True
                            drs_msg = get_drs_stage(DRS_STAGE)
                            request.messages.append(
                                {
                                    "role": "assistant",
                                    "content": full_content,
                                }
                            )
                            request.messages.append(
                                {
                                    "role": "user",
                                    "content": drs_msg,
                                }
                            )
                        elif response_content["status"] == "need_more_search":
                            DRS_STAGE = 2
                            search_chunk = {
                                "choices": [{
                                    "delta": {
                                        "tool_content": f"\n\n🔍{await t("need_more_search")}\n\n"
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(search_chunk)}\n\n"
                            search_not_done = True
                            search_task = response_content["unfinished_task"]
                            task_prompt = f"请继续查询如下信息：\n\n{search_task}\n\n初始任务：{user_prompt}\n\n"
                            request.messages.append(
                                {
                                    "role": "assistant",
                                    "content": full_content,
                                }
                            )
                            request.messages.append(
                                {
                                    "role": "user",
                                    "content": task_prompt,
                                }
                            )
                        elif response_content["status"] == "answer":
                            DRS_STAGE = 3
                            search_chunk = {
                                "choices": [{
                                    "delta": {
                                        "tool_content": f"\n\n⭐{await t("enter_answer_stage")}\n\n"
                                    }
                                }]
                            }
                            yield f"data: {json.dumps(search_chunk)}\n\n"
                            search_not_done = True
                            drs_msg = get_drs_stage(DRS_STAGE)
                            request.messages.append(
                                {
                                    "role": "assistant",
                                    "content": full_content,
                                }
                            )
                            request.messages.append(
                                {
                                    "role": "user",
                                    "content": drs_msg,
                                }
                            )
                yield "data: [DONE]\n\n"
                if m0:
                    messages=[
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                        {
                            "role": "assistant",
                            "content": full_content,
                        }
                    ]
                    executor = ThreadPoolExecutor()
                    async def add_async():
                        loop = asyncio.get_event_loop()
                        # 绑定 user_id 关键字参数
                        func = partial(m0.add, user_id=memoryId)
                        # 传递 messages 作为位置参数
                        await loop.run_in_executor(executor, func, messages)
                        print("知识库更新完成")

                    asyncio.create_task(add_async())
                    print("知识库更新任务已提交")
                return
            except Exception as e:
                # 捕获异常并返回错误信息
                error_chunk = {
                    "choices": [{
                        "delta": {
                            "tool_content": f"❌ {str(e)}\n\n",
                        }
                    }]
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
                yield "data: [DONE]\n\n"  # 确保最终结束
                return
        
        return StreamingResponse(
            stream_generator(user_prompt, DRS_STAGE),
            media_type="text/event-stream",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except Exception as e:
        # 如果e.status_code存在，则使用它作为HTTP状态码，否则使用500
        return JSONResponse(
            status_code=getattr(e, "status_code", 500),
            content={"error": str(e)},
        )

async def generate_complete_response(client,reasoner_client, request: ChatRequest, settings: dict,fastapi_base_url,enable_thinking,enable_deep_research,enable_web_search):
    global mcp_client_list
    DRS_STAGE = 1 # 1: 明确用户需求阶段 2: 查询搜索阶段 3: 生成结果阶段
    from py.load_files import get_files_content,file_tool,image_tool
    from py.web_search import (
        DDGsearch_async, 
        searxng_async, 
        Tavily_search_async,
        Bing_search_async,
        Google_search_async,
        Brave_search_async,
        Exa_search_async,
        Serper_search_async,
        bochaai_search_async,
        duckduckgo_tool, 
        searxng_tool, 
        tavily_tool, 
        bing_tool,
        google_tool,
        brave_tool,
        exa_tool,
        serper_tool,
        bochaai_tool,
        jina_crawler_tool, 
        Crawl4Ai_tool
    )
    from py.know_base import kb_tool,query_knowledge_base,rerank_knowledge_base
    from py.agent_tool import get_agent_tool
    from py.a2a_tool import get_a2a_tool
    from py.llm_tool import get_llm_tool
    from py.pollinations import pollinations_image_tool,openai_image_tool,siliconflow_image_tool
    from py.code_interpreter import e2b_code_tool,local_run_code_tool
    m0 = None
    if settings["memorySettings"]["is_memory"]:
        memoryId = settings["memorySettings"]["selectedMemory"]
        cur_memory = None
        for memory in settings["memories"]:
            if memory["id"] == memoryId:
                cur_memory = memory
                break
        if cur_memory:

            config={
                "embedder": {
                    "provider": 'openai',
                    "config": {
                        "model": cur_memory['model'],
                        "api_key": cur_memory['api_key'],
                        "openai_base_url":cur_memory["base_url"],
                        "embedding_dims":1024
                    },
                },
                "llm": {
                    "provider": 'openai',
                    "config": {
                        "model": settings['model'],
                        "api_key": settings['api_key'],
                        "openai_base_url":settings["base_url"]
                    }
                },
                "vector_store": {
                    "provider": "faiss",
                    "config": {
                        "collection_name": "agent-party",
                        "path": os.path.join(MEMORY_CACHE_DIR,memoryId),
                        "distance_strategy": "euclidean",
                        "embedding_model_dims": 1024
                    }
                }
            }
            m0 = Memory.from_config(config)
    images = await images_in_messages(request.messages,fastapi_base_url)
    request.messages = await message_without_images(request.messages)
    open_tag = "<think>"
    close_tag = "</think>"
    tools = request.tools or []
    tools = request.tools or []
    if mcp_client_list:
        for server_name, mcp_client in mcp_client_list.items():
            if server_name in settings['mcpServers']:
                if 'disabled' not in settings['mcpServers'][server_name]:
                    settings['mcpServers'][server_name]['disabled'] = False
                if settings['mcpServers'][server_name]['disabled'] == False and settings['mcpServers'][server_name]['processingStatus'] == 'ready':
                    function = await mcp_client.get_openai_functions()
                    if function:
                        tools.extend(function)
    get_llm_tool_fuction = await get_llm_tool(settings)
    if get_llm_tool_fuction:
        tools.append(get_llm_tool_fuction)
    get_agent_tool_fuction = await get_agent_tool(settings)
    if get_agent_tool_fuction:
        tools.append(get_agent_tool_fuction)
    get_a2a_tool_fuction = await get_a2a_tool(settings)
    if get_a2a_tool_fuction:
        tools.append(get_a2a_tool_fuction)
    if settings['text2imgSettings']['enabled']:
        if settings['text2imgSettings']['engine'] == 'pollinations':
            tools.append(pollinations_image_tool)
        elif settings['text2imgSettings']['engine'] == 'openai':
            if settings['text2imgSettings']['vendor'] == 'siliconflow':
                tools.append(siliconflow_image_tool)
            else:
                tools.append(openai_image_tool)
    if settings['tools']['getFile']['enabled']:
        tools.append(file_tool)
        tools.append(image_tool)
    if settings["codeSettings"]['enabled']:
        if settings["codeSettings"]["engine"] == "e2b":
            tools.append(e2b_code_tool)
        elif settings["codeSettings"]["engine"] == "sandbox":
            tools.append(local_run_code_tool)
    if settings["custom_http"]:
        for custom_http in settings["custom_http"]:
            if custom_http["enabled"]:
                if custom_http['body'] == "":
                    custom_http['body'] = "{}"
                custom_http_tool = {
                    "type": "function",
                    "function": {
                        "name": f"custom_http_{custom_http['name']}",
                        "description": f"{custom_http['description']}",
                        "parameters": json.loads(custom_http['body']),
                    },
                }
                tools.append(custom_http_tool)
    if settings["workflows"]:
        for workflow in settings["workflows"]:
            if workflow["enabled"]:
                comfyui_properties = {}
                comfyui_required = []
                if workflow["text_input"] is not None:
                    comfyui_properties["text_input"] = {
                        "description": "第一个文字输入，需要输入的提示词，用于生成图片或者视频，如果无特别提示，默认为英文",
                        "type": "string"
                    }
                    comfyui_required.append("text_input")
                if workflow["text_input_2"] is not None:
                    comfyui_properties["text_input_2"] = {
                        "description": "第二个文字输入，需要输入的提示词，用于生成图片或者视频，如果无特别提示，默认为英文",
                        "type": "string"
                    }
                    comfyui_required.append("text_input_2")
                if workflow["image_input"] is not None:
                    comfyui_properties["image_input"] = {
                        "description": "第一个图片输入，需要输入的图片，必须是图片URL，可以是外部链接，也可以是服务器内部的URL，例如：https://www.example.com/xxx.png  或者  http://127.0.0.1:3456/xxx.jpg",
                        "type": "string"
                    }
                    comfyui_required.append("image_input")
                if workflow["image_input_2"] is not None:
                    comfyui_properties["image_input_2"] = {
                        "description": "第二个图片输入，需要输入的图片，必须是图片URL，可以是外部链接，也可以是服务器内部的URL，例如：https://www.example.com/xxx.png  或者  http://127.0.0.1:3456/xxx.jpg",
                        "type": "string"
                    }
                    comfyui_required.append("image_input_2")
                comfyui_parameters = {
                    "type": "object",
                    "properties": comfyui_properties,
                    "required": comfyui_required
                }
                comfyui_tool = {
                    "type": "function",
                    "function": {
                        "name": f"comfyui_{workflow['unique_filename']}",
                        "description": f"{workflow['description']}+\n如果要输入图片提示词或者修改提示词，尽可能使用英语。\n返回的图片结果，请将图片的URL放入![image]()这样的markdown语法中，用户才能看到图片。如果是视频，请将视频的URL放入<video controls> <source src=''></video>的中src中，用户才能看到视频。如果有多个结果，则请用换行符分隔开这几个图片或者视频，用户才能看到多个结果。",
                        "parameters": comfyui_parameters,
                    },
                }
                tools.append(comfyui_tool)
    search_not_done = False
    search_task = ""
    try:
        model = settings['model']
        extra_params = settings['extra_params']
        # 移除extra_params这个list中"name"不包含非空白符的键值对
        if extra_params:
            for extra_param in extra_params:
                if not extra_param['name'].strip():
                    extra_params.remove(extra_param)
            # 列表转换为字典
            extra_params = {item['name']: item['value'] for item in extra_params}
        else:
            extra_params = {}
        if request.fileLinks:
            # 异步获取文件内容
            files_content = await get_files_content(request.fileLinks)
            system_message = f"\n\n相关文件内容：{files_content}"
            
            # 修复字符串拼接错误
            if request.messages and request.messages[0]['role'] == 'system':
                request.messages[0]['content'] += system_message
            else:
                request.messages.insert(0, {'role': 'system', 'content': system_message})
        kb_list = []
        user_prompt = request.messages[-1]['content']
        if m0:
            lore_content = ""
            assistant_reply = ""
            # 找出request.messages中上次的assistant回复
            for i in range(len(request.messages)-1, -1, -1):
                if request.messages[i]['role'] == 'assistant':
                    assistant_reply = request.messages[i]['content']
                    break
            if cur_memory["lorebook"]:
                for lore in cur_memory["lorebook"]:
                    if lore["name"] != "" and (lore["name"] in user_prompt or lore["name"] in assistant_reply):
                        lore_content = lore_content + "\n\n" + f"{lore['name']}：{lore['value']}"
            global cur_random 
            # 如果request.messages中不包含assistant回复，说明是首次提问，触发随机设定
            if not assistant_reply:
                # 如果 cur_memory 中有 random 条目
                if cur_memory.get("random") and len(cur_memory["random"]) > 0:
                    # 随机选择一个 random 条目
                    random_entry = random.choice(cur_memory["random"])
                    if random_entry.get("value"):
                        lore_content = lore_content + "\n\n" + f"{random_entry['value']}"
                        cur_random.append({"id":memoryId,"value":random_entry["value"]})
                        print("新随机设定：",{"id":memoryId,"value":random_entry["value"]})
            else:
                for item in cur_random:
                    if item["id"] == memoryId:
                        lore_content = lore_content + "\n\n" + f"{item['value']}"
                        print("沿用随机设定：",{"id":memoryId,"value":item['value']})  
                        break  
            memoryLimit = settings["memorySettings"]["memoryLimit"]
            try:
                print("查询记忆")
                relevant_memories = m0.search(query=user_prompt, user_id=memoryId, limit=memoryLimit)
                relevant_memories = json.dumps(relevant_memories, ensure_ascii=False)
                print("查询记忆结束")
            except Exception as e:
                print("m0.search error:",e)
                relevant_memories = ""
            if request.messages and request.messages[0]['role'] == 'system':
                request.messages[0]['content'] += "之前的相关记忆：\n\n" + relevant_memories + "\n\n相关结束\n\n"
            else:
                request.messages.insert(0, {'role': 'system', 'content': "之前的相关记忆：\n\n" + relevant_memories + "\n\n相关结束\n\n"})
            if cur_memory["basic_character"]:
                print("添加角色设定：\n\n" + cur_memory["basic_character"] + "\n\n角色设定结束\n\n")
                if request.messages and request.messages[0]['role'] == 'system':
                    request.messages[0]['content'] += "角色设定：\n\n" + cur_memory["basic_character"] + "\n\n角色设定结束\n\n"
                else:
                    request.messages.insert(0, {'role': 'system', 'content': "角色设定：\n\n" + cur_memory["basic_character"] + "\n\n角色设定结束\n\n"})
            if lore_content:
                print("添加世界观设定：\n\n" + lore_content + "\n\n世界观设定结束\n\n")
                if request.messages and request.messages[0]['role'] == 'system':
                    request.messages[0]['content'] += "世界观设定：\n\n" + lore_content + "\n\n世界观设定结束\n\n"
                else:
                    request.messages.insert(0, {'role': 'system', 'content': "世界观设定：\n\n" + lore_content + "\n\n世界观设定结束\n\n"})
        if settings["knowledgeBases"]:
            for kb in settings["knowledgeBases"]:
                if kb["enabled"] and kb["processingStatus"] == "completed":
                    kb_list.append({"kb_id":kb["id"],"name": kb["name"],"introduction":kb["introduction"]})
        if settings["KBSettings"]["when"] == "before_thinking" or settings["KBSettings"]["when"] == "both":
            if kb_list:
                all_kb_content = []
                # 用query_knowledge_base函数查询kb_list中所有的知识库
                for kb in kb_list:
                    kb_content = await query_knowledge_base(kb["kb_id"],user_prompt)
                    all_kb_content.extend(kb_content)
                    if settings["KBSettings"]["is_rerank"]:
                        all_kb_content = await rerank_knowledge_base(user_prompt,all_kb_content)
                if all_kb_content:
                    kb_message = f"\n\n可参考的知识库内容：{all_kb_content}"
                    request.messages[-1]['content'] += f"{kb_message}\n\n用户：{user_prompt}"
        if settings["KBSettings"]["when"] == "after_thinking" or settings["KBSettings"]["when"] == "both":
            if kb_list:
                kb_list_message = f"\n\n可调用的知识库列表：{json.dumps(kb_list, ensure_ascii=False)}"
                if request.messages and request.messages[0]['role'] == 'system':
                    request.messages[0]['content'] += kb_list_message
                else:
                    request.messages.insert(0, {'role': 'system', 'content': kb_list_message})
        else:
            kb_list = []
        request = await tools_change_messages(request, settings)
        if settings['webSearch']['enabled'] or enable_web_search:
            if settings['webSearch']['when'] == 'before_thinking' or settings['webSearch']['when'] == 'both':
                if settings['webSearch']['engine'] == 'duckduckgo':
                    results = await DDGsearch_async(user_prompt)
                elif settings['webSearch']['engine'] == 'searxng':
                    results = await searxng_async(user_prompt)
                elif settings['webSearch']['engine'] == 'tavily':
                    results = await Tavily_search_async(user_prompt)
                elif settings['webSearch']['engine'] == 'bing':
                    results = await Bing_search_async(user_prompt)
                elif settings['webSearch']['engine'] == 'google':
                    results = await Google_search_async(user_prompt)
                elif settings['webSearch']['engine'] == 'brave':
                    results = await Brave_search_async(user_prompt)
                elif settings['webSearch']['engine'] == 'exa':
                    results = await Exa_search_async(user_prompt)
                elif settings['webSearch']['engine'] == 'serper':
                    results = await Serper_search_async(user_prompt)
                elif settings['webSearch']['engine'] == 'bochaai':
                    results = await bochaai_search_async(user_prompt)
                if results:
                    request.messages[-1]['content'] += f"\n\n联网搜索结果：{results}"
            if settings['webSearch']['when'] == 'after_thinking' or settings['webSearch']['when'] == 'both':
                if settings['webSearch']['engine'] == 'duckduckgo':
                    tools.append(duckduckgo_tool)
                elif settings['webSearch']['engine'] == 'searxng':
                    tools.append(searxng_tool)
                elif settings['webSearch']['engine'] == 'tavily':
                    tools.append(tavily_tool)
                elif settings['webSearch']['engine'] == 'bing':
                    tools.append(bing_tool)
                elif settings['webSearch']['engine'] == 'google':
                    tools.append(google_tool)
                elif settings['webSearch']['engine'] == 'brave':
                    tools.append(brave_tool)
                elif settings['webSearch']['engine'] == 'exa':
                    tools.append(exa_tool)
                elif settings['webSearch']['crawler'] == 'serper':
                    tools.append(serper_tool)
                elif settings['webSearch']['crawler'] == 'bochaai':
                    tools.append(bochaai_tool)

                if settings['webSearch']['crawler'] == 'jina':
                    tools.append(jina_crawler_tool)
                elif settings['webSearch']['crawler'] == 'crawl4ai':
                    tools.append(Crawl4Ai_tool)
        if kb_list:
            tools.append(kb_tool)
        if settings['tools']['deepsearch']['enabled'] or enable_deep_research: 
            deepsearch_messages = copy.deepcopy(request.messages)
            deepsearch_messages[-1]['content'] += "\n\n将用户提出的问题或给出的当前任务拆分成多个步骤，每一个步骤用一句简短的话概括即可，无需回答或执行这些内容，直接返回总结即可，但不能省略问题或任务的细节。如果用户输入的只是闲聊或者不包含任务和问题，直接把用户输入重复输出一遍即可。如果是非常简单的问题，也可以只给出一个步骤即可。一般情况下都是需要拆分成多个步骤的。"
            response = await client.chat.completions.create(
                model=model,
                messages=deepsearch_messages,
                temperature=0.5, 
                max_tokens=512,
                extra_body = extra_params, # 其他参数
            )
            user_prompt = response.choices[0].message.content
            request.messages[-1]['content'] += f"\n\n如果用户没有提出问题或者任务，直接闲聊即可，如果用户提出了问题或者任务，任务描述不清晰或者你需要进一步了解用户的真实需求，你可以暂时不完成任务，而是分析需要让用户进一步明确哪些需求。"
        if settings['reasoner']['enabled'] or enable_thinking:
            reasoner_messages = copy.deepcopy(request.messages)
            if settings['tools']['deepsearch']['enabled'] or enable_deep_research: 
                drs_msg = get_drs_stage(DRS_STAGE)
                if drs_msg:
                    reasoner_messages[-1]['content'] += f"\n\n{drs_msg}\n\n"
                reasoner_messages[-1]['content'] += f"\n\n可参考的步骤：{user_prompt}\n\n"
            if tools:
                reasoner_messages[-1]['content'] += f"可用工具：{json.dumps(tools)}"
            for modelProvider in settings['modelProviders']: 
                if modelProvider['id'] == settings['reasoner']['selectedProvider']:
                    vendor = modelProvider['vendor']
                    break
            msg = await images_add_in_messages(reasoner_messages, images,settings)    
            if vendor == 'Ollama':
                reasoner_response = await reasoner_client.chat.completions.create(
                    model=settings['reasoner']['model'],
                    messages=msg,
                    stream=False,
                    temperature=settings['reasoner']['temperature']
                )
                # 将推理结果中的思考内容提取出来
                reasoning_content = reasoner_response.model_dump()['choices'][0]['message']['content']
                # open_tag和close_tag之间的内容
                start_index = reasoning_content.find(open_tag) + len(open_tag)
                end_index = reasoning_content.find(close_tag)
                if start_index != -1 and end_index != -1:
                    reasoning_content = reasoning_content[start_index:end_index]
                else:
                    reasoning_content = ""
                request.messages[-1]['content'] = request.messages[-1]['content'] + "\n\n可参考的推理过程：" + reasoning_content
            else:
                reasoner_response = await reasoner_client.chat.completions.create(
                    model=settings['reasoner']['model'],
                    messages=msg,
                    stream=False,
                    max_tokens=1, # 根据实际情况调整
                    temperature=settings['reasoner']['temperature']
                )
                request.messages[-1]['content'] = request.messages[-1]['content'] + "\n\n可参考的推理过程：" + reasoner_response.model_dump()['choices'][0]['message']['reasoning_content']
        if settings['tools']['deepsearch']['enabled'] or enable_deep_research: 
            request.messages[-1]['content'] += f"\n\n可参考的步骤：{user_prompt}\n\n"
            drs_msg = get_drs_stage(DRS_STAGE)
            if drs_msg:
                request.messages[-1]['content'] += f"\n\n{drs_msg}\n\n"
        msg = await images_add_in_messages(request.messages, images,settings)
        if tools:
            response = await client.chat.completions.create(
                model=model,
                messages=msg,  # 添加图片信息到消息
                temperature=request.temperature,
                tools=tools,
                stream=False,
                max_tokens=request.max_tokens or settings['max_tokens'],
                top_p=request.top_p or settings['top_p'],
                frequency_penalty=request.frequency_penalty,
                presence_penalty=request.presence_penalty,
                extra_body = extra_params, # 其他参数
            )
        else:
            response = await client.chat.completions.create(
                model=model,
                messages=msg,  # 添加图片信息到消息
                temperature=request.temperature,
                stream=False,
                max_tokens=request.max_tokens or settings['max_tokens'],
                top_p=request.top_p or settings['top_p'],
                frequency_penalty=request.frequency_penalty,
                presence_penalty=request.presence_penalty,
                extra_body = extra_params, # 其他参数
            )
        if response.choices[0].message.tool_calls:
            pass
        elif settings['tools']['deepsearch']['enabled'] or enable_deep_research: 
            search_prompt = get_drs_stage_system_message(DRS_STAGE,user_prompt,response.choices[0].message.content)
            research_response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                    "role": "user",
                    "content": search_prompt,
                    }
                ],
                temperature=0.5,
                extra_body = extra_params, # 其他参数
            )
            response_content = research_response.choices[0].message.content
            # 用re 提取```json 包裹json字符串 ```
            if "```json" in response_content:
                try:
                    response_content = re.search(r'```json(.*?)```', response_content, re.DOTALL).group(1)
                except:
                    # 用re 提取```json 之后的内容
                    response_content = re.search(r'```json(.*?)', response_content, re.DOTALL).group(1)
            response_content = json.loads(response_content)
            if response_content["status"] == "done":
                search_not_done = False
            elif response_content["status"] == "not_done":
                search_not_done = True
                search_task = response_content["unfinished_task"]
                task_prompt = f"请继续完成初始任务中未完成的任务：\n\n{search_task}\n\n初始任务：{user_prompt}\n\n最后，请给出完整的初始任务的最终结果。"
                request.messages.append(
                    {
                        "role": "assistant",
                        "content": research_response.choices[0].message.content,
                    }
                )
                request.messages.append(
                    {
                        "role": "user",
                        "content": task_prompt,
                    }
                )
            elif response_content["status"] == "need_more_info":
                DRS_STAGE = 2
                search_not_done = False
            elif response_content["status"] == "search":
                DRS_STAGE = 2
                search_not_done = True
                drs_msg = get_drs_stage(DRS_STAGE)
                request.messages.append(
                    {
                        "role": "assistant",
                        "content": research_response.choices[0].message.content,
                    }
                )
                request.messages.append(
                    {
                        "role": "user",
                        "content": drs_msg,
                    }
                )
            elif response_content["status"] == "need_more_search":
                DRS_STAGE = 2
                search_not_done = True
                search_task = response_content["unfinished_task"]
                task_prompt = f"请继续查询如下信息：\n\n{search_task}\n\n初始任务：{user_prompt}\n\n"
                request.messages.append(
                    {
                        "role": "assistant",
                        "content": research_response.choices[0].message.content,
                    }
                )
                request.messages.append(
                    {
                        "role": "user",
                        "content": task_prompt,
                    }
                )
            elif response_content["status"] == "answer":
                DRS_STAGE = 3
                search_not_done = True
                drs_msg = get_drs_stage(DRS_STAGE)
                request.messages.append(
                    {
                        "role": "assistant",
                        "content": research_response.choices[0].message.content,
                    }
                )
                request.messages.append(
                    {
                        "role": "user",
                        "content": drs_msg,
                    }
                )
        reasoner_messages = copy.deepcopy(request.messages)
        while response.choices[0].message.tool_calls or search_not_done:
            if response.choices[0].message.tool_calls:
                assistant_message = response.choices[0].message
                response_content = assistant_message.tool_calls[0].function
                print(response_content.name)
                modified_data = '[' + response_content.arguments.replace('}{', '},{') + ']'
                # 使用json.loads来解析修改后的字符串为列表
                data_list = json.loads(modified_data)
                # 存储处理结果
                results = []
                for data in data_list:
                    result = await dispatch_tool(response_content.name, data,settings) # 将结果添加到results列表中
                    if result is not None:
                        # 将结果添加到results列表中
                        results.append(json.dumps(result))

                # 将所有结果拼接成一个连续的字符串
                combined_results = ''.join(results)
                if combined_results:
                    results = combined_results
                else:
                    results = None
                if results is None:
                    break
                if response_content.name in ["query_knowledge_base"]:
                    if settings["KBSettings"]["is_rerank"]:
                        results = await rerank_knowledge_base(user_prompt,results)
                    results = json.dumps(results, ensure_ascii=False, indent=4)
                request.messages.append(
                    {
                        "tool_calls": [
                            {
                                "id": assistant_message.tool_calls[0].id,
                                "function": {
                                    "arguments": response_content.arguments,
                                    "name": response_content.name,
                                },
                                "type": assistant_message.tool_calls[0].type,
                            }
                        ],
                        "role": "assistant",
                        "content": str(response_content),
                    }
                )
                request.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": assistant_message.tool_calls[0].id,
                        "name": response_content.name,
                        "content": str(results),
                    }
                )
            if settings['webSearch']['when'] == 'after_thinking' or settings['webSearch']['when'] == 'both':
                request.messages[-1]['content'] += f"\n对于联网搜索的结果，如果联网搜索的信息不足以回答问题时，你可以进一步使用联网搜索查询还未给出的必要信息。如果已经足够回答问题，请直接回答问题。"
            reasoner_messages.append(
                {
                    "role": "assistant",
                    "content": str(response_content),
                }
            )
            reasoner_messages.append(
                {
                    "role": "user",
                    "content": f"{response_content.name}工具结果："+str(results),
                }
            )
            if settings['reasoner']['enabled'] or enable_thinking:

                if tools:
                    reasoner_messages[-1]['content'] += f"可用工具：{json.dumps(tools)}"
                for modelProvider in settings['modelProviders']: 
                    if modelProvider['id'] == settings['reasoner']['selectedProvider']:
                        vendor = modelProvider['vendor']
                        break
                msg = await images_add_in_messages(reasoner_messages, images,settings)
                if vendor == 'Ollama':
                    reasoner_response = await reasoner_client.chat.completions.create(
                        model=settings['reasoner']['model'],
                        messages=msg,
                        stream=False,
                        temperature=settings['reasoner']['temperature']
                    )
                    # 将推理结果中的思考内容提取出来
                    reasoning_content = reasoner_response.model_dump()['choices'][0]['message']['content']
                    # open_tag和close_tag之间的内容
                    start_index = reasoning_content.find(open_tag) + len(open_tag)
                    end_index = reasoning_content.find(close_tag)
                    if start_index != -1 and end_index != -1:
                        reasoning_content = reasoning_content[start_index:end_index]
                    else:
                        reasoning_content = ""
                    request.messages[-1]['content'] = request.messages[-1]['content'] + "\n\n可参考的推理过程：" + reasoning_content
                else:
                    reasoner_response = await reasoner_client.chat.completions.create(
                        model=settings['reasoner']['model'],
                        messages=msg,
                        stream=False,
                        max_tokens=1, # 根据实际情况调整
                        temperature=settings['reasoner']['temperature']
                    )
                    request.messages[-1]['content'] = request.messages[-1]['content'] + "\n\n可参考的推理过程：" + reasoner_response.model_dump()['choices'][0]['message']['reasoning_content']
            msg = await images_add_in_messages(request.messages, images,settings)
            if tools:
                response = await client.chat.completions.create(
                    model=model,
                    messages=msg,  # 添加图片信息到消息
                    temperature=request.temperature,
                    tools=tools,
                    stream=False,
                    max_tokens=request.max_tokens or settings['max_tokens'],
                    top_p=request.top_p or settings['top_p'],
                    frequency_penalty=request.frequency_penalty,
                    presence_penalty=request.presence_penalty,
                    extra_body = extra_params, # 其他参数
                )
            else:
                response = await client.chat.completions.create(
                    model=model,
                    messages=msg,  # 添加图片信息到消息
                    temperature=request.temperature,
                    stream=False,
                    max_tokens=request.max_tokens or settings['max_tokens'],
                    top_p=request.top_p or settings['top_p'],
                    frequency_penalty=request.frequency_penalty,
                    presence_penalty=request.presence_penalty,
                    extra_body = extra_params, # 其他参数
                )
            if response.choices[0].message.tool_calls:
                pass
            elif settings['tools']['deepsearch']['enabled'] or enable_deep_research: 
                search_prompt = get_drs_stage_system_message(DRS_STAGE,user_prompt,response.choices[0].message.content)
                research_response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                        "role": "user",
                        "content": search_prompt,
                        }
                    ],
                    temperature=0.5,
                    extra_body = extra_params, # 其他参数
                )
                response_content = research_response.choices[0].message.content
                # 用re 提取```json 包裹json字符串 ```
                if "```json" in response_content:
                    try:
                        response_content = re.search(r'```json(.*?)```', response_content, re.DOTALL).group(1)
                    except:
                        # 用re 提取```json 之后的内容
                        response_content = re.search(r'```json(.*?)', response_content, re.DOTALL).group(1)
                response_content = json.loads(response_content)
                if response_content["status"] == "done":
                    search_not_done = False
                elif response_content["status"] == "not_done":
                    search_not_done = True
                    search_task = response_content["unfinished_task"]
                    task_prompt = f"请继续完成初始任务中未完成的任务：\n\n{search_task}\n\n初始任务：{user_prompt}\n\n最后，请给出完整的初始任务的最终结果。"
                    request.messages.append(
                        {
                            "role": "assistant",
                            "content": research_response.choices[0].message.content,
                        }
                    )
                    request.messages.append(
                        {
                            "role": "user",
                            "content": task_prompt,
                        }
                    )
                elif response_content["status"] == "need_more_info":
                    DRS_STAGE = 2
                    search_not_done = False
                elif response_content["status"] == "search":
                    DRS_STAGE = 2
                    search_not_done = True
                    drs_msg = get_drs_stage(DRS_STAGE)
                    request.messages.append(
                        {
                            "role": "assistant",
                            "content": research_response.choices[0].message.content,
                        }
                    )
                    request.messages.append(
                        {
                            "role": "user",
                            "content": drs_msg,
                        }
                    )
                elif response_content["status"] == "need_more_search":
                    DRS_STAGE = 2
                    search_not_done = True
                    search_task = response_content["unfinished_task"]
                    task_prompt = f"请继续查询如下信息：\n\n{search_task}\n\n初始任务：{user_prompt}\n\n"
                    request.messages.append(
                        {
                            "role": "assistant",
                            "content": research_response.choices[0].message.content,
                        }
                    )
                    request.messages.append(
                        {
                            "role": "user",
                            "content": task_prompt,
                        }
                    )
                elif response_content["status"] == "answer":
                    DRS_STAGE = 3
                    search_not_done = True
                    drs_msg = get_drs_stage(DRS_STAGE)
                    request.messages.append(
                        {
                            "role": "assistant",
                            "content": research_response.choices[0].message.content,
                        }
                    )
                    request.messages.append(
                        {
                            "role": "user",
                            "content": drs_msg,
                        }
                    )
       # 处理响应内容
        response_dict = response.model_dump()
        content = response_dict["choices"][0]['message']['content']
        if open_tag in content and close_tag in content:
            reasoning_content = re.search(fr'{open_tag}(.*?)\{close_tag}', content, re.DOTALL)
            if reasoning_content:
                # 存储到 reasoning_content 字段
                response_dict["choices"][0]['message']['reasoning_content'] = reasoning_content.group(1).strip()
                # 移除原内容中的标签部分
                response_dict["choices"][0]['message']['content'] = re.sub(fr'{open_tag}(.*?)\{close_tag}', '', content, flags=re.DOTALL).strip()
        if settings['reasoner']['enabled'] or enable_thinking:
            response_dict["choices"][0]['message']['reasoning_content'] = reasoner_response.model_dump()['choices'][0]['message']['reasoning_content']
        if m0:
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                },
                {
                    "role": "assistant",
                    "content": response_dict["choices"][0]['message']['content'],
                }
            ]
            executor = ThreadPoolExecutor()
            async def add_async():
                loop = asyncio.get_event_loop()
                # 绑定 user_id 关键字参数
                func = partial(m0.add, user_id=memoryId)
                # 传递 messages 作为位置参数
                await loop.run_in_executor(executor, func, messages)
                print("知识库更新完成")

            asyncio.create_task(add_async())
        return JSONResponse(content=response_dict)
    except Exception as e:
        return JSONResponse(
            content={"error": {"message": e.message, "type": "api_error", "code": e.code}}
        )

# 在现有路由后添加以下代码
@app.get("/v1/models")
async def get_models():
    """
    获取模型列表
    """
    from openai.types import Model
    from openai.pagination import SyncPage
    try:
        # 重新加载最新设置
        current_settings = await load_settings()
        agents = current_settings['agents']
        # 构造符合 OpenAI 格式的 Model 对象
        model_data = [
            Model(
                id=agent["name"],  
                created=0,  
                object="model",
                owned_by="super-agent-party"  # 非空字符串
            )
            for agent in agents.values()  
        ]
        # 添加默认的 'super-model'
        model_data.append(
            Model(
                id='super-model',
                created=0,
                object="model",
                owned_by="super-agent-party"  # 非空字符串
            )
        )

        # 构造完整 SyncPage 响应
        response = SyncPage[Model](
            object="list",
            data=model_data,
            has_more=False  # 添加分页标记
        )
        # 直接返回模型字典，由 FastAPI 自动序列化为 JSON
        return response.model_dump()  
        
    except Exception as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "error": {
                    "message": e.message,
                    "type": e.type or "api_error",
                    "code": e.code
                }
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "message": str(e),
                    "type": "server_error",
                    "code": 500
                }
            }
        )

# 在现有路由后添加以下代码
@app.get("/v1/agents",operation_id="get_agents")
async def get_agents():
    """
    获取模型列表
    """
    from openai.types import Model
    from openai.pagination import SyncPage
    try:
        # 重新加载最新设置
        current_settings = await load_settings()
        agents = current_settings['agents']
        # 构造符合 OpenAI 格式的 Model 对象
        model_data = [
            {
                "name": agent["name"],
                "description": agent["system_prompt"],
            }
            for agent in agents.values()  
        ]
        # 添加默认的 'super-model'
        model_data.append(
            {
                "name": 'super-model',
                "description": "Super-Agent-Party default agent",
            }
        )
        return model_data
        
    except Exception as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "error": {
                    "message": e.message,
                    "type": e.type or "api_error",
                    "code": e.code
                }
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "message": str(e),
                    "type": "server_error",
                    "code": 500
                }
            }
        )

class ProviderModelRequest(BaseModel):
    url: str
    api_key: str

@app.post("/v1/providers/models")
async def fetch_provider_models(request: ProviderModelRequest):
    try:
        # 使用传入的provider配置创建AsyncOpenAI客户端
        client = AsyncOpenAI(api_key=request.api_key, base_url=request.url)
        # 获取模型列表
        model_list = await client.models.list()
        # 提取模型ID并返回
        return JSONResponse(content={"data": [model.id for model in model_list.data]})
    except Exception as e:
        # 处理异常，返回错误信息
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/chat/completions", operation_id="chat_with_agent_party")
async def chat_endpoint(request: ChatRequest,fastapi_request: Request):
    """
    用来与agent party中的模型聊天
    messages: 必填项，聊天记录，包括role和content
    model: 可选项，默认使用 'super-model'，可以用get_models()获取所有可用的模型
    stream: 可选项，默认为False，是否启用流式响应
    enable_thinking: 默认为False，是否启用思考模式
    enable_deep_research: 默认为False，是否启用深度研究模式
    enable_web_search: 默认为False，是否启用网络搜索
    """
    fastapi_base_url = str(fastapi_request.base_url)
    global client, settings,reasoner_client,mcp_client_list
    model = request.model or 'super-model' # 默认使用 'super-model'
    enable_thinking = request.enable_thinking or False
    enable_deep_research = request.enable_deep_research or False
    enable_web_search = request.enable_web_search or False
    async_tools_id = request.asyncToolsID or None
    if model == 'super-model':
        current_settings = await load_settings()
        # 动态更新客户端配置
        if (current_settings['api_key'] != settings['api_key'] 
            or current_settings['base_url'] != settings['base_url']):
            client = AsyncOpenAI(
                api_key=current_settings['api_key'],
                base_url=current_settings['base_url'] or "https://api.openai.com/v1",
            )
        if (current_settings['reasoner']['api_key'] != settings['reasoner']['api_key'] 
            or current_settings['reasoner']['base_url'] != settings['reasoner']['base_url']):
            reasoner_client = AsyncOpenAI(
                api_key=current_settings['reasoner']['api_key'],
                base_url=current_settings['reasoner']['base_url'] or "https://api.openai.com/v1",
            )
        # 将"system_prompt"插入到request.messages[0].content中
        if current_settings['system_prompt']:
            if request.messages[0]['role'] == 'system':
                request.messages[0]['content'] = current_settings['system_prompt'] + "\n\n" + request.messages[0]['content']
            else:
                request.messages.insert(0, {'role': 'system', 'content': current_settings['system_prompt']})
        if current_settings != settings:
            settings = current_settings
        try:
            if request.stream:
                return await generate_stream_response(client,reasoner_client, request, settings,fastapi_base_url,enable_thinking,enable_deep_research,enable_web_search,async_tools_id)
            return await generate_complete_response(client,reasoner_client, request, settings,fastapi_base_url,enable_thinking,enable_deep_research,enable_web_search)
        except asyncio.CancelledError:
            # 处理客户端中断连接的情况
            print("Client disconnected")
            raise
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": {"message": str(e), "type": "server_error", "code": 500}}
            )
    else:
        current_settings = await load_settings()
        agentSettings = current_settings['agents'].get(model, {})
        if not agentSettings:
            for agentId , agentConfig in current_settings['agents'].items():
                if current_settings['agents'][agentId]['name'] == model:
                    agentSettings = current_settings['agents'][agentId]
                    break
        if not agentSettings:
            return JSONResponse(
                status_code=404,
                content={"error": {"message": f"Agent {model} not found", "type": "not_found", "code": 404}}
            )
        if agentSettings['config_path']:
            with open(agentSettings['config_path'], 'r' , encoding='utf-8') as f:
                agent_settings = json.load(f)
            # 将"system_prompt"插入到request.messages[0].content中
            if agentSettings['system_prompt']:
                if request.messages[0]['role'] == 'system':
                    request.messages[0]['content'] = agentSettings['system_prompt'] + "\n\n" + request.messages[0]['content']
                else:
                    request.messages.insert(0, {'role': 'system', 'content': agentSettings['system_prompt']})
        agent_client = AsyncOpenAI(
            api_key=agent_settings['api_key'],
            base_url=agent_settings['base_url'] or "https://api.openai.com/v1",
        )
        agent_reasoner_client = AsyncOpenAI(
            api_key=agent_settings['reasoner']['api_key'],
            base_url=agent_settings['reasoner']['base_url'] or "https://api.openai.com/v1",
        )
        try:
            if request.stream:
                return await generate_stream_response(agent_client,agent_reasoner_client, request, agent_settings,fastapi_base_url,enable_thinking,enable_deep_research,enable_web_search,async_tools_id)
            return await generate_complete_response(agent_client,agent_reasoner_client, request, agent_settings,fastapi_base_url,enable_thinking,enable_deep_research,enable_web_search)
        except asyncio.CancelledError:
            # 处理客户端中断连接的情况
            print("Client disconnected")
            raise
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": {"message": str(e), "type": "server_error", "code": 500}}
            )


# 存储活跃的ASR WebSocket连接
asr_connections = []

# 存储每个连接的音频帧数据
audio_buffer: Dict[str, Dict[str, Any]] = {}

def convert_audio_to_pcm16(audio_bytes: bytes, target_sample_rate: int = 16000) -> bytes:
    """
    将音频数据转换为PCM16格式，采样率16kHz
    """
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_file_path = temp_file.name
        
        try:
            # 读取音频文件
            sample_rate, audio_data = wavfile.read(temp_file_path)
            
            # 转换为单声道
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)
            
            # 转换为float32进行重采样
            if audio_data.dtype != np.float32:
                if audio_data.dtype == np.int16:
                    audio_data = audio_data.astype(np.float32) / 32768.0
                elif audio_data.dtype == np.int32:
                    audio_data = audio_data.astype(np.float32) / 2147483648.0
                else:
                    audio_data = audio_data.astype(np.float32)
            
            # 重采样到目标采样率
            if sample_rate != target_sample_rate:
                from scipy.signal import resample
                num_samples = int(len(audio_data) * target_sample_rate / sample_rate)
                audio_data = resample(audio_data, num_samples)
            
            # 转换为int16 PCM格式
            audio_data = (audio_data * 32767).astype(np.int16)
            
            return audio_data.tobytes()
            
        finally:
            # 删除临时文件
            os.unlink(temp_file_path)
            
    except Exception as e:
        print(f"Audio conversion error: {e}")
        # 如果转换失败，尝试直接返回原始数据
        return audio_bytes

async def funasr_recognize(audio_data: bytes, funasr_settings: dict,ws: WebSocket,frame_id) -> str:
    """
    使用FunASR进行语音识别
    """
    try:
        # 获取FunASR服务器地址
        funasr_url = funasr_settings.get('funasr_ws_url', 'ws://localhost:10095')
        hotwords = funasr_settings.get('hotwords', '')
        if not funasr_url.startswith('ws://') and not funasr_url.startswith('wss://'):
            funasr_url = f"ws://{funasr_url}"
        
        # 连接到FunASR服务器
        async with websockets.connect(funasr_url) as websocket:
            print(f"Connected to FunASR server: {funasr_url}")
            
            # 1. 发送初始化配置
            init_config = {
                "chunk_size": [5, 10, 5],
                "wav_name": "python_client",
                "is_speaking": True,
                "chunk_interval": 10,
                "mode": "offline",  # 使用离线模式
                "hotwords": hotwords_to_json(hotwords),
                "use_itn": True
            }
            
            await websocket.send(json.dumps(init_config))
            print("Sent init config")
            
            # 2. 转换音频数据为PCM16格式
            pcm_data = convert_audio_to_pcm16(audio_data)
            print(f"PCM data length: {len(pcm_data)} bytes")
            
            # 3. 分块发送音频数据
            chunk_size = 960  # 30ms的音频数据 (16000 * 0.03 * 2 = 960字节)
            total_sent = 0
            
            while total_sent < len(pcm_data):
                chunk_end = min(total_sent + chunk_size, len(pcm_data))
                chunk = pcm_data[total_sent:chunk_end]
                
                # 发送二进制PCM数据
                await websocket.send(chunk)
                total_sent = chunk_end
            
            print(f"Sent all audio data: {total_sent} bytes")
            
            # 4. 发送结束信号
            end_config = {
                "is_speaking": False,
            }
            
            await websocket.send(json.dumps(end_config))
            print("Sent end signal")
            
            # 5. 等待识别结果
            result_text = ""
            timeout_count = 0
            max_timeout = 200  # 最大等待20秒
            
            while timeout_count < max_timeout:
                try:
                    # 等待响应消息
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                    
                    try:
                        # 尝试解析JSON响应
                        json_response = json.loads(response)
                        print(f"Received response: {json_response}")
                        
                        if 'text' in json_response:
                            text = json_response['text']
                            if text and text.strip():
                                result_text += text
                                print(f"Got text: {text}")
                                # 发送结果
                                await ws.send_json({
                                    "type": "transcription",
                                    "id": frame_id,
                                    "text": result_text,
                                    "is_final": True
                                })
                            # 检查是否为最终结果
                            if json_response.get('is_final', False):
                                print("Got final result")
                                break
                                
                    except json.JSONDecodeError:
                        # 如果不是JSON格式，可能是二进制数据，忽略
                        print(f"Non-JSON response: {response}")
                        pass
                        
                except asyncio.TimeoutError:
                    timeout_count += 1
                    continue
                except websockets.exceptions.ConnectionClosed:
                    print("WebSocket connection closed")
                    break
            
            if not result_text:
                print("No recognition result received")
                return ""
            
            return result_text.strip()
            
    except Exception as e:
        print(f"FunASR recognition error: {e}")
        import traceback
        traceback.print_exc()
        return f"FunASR识别错误: {str(e)}"

def hotwords_to_json(input_str):
    # 初始化结果字典
    result = {}
    
    # 按行分割输入字符串
    lines = input_str.split('\n')
    
    for line in lines:
        # 清理行首尾的空白字符
        cleaned_line = line.strip()
        
        # 跳过空行
        if not cleaned_line:
            continue
            
        # 分割词语和权重
        parts = cleaned_line.rsplit(' ', 1)  # 从右边分割一次
        
        if len(parts) != 2:
            continue  # 跳过格式不正确的行
            
        word = parts[0].strip()
        try:
            weight = int(parts[1])
        except ValueError:
            continue  # 跳过权重不是数字的行
            
        # 添加到结果字典
        result[word] = weight
    
    # 转换为JSON字符串
    return json.dumps(result, ensure_ascii=False)

# ASR WebSocket处理
@app.websocket("/asr_ws")
async def asr_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # 生成唯一的连接ID
    connection_id = str(uuid.uuid4())
    asr_connections.append(websocket)
    funasr_websocket = None
    # 新增：连接状态跟踪变量
    asr_engine = None
    funasr_mode = None
    
    try:
        # 处理消息
        async for message in websocket.iter_json():
            msg_type = message.get("type")
            
            if msg_type == "init":
                # 加载设置
                settings = await load_settings()
                asr_settings = settings.get('asrSettings', {})
                asr_engine = asr_settings.get('engine', 'openai')  # 存储引擎类型
                if asr_engine == "funasr":
                    funasr_mode = asr_settings.get('funasr_mode', 'openai')  # 存储模式
                    if funasr_mode == "2pass" or funasr_mode == "online":
                        # 获取FunASR服务器地址
                        funasr_url = asr_settings.get('funasr_ws_url', 'ws://localhost:10095')
                        if not funasr_url.startswith('ws://') and not funasr_url.startswith('wss://'):
                            funasr_url = f"ws://{funasr_url}"
                        try:
                            funasr_websocket = await websockets.connect(funasr_url)
                        except Exception as e:
                            funasr_websocket = None
                            print(f"连接FunASR失败: {e}")
                await websocket.send_json({
                    "type": "init_response",
                    "status": "ready"
                })
            elif msg_type == "audio_start":
                frame_id = message.get("id")
                # 加载设置
                settings = await load_settings()
                asr_settings = settings.get('asrSettings', {})
                asr_engine = asr_settings.get('engine', 'openai')  # 存储引擎类型
                if asr_engine == "funasr":
                    funasr_mode = asr_settings.get('funasr_mode', '2pass')  # 存储模式
                    hotwords = asr_settings.get('hotwords', '')
                    if funasr_mode == "2pass":
                        # 获取FunASR服务器地址
                        funasr_url = asr_settings.get('funasr_ws_url', 'ws://localhost:10095')
                        if not funasr_url.startswith('ws://') and not funasr_url.startswith('wss://'):
                            funasr_url = f"ws://{funasr_url}"
                        try:
                            if not funasr_websocket:
                                # 连接到FunASR服务器 
                                funasr_websocket = await websockets.connect(funasr_url)
                            # 1. 发送初始化配置
                            init_config = {
                                "chunk_size": [5, 10, 5],
                                "wav_name": "python_client",
                                "is_speaking": True,
                                "chunk_interval": 10,
                                "mode": funasr_mode,  
                                "hotwords": hotwords_to_json(hotwords),
                                "use_itn": True
                            }
                            await funasr_websocket.send(json.dumps(init_config))
                            print("Sent init config")
                            # 2. 开启一个异步任务处理FunASR的响应
                            asyncio.create_task(handle_funasr_response(funasr_websocket, websocket))
                        except Exception as e:
                            print(f"连接FunASR失败: {e}")
                            await websocket.send_json({
                                "type": "error",
                                "message": f"无法连接FunASR服务器: {str(e)}"
                            })
                            # 标记连接失败，避免后续操作
                            funasr_websocket = None
                    else:
                        # 关闭异步任务处理FunASR的响应
                        funasr_websocket = None
                else:
                    # 关闭异步任务处理FunASR的响应
                    funasr_websocket = None
            # 修改点：增加流式音频处理前的检查
            elif msg_type == "audio_stream":
                frame_id = message.get("id")
                audio_base64 = message.get("audio")

                # 关键检查：确保funasr_websocket已初始化
                if not funasr_websocket:
                    continue  # 跳过当前消息处理

                if audio_base64:
                    # 1. Base64 解码 → 得到二进制 PCM (Int16)
                    pcm_data = base64.b64decode(audio_base64)

                    # 2. 直接转发二进制给 FunASR
                    try:
                        await funasr_websocket.send(pcm_data)
                    except websockets.exceptions.ConnectionClosed:
                        funasr_websocket = None
                        # 加载设置
                        settings = await load_settings()
                        asr_settings = settings.get('asrSettings', {})
                        asr_engine = asr_settings.get('engine', 'openai')  # 存储引擎类型
                        if asr_engine == "funasr":
                            funasr_mode = asr_settings.get('funasr_mode', '2pass')  # 存储模式
                            if funasr_mode == "2pass":
                                # 获取FunASR服务器地址
                                funasr_url = asr_settings.get('funasr_ws_url', 'ws://localhost:10095')
                                if not funasr_url.startswith('ws://') and not funasr_url.startswith('wss://'):
                                    funasr_url = f"ws://{funasr_url}"
                                try:
                                    funasr_websocket = await websockets.connect(funasr_url)
                                except Exception as e:
                                    funasr_websocket = None
                                    print(f"连接FunASR失败: {e}")
            elif msg_type == "audio_complete":
                # 处理完整的音频数据（非流式模式）
                frame_id = message.get("id")
                audio_b64 = message.get("audio")
                audio_format = message.get("format", "wav")
                
                if audio_b64:
                    # 解码base64数据
                    audio_bytes = base64.b64decode(audio_b64)
                    print(f"Received audio data: {len(audio_bytes)} bytes, format: {audio_format}")
                    
                    try:
                        # 加载设置
                        settings = await load_settings()
                        asr_settings = settings.get('asrSettings', {})
                        asr_engine = asr_settings.get('engine', 'openai')
                        
                        result = ""
                        
                        if asr_engine == "openai":
                            # OpenAI ASR
                            audio_file = BytesIO(audio_bytes)
                            audio_file.name = f"audio.{audio_format}"
                            
                            client = AsyncOpenAI(
                                api_key=asr_settings.get('api_key', ''),
                                base_url=asr_settings.get('base_url', '') or "https://api.openai.com/v1"
                            )
                            response = await client.audio.transcriptions.create(
                                file=audio_file,
                                model=asr_settings.get('model', 'whisper-1'),
                            )
                            result = response.text
                            # 发送结果
                            await websocket.send_json({
                                "type": "transcription",
                                "id": frame_id,
                                "text": result,
                                "is_final": True
                            })
                        elif asr_engine == "funasr":
                            # FunASR
                            print("Using FunASR engine")
                            funasr_mode = asr_settings.get('funasr_mode', 'offline')
                            if funasr_mode == "offline":
                                result = await funasr_recognize(audio_bytes, asr_settings,websocket,frame_id)
                            else:
                                # 关键检查：确保连接有效
                                if not funasr_websocket:
                                    continue
                                
                                # 4. 发送结束信号
                                end_config = {
                                    "is_speaking": False  # 只需发送必要的结束标记
                                }
                                try:
                                    await funasr_websocket.send(json.dumps(end_config))
                                    print("Sent end signal")
                                except websockets.exceptions.ConnectionClosed:
                                    print("FunASR连接已关闭，无法发送结束信号")
                            funasr_websocket = None
                    except WebSocketDisconnect:
                        print(f"ASR WebSocket disconnected: {connection_id}")
                    except Exception as e:
                        print(f"ASR WebSocket error: {e}")
                        import traceback
                        traceback.print_exc()
    finally:
        # 清理资源
        if connection_id in audio_buffer:
            del audio_buffer[connection_id]
        if websocket in asr_connections:
            asr_connections.remove(websocket)
        # 新增：确保关闭FunASR连接
        if funasr_websocket:
            await funasr_websocket.close()


async def handle_funasr_response(funasr_websocket, 
                               client_websocket: WebSocket):
    """
    处理 FunASR 服务器的响应，并将结果转发给客户端
    """
    try:
        async for message in funasr_websocket:
            try:
                if funasr_websocket:
                    # FunASR 返回的数据可能是 JSON 或二进制
                    if isinstance(message, bytes):
                        message = message.decode('utf-8')
                    
                    data = json.loads(message)
                    print(f"FunASR response: {data}")
                    # 解析 FunASR 响应
                    if "text" in data:  # 普通识别结果
                        if data.get('mode', '') == "2pass-online":
                            await client_websocket.send_json({
                                "type": "transcription",
                                "text": data["text"],
                                "is_final": False
                            })
                        else:
                            await client_websocket.send_json({
                                "type": "transcription",
                                "text": data["text"],
                                "is_final": True
                            })
                    elif "mode" in data:  # 初始化响应
                        print(f"FunASR initialized: {data}")
                    else:
                        print(f"Unknown FunASR response: {data}")
                else:
                    # 如果 FunASR 连接关闭，发送错误消息，退出循环，结束任务
            
                    break
            except json.JSONDecodeError:
                print(f"FunASR sent non-JSON data: {message[:100]}...")
            except Exception as e:
                print(f"Error processing FunASR response: {e}")
                break

    except websockets.exceptions.ConnectionClosed:
        print("FunASR connection closed")
    except Exception as e:
        print(f"FunASR handler error: {e}")
    finally:
        await funasr_websocket.close()

@app.post("/tts")
async def text_to_speech(request: Request):
    fastapi_base_url = str(request.base_url)
    data = await request.json()
    text = data['text']
    index = data['index'] # chunk在ttsChunks中的索引
    
    # 使用edge-tts生成语音
    communicate = edge_tts.Communicate(text, "zh-CN-YunxiNeural")
    filename = f"tts_{int(time.time())}.mp3"
    
    # 保存文件
    with open(os.path.join(UPLOAD_FILES_DIR, filename), "wb") as fp:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fp.write(chunk["data"])
    
    return {"audioUrl": f"{fastapi_base_url}uploaded_files/{filename}", "index": index}


# 添加状态存储
mcp_status = {}
@app.post("/create_mcp")
async def create_mcp_endpoint(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    mcp_id = data.get("mcpId")
    
    if not mcp_id:
        raise HTTPException(status_code=400, detail="Missing mcpId")
    
    # 将任务添加到后台队列
    background_tasks.add_task(process_mcp, mcp_id)
    
    return {"success": True, "message": "MCP服务器初始化已开始"}
@app.get("/mcp_status/{mcp_id}")
async def get_mcp_status(mcp_id: str):
    status = mcp_status.get(mcp_id, "not_found")
    return {"mcp_id": mcp_id, "status": status}
async def process_mcp(mcp_id: str):
    global mcp_client_list
    mcp_status[mcp_id] = "initializing"
    try:
        # 获取对应服务器的配置
        cur_settings = await load_settings()
        server_config = cur_settings['mcpServers'][mcp_id]
        
        # 执行初始化逻辑
        mcp_client_list[mcp_id] = McpClient()    
        await asyncio.wait_for(mcp_client_list[mcp_id].initialize(mcp_id, server_config), timeout=6)
        mcp_status[mcp_id] = "ready"
        mcp_client_list[mcp_id].disabled = False
        
    except Exception as e:
        mcp_client_list[mcp_id].disabled = True
        mcp_status[mcp_id] = f"failed: {str(e)}"

@app.delete("/remove_mcp")
async def remove_mcp_server(request: Request):
    global settings, mcp_client_list
    try:
        data = await request.json()
        server_name = data.get("serverName", "")

        if not server_name:
            raise HTTPException(status_code=400, detail="No server names provided")

        # 移除指定的MCP服务器
        current_settings = await load_settings()
        if server_name in current_settings['mcpServers']:
            del current_settings['mcpServers'][server_name]
            await save_settings(current_settings)
            settings = current_settings

            # 从mcp_client_list中移除
            if server_name in mcp_client_list:
                mcp_client_list[server_name].disabled = True
                await mcp_client_list[server_name].close()
                del mcp_client_list[server_name]
                print(f"关闭MCP服务器: {server_name}")

            return JSONResponse({"success": True, "removed": server_name})
        else:
            raise HTTPException(status_code=404, detail="Server not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        logger.error(f"移除MCP服务器失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/remove_memory")
async def remove_memory_endpoint(request: Request):
    data = await request.json()
    memory_id = data.get("memoryId")
    if memory_id:
        try:
            # 删除MEMORY_CACHE_DIR目录下的memory_id文件夹
            memory_dir = os.path.join(MEMORY_CACHE_DIR, memory_id)
            shutil.rmtree(memory_dir)
            return JSONResponse({"success": True, "message": "Memory removed"})
        except Exception as e:
            return JSONResponse({"success": False, "message": str(e)})
    else:
        return JSONResponse({"success": False, "message": "No memoryId provided"})

@app.delete("/remove_agent")
async def remove_agent_endpoint(request: Request):
    data = await request.json()
    agent_id = data.get("agentId")
    if agent_id:
        try:
            # 删除AGENT_CACHE_DIR目录下的agent_id文件夹
            agent_dir = os.path.join(AGENT_DIR, f"{agent_id}.json")
            shutil.rmtree(agent_dir)
            return JSONResponse({"success": True, "message": "Agent removed"})
        except Exception as e:
            return JSONResponse({"success": False, "message": str(e)})
    else:
        return JSONResponse({"success": False, "message": "No agentId provided"})

@app.post("/a2a")
async def initialize_a2a(request: Request):
    from python_a2a import A2AClient
    data = await request.json()
    try:
        client = A2AClient(data['url'])
        agent_card = client.agent_card.to_json()
        agent_card = json.loads(agent_card)
        return JSONResponse({
            **agent_card,
            "status": "ready",
            "enabled": True
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# 在现有路由之后添加health路由
@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/load_file")
async def load_file_endpoint(request: Request, files: List[UploadFile] = File(None)):
    fastapi_base_url = str(request.base_url)
    logger.info(f"Received request with content type: {request.headers.get('Content-Type')}")
    file_links = []
    textFiles = []
    imageFiles = []
    content_type = request.headers.get('Content-Type', '')
    try:
        if 'multipart/form-data' in content_type:
            # 处理浏览器上传的文件
            if not files:
                raise HTTPException(status_code=400, detail="No files provided")
            
            for file in files:
                file_extension = os.path.splitext(file.filename)[1]
                unique_filename = f"{uuid.uuid4()}{file_extension}"
                destination = os.path.join(UPLOAD_FILES_DIR, unique_filename)
                
                # 保存上传的文件
                with open(destination, "wb") as buffer:
                    content = await file.read()
                    buffer.write(content)
                
                file_link = {
                    "path": f"{fastapi_base_url}uploaded_files/{unique_filename}",
                    "name": file.filename
                }
                file_links.append(file_link)
                file_meta = {
                    "unique_filename": unique_filename,
                    "original_filename": file.filename,
                }
                # file_extension移除点号
                file_extension = file_extension[1:]
                if file_extension in ALLOWED_EXTENSIONS:
                    textFiles.append(file_meta)
                elif file_extension in ALLOWED_IMAGE_EXTENSIONS:
                    imageFiles.append(file_meta)
        elif 'application/json' in content_type:
            # 处理Electron发送的JSON文件路径
            data = await request.json()
            logger.info(f"Processing JSON data: {data}")
            
            for file_info in data.get("files", []):
                file_path = file_info.get("path")
                file_name = file_info.get("name", os.path.basename(file_path))
                
                if not os.path.isfile(file_path):
                    logger.error(f"File not found: {file_path}")
                    continue
                
                # 生成唯一文件名
                file_extension = os.path.splitext(file_name)[1]
                unique_filename = f"{uuid.uuid4()}{file_extension}"
                destination = os.path.join(UPLOAD_FILES_DIR, unique_filename)
                
                # 复制文件到上传目录
                with open(file_path, "rb") as src, open(destination, "wb") as dst:
                    dst.write(src.read())
                
                file_link = {
                    "path": f"{fastapi_base_url}uploaded_files/{unique_filename}",
                    "name": file_name
                }
                file_links.append(file_link)
                file_meta = {
                    "unique_filename": unique_filename,
                    "original_filename": file_name,
                }
                # file_extension移除点号
                file_extension = file_extension[1:]
                if file_extension in ALLOWED_EXTENSIONS:
                    textFiles.append(file_meta)
                elif file_extension in ALLOWED_IMAGE_EXTENSIONS:
                    imageFiles.append(file_meta)
        else:
            raise HTTPException(status_code=400, detail="Unsupported Content-Type")
        return JSONResponse(content={"success": True, "fileLinks": file_links , "textFiles": textFiles, "imageFiles": imageFiles})
    
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete_file")
async def delete_file_endpoint(request: Request):
    data = await request.json()
    file_name = data.get("fileName")
    file_path = os.path.join(UPLOAD_FILES_DIR, file_name)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return JSONResponse(content={"success": True})
        else:
            return JSONResponse(content={"success": False, "message": "File not found"})
    except Exception as e:
        return JSONResponse(content={"success": False, "message": str(e)})

@app.get("/update_storage")
async def update_storage_endpoint(request: Request):
    settings = await load_settings()
    textFiles = settings.get("textFiles") or []
    imageFiles = settings.get("imageFiles") or []
    videoFiles = settings.get("videoFiles") or []
    # 检查UPLOAD_FILES_DIR目录中的文件，根据ALLOWED_EXTENSIONS、ALLOWED_IMAGE_EXTENSIONS、ALLOWED_VIDEO_EXTENSIONS分类，如果不存在于textFiles、imageFiles、videoFiles中则添加进去
    # 三个列表的元素是字典，包含"unique_filename"和"original_filename"两个键
    
    for file in os.listdir(UPLOAD_FILES_DIR):
        file_path = os.path.join(UPLOAD_FILES_DIR, file)
        if os.path.isfile(file_path):
            file_extension = os.path.splitext(file)[1][1:]
            if file_extension in ALLOWED_EXTENSIONS:
                if file not in [item["unique_filename"] for item in textFiles]:
                    textFiles.append({"unique_filename": file, "original_filename": file})
            elif file_extension in ALLOWED_IMAGE_EXTENSIONS:
                if file not in [item["unique_filename"] for item in imageFiles]:
                    imageFiles.append({"unique_filename": file, "original_filename": file})
            elif file_extension in ALLOWED_VIDEO_EXTENSIONS:
                if file not in [item["unique_filename"] for item in videoFiles]:
                    videoFiles.append({"unique_filename": file, "original_filename": file})

    # 发给前端
    return JSONResponse(content={"textFiles": textFiles, "imageFiles": imageFiles, "videoFiles": videoFiles})


@app.post("/create_kb")
async def create_kb_endpoint(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    kb_id = data.get("kbId")
    
    if not kb_id:
        raise HTTPException(status_code=400, detail="Missing kbId")
    
    # 将任务添加到后台队列
    background_tasks.add_task(process_kb, kb_id)
    
    return {"success": True, "message": "知识库处理已开始，请稍后查询状态"}

@app.delete("/remove_kb")
async def remove_kb_endpoint(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    kb_id = data.get("kbId")

    if not kb_id:
        raise HTTPException(status_code=400, detail="Missing kbId")
    try:
        background_tasks.add_task(remove_kb, kb_id)
    except Exception as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "message": "知识库已删除"}

# 删除知识库
async def remove_kb(kb_id):
    # 删除KB_DIR/kb_id目录
    kb_dir = os.path.join(KB_DIR, str(kb_id))
    if os.path.exists(kb_dir):
        shutil.rmtree(kb_dir)
    else:
        print(f"KB directory {kb_dir} does not exist.")
    return

# 添加状态存储
kb_status = {}
@app.get("/kb_status/{kb_id}")
async def get_kb_status(kb_id):
    status = kb_status.get(kb_id, "not_found")
    print (f"kb_status: {kb_id} - {status}")
    return {"kb_id": kb_id, "status": status}

# 修改 process_kb
async def process_kb(kb_id):
    kb_status[kb_id] = "processing"
    try:
        from py.know_base import process_knowledge_base
        await process_knowledge_base(kb_id)
        kb_status[kb_id] = "completed"
    except Exception as e:
        kb_status[kb_id] = f"failed: {str(e)}"

@app.post("/create_sticker_pack")
async def create_sticker_pack(
    request: Request,
    files: List[UploadFile] = File(..., description="表情文件列表"),
    pack_name: str = Form(..., description="表情包名称"),
    descriptions: List[str] = Form(..., description="表情描述列表")
):
    """
    创建新表情包
    - files: 上传的图片文件列表
    - pack_name: 表情包名称
    - descriptions: 每个表情的描述列表
    """
    fastapi_base_url = str(request.base_url)
    imageFiles = []
    stickers_data = []
    
    try:
        # 验证输入数据
        if not pack_name:
            raise HTTPException(status_code=400, detail="表情包名称不能为空")
        if len(files) == 0:
            raise HTTPException(status_code=400, detail="至少需要上传一个表情")
        if len(descriptions) != len(files):
            raise HTTPException(
                status_code=400, 
                detail=f"描述数量({len(descriptions)})与文件数量({len(files)})不匹配"
            )

        # 处理上传的表情文件
        for idx, file in enumerate(files):
            # 获取文件扩展名
            file_extension = os.path.splitext(file.filename)[1].lower()
            
            # 验证文件类型
            if file_extension not in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
                raise HTTPException(
                    status_code=400, 
                    detail=f"不支持的文件类型: {file_extension}"
                )
            
            # 生成唯一文件名
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            destination = os.path.join(UPLOAD_FILES_DIR, unique_filename)

            # 保存文件
            with open(destination, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # 构建返回数据
            imageFiles.append({
                "unique_filename": unique_filename,
                "original_filename": file.filename,
            })
            
            # 获取对应的描述（处理可能的索引越界）
            description = descriptions[idx] if idx < len(descriptions) else ""

            # 构建表情数据
            stickers_data.append({
                "unique_filename": unique_filename,
                "original_filename": file.filename,
                "url": f"{fastapi_base_url}uploaded_files/{unique_filename}",
                "description": description
            })

        # 创建表情包ID（可替换为数据库存储逻辑）
        sticker_pack_id = str(uuid.uuid4())
        
        return JSONResponse(content={
            "success": True,
            "id": sticker_pack_id,
            "name": pack_name,
            "stickers": stickers_data,
            "imageFiles": imageFiles,
            "cover": stickers_data[0]["url"] if stickers_data else None
        })
    
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"创建表情包时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")

# 定义请求体
class QQBotConfig(BaseModel):
    QQAgent: str
    memoryLimit: int
    appid: str
    secret: str
    separators: List[str]
    reasoningVisible: bool
    quickRestart: bool

# 全局机器人管理器
qq_bot_manager = QQBotManager()

@app.post("/start_qq_bot")
async def start_qq_bot(config: QQBotConfig):
    try:
        qq_bot_manager.start_bot(config)
        return {
            "success": True,
            "message": "QQ机器人已成功启动",
            "environment": "thread-based"
        }
    except Exception as e:
        logger.error(f"启动QQ机器人失败: {e}")
        return JSONResponse(
            status_code=400,  # 改为 400 表示客户端错误
            content={
                "success": False, 
                "message": f"启动失败: {str(e)}",
                "error_type": "startup_error"
            }
        )

@app.post("/stop_qq_bot")
async def stop_qq_bot():
    try:
        qq_bot_manager.stop_bot()
        return {"success": True, "message": "QQ机器人已停止"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)}
        )

@app.get("/qq_bot_status")
async def qq_bot_status():
    status = qq_bot_manager.get_status()
    # 如果有启动错误，在状态中包含错误信息
    if status.get("startup_error") and not status.get("is_running"):
        status["error_message"] = f"启动失败: {status['startup_error']}"
    return status

@app.post("/reload_qq_bot")
async def reload_qq_bot(config: QQBotConfig):
    try:
        # 先停止再启动
        qq_bot_manager.stop_bot()
        await asyncio.sleep(1)  # 等待完全停止
        qq_bot_manager.start_bot(config)
        
        return {
            "success": True,
            "message": "QQ机器人已重新加载",
            "config_changed": True
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)}
        )

@app.post("/add_workflow")
async def add_workflow(file: UploadFile = File(...), workflow_data: str = Form(...)):
    # 检查文件类型是否为 JSON
    if file.content_type != "application/json":
        raise HTTPException(
            status_code=400,
            detail="Only JSON files are allowed."
        )

    # 生成唯一文件名，uuid.uuid4()，没有连词符
    unique_filename = str(uuid.uuid4()).replace('-', '')

    # 拼接文件路径
    file_path = os.path.join(UPLOAD_FILES_DIR, unique_filename + ".json")

    # 保存文件
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}"
        )

    # 解析 workflow_data
    workflow_data_dict = json.loads(workflow_data)

    # 返回文件信息
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "File uploaded successfully",
            "file": {
                "unique_filename": unique_filename,
                "original_filename": file.filename,
                "url": f"/uploaded_files/{unique_filename}",
                "enabled": True,
                "text_input": workflow_data_dict.get("textInput"),
                "text_input_2": workflow_data_dict.get("textInput2"),
                "image_input": workflow_data_dict.get("imageInput"),
                "image_input_2": workflow_data_dict.get("imageInput2"),
                "description": workflow_data_dict.get("description")
            }
        }
    )

@app.delete("/delete_workflow/{filename}")
async def delete_workflow(filename: str):
    file_path = os.path.join(UPLOAD_FILES_DIR, filename + ".json")
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # 删除文件
    try:
        os.remove(file_path)
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "File deleted successfully"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete file: {str(e)}"
        )

settings_lock = asyncio.Lock()
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)

    try:
        async with settings_lock:  # 读取时加锁
            current_settings = await load_settings()
        await websocket.send_json({"type": "settings", "data": current_settings})
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") == "save_settings":
                await save_settings(data.get("data", {}))
                # 发送确认消息（携带相同 correlationId）
                await websocket.send_json({
                    "type": "settings_saved",
                    "correlationId": data.get("correlationId"),
                    "success": True
                })
            elif data.get("type") == "get_settings":
                settings = await load_settings()
                await websocket.send_json({"type": "settings", "data": settings})
            elif data.get("type") == "save_agent":
                current_settings = await load_settings()
                
                # 生成智能体ID和配置路径
                agent_id = str(shortuuid.ShortUUID().random(length=8))
                config_path = os.path.join(AGENT_DIR, f"{agent_id}.json")
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(current_settings, f, indent=4, ensure_ascii=False)
                
                # 更新主配置
                current_settings['agents'][agent_id] = {
                    "id": agent_id,
                    "name": data['data']['name'],
                    "system_prompt": data['data']['system_prompt'],
                    "config_path": config_path,
                    "enabled": False,
                }
                await save_settings(current_settings)
                
                # 广播更新后的配置
                await websocket.send_json({
                    "type": "settings",
                    "data": current_settings
                })
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        active_connections.remove(websocket)

mcp = FastApiMCP(
    app,
    name="Agent party MCP - chat with multiple agents",
    include_operations=["get_agents", "chat_with_agent_party"],
)

mcp.mount()

app.mount("/uploaded_files", StaticFiles(directory=UPLOAD_FILES_DIR), name="uploaded_files")
app.mount("/node_modules", StaticFiles(directory=os.path.join(base_path, "node_modules")), name="node_modules")
app.mount("/", StaticFiles(directory=os.path.join(base_path, "static"), html=True), name="static")

# 简化main函数
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=HOST,
        port=PORT
    )