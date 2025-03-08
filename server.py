from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

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
    await websocket.send_text("连接成功！")
    try:
        while True:
            data = await websocket.receive_text()
            print(f"收到消息: {data}")
            await websocket.send_text(f"你发送了: {data}")
    except Exception as e:
        print(f"WebSocket连接关闭: {e}")
