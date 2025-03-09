import json
import os
from fastapi import FastAPI, HTTPException, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI, APIStatusError
from pydantic import BaseModel
from fastapi import status
from fastapi.responses import JSONResponse, StreamingResponse
import uuid
import time
from typing import List, Dict

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
            "model": "gpt-4o-mini",  # 使用OpenAI官方参数名
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "temperature": 0.7,
            "max_tokens": 4096,
            "max_rounds": 10,
            "tools": {
                "time": {
                    "enabled": False,
                },
                "knowledge": {
                    "enabled": False,
                    "model": "",
                    "file_path": ""
                },
                "network": {
                    "enabled": False,
                    "search_engine": "duckduckgo"
                }
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
    stream: bool = False
    max_tokens: int = None
    top_p: float = 1
    frequency_penalty: float = 0
    presence_penalty: float = 0

async def generate_stream_response(client, request: ChatRequest, settings: dict):
    try:
        if settings['tools']['time']:
            print("time")
            if request.messages[0]:
                if request.messages[0]['role'] == 'system':
                    request.messages[0]['content'] += f"当前时间： {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
                else:
                    request.messages.insert(0, {
                        "role": "system",
                        "content": f"\n\n当前时间： {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
                    })

        response = await client.chat.completions.create(
            model=request.model or settings['model'],
            messages=request.messages,
            temperature=request.temperature,
            stream=True,
            max_tokens=request.max_tokens or settings['max_tokens'],
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
        )

        async def stream_generator():
            async for chunk in response:
                yield f"data: {chunk.model_dump_json()}\n\n"
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
            print("time")
            if request.messages[0]:
                if request.messages[0]['role'] == 'system':
                    request.messages[0]['content'] += f"当前时间： {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
                else:
                    request.messages.insert(0, {
                        "role": "system",
                        "content": f"\n\n当前时间： {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
                    })

        response = await client.chat.completions.create(
            model=request.model or settings['model'],
            messages=request.messages,
            temperature=request.temperature,
            stream=False,
            max_tokens=request.max_tokens or settings['max_tokens'],
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
        )
        return JSONResponse(content=response.model_dump())
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
        return JSONResponse(content=model_list.model_dump())
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3456)
