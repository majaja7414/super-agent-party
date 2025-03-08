import json
import os
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
import asyncio

app = FastAPI()
SETTINGS_FILE = 'settings.json'

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"modelName": "", "baseURL": "", "apiKey": ""}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

# Allow CORS for WebSocket connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # 连接成功后立即发送当前设置
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
            else:
                print(f"收到消息: {data}")
                await websocket.send_text(f"你发送了: {str(data)}")
    except Exception as e:
        print(f"WebSocket连接关闭: {e}")

async def get_openai_response(client: AsyncOpenAI, messages: list, websocket: WebSocket):
    try:
        stream = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            stream=True
        )
        
        collected_chunks = []
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                collected_chunks.append(content)
                # 实时发送每个文本片段
                await websocket.send_json({
                    "type": "assistant_chunk",
                    "content": content
                })
        
        # 发送完成标记
        await websocket.send_json({
            "type": "assistant_complete",
            "content": "".join(collected_chunks)
        })
        
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })

@app.websocket("/chat")
async def chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    settings = load_settings()
    
    if not settings.get("apiKey"):
        await websocket.send_json({
            "type": "error",
            "message": "API key not configured"
        })
        return
        
    client = AsyncOpenAI(
        api_key=settings.get("apiKey"),
        base_url=settings.get("baseURL") if settings.get("baseURL") else "https://api.openai.com/v1"
    )
    
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "chat_message":
                messages = data.get("messages", [])
                await get_openai_response(client, messages, websocket)
    except Exception as e:
        print(f"Chat WebSocket连接关闭: {e}")
