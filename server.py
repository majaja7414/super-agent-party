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

from fastapi import HTTPException
from pydantic import BaseModel
from fastapi.responses import JSONResponse

class ChatRequest(BaseModel):
    messages: list

async def get_openai_response(client: AsyncOpenAI, messages: list, model="gpt-4o-mini"):
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/completions")
async def chat_endpoint(request: ChatRequest):
    settings = load_settings()
    
    if not settings.get("apiKey"):
        return JSONResponse(
            status_code=400,
            content={"error": "API key not configured"}
        )
        
    client = AsyncOpenAI(
        api_key=settings.get("apiKey"),
        base_url=settings.get("baseURL") if settings.get("baseURL") else "https://api.openai.com/v1"
    )
    model = settings.get("modelName") or "gpt-4o-mini"
    try:
        response = await get_openai_response(client, request.messages,model=model)
        return {"response": response}
    except Exception as e:
        print(f"处理请求时发生错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3456)
