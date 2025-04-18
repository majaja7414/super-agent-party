# -- coding: utf-8 --
import asyncio
import copy
import json
import os
import re
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile, WebSocket, Request
import logging
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI, APIStatusError
from pydantic import BaseModel
from fastapi import status
from fastapi.responses import JSONResponse, StreamingResponse
import uuid
import time
import shutil
from typing import List, Dict

import shortuuid
from py.mcp_clients import McpClient
from py.get_setting import load_settings,save_settings,base_path,in_docker
from contextlib import asynccontextmanager
os.environ["no_proxy"] = "localhost,127.0.0.1"
if in_docker():
    HOST = '0.0.0.0'
else:
    HOST = '127.0.0.1'
PORT = 3456
local_timezone = None
logger = None
settings = None
client = None
reasoner_client = None
mcp_client_list = {}
_TOOL_HOOKS = {}

@asynccontextmanager
async def lifespan(app: FastAPI): 
    global settings, client, reasoner_client, mcp_client_list,local_timezone,logger
    from tzlocal import get_localzone
    local_timezone = get_localzone()
    logger = logging.getLogger(__name__)
    settings = load_settings()
    if settings:
        client = AsyncOpenAI(api_key=settings['api_key'], base_url=settings['base_url'])
        reasoner_client = AsyncOpenAI(api_key=settings['reasoner']['api_key'],base_url=settings['reasoner']['base_url'])
    else:
        client = AsyncOpenAI()
        reasoner_client = AsyncOpenAI()
    if settings:
        for server_name,server_config in settings['mcpServers'].items():
            mcp_client_list[server_name] = McpClient()
            # 初始化mcp客户端，限制10秒内，否则跳过
            try:
                await asyncio.wait_for(mcp_client_list[server_name].initialize(server_name, server_config), timeout=5)
            except asyncio.TimeoutError:
                logger.error(f"Failed to initialize MCP client for {server_name} in 5 seconds")
                mcp_client_list[server_name].disabled = True
                del settings['mcpServers'][server_name]
                save_settings(settings)
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def dispatch_tool(tool_name: str, tool_params: dict) -> str:
    global mcp_client_list,_TOOL_HOOKS
    from py.web_search import (
        DDGsearch_async, 
        searxng_async, 
        Tavily_search_async,
        jina_crawler_async,
        Crawl4Ai_search_async, 
    )
    from py.know_base import query_knowledge_base
    _TOOL_HOOKS = {
        "DDGsearch_async": DDGsearch_async,
        "searxng_async": searxng_async,
        "Tavily_search_async": Tavily_search_async,
        "query_knowledge_base": query_knowledge_base,
        "jina_crawler_async": jina_crawler_async,
        "Crawl4Ai_search_async": Crawl4Ai_search_async,
    }
    if "multi_tool_use." in tool_name:
        tool_name = tool_name.replace("multi_tool_use.", "")
    if tool_name not in _TOOL_HOOKS:
        for server_name, mcp_client in mcp_client_list.items():
            if tool_name in mcp_client.tools_list:
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

def tools_change_messages(request: ChatRequest, settings: dict):
    if settings['tools']['time']['enabled']:
        request.messages[-1]['content'] = f"当前系统时间：{local_timezone}  {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n\n用户：" + request.messages[-1]['content']
    if settings['tools']['inference']['enabled']:
        inference_message = "回答用户前请先思考推理，再回答问题，你的思考推理的过程必须放在<think>与</think>之间。\n\n"
        request.messages[-1]['content'] = f"{inference_message}\n\n用户：" + request.messages[-1]['content']
    if settings['tools']['formula']['enabled']:
        latex_message = "\n\n当你想使用latex公式时，你必须是用 ['$', '$'] 作为行内公式定界符，以及 ['$$', '$$'] 作为行间公式定界符。\n\n"
        if request.messages and request.messages[0]['role'] == 'system':
            request.messages[0]['content'] += latex_message
        else:
            request.messages.insert(0, {'role': 'system', 'content': latex_message})
    return request

