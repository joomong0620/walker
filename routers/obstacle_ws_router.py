# routers/obstacle_ws.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

obstacle_ws_router = APIRouter()

connected_clients = []

@obstacle_ws_router.websocket("/ws/obstacle")
async def websocket_obstacle(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    print("🔌 WebSocket 연결됨")

    try:
        while True:
            await websocket.receive_text()  # or just await asyncio.sleep(1)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        print("❌ WebSocket 연결 끊김")
