from fastapi import WebSocket
from typing import List, Any
from datetime import datetime


def _make_json_serializable(obj: Any) -> Any:
    """递归将 datetime 转为 ISO 字符串，确保可被 json.dumps 序列化"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_serializable(x) for x in obj]
    return obj


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message_type: str, data: Any):
        msg = {
            "type": message_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": _make_json_serializable(data),
        }
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(msg)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.disconnect(d)

manager = ConnectionManager()