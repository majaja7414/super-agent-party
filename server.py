import json
import os
from fastapi import FastAPI, HTTPException, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI, APIStatusError
from pydantic import BaseModel
from fastapi.responses import JSONResponse, StreamingResponse
import uuid
import time
from typing import List, Dict

app = FastAPI()
SETTINGS_FILE = 'settings.json'

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "model": "gpt-4o-mini",  # 使用OpenAI官方参数名
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "temperature": 0.7,
            "max_tokens": 4096
        }

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

    if cur_settings != settings:
        settings = cur_settings
        client = AsyncOpenAI(
            api_key=settings['api_key'],
            base_url=settings['base_url'] or "https://api.openai.com/v1",
        )

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
