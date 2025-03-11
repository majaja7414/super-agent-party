import json
import os
from fastapi import FastAPI, HTTPException, WebSocket, Request
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
local_timezone = get_localzone()
app = FastAPI()
SETTINGS_FILE = 'config/settings.json'

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # 创建config文件夹
        os.makedirs('config', exist_ok=True)
        # 创建settings.json文件
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            f.write('{}')
        default_settings =  {
            "model": "qwen2.5:14b",  # 使用OpenAI官方参数名
            "base_url": "http://localhost:11434/v1",
            "api_key": "",
            "temperature": 0.7,
            "max_tokens": 4096,
            "max_rounds": 10,
            "tools": {
                "time": {
                    "enabled": False,
                }
            },
              "reasoner": {
                "enabled": False,
                "model": "deepseek-r1:14b",
                "base_url": "http://localhost:11434/v1",
                "api_key": ""
            }
        }
        return default_settings

settings = load_settings()
client = AsyncOpenAI(api_key=settings['api_key'], base_url=settings['base_url'])

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

async def generate_stream_response(client, request: ChatRequest, settings: dict):
    try:
        if settings['tools']['time']:
            if request.messages[-1]['role'] == 'user':
                request.messages[-1]['content'] = f"当前系统时间：{local_timezone}  {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n\n用户：" + request.messages[-1]['content']

        model = request.model or settings['model']
        if model == 'super-model':
            model = settings['model']
        
        response = await client.chat.completions.create(
            model=model,
            messages=request.messages,
            temperature=request.temperature,
            tools=request.tools,
            stream=True,
            max_tokens=request.max_tokens or settings['max_tokens'],
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
        )

        async def stream_generator():
            # 状态跟踪变量
            in_reasoning = False
            reasoning_buffer = []
            content_buffer = []
            open_tag = "<think>"
            close_tag = "</think>"
            
            async for chunk in response:
                if not chunk.choices:
                    continue
                
                # 创建原始chunk的拷贝
                chunk_dict = chunk.model_dump()
                delta = chunk_dict["choices"][0]["delta"]
                
                # 初始化必要字段
                delta.setdefault("content", "")
                delta.setdefault("reasoning_content", "")
                
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

async def generate_complete_response(client, request: ChatRequest, settings: dict):
    try:
        if settings['tools']['time']:
            if request.messages[-1]['role'] == 'user':
                request.messages[-1]['content'] = f"当前系统时间：{local_timezone}  {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n\n用户：" + request.messages[-1]['content']

        model = request.model or settings['model']
        if model == 'super-model':
            model = settings['model']
        response = await client.chat.completions.create(
            model=model,
            messages=request.messages,
            temperature=request.temperature,
            tools=request.tools,
            stream=False,
            max_tokens=request.max_tokens or settings['max_tokens'],
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
        )
        open_tag = "<think>"
        close_tag = "</think>"
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
        
        return JSONResponse(content=response_dict)
    except APIStatusError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"error": {"message": e.message, "type": "api_error", "code": e.code}}
        )

# 在现有路由后添加以下代码
@app.get("/v1/models")
async def get_models():
    global client, settings
    
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
    global client, settings

    cur_settings = load_settings()
    
    if not cur_settings.get("api_key"):
        raise HTTPException(status_code=400, detail={
            "error": {
                "message": "API key not configured",
                "type": "invalid_request_error",
                "code": "api_key_missing"
            }
        })

    if cur_settings['api_key'] != settings['api_key'] or cur_settings['base_url'] != settings['base_url']:
        settings = cur_settings
        client = AsyncOpenAI(
            api_key=settings['api_key'],
            base_url=settings['base_url'] or "https://api.openai.com/v1",
        )
    elif cur_settings != settings:
        settings = cur_settings

    try:
        if request.stream:
            return await generate_stream_response(client, request, settings)
        return await generate_complete_response(client, request, settings)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e), "type": "server_error", "code": 500}}
        )

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

app.mount("/node_modules", StaticFiles(directory="node_modules"), name="node_modules")
app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/js", StaticFiles(directory="js"), name="js")
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3456)