async def generate_stream_response(client,reasoner_client, request: ChatRequest, settings: dict):
    global mcp_client_list
    from py.load_files import get_files_content
    from py.web_search import (
        DDGsearch_async, 
        searxng_async, 
        Tavily_search_async,
        duckduckgo_tool, 
        searxng_tool, 
        tavily_tool, 
        jina_crawler_tool, 
        Crawl4Ai_tool
    )
    from py.know_base import kb_tool
    try:
        tools = request.tools or []
        print(tools)
        if mcp_client_list:
            for server_name, mcp_client in mcp_client_list.items():
                if server_name in settings['mcpServers']:
                    if 'disabled' not in settings['mcpServers'][server_name]:
                        settings['mcpServers'][server_name]['disabled'] = False
                    if settings['mcpServers'][server_name]['disabled'] == False and settings['mcpServers'][server_name]['processingStatus'] == 'ready':
                        function = await mcp_client.get_openai_functions()
                        if function:
                            tools.extend(function)
        source_prompt = ""
        if request.fileLinks:
            # 遍历文件链接列表
            for file_link in request.fileLinks:
                # 如果file_link是http://${HOST}:${PORT}开头
                if file_link.startswith(f"http://${HOST}:{PORT}"):
                    # 将"http://${HOST}:{PORT}"替换为"uploaded_files"
                    file_link = file_link.replace(f"http://{HOST}:{PORT}", "uploaded_files")
            # 异步获取文件内容
            files_content = await get_files_content(request.fileLinks)
            fileLinks_message = f"\n\n相关文件内容：{files_content}"
            
            # 修复字符串拼接错误
            if request.messages and request.messages[0]['role'] == 'system':
                request.messages[0]['content'] += fileLinks_message
            else:
                request.messages.insert(0, {'role': 'system', 'content': fileLinks_message})
            source_prompt += fileLinks_message
        kb_list = []
        if settings["knowledgeBases"]:
            for kb in settings["knowledgeBases"]:
                if kb["enabled"] and kb["processingStatus"] == "completed":
                    kb_list.append({"kb_id":kb["id"],"name": kb["name"],"introduction":kb["introduction"]})
        if kb_list:
            kb_list_message = f"\n\n可调用的知识库列表：{json.dumps(kb_list, ensure_ascii=False)}"
            if request.messages and request.messages[0]['role'] == 'system':
                request.messages[0]['content'] += kb_list_message
            else:
                request.messages.insert(0, {'role': 'system', 'content': kb_list_message})
        user_prompt = request.messages[-1]['content']
        request = tools_change_messages(request, settings)
        model = settings['model']
        async def stream_generator(user_prompt):
            if settings['webSearch']['enabled']:
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
                                    "reasoning_content": "思考前联网搜索中，请稍候...\n\n"
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
                    if results:
                        request.messages[-1]['content'] += f"\n\n联网搜索结果：{results}\n\n请根据联网搜索结果组织你的回答，并确保你的回答是准确的。"
                        # 获取时间戳和uuid
                        timestamp = time.time()
                        uid = str(uuid.uuid4())
                        # 构造文件名
                        filename = f"{timestamp}_{uid}.txt"
                        # 将搜索结果写入uploaded_file文件夹下的filename文件
                        with open(f"uploaded_files/{filename}", "w", encoding='utf-8') as f:
                            f.write(str(results))           
                        # 将文件链接更新为新的链接
                        fileLink=f"http://{HOST}:{PORT}/uploaded_files/{filename}"
                        tool_chunk = {
                            "choices": [{
                                "delta": {
                                    "reasoning_content": f"\n\n[搜索结果]({fileLink})\n\n",
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
                    if settings['webSearch']['crawler'] == 'jina':
                        tools.append(jina_crawler_tool)
                    elif settings['webSearch']['crawler'] == 'crawl4ai':
                        tools.append(Crawl4Ai_tool)
            if kb_list:
                tools.append(kb_tool)
            if settings['tools']['deepsearch']['enabled']: 
                deepsearch_messages = copy.deepcopy(request.messages)
                deepsearch_messages[-1]['content'] += "\n\n总结概括一下用户的问题或给出的当前任务，无需回答或执行这些内容，直接返回总结即可，但不能省略问题或任务的细节。如果用户输入的只是闲聊或者不包含任务和问题，直接把用户输入重复输出一遍即可。"
                print(request.messages[-1]['content'])
                response = await client.chat.completions.create(
                    model=model,
                    messages=deepsearch_messages,
                    temperature=0.5
                )
                user_prompt = response.choices[0].message.content
                deepsearch_chunk = {
                    "choices": [{
                        "delta": {
                            "reasoning_content": f"\n\n💖开始执行任务：{user_prompt}\n\n",
                        }
                    }]
                }
                yield f"data: {json.dumps(deepsearch_chunk)}\n\n"
                request.messages[-1]['content'] += f"\n\n如果用户没有提出问题或者任务，直接闲聊即可，如果用户提出了问题或者任务，任务描述不清晰或者你需要进一步了解用户的真实需求，你可以暂时不完成任务，而是分析需要让用户进一步明确哪些需求。"
                print(request.messages[-1]['content'])
            # 如果启用推理模型
            if settings['reasoner']['enabled']:
                reasoner_messages = copy.deepcopy(request.messages)
                if settings['tools']['language']['enabled']:
                    reasoner_messages[-1]['content'] = f"请使用{settings['tools']['language']['language']}语言推理分析思考，不要使用其他语言推理分析，语气风格为{settings['tools']['language']['tone']}\n\n用户：" + reasoner_messages[-1]['content']
                if tools:
                    reasoner_messages[-1]['content'] += f"可用工具：{json.dumps(tools)}"
                # 流式调用推理模型
                reasoner_stream = await reasoner_client.chat.completions.create(
                    model=settings['reasoner']['model'],
                    messages=reasoner_messages,
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
            open_tag = "<think>"
            close_tag = "</think>"
            if settings['tools']['language']['enabled']:
                request.messages[-1]['content'] = f"请使用{settings['tools']['language']['language']}语言回答问题，语气风格为{settings['tools']['language']['tone']}\n\n用户：" + request.messages[-1]['content']
            if tools:
                response = await client.chat.completions.create(
                    model=model,
                    messages=request.messages,
                    temperature=request.temperature,
                    tools=tools,
                    stream=True,
                    max_tokens=request.max_tokens or settings['max_tokens'],
                    top_p=request.top_p,
                    frequency_penalty=request.frequency_penalty,
                    presence_penalty=request.presence_penalty,
                )
            else:
                response = await client.chat.completions.create(
                    model=model,
                    messages=request.messages,
                    temperature=request.temperature,
                    stream=True,
                    max_tokens=request.max_tokens or settings['max_tokens'],
                    top_p=request.top_p,
                    frequency_penalty=request.frequency_penalty,
                    presence_penalty=request.presence_penalty,
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
                            tool_calls[idx].function.arguments += tool.function.arguments
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
            elif settings['tools']['deepsearch']['enabled']: 
                search_prompt = f"""
初始任务：
{user_prompt}

当前结果：
{full_content}

请判断初始任务是否被完成或需要用户明确需求。

如果完成，请输出json字符串：
{{
    "status": "done",
    "unfinished_task": ""
}}

如果未完成，请输出json字符串：
{{
    "status": "not_done",
    "unfinished_task": "这里填入未完成的任务"
}}

如果需要用户明确需求，请输出json字符串：
{{
    "status": "need_more_info",
    "unfinished_task": ""
}}
"""
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
                    temperature=0.5
                )
                response_content = response.choices[0].message.content
                # 用re 提取```json 包裹json字符串 ```
                if "```json" in response_content:
                    try:
                        response_content = re.search(r'```json(.*?)```', response_content, re.DOTALL).group(1)
                    except:
                        # 用re 提取```json 之后的内容
                        response_content = re.search(r'```json(.*?)', response_content, re.DOTALL).group(1)
                response_content = json.loads(response_content)
                if response_content["status"] == "done":
                    search_chunk = {
                        "choices": [{
                            "delta": {
                                "reasoning_content": "\n\n✅任务完成\n\n",
                            }
                        }]
                    }
                    yield f"data: {json.dumps(search_chunk)}\n\n"
                    search_not_done = False
                elif response_content["status"] == "not_done":
                    search_chunk = {
                        "choices": [{
                            "delta": {
                                "reasoning_content": "\n\n❎任务未完成\n\n",
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
                    search_chunk = {
                        "choices": [{
                            "delta": {
                                "reasoning_content": "\n\n❓需要用户明确需求\n\n",
                            }
                        }]
                    }
                    yield f"data: {json.dumps(search_chunk)}\n\n"
                    search_not_done = False
            reasoner_messages = copy.deepcopy(request.messages)
            while tool_calls or search_not_done:
                full_content = ""
                if tool_calls:
                    response_content = tool_calls[0].function
                    if response_content.name in  ["DDGsearch_async","searxng_async", "Tavily_search_async"]:
                        chunk_dict = {
                            "id": "webSearch",
                            "choices": [
                                {
                                    "finish_reason": None,
                                    "index": 0,
                                    "delta": {
                                        "role":"assistant",
                                        "content": "",
                                        "reasoning_content": "\n\n思考后联网搜索中，请稍候...\n\n"
                                    }
                                }
                            ]
                        }
                        yield f"data: {json.dumps(chunk_dict)}\n\n"
                    elif response_content.name in  ["jina_crawler_async","Crawl4Ai_search_async"]:
                        chunk_dict = {
                            "id": "webSearch",
                            "choices": [
                                {
                                    "finish_reason": None,
                                    "index": 0,
                                    "delta": {
                                        "role":"assistant",
                                        "content": "",
                                        "reasoning_content": "\n\n搜索网页详细信息中，请稍候...\n\n"
                                    }
                                }
                            ]
                        }
                        yield f"data: {json.dumps(chunk_dict)}\n\n"
                    elif response_content.name in ["query_knowledge_base"]:
                        chunk_dict = {
                            "id": "webSearch",
                            "choices": [
                                {
                                    "finish_reason": None,
                                    "index": 0,
                                    "delta": {
                                        "role":"assistant",
                                        "content": "",
                                        "reasoning_content": "\n\n查询知识库中，请稍候...\n\n"
                                    }
                                }
                            ]
                        }
                        yield f"data: {json.dumps(chunk_dict)}\n\n"
                    else:
                        chunk_dict = {
                            "id": "webSearch",
                            "choices": [
                                {
                                    "finish_reason": None,
                                    "index": 0,
                                    "delta": {
                                        "role":"assistant",
                                        "content": "",
                                        "reasoning_content": f"\n\n调用{response_content.name}工具中，请稍候...\n\n"
                                    }
                                }
                            ]
                        }
                        yield f"data: {json.dumps(chunk_dict)}\n\n"
                    print(response_content.arguments)
                    modified_data = '[' + response_content.arguments.replace('}{', '},{') + ']'
                    print(modified_data)
                    # 使用json.loads来解析修改后的字符串为列表
                    data_list = json.loads(modified_data)
                    results = await dispatch_tool(response_content.name, data_list[0])
                    if results is None:
                        chunk = {
                            "id": "extra_tools",
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "role":"assistant",
                                        "content": "",
                                        "tool_calls":tool_calls,
                                    }
                                }
                            ]
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
                        break
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
                    # 获取时间戳和uuid
                    timestamp = time.time()
                    uid = str(uuid.uuid4())
                    # 构造文件名
                    filename = f"{timestamp}_{uid}.txt"
                    # 将搜索结果写入uploaded_file文件夹下的filename文件
                    with open(f"uploaded_files/{filename}", "w", encoding='utf-8') as f:
                        f.write(str(results))            
                    # 将文件链接更新为新的链接
                    fileLink=f"http://{HOST}:{PORT}/uploaded_files/{filename}"
                    tool_chunk = {
                        "choices": [{
                            "delta": {
                                "reasoning_content": f"\n\n[{response_content.name}工具结果]({fileLink})\n\n",
                            }
                        }]
                    }
                    yield f"data: {json.dumps(tool_chunk)}\n\n"
                # 如果启用推理模型
                if settings['reasoner']['enabled']:
                    # 流式调用推理模型
                    reasoner_stream = await reasoner_client.chat.completions.create(
                        model=settings['reasoner']['model'],
                        messages=reasoner_messages,
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
                if tools:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=request.messages,
                        temperature=request.temperature,
                        tools=tools,
                        stream=True,
                        max_tokens=request.max_tokens or settings['max_tokens'],
                        top_p=request.top_p,
                        frequency_penalty=request.frequency_penalty,
                        presence_penalty=request.presence_penalty,
                    )
                else:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=request.messages,
                        temperature=request.temperature,
                        stream=True,
                        max_tokens=request.max_tokens or settings['max_tokens'],
                        top_p=request.top_p,
                        frequency_penalty=request.frequency_penalty,
                        presence_penalty=request.presence_penalty,
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
                                    tool_calls[idx].function.arguments += tool.function.arguments
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
                elif settings['tools']['deepsearch']['enabled']: 
                    search_prompt = f"""
初始任务：
{user_prompt}

当前结果：
{full_content}

请判断初始任务是否被完成或需要用户明确需求。

如果完成，请输出json字符串：
{{
    "status": "done",
    "unfinished_task": ""
}}

如果未完成，请输出json字符串：
{{
    "status": "not_done",
    "unfinished_task": "这里填入未完成的任务"
}}

如果需要用户明确需求，请输出json字符串：
{{
    "status": "need_more_info",
    "unfinished_task": ""
}}
"""
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
                    )
                    response_content = response.choices[0].message.content
                    # 用re 提取```json 包裹json字符串 ```
                    if "```json" in response_content:
                        try:
                            response_content = re.search(r'```json(.*?)```', response_content, re.DOTALL).group(1)
                        except:
                            # 用re 提取```json 之后的内容
                            response_content = re.search(r'```json(.*?)', response_content, re.DOTALL).group(1)
                    response_content = json.loads(response_content)
                    if response_content["status"] == "done":
                        search_chunk = {
                            "choices": [{
                                "delta": {
                                    "reasoning_content": "\n\n✅任务完成\n\n",
                                }
                            }]
                        }
                        yield f"data: {json.dumps(search_chunk)}\n\n"
                        search_not_done = False
                    elif response_content["status"] == "not_done":
                        search_chunk = {
                            "choices": [{
                                "delta": {
                                    "reasoning_content": "\n\n❎任务未完成\n\n",
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
                        search_chunk = {
                            "choices": [{
                                "delta": {
                                    "reasoning_content": "\n\n❓需要用户明确需求\n\n",
                                }
                            }]
                        }
                        yield f"data: {json.dumps(search_chunk)}\n\n"
                        search_not_done = False
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream_generator(user_prompt),
            media_type="text/event-stream",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except APIStatusError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"error": {"message": e.message, "type": "api_error", "code": e.code}}
        )

async def generate_complete_response(client,reasoner_client, request: ChatRequest, settings: dict):
    global mcp_client_list
    from py.load_files import get_files_content
    from py.web_search import (
        DDGsearch_async, 
        searxng_async, 
        Tavily_search_async,
        duckduckgo_tool, 
        searxng_tool, 
        tavily_tool, 
        jina_crawler_tool, 
        Crawl4Ai_tool
    )
    from py.know_base import kb_tool
    open_tag = "<think>"
    close_tag = "</think>"
    tools = request.tools or []
    tools = request.tools or []
    print(tools)
    if mcp_client_list:
        for server_name, mcp_client in mcp_client_list.items():
            if server_name in settings['mcpServers']:
                if 'disabled' not in settings['mcpServers'][server_name]:
                    settings['mcpServers'][server_name]['disabled'] = False
                if settings['mcpServers'][server_name]['disabled'] == False and settings['mcpServers'][server_name]['processingStatus'] == 'ready':
                    function = await mcp_client.get_openai_functions()
                    if function:
                        tools.extend(function)
    search_not_done = False
    search_task = ""
    try:
        model = settings['model']
        if request.fileLinks:
            # 遍历文件链接列表
            for file_link in request.fileLinks:
                # 如果file_link是http://${HOST}:${PORT}开头
                if file_link.startswith(f"http://${HOST}:{PORT}"):
                    # 将"http://${HOST}:{PORT}"替换为"uploaded_files"
                    file_link = file_link.replace(f"http://{HOST}:{PORT}", "uploaded_files")
            # 异步获取文件内容
            files_content = await get_files_content(request.fileLinks)
            system_message = f"\n\n相关文件内容：{files_content}"
            
            # 修复字符串拼接错误
            if request.messages and request.messages[0]['role'] == 'system':
                request.messages[0]['content'] += system_message
            else:
                request.messages.insert(0, {'role': 'system', 'content': system_message})
        kb_list = []
        if settings["knowledgeBases"]:
            for kb in settings["knowledgeBases"]:
                if kb["enabled"] and kb["processingStatus"] == "completed":
                    kb_list.append({"kb_id":kb["id"],"name": kb["name"],"introduction":kb["introduction"]})
        if kb_list:
            kb_list_message = f"\n\n可调用的知识库列表：{json.dumps(kb_list, ensure_ascii=False)}"
            if request.messages and request.messages[0]['role'] == 'system':
                request.messages[0]['content'] += kb_list_message
            else:
                request.messages.insert(0, {'role': 'system', 'content': kb_list_message})
        user_prompt = request.messages[-1]['content']
        request = tools_change_messages(request, settings)
        if settings['webSearch']['enabled']:
            if settings['webSearch']['when'] == 'before_thinking' or settings['webSearch']['when'] == 'both':
                if settings['webSearch']['engine'] == 'duckduckgo':
                    results = await DDGsearch_async(user_prompt)
                elif settings['webSearch']['engine'] == 'searxng':
                    results = await searxng_async(user_prompt)
                elif settings['webSearch']['engine'] == 'tavily':
                    results = await Tavily_search_async(user_prompt)
                if results:
                    request.messages[-1]['content'] += f"\n\n联网搜索结果：{results}"
            if settings['webSearch']['when'] == 'after_thinking' or settings['webSearch']['when'] == 'both':
                if settings['webSearch']['engine'] == 'duckduckgo':
                    tools.append(duckduckgo_tool)
                elif settings['webSearch']['engine'] == 'searxng':
                    tools.append(searxng_tool)
                elif settings['webSearch']['engine'] == 'tavily':
                    tools.append(tavily_tool)
                if settings['webSearch']['crawler'] == 'jina':
                    tools.append(jina_crawler_tool)
                elif settings['webSearch']['crawler'] == 'crawl4ai':
                    tools.append(Crawl4Ai_tool)
        if kb_list:
            tools.append(kb_tool)
        if settings['tools']['deepsearch']['enabled']: 
            deepsearch_messages = copy.deepcopy(request.messages)
            deepsearch_messages[-1]['content'] += "/n/n总结概括一下用户的问题或给出的当前任务，无需回答或执行这些内容，直接返回总结即可，但不能省略问题或任务的细节。如果用户输入的只是闲聊或者不包含任务和问题，直接把用户输入重复输出一遍即可。"
            response = await client.chat.completions.create(
                model=model,
                messages=deepsearch_messages,
                temperature=0.5, 
                max_tokens=512
            )
            user_prompt = response.choices[0].message.content
            request.messages[-1]['content'] += f"\n\n如果用户没有提出问题或者任务，直接闲聊即可，如果用户提出了问题或者任务，任务描述不清晰或者你需要进一步了解用户的真实需求，你可以暂时不完成任务，而是分析需要让用户进一步明确哪些需求。"
        if settings['reasoner']['enabled']:
            reasoner_messages = copy.deepcopy(request.messages)
            if settings['tools']['language']['enabled']:
                reasoner_messages[-1]['content'] = f"请使用{settings['tools']['language']['language']}语言推理分析思考，不要使用其他语言推理分析，语气风格为{settings['tools']['language']['tone']}\n\n用户：" + reasoner_messages[-1]['content']
            if tools:
                reasoner_messages[-1]['content'] += f"可用工具：{json.dumps(tools)}"
            reasoner_response = await reasoner_client.chat.completions.create(
                model=settings['reasoner']['model'],
                messages=reasoner_messages,
                stream=False,
                max_tokens=1, # 根据实际情况调整
                temperature=settings['reasoner']['temperature']
            )
            request.messages[-1]['content'] = request.messages[-1]['content'] + "\n\n可参考的推理过程：" + reasoner_response.model_dump()['choices'][0]['message']['reasoning_content']
        if settings['tools']['language']['enabled']:
            request.messages[-1]['content'] = f"请使用{settings['tools']['language']['language']}语言回答问题，语气风格为{settings['tools']['language']['tone']}\n\n用户：" + request.messages[-1]['content']
        if tools:
            response = await client.chat.completions.create(
                model=model,
                messages=request.messages,
                temperature=request.temperature,
                tools=tools,
                stream=False,
                max_tokens=request.max_tokens or settings['max_tokens'],
                top_p=request.top_p,
                frequency_penalty=request.frequency_penalty,
                presence_penalty=request.presence_penalty,
            )
        else:
            response = await client.chat.completions.create(
                model=model,
                messages=request.messages,
                temperature=request.temperature,
                stream=False,
                max_tokens=request.max_tokens or settings['max_tokens'],
                top_p=request.top_p,
                frequency_penalty=request.frequency_penalty,
                presence_penalty=request.presence_penalty,
            )
        if response.choices[0].message.tool_calls:
            pass
        elif settings['tools']['deepsearch']['enabled']: 
            search_prompt = f"""
初始任务：
{user_prompt}

当前结果：
{response.choices[0].message.content}

请判断初始任务是否被完成或需要用户明确需求。

如果完成，请输出json字符串：
{{
    "status": "done",
    "unfinished_task": ""
}}

如果未完成，请输出json字符串：
{{
    "status": "not_done",
    "unfinished_task": "这里填入未完成的任务"
}}

如果需要用户明确需求，请输出json字符串：
{{
    "status": "need_more_info",
    "unfinished_task": ""
}}
"""
            search_response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                    "role": "user",
                    "content": search_prompt,
                    }
                ],
                temperature=0.5,
            )
            response_content = search_response.choices[0].message.content
            print(response_content)
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
                        "content": search_response.choices[0].message.content,
                    }
                )
                request.messages.append(
                    {
                        "role": "user",
                        "content": task_prompt,
                    }
                )
            elif response_content["status"] == "need_more_info":
                search_not_done = False
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
                    result = await dispatch_tool(response_content.name, data) # 将结果添加到results列表中
                    if result is not None:
                        # 将结果添加到results列表中
                        results.append(json.dumps(result))

                # 将所有结果拼接成一个连续的字符串
                combined_results = ''.join(results)
                if combined_results:
                    results = combined_results
                else:
                    results = None
                print(results)
                if results is None:
                    break
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
            if settings['reasoner']['enabled']:

                if tools:
                    reasoner_messages[-1]['content'] += f"可用工具：{json.dumps(tools)}"
                reasoner_response = await reasoner_client.chat.completions.create(
                    model=settings['reasoner']['model'],
                    messages=request.messages,
                    stream=False,
                    max_tokens=1, # 根据实际情况调整
                    temperature=settings['reasoner']['temperature']
                )
                request.messages[-1]['content'] = request.messages[-1]['content'] + "\n\n可参考的推理过程：" + reasoner_response.model_dump()['choices'][0]['message']['reasoning_content']
            if tools:
                response = await client.chat.completions.create(
                    model=model,
                    messages=request.messages,
                    temperature=request.temperature,
                    tools=tools,
                    stream=False,
                    max_tokens=request.max_tokens or settings['max_tokens'],
                    top_p=request.top_p,
                    frequency_penalty=request.frequency_penalty,
                    presence_penalty=request.presence_penalty,
                )
            else:
                response = await client.chat.completions.create(
                    model=model,
                    messages=request.messages,
                    temperature=request.temperature,
                    stream=False,
                    max_tokens=request.max_tokens or settings['max_tokens'],
                    top_p=request.top_p,
                    frequency_penalty=request.frequency_penalty,
                    presence_penalty=request.presence_penalty,
                )
            print(response)
            if response.choices[0].message.tool_calls:
                pass
            elif settings['tools']['deepsearch']['enabled']: 
                search_prompt = f"""
初始任务：
{user_prompt}

当前结果：
{response.choices[0].message.content}

请判断初始任务是否被完成或需要用户明确需求。

如果完成，请输出json字符串：
{{
    "status": "done",
    "unfinished_task": ""
}}

如果未完成，请输出json字符串：
{{
    "status": "not_done",
    "unfinished_task": "这里填入未完成的任务"
}}

如果需要用户明确需求，请输出json字符串：
{{
    "status": "need_more_info",
    "unfinished_task": ""
}}
"""
                search_response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                        "role": "user",
                        "content": search_prompt,
                        }
                    ],
                    temperature=0.5,
                )
                response_content = search_response.choices[0].message.content
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
                            "content": search_response.choices[0].message.content,
                        }
                    )
                    request.messages.append(
                        {
                            "role": "user",
                            "content": task_prompt,
                        }
                    )
                elif response_content["status"] == "need_more_info":
                    search_not_done = False
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
        if settings['reasoner']['enabled']:
            response_dict["choices"][0]['message']['reasoning_content'] = reasoner_response.model_dump()['choices'][0]['message']['reasoning_content']
        return JSONResponse(content=response_dict)
    except APIStatusError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"error": {"message": e.message, "type": "api_error", "code": e.code}}
        )

