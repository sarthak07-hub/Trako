import json
from typing import Dict, List
from fastapi import WebSocket

class TrackingConnectionManager:
    def __init__(self):
        # trip_id -> list of active WebSocket connections
        self.trip_connections: Dict[int, List[WebSocket]] = {}
        # operator_id -> list of active fleet monitor WebSockets
        self.operator_connections: Dict[int, List[WebSocket]] = {}

    async def connect_trip(self, trip_id: int, websocket: WebSocket):
        await websocket.accept()
        if trip_id not in self.trip_connections:
            self.trip_connections[trip_id] = []
        self.trip_connections[trip_id].append(websocket)

    def disconnect_trip(self, trip_id: int, websocket: WebSocket):
        if trip_id in self.trip_connections:
            if websocket in self.trip_connections[trip_id]:
                self.trip_connections[trip_id].remove(websocket)
            if not self.trip_connections[trip_id]:
                del self.trip_connections[trip_id]

    async def broadcast_trip_location(self, trip_id: int, message: dict):
        if trip_id in self.trip_connections:
            disconnected = []
            for connection in self.trip_connections[trip_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception:
                    disconnected.append(connection)
            for d in disconnected:
                self.disconnect_trip(trip_id, d)

    async def connect_operator(self, operator_id: int, websocket: WebSocket):
        await websocket.accept()
        if operator_id not in self.operator_connections:
            self.operator_connections[operator_id] = []
        self.operator_connections[operator_id].append(websocket)

    def disconnect_operator(self, operator_id: int, websocket: WebSocket):
        if operator_id in self.operator_connections:
            if websocket in self.operator_connections[operator_id]:
                self.operator_connections[operator_id].remove(websocket)
            if not self.operator_connections[operator_id]:
                del self.operator_connections[operator_id]

    async def broadcast_operator_fleet(self, operator_id: int, message: dict):
        if operator_id in self.operator_connections:
            disconnected = []
            for connection in self.operator_connections[operator_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception:
                    disconnected.append(connection)
            for d in disconnected:
                self.disconnect_operator(operator_id, d)

ws_manager = TrackingConnectionManager()
