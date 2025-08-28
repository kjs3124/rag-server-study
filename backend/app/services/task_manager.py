from typing import Dict, Optional, Any, List
from datetime import datetime
from enum import Enum
import uuid
import json
import asyncio
from dataclasses import dataclass, asdict
from collections import deque
import threading
import logging
from .persistence import load_tasks, save_tasks

logger = logging.getLogger(__name__)

class TaskStatus(str, Enum):
    """작업 상태"""
    PENDING = "pending"      # 대기 중
    PROCESSING = "processing"  # 처리 중
    COMPLETED = "completed"   # 완료
    FAILED = "failed"        # 실패
    CANCELLED = "cancelled"   # 취소됨

class TaskType(str, Enum):
    """작업 타입"""
    FILE_UPLOAD = "file_upload"
    WEB_CRAWL = "web_crawl"
    DOCUMENT_PARSE = "document_parse"

@dataclass
class TaskInfo:
    """작업 정보"""
    task_id: str
    task_type: TaskType
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0  # 0-100%
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    # 작업별 메타데이터
    metadata: Optional[Dict[str, Any]] = None

class TaskManager:
    """비동기 작업 관리자 (파일 기반 영속성 지원)"""
    
    def __init__(self):
        # 기존 작업 정보 로드
        try:
            loaded_tasks = load_tasks()
            # TaskInfo 객체로 재구성 (pickle이 dataclass를 처리)
            self.tasks: Dict[str, TaskInfo] = loaded_tasks
            
            # 대기 중인 작업만 큐에 다시 추가
            self.task_queue: deque = deque()
            for task_id, task in self.tasks.items():
                if task.status == TaskStatus.PENDING:
                    self.task_queue.append(task_id)
            
            logger.info(f"📋 기존 작업 데이터 로드 완료: {len(self.tasks)}개 작업, {len(self.task_queue)}개 대기 중")
        except Exception as e:
            logger.warning(f"작업 데이터 로드 실패, 새로 시작: {e}")
            self.tasks: Dict[str, TaskInfo] = {}
            self.task_queue: deque = deque()
            
        self.lock = threading.Lock()
        
    def create_task(self, task_type: TaskType, metadata: Optional[Dict] = None) -> str:
        """새 작업 생성"""
        task_id = str(uuid.uuid4())
        
        task_info = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            metadata=metadata or {}
        )
        
        with self.lock:
            # 메모리에 작업 정보 저장
            self.tasks[task_id] = task_info
            
            # 작업 큐에 추가
            self.task_queue.append(task_id)
            
            # 파일로 영속화
            save_tasks(self.tasks)
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """작업 정보 조회"""
        return self.tasks.get(task_id)
    
    def update_task(self, task_id: str, **updates) -> bool:
        """작업 상태 업데이트"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
                
            # 업데이트 적용
            for key, value in updates.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            
            # 상태 변경 시 시간 자동 설정
            if 'status' in updates:
                if updates['status'] == TaskStatus.PROCESSING and not task.started_at:
                    task.started_at = datetime.now()
                elif updates['status'] in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    task.completed_at = datetime.now()
            
            # 파일로 영속화
            save_tasks(self.tasks)
        
        return True
    
    def get_pending_task(self) -> Optional[str]:
        """대기 중인 작업 하나 가져오기"""
        with self.lock:
            # 큐에서 대기 중인 작업 찾기
            while self.task_queue:
                task_id = self.task_queue.popleft()
                task = self.tasks.get(task_id)
                
                if task and task.status == TaskStatus.PENDING:
                    # 작업 상태를 처리 중으로 변경
                    task.status = TaskStatus.PROCESSING
                    task.started_at = datetime.now()
                    return task_id
                    
        return None
    
    def get_user_tasks(self, user_id: Optional[str] = None, limit: int = 50) -> List[TaskInfo]:
        """사용자 작업 목록 조회 (현재는 전체 조회)"""
        with self.lock:
            tasks = list(self.tasks.values())
            
        # 생성 시간 역순 정렬
        tasks.sort(key=lambda x: x.created_at, reverse=True)
        
        # 제한된 수만큼 반환
        return tasks[:limit]
    
    def cancel_task(self, task_id: str) -> bool:
        """작업 취소"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task or task.status not in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
                return False
            
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            
            # 큐에서 제거 (대기 중인 경우)
            if task_id in self.task_queue:
                self.task_queue.remove(task_id)
            
            # 파일로 영속화
            save_tasks(self.tasks)
                
        return True
    
    def cleanup_old_tasks(self, hours: int = 24):
        """오래된 작업 정리 (선택적)"""
        with self.lock:
            now = datetime.now()
            to_remove = []
            
            for task_id, task in self.tasks.items():
                if task.completed_at:
                    age = (now - task.completed_at).total_seconds() / 3600
                    if age > hours:
                        to_remove.append(task_id)
                        
            for task_id in to_remove:
                del self.tasks[task_id]
            
            # 삭제 후 파일로 영속화
            if to_remove:
                save_tasks(self.tasks)
                logger.info(f"🗑️ 오래된 작업 {len(to_remove)}개 정리 완료")
                
            return len(to_remove)

# 싱글톤 인스턴스
task_manager = TaskManager()