"""
메모리 관리 유틸리티
메모리 사용량 모니터링, 정리, 최적화 기능
"""

import gc
import os
import psutil  # type: ignore
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta
import weakref

logger = logging.getLogger(__name__)

class MemoryManager:
    """메모리 관리자"""
    
    def __init__(self) -> None:
        self.process = psutil.Process()
        self.parser_instances: weakref.WeakSet[Any] = weakref.WeakSet()  # 약한 참조로 파서 인스턴스 추적
        self.last_cleanup = datetime.now()
        self.cleanup_interval = timedelta(minutes=30)  # 30분마다 자동 정리
        
    def get_memory_usage(self) -> Dict[str, Union[float, str]]:
        """현재 메모리 사용량 조회"""
        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            return {
                "rss_mb": memory_info.rss / 1024 / 1024,  # 물리 메모리
                "vms_mb": memory_info.vms / 1024 / 1024,  # 가상 메모리
                "percent": memory_percent,
                "available_mb": psutil.virtual_memory().available / 1024 / 1024
            }
        except Exception as e:
            logger.error(f"메모리 사용량 조회 실패: {e}")
            return {"error": str(e)}
    
    def cleanup_document_memory(self, document_data: Dict[str, Any]) -> bool:
        """문서 관련 메모리 정리"""
        try:
            # parsed_doc 객체 정리
            if "parsed_doc" in document_data:
                parsed_doc = document_data["parsed_doc"]
                if hasattr(parsed_doc, 'chunks'):
                    # 청크 데이터 명시적 정리
                    for chunk in parsed_doc.chunks:
                        if hasattr(chunk, 'content'):
                            del chunk.content
                        if hasattr(chunk, 'metadata'):
                            del chunk.metadata
                    parsed_doc.chunks.clear()
                
                # 메타데이터 정리
                if hasattr(parsed_doc, 'metadata'):
                    parsed_doc.metadata.clear()
                
                del document_data["parsed_doc"]
            
            # 기타 메모리 집약적 필드 정리
            memory_intensive_fields = ["file_content", "raw_text", "embeddings"]
            for field in memory_intensive_fields:
                if field in document_data:
                    del document_data[field]
            
            logger.debug(f"문서 메모리 정리 완료")
            return True
            
        except Exception as e:
            logger.error(f"문서 메모리 정리 실패: {e}")
            return False
    
    def force_garbage_collection(self) -> Dict[str, Union[int, str]]:
        """강제 가비지 컬렉션 실행"""
        try:
            # 세대별 가비지 컬렉션
            collected: Dict[str, Union[int, str]] = {
                "generation_0": gc.collect(0),
                "generation_1": gc.collect(1), 
                "generation_2": gc.collect(2)
            }
            
            total_collected = sum(v for v in collected.values() if isinstance(v, int))
            logger.info(f"가비지 컬렉션 완료: {total_collected}개 객체 정리됨")
            
            return collected
            
        except Exception as e:
            logger.error(f"가비지 컬렉션 실패: {e}")
            return {"error": str(e)}
    
    def cleanup_temp_files(self, temp_dir: str = "./data") -> int:
        """임시 파일 정리"""
        if not os.path.exists(temp_dir):
            return 0
            
        cleaned_count = 0
        current_time = datetime.now()
        
        try:
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                
                # 1시간 이상 된 임시 파일 삭제
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if current_time - file_time > timedelta(hours=1):
                        try:
                            os.remove(file_path)
                            cleaned_count += 1
                            logger.debug(f"임시 파일 삭제: {filename}")
                        except Exception as e:
                            logger.warning(f"임시 파일 삭제 실패 {filename}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"임시 파일 {cleaned_count}개 정리 완료")
                
        except Exception as e:
            logger.error(f"임시 파일 정리 실패: {e}")
            
        return cleaned_count
    
    def register_parser(self, parser_instance: Any) -> None:
        """파서 인스턴스 등록 (약한 참조)"""
        self.parser_instances.add(parser_instance)
    
    def get_parser_count(self) -> int:
        """현재 활성 파서 인스턴스 수"""
        return len(self.parser_instances)
    
    def should_cleanup(self) -> bool:
        """자동 정리가 필요한지 확인"""
        return datetime.now() - self.last_cleanup > self.cleanup_interval
    
    def auto_cleanup(self, documents_db: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """자동 메모리 정리"""
        if not self.should_cleanup():
            return {"skipped": "아직 정리 시간이 아님"}
        
        cleanup_results: Dict[str, Any] = {}
        
        try:
            # 메모리 사용량 체크
            memory_before = self.get_memory_usage()
            cleanup_results["memory_before"] = memory_before
            
            # 임시 파일 정리
            temp_cleaned = self.cleanup_temp_files()
            cleanup_results["temp_files_cleaned"] = temp_cleaned
            
            # 가비지 컬렉션
            gc_results = self.force_garbage_collection()
            cleanup_results["garbage_collected"] = gc_results
            
            # 메모리 사용량 재측정
            memory_after = self.get_memory_usage()
            cleanup_results["memory_after"] = memory_after
            
            # 메모리 절약량 계산
            if "rss_mb" in memory_before and "rss_mb" in memory_after and isinstance(memory_before["rss_mb"], (int, float)) and isinstance(memory_after["rss_mb"], (int, float)):
                saved_mb = float(memory_before["rss_mb"]) - float(memory_after["rss_mb"])
                cleanup_results["memory_saved_mb"] = saved_mb
            
            # 파서 인스턴스 정보
            cleanup_results["active_parsers"] = self.get_parser_count()
            
            self.last_cleanup = datetime.now()
            cleanup_results["cleanup_time"] = self.last_cleanup.isoformat()
            
            logger.info(f"자동 메모리 정리 완료: {cleanup_results}")
            
        except Exception as e:
            logger.error(f"자동 메모리 정리 실패: {e}")
            cleanup_results["error"] = str(e)
        
        return cleanup_results
    
    def get_memory_status(self) -> Dict[str, Any]:
        """메모리 상태 정보 반환"""
        return {
            "current_usage": self.get_memory_usage(),
            "active_parsers": self.get_parser_count(),
            "last_cleanup": self.last_cleanup.isoformat(),
            "next_cleanup": (self.last_cleanup + self.cleanup_interval).isoformat()
        }

# 글로벌 메모리 매니저 인스턴스
memory_manager = MemoryManager()

def cleanup_document_memory(document_data: Dict[str, Any]) -> bool:
    """문서 메모리 정리 (편의 함수)"""
    return memory_manager.cleanup_document_memory(document_data)

def get_memory_usage() -> Dict[str, Union[float, str]]:
    """메모리 사용량 조회 (편의 함수)"""
    return memory_manager.get_memory_usage()

def auto_cleanup(documents_db: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """자동 메모리 정리 (편의 함수)"""
    return memory_manager.auto_cleanup(documents_db)