# 在现有路由后添加以下代码
@app.get("/v1/models")
async def get_models():
    global client, settings,reasoner_client
    
    try:
        # 重新加载最新设置
        current_settings = load_settings()
        
        # 验证API密钥
        if not current_settings.get("api_key"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "message": "API key not configured",
                        "type": "invalid_request_error",
                        "code": "api_key_missing"
                    }
                }
            )
        
        # 动态更新客户端配置
        if (current_settings['api_key'] != settings['api_key'] 
            or current_settings['base_url'] != settings['base_url']):
            client = AsyncOpenAI(
                api_key=current_settings['api_key'],
                base_url=current_settings['base_url'] or "https://api.openai.com/v1",
            )
            settings = current_settings
        if (current_settings['reasoner']['api_key'] != settings['reasoner']['api_key'] 
            or current_settings['reasoner']['base_url'] != settings['reasoner']['base_url']):
            reasoner_client = AsyncOpenAI(
                api_key=current_settings['reasoner']['api_key'],
                base_url=current_settings['reasoner']['base_url'] or "https://api.openai.com/v1",
            )
            settings = current_settings
        # 获取模型列表
        model_list = await client.models.list()
        
        # 转换响应格式与官方API一致
        return JSONResponse(content=model_list.model_dump_json())
        
    except APIStatusError as e:
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

