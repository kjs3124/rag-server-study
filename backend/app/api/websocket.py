from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import asyncio
from ..services.task_manager import task_manager, TaskStatus

router = APIRouter()

class ConnectionManager:
    """WebSocket 연결 관리자"""
    
    def __init__(self):
        # 연결된 클라이언트들: {client_id: websocket}
        self.active_connections: Dict[str, WebSocket] = {}
        # 클라이언트별 구독 중인 작업들: {client_id: [task_ids]}
        self.subscriptions: Dict[str, List[str]] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str):
        """클라이언트 연결"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.subscriptions[client_id] = []
        print(f"WebSocket 클라이언트 연결: {client_id}")
        
    def disconnect(self, client_id: str):
        """클라이언트 연결 해제"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.subscriptions:
            del self.subscriptions[client_id]
        print(f"WebSocket 클라이언트 연결 해제: {client_id}")
        
    async def send_personal_message(self, message: dict, client_id: str):
        """특정 클라이언트에게 메시지 전송"""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                print(f"메시지 전송 실패 {client_id}: {e}")
                self.disconnect(client_id)
                
    async def broadcast(self, message: dict):
        """모든 연결된 클라이언트에게 메시지 전송"""
        for client_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, client_id)
    
    def subscribe_to_task(self, client_id: str, task_id: str):
        """작업 상태 구독"""
        if client_id in self.subscriptions:
            if task_id not in self.subscriptions[client_id]:
                self.subscriptions[client_id].append(task_id)
                
    def unsubscribe_from_task(self, client_id: str, task_id: str):
        """작업 상태 구독 해제"""
        if client_id in self.subscriptions and task_id in self.subscriptions[client_id]:
            self.subscriptions[client_id].remove(task_id)
    
    async def notify_task_update(self, task_id: str):
        """작업 상태 업데이트를 구독자들에게 알림"""
        task = task_manager.get_task(task_id)
        if not task:
            return
            
        message = {
            "type": "task_update",
            "task_id": task_id,
            "status": task.status,
            "progress": task.progress,
            "message": task.message,
            "result": task.result,
            "error": task.error
        }
        
        # 해당 작업을 구독 중인 모든 클라이언트에게 알림
        for client_id, subscribed_tasks in self.subscriptions.items():
            if task_id in subscribed_tasks:
                await self.send_personal_message(message, client_id)

manager = ConnectionManager()

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket 연결 엔드포인트"""
    await manager.connect(websocket, client_id)
    try:
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # 메시지 타입에 따른 처리
            if message["type"] == "subscribe":
                # 작업 구독
                task_id = message.get("task_id")
                if task_id:
                    manager.subscribe_to_task(client_id, task_id)
                    
                    # 현재 작업 상태 즉시 전송
                    task = task_manager.get_task(task_id)
                    if task:
                        await manager.send_personal_message({
                            "type": "task_update",
                            "task_id": task_id,
                            "status": task.status,
                            "progress": task.progress,
                            "message": task.message,
                            "result": task.result,
                            "error": task.error
                        }, client_id)
                        
            elif message["type"] == "unsubscribe":
                # 작업 구독 해제
                task_id = message.get("task_id")
                if task_id:
                    manager.unsubscribe_from_task(client_id, task_id)
                    
            elif message["type"] == "ping":
                # 연결 확인
                await manager.send_personal_message({
                    "type": "pong",
                    "timestamp": message.get("timestamp")
                }, client_id)
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)

class TaskNotifier:
    """작업 상태 변경 알림 헬퍼"""
    
    @staticmethod
    async def notify_progress(task_id: str, progress: int, message: str = ""):
        """진행상황 업데이트"""
        task_manager.update_task(task_id, progress=progress, message=message)
        await manager.notify_task_update(task_id)
        
    @staticmethod
    async def notify_completed(task_id: str, result: dict):
        """작업 완료 알림"""
        task_manager.update_task(
            task_id, 
            status=TaskStatus.COMPLETED, 
            progress=100,
            message="작업이 완료되었습니다",
            result=result
        )
        await manager.notify_task_update(task_id)
        
    @staticmethod
    async def notify_failed(task_id: str, error: str):
        """작업 실패 알림"""
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message="작업이 실패했습니다", 
            error=error
        )
        await manager.notify_task_update(task_id)
        
    @staticmethod
    async def notify_started(task_id: str):
        """작업 시작 알림"""
        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=0,
            message="작업을 시작합니다"
        )
        await manager.notify_task_update(task_id)

# 전역 인스턴스
task_notifier = TaskNotifier()