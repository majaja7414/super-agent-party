# -- coding: utf-8 --
import copy
import json
import os
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, Request
import logging
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI, APIStatusError
from pydantic import BaseModel
from fastapi import status
from fastapi.responses import JSONResponse, StreamingResponse
import uuid
import time
from typing import List, Dict
from tzlocal import get_localzone
from py.load_files import get_files_content
from py.web_search import DDGsearch_async,duckduckgo_tool,searxng_async, searxng_tool,Tavily_search_async, tavily_tool
HOST = '127.0.0.1'
PORT = 3456
local_timezone = get_localzone()
logger = logging.getLogger(__name__)
app = FastAPI()
SETTINGS_FILE = 'config/settings.json'
# 设置模板文件
SETTINGS_TEMPLATE_FILE = 'config/settings_template.json'
# 加载settings_template.json文件
with open(SETTINGS_TEMPLATE_FILE, 'r', encoding='utf-8') as f:
    default_settings = json.load(f)
def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        # 与default_settings比较，如果缺少字段或者二级字段，则添加默认值
        for key, value in default_settings.items():
            if key not in settings:
                settings[key] = value
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if sub_key not in settings[key]:
                        settings[key][sub_key] = sub_value
        return settings
    except FileNotFoundError:
        # 创建config文件夹
        os.makedirs('config', exist_ok=True)
        # 创建settings.json文件，并写入默认设置
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, ensure_ascii=False, indent=2)
        return default_settings

settings = load_settings()
if settings:
    client = AsyncOpenAI(api_key=settings['api_key'], base_url=settings['base_url'])
    reasoner_client = AsyncOpenAI(api_key=settings['reasoner']['api_key'],base_url=settings['reasoner']['base_url'])
else:
    client = AsyncOpenAI()
    reasoner_client = AsyncOpenAI()
def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_TOOL_HOOKS = {
    "DDGsearch_async": DDGsearch_async,
    "searxng_async": searxng_async,
    "Tavily_search_async": Tavily_search_async
}

async def dispatch_tool(tool_name: str, tool_params: dict) -> str:
    if "multi_tool_use." in tool_name:
        tool_name = tool_name.replace("multi_tool_use.", "")
    if tool_name not in _TOOL_HOOKS:
        return None
    tool_call = globals().get(tool_name)
    try:
        ret_out = await tool_call(**tool_params)
        return ret_out
    except:
        return f"调用工具{tool_name}失败"


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
    if settings['tools']['language']['enabled']:
        request.messages[-1]['content'] = f"请使用{settings['tools']['language']['language']}语言回答问题，语气风格为{settings['tools']['language']['tone']}\n\n用户：" + request.messages[-1]['content']
    if settings['tools']['inference']['enabled']:
        inference_message = "回答用户前请先思考推理，再回答问题，你的思考推理的过程必须放在<think>与</think>之间。\n\n"
        request.messages[-1]['content'] = f"{inference_message}\n\n用户：" + request.messages[-1]['content']
    return request