@app.post("/v1/chat/completions")
async def chat_endpoint(request: ChatRequest):
    global client, settings,reasoner_client,mcp_client_list
    model = request.model or 'super-model' # 默认使用 'super-model'
    if model == 'super-model':
        current_settings = load_settings()

        # 动态更新客户端配置
        if (current_settings['api_key'] != settings['api_key'] 
            or current_settings['base_url'] != settings['base_url']):
            if current_settings['api_key']:
                client = AsyncOpenAI(
                    api_key=current_settings['api_key'],
                    base_url=current_settings['base_url'] or "https://api.openai.com/v1",
                )
            else:
                client = AsyncOpenAI(
                    base_url=settings['base_url'] or "https://api.openai.com/v1",
                )
        if (current_settings['reasoner']['api_key'] != settings['reasoner']['api_key'] 
            or current_settings['reasoner']['base_url'] != settings['reasoner']['base_url']):
            if current_settings['reasoner']['api_key']:
                reasoner_client = AsyncOpenAI(
                    api_key=current_settings['reasoner']['api_key'],
                    base_url=current_settings['reasoner']['base_url'] or "https://api.openai.com/v1",
                )
            else:
                reasoner_client = AsyncOpenAI(
                    base_url=settings['reasoner']['base_url'] or "https://api.openai.com/v1",
                )

        if current_settings != settings:
            settings = current_settings
        try:
            if request.stream:
                return await generate_stream_response(client,reasoner_client, request, settings)
            return await generate_complete_response(client,reasoner_client, request, settings)
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
        current_settings = load_settings()
        agentSettings = current_settings['agents'].get(model, {})
        if not agentSettings:
            raise HTTPException(status_code=400, detail="Agent not found")
        if agentSettings['config_path']:
            with open(agentSettings['config_path'], 'r') as f:
                agent_settings = json.load(f)
            # 将"system_prompt"插入到request.messages[0].content中
            if agentSettings['system_prompt']:
                if request.messages[0]['role'] == 'system':
                    request.messages[0]['content'] = agentSettings['system_prompt'] + "\n\n" + request.messages[0].content
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
                return await generate_stream_response(agent_client,agent_reasoner_client, request, agent_settings)
            return await generate_complete_response(agent_client,agent_reasoner_client, request, agent_settings)
        except asyncio.CancelledError:
            # 处理客户端中断连接的情况
            print("Client disconnected")
            raise
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": {"message": str(e), "type": "server_error", "code": 500}}
            )
    
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
        cur_settings = load_settings()
        server_config = cur_settings['mcpServers'][mcp_id]
        
        # 执行初始化逻辑
        if mcp_id not in mcp_client_list:
            mcp_client_list[mcp_id] = McpClient()    
            await asyncio.wait_for(mcp_client_list[mcp_id].initialize(mcp_id, server_config), timeout=10)
        else:
            mcp_client_list[mcp_id].disabled = False
        mcp_status[mcp_id] = "ready"
        
    except Exception as e:
        mcp_client_list[mcp_id].disabled = True
        mcp_status[mcp_id] = f"failed: {str(e)}"
        # 清理失败配置
        cur_settings['mcpServers'].pop(mcp_id, None)
        save_settings(cur_settings)

