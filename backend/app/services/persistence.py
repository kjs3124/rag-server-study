"""
데이터 영속성 관리 모듈
서버 재시작 시에도 데이터를 유지하기 위한 파일 기반 저장소
"""

import os
import pickle
import json
import logging
from typing import Any, Dict, Optional
from pathlib import Path
from datetime import datetime
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class PersistenceManager:
    """
    파일 기반 데이터 영속성 관리자
    
    Features:
    - 자동 저장/로드
    - 백업 관리
    - 스레드 안전성
    - 에러 복구
    """
    
    def __init__(self, data_dir: str = "./data/persistence"):
        """
        Args:
            data_dir: 데이터 저장 디렉토리
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        
        # 파일 경로 설정
        self.documents_file = self.data_dir / "documents.pickle"
        self.tasks_file = self.data_dir / "tasks.pickle"
        
        # 백업 디렉토리
        self.backup_dir = self.data_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
    def save_documents(self, documents_db: Dict[str, Any]) -> bool:
        """
        문서 데이터베이스 저장
        
        Args:
            documents_db: 저장할 문서 딕셔너리
            
        Returns:
            bool: 저장 성공 여부
        """
        return self._save_data(documents_db, self.documents_file, "documents")
    
    def load_documents(self) -> Dict[str, Any]:
        """
        문서 데이터베이스 로드
        
        Returns:
            Dict: 문서 데이터베이스 (없으면 빈 딕셔너리)
        """
        return self._load_data(self.documents_file, "documents")
    
    def save_tasks(self, tasks: Dict[str, Any]) -> bool:
        """
        작업 정보 저장
        
        Args:
            tasks: 저장할 작업 딕셔너리
            
        Returns:
            bool: 저장 성공 여부
        """
        return self._save_data(tasks, self.tasks_file, "tasks")
    
    def load_tasks(self) -> Dict[str, Any]:
        """
        작업 정보 로드
        
        Returns:
            Dict: 작업 딕셔너리 (없으면 빈 딕셔너리)
        """
        return self._load_data(self.tasks_file, "tasks")
    
    def _save_data(self, data: Any, file_path: Path, data_type: str) -> bool:
        """
        데이터를 파일로 저장 (내부 메서드)
        
        Args:
            data: 저장할 데이터
            file_path: 저장 경로
            data_type: 데이터 타입 (로깅용)
            
        Returns:
            bool: 저장 성공 여부
        """
        with self.lock:
            try:
                # 기존 파일 백업
                if file_path.exists():
                    self._create_backup(file_path, data_type)
                
                # 임시 파일에 먼저 저장 (원자성 보장)
                temp_path = file_path.with_suffix('.tmp')
                with open(temp_path, 'wb') as f:
                    pickle.dump(data, f)
                
                # 임시 파일을 실제 파일로 이동
                temp_path.replace(file_path)
                
                logger.info(f"✅ {data_type} 데이터 저장 완료: {len(data)} 항목")
                return True
                
            except Exception as e:
                logger.error(f"❌ {data_type} 저장 실패: {str(e)}")
                # 백업에서 복구 시도
                self._restore_from_backup(file_path, data_type)
                return False
    
    def _load_data(self, file_path: Path, data_type: str) -> Dict[str, Any]:
        """
        파일에서 데이터 로드 (내부 메서드)
        
        Args:
            file_path: 로드할 파일 경로
            data_type: 데이터 타입 (로깅용)
            
        Returns:
            Dict: 로드된 데이터 또는 빈 딕셔너리
        """
        with self.lock:
            try:
                if not file_path.exists():
                    logger.info(f"📄 {data_type} 파일 없음, 새로 시작")
                    return {}
                
                with open(file_path, 'rb') as f:
                    data = pickle.load(f)
                
                logger.info(f"✅ {data_type} 데이터 로드 완료: {len(data)} 항목")
                return data
                
            except Exception as e:
                logger.error(f"❌ {data_type} 로드 실패: {str(e)}")
                # 백업에서 복구 시도
                backup_data = self._restore_from_backup(file_path, data_type)
                return backup_data if backup_data else {}
    
    def _create_backup(self, file_path: Path, data_type: str):
        """
        백업 파일 생성
        
        Args:
            file_path: 백업할 파일
            data_type: 데이터 타입
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"{data_type}_{timestamp}.pickle"
            
            # 최대 5개 백업 유지
            self._cleanup_old_backups(data_type, keep=5)
            
            # 백업 생성
            import shutil
            shutil.copy2(file_path, backup_path)
            logger.debug(f"백업 생성: {backup_path}")
            
        except Exception as e:
            logger.warning(f"백업 실패: {str(e)}")
    
    def _restore_from_backup(self, file_path: Path, data_type: str) -> Optional[Dict]:
        """
        백업에서 복구
        
        Args:
            file_path: 복구할 파일 경로
            data_type: 데이터 타입
            
        Returns:
            복구된 데이터 또는 None
        """
        try:
            # 최신 백업 찾기
            backup_pattern = f"{data_type}_*.pickle"
            backups = sorted(self.backup_dir.glob(backup_pattern), reverse=True)
            
            if not backups:
                logger.warning(f"복구할 백업 없음: {data_type}")
                return None
            
            # 최신 백업에서 복구
            latest_backup = backups[0]
            with open(latest_backup, 'rb') as f:
                data = pickle.load(f)
            
            # 복구된 파일 저장
            with open(file_path, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"✅ 백업에서 복구 완료: {latest_backup}")
            return data
            
        except Exception as e:
            logger.error(f"백업 복구 실패: {str(e)}")
            return None
    
    def _cleanup_old_backups(self, data_type: str, keep: int = 5):
        """
        오래된 백업 정리
        
        Args:
            data_type: 데이터 타입
            keep: 유지할 백업 개수
        """
        try:
            backup_pattern = f"{data_type}_*.pickle"
            backups = sorted(self.backup_dir.glob(backup_pattern), reverse=True)
            
            # keep 개수 초과하는 백업 삭제
            for backup in backups[keep:]:
                backup.unlink()
                logger.debug(f"오래된 백업 삭제: {backup}")
                
        except Exception as e:
            logger.warning(f"백업 정리 실패: {str(e)}")
    
    def export_to_json(self, data: Any, output_file: str) -> bool:
        """
        데이터를 JSON으로 내보내기 (디버깅/마이그레이션용)
        
        Args:
            data: 내보낼 데이터
            output_file: 출력 파일 경로
            
        Returns:
            bool: 성공 여부
        """
        try:
            # ParsedDocument 등 커스텀 객체를 딕셔너리로 변환
            def default_serializer(obj):
                if hasattr(obj, '__dict__'):
                    return obj.__dict__
                return str(obj)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, default=default_serializer, 
                         indent=2, ensure_ascii=False)
            
            logger.info(f"JSON 내보내기 완료: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"JSON 내보내기 실패: {str(e)}")
            return False

# 싱글톤 인스턴스
persistence_manager = PersistenceManager()

# 편의 함수들
def save_documents(documents_db: Dict[str, Any]) -> bool:
    """문서 저장 편의 함수"""
    return persistence_manager.save_documents(documents_db)

def load_documents() -> Dict[str, Any]:
    """문서 로드 편의 함수"""
    return persistence_manager.load_documents()

def save_tasks(tasks: Dict[str, Any]) -> bool:
    """작업 저장 편의 함수"""
    return persistence_manager.save_tasks(tasks)

def load_tasks() -> Dict[str, Any]:
    """작업 로드 편의 함수"""
    return persistence_manager.load_tasks()

@contextmanager
def auto_save_documents(documents_db: Dict[str, Any]):
    """
    컨텍스트 매니저: with 블록 종료 시 자동 저장
    
    사용법:
        with auto_save_documents(documents_db):
            documents_db[doc_id] = doc_data
    """
    try:
        yield documents_db
    finally:
        save_documents(documents_db)

@contextmanager  
def auto_save_tasks(tasks: Dict[str, Any]):
    """
    컨텍스트 매니저: with 블록 종료 시 자동 저장
    
    사용법:
        with auto_save_tasks(tasks):
            tasks[task_id] = task_info
    """
    try:
        yield tasks
    finally:
        save_tasks(tasks)