async def generate_stream_response(client,reasoner_client, request: ChatRequest, settings: dict):
    try:
        tools = request.tools or []
        if request.fileLinks:
            # 异步获取文件内容
            files_content = await get_files_content(request.fileLinks)
            system_message = f"\n\n相关文件内容：{files_content}"
            
            # 修复字符串拼接错误
            if request.messages and request.messages[0]['role'] == 'system':
                request.messages[0]['content'] += system_message
            else:
                request.messages.insert(0, {'role': 'system', 'content': system_message})
        user_prompt = request.messages[-1]['content']
        request = tools_change_messages(request, settings)
        model = request.model or settings['model']
        if model == 'super-model':
            model = settings['model']
        async def stream_generator():
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
                if settings['webSearch']['when'] == 'after_thinking' or settings['webSearch']['when'] == 'both':
                    if settings['webSearch']['engine'] == 'duckduckgo':
                        tools.append(duckduckgo_tool)
                    elif settings['webSearch']['engine'] == 'searxng':
                        tools.append(searxng_tool)
                    elif settings['webSearch']['engine'] == 'tavily':
                        tools.append(tavily_tool)
            # 如果启用推理模型
            if settings['reasoner']['enabled']:
                reasoner_messages = request.messages.copy()
                if tools:
                    reasoner_messages[-1]['content'] += f"可用工具：{json.dumps(tools)}"
                # 流式调用推理模型
                reasoner_stream = await reasoner_client.chat.completions.create(
                    model=settings['reasoner']['model'],
                    messages=request.messages,
                    stream=True,
                    max_tokens=1 # 根据实际情况调整
                )
                full_reasoning = ""
                # 处理推理模型的流式响应
                async for chunk in reasoner_stream:
                    if not chunk.choices:
                        continue

                    chunk_dict = chunk.model_dump()
                    delta = chunk_dict["choices"][0].get("delta", {})
                    full_reasoning += delta.get("reasoning_content", "")
                    
                    yield f"data: {json.dumps(chunk_dict)}\n\n"

                # 在推理结束后添加完整推理内容到消息
                request.messages[-1]['content'] += f"\n\n可参考的推理过程：{full_reasoning}"
            # 状态跟踪变量
            in_reasoning = False
            reasoning_buffer = []
            content_buffer = []
            open_tag = "<think>"
            close_tag = "</think>"

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
            tool_calls = []
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
            while tool_calls:
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
                results = await dispatch_tool(response_content.name, json.loads(response_content.arguments))
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
                                    "arguments": response_content.arguments,
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
            
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream_generator(),
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
    open_tag = "<think>"
    close_tag = "</think>"
    tools = request.tools or []
    try:
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
        if settings['reasoner']['enabled']:
            reasoner_messages = request.messages.copy()
            if tools:
                reasoner_messages[-1]['content'] += f"可用工具：{json.dumps(tools)}"
            reasoner_response = await reasoner_client.chat.completions.create(
                model=settings['reasoner']['model'],
                messages=request.messages,
                stream=False,
                max_tokens=1,
            )
            request.messages[-1]['content'] = request.messages[-1]['content'] + "\n\n可参考的推理过程：" + reasoner_response.model_dump()['choices'][0]['message']['reasoning_content']
            print(request.messages[-1]['content'])
        model = request.model or settings['model']
        if model == 'super-model':
            model = settings['model']
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
        print(request.messages)
        while response.choices[0].message.tool_calls:
            assistant_message = response.choices[0].message
            response_content = assistant_message.tool_calls[0].function
            print(response_content.name)
            results = await dispatch_tool(response_content.name, json.loads(response_content.arguments))
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
            print(request.messages)
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
            print(response)
       # 处理响应内容
        response_dict = response.model_dump()
        content = response_dict["choices"][0]['message']['content']
        if open_tag in content and close_tag in content:
            # 使用正则表达式提取标签内容
            import re
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

@app.post("/v1/chat/completions")
async def chat_endpoint(request: ChatRequest):
    global client, settings,reasoner_client

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
                api_key="ollama",
                base_url=settings['base_url'] or "https://api.openai.com/v1",
            )
        settings = current_settings
    if (current_settings['reasoner']['api_key'] != settings['reasoner']['api_key'] 
        or current_settings['reasoner']['base_url'] != settings['reasoner']['base_url']):
        if current_settings['reasoner']['api_key']:
            reasoner_client = AsyncOpenAI(
                api_key=current_settings['reasoner']['api_key'],
                base_url=current_settings['reasoner']['base_url'] or "https://api.openai.com/v1",
            )
        else:
            reasoner_client = AsyncOpenAI(
                api_key="ollama",
                base_url=settings['reasoner']['base_url'] or "https://api.openai.com/v1",
            )
        settings = current_settings
    elif current_settings != settings:
        settings = current_settings

    try:
        if request.stream:
            return await generate_stream_response(client,reasoner_client, request, settings)
        return await generate_complete_response(client,reasoner_client, request, settings)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e), "type": "server_error", "code": 500}}
        )
    

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
    except Exception as e:
        print(f"WebSocket error: {e}")

app.mount("/uploaded_files", StaticFiles(directory="uploaded_files"), name="uploaded_files")
app.mount("/node_modules", StaticFiles(directory="node_modules"), name="node_modules")
app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/js", StaticFiles(directory="js"), name="js")
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)