@app.post("/api/remove_mcp")
async def remove_mcp_server(request: Request):
    global settings, mcp_client_list
    try:
        data = await request.json()
        server_name = data.get("serverName", "")

        if not server_name:
            raise HTTPException(status_code=400, detail="No server names provided")

        # 移除指定的MCP服务器
        current_settings = load_settings()
        if server_name in current_settings['mcpServers']:
            del current_settings['mcpServers'][server_name]
            save_settings(current_settings)
            settings = current_settings

            # 从mcp_client_list中移除
            if server_name in mcp_client_list:
                mcp_client_list[server_name].disabled = True

            return JSONResponse({"success": True, "removed": server_name})
        else:
            raise HTTPException(status_code=404, detail="Server not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        logger.error(f"移除MCP服务器失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 在现有路由之后添加health路由
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 设置文件存储目录
UPLOAD_DIRECTORY = "./uploaded_files"

if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

@app.post("/load_file")
async def load_file_endpoint(request: Request, files: List[UploadFile] = File(None)):
    logger.info(f"Received request with content type: {request.headers.get('Content-Type')}")
    file_links = []
    
    content_type = request.headers.get('Content-Type', '')
    
    try:
        if 'multipart/form-data' in content_type:
            # 处理浏览器上传的文件
            if not files:
                raise HTTPException(status_code=400, detail="No files provided")
            
            for file in files:
                file_extension = os.path.splitext(file.filename)[1]
                unique_filename = f"{uuid.uuid4()}{file_extension}"
                destination = os.path.join(UPLOAD_DIRECTORY, unique_filename)
                
                # 保存上传的文件
                with open(destination, "wb") as buffer:
                    content = await file.read()
                    buffer.write(content)
                
                file_link = {
                    "path": f"http://{HOST}:{PORT}/uploaded_files/{unique_filename}",
                    "name": file.filename
                }
                file_links.append(file_link)
        
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
                destination = os.path.join(UPLOAD_DIRECTORY, unique_filename)
                
                # 复制文件到上传目录
                with open(file_path, "rb") as src, open(destination, "wb") as dst:
                    dst.write(src.read())
                
                file_link = {
                    "path": f"http://{HOST}:{PORT}/uploaded_files/{unique_filename}",
                    "name": file_name
                }
                file_links.append(file_link)
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported Content-Type")
        
        return JSONResponse(content={"success": True, "fileLinks": file_links})
    
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create_kb")
async def create_kb_endpoint(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    kb_id = data.get("kbId")
    
    if not kb_id:
        raise HTTPException(status_code=400, detail="Missing kbId")
    
    # 将任务添加到后台队列
    background_tasks.add_task(process_kb, kb_id)
    
    return {"success": True, "message": "知识库处理已开始，请稍后查询状态"}

# 添加状态存储
kb_status = {}
@app.get("/kb_status/{kb_id}")
async def get_kb_status(kb_id: int):
    status = kb_status.get(kb_id, "not_found")
    return {"kb_id": kb_id, "status": status}

# 修改 process_kb
async def process_kb(kb_id: int):
    kb_status[kb_id] = "processing"
    try:
        from py.know_base import process_knowledge_base
        await process_knowledge_base(kb_id)
        kb_status[kb_id] = "completed"
    except Exception as e:
        kb_status[kb_id] = f"failed: {str(e)}"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    current_settings = load_settings()
    await websocket.send_json({"type": "settings", "data": current_settings})
    
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "save_settings":
                save_settings(data.get("data", {}))
                await websocket.send_json({"type": "settings_saved", "success": True})
            elif data.get("type") == "get_settings":
                settings = load_settings()
                await websocket.send_json({"type": "settings", "data": settings})
            elif data.get("type") == "save_agent":
                current_settings = load_settings()
                
                # 生成智能体ID和配置路径
                agent_id = str(shortuuid.ShortUUID().random(length=8))
                os.makedirs('agents', exist_ok=True)
                config_path = os.path.join('agents', f"{agent_id}.json")
                
                with open(config_path, 'w') as f:
                    json.dump(current_settings, f, indent=4, ensure_ascii=False)
                
                # 更新主配置
                current_settings['agents'][agent_id] = {
                    "id": agent_id,
                    "name": data['data']['name'],
                    "system_prompt": data['data']['system_prompt'],
                    "config_path": config_path,
                    "enabled": False,
                }
                save_settings(current_settings)
                
                # 广播更新后的配置
                await websocket.send_json({
                    "type": "settings",
                    "data": current_settings
                })
    except Exception as e:
        print(f"WebSocket error: {e}")

app.mount("/uploaded_files", StaticFiles(directory="uploaded_files"), name="uploaded_files")
app.mount("/node_modules", StaticFiles(directory=os.path.join(base_path, "node_modules")), name="node_modules")
app.mount("/", StaticFiles(directory=os.path.join(base_path, "static"), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)