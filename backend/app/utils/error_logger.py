import logging
import traceback
import json
from datetime import datetime
from typing import Dict, Any, Optional, Union
from pathlib import Path
import sys
from enum import Enum

class ErrorLevel(Enum):
    """에러 레벨 정의"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ErrorLogger:
    """종합 에러 로깅 시스템"""
    
    def __init__(self, log_file: str = "logs/app_errors.log"):
        self.log_file = Path(log_file)
        self.setup_logger()
    
    def setup_logger(self):
        """로거 설정"""
        # 로그 디렉토리 생성
        self.log_file.parent.mkdir(exist_ok=True)
        
        # 로거 생성
        self.logger = logging.getLogger("RAGErrorLogger")
        self.logger.setLevel(logging.DEBUG)
        
        # 중복 핸들러 방지
        if self.logger.handlers:
            return
        
        # 파일 핸들러 (상세 로그)
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # 콘솔 핸들러 (중요한 에러만)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def log_error(self, 
                  error: Union[BaseException, str],
                  context: str,
                  level: ErrorLevel = ErrorLevel.ERROR,
                  extra_data: Optional[Dict[str, Any]] = None) -> str:
        """
        구조화된 에러 로깅
        
        Args:
            error: 에러 객체 또는 메시지
            context: 에러 발생 컨텍스트 (예: "document_upload", "pdf_parsing")
            level: 에러 레벨
            extra_data: 추가 디버그 정보
        
        Returns:
            에러 ID (추적용)
        """
        error_id = self._generate_error_id()
        
        error_data: Dict[str, Any] = {
            "error_id": error_id,
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "level": level.value
        }
        
        if isinstance(error, BaseException):
            error_data["error_type"] = error.__class__.__name__
            error_data["error_message"] = str(error)
            error_data["traceback"] = traceback.format_exc()
            error_data["error_args"] = getattr(error, 'args', [])
        else:
            error_data["error_type"] = "CustomError"
            error_data["error_message"] = str(error)
            error_data["traceback"] = None
        
        if extra_data:
            error_data["extra_data"] = extra_data
        
        # JSON 형태로 로깅
        log_message = f"[{error_id}] {context}: {json.dumps(error_data, ensure_ascii=False, indent=2)}"
        
        # 레벨에 따른 로깅
        if level == ErrorLevel.DEBUG:
            self.logger.debug(log_message)
        elif level == ErrorLevel.INFO:
            self.logger.info(log_message)
        elif level == ErrorLevel.WARNING:
            self.logger.warning(log_message)
        elif level == ErrorLevel.ERROR:
            self.logger.error(log_message)
        elif level == ErrorLevel.CRITICAL:
            self.logger.critical(log_message)
        
        return error_id
    
    def log_processing_error(self, 
                           file_path: str,
                           parser_name: str,
                           error: Exception,
                           file_size: Optional[int] = None) -> str:
        """문서 처리 에러 전용 로깅"""
        extra_data = {
            "file_path": file_path,
            "parser_name": parser_name,
            "file_size": file_size
        }
        
        return self.log_error(
            error=error,
            context="document_processing",
            level=ErrorLevel.ERROR,
            extra_data=extra_data
        )
    
    def log_api_error(self,
                     endpoint: str,
                     method: str,
                     error: Exception,
                     request_data: Optional[Dict] = None,
                     user_id: Optional[str] = None) -> str:
        """API 에러 전용 로깅"""
        extra_data = {
            "endpoint": endpoint,
            "method": method,
            "request_data": request_data,
            "user_id": user_id
        }
        
        return self.log_error(
            error=error,
            context="api_request",
            level=ErrorLevel.ERROR,
            extra_data=extra_data
        )
    
    def log_validation_error(self,
                           validation_type: str,
                           invalid_data: Any,
                           expected_format: str,
                           error_message: str) -> str:
        """데이터 검증 에러 로깅"""
        extra_data = {
            "validation_type": validation_type,
            "invalid_data": str(invalid_data)[:1000],  # 너무 길면 자름
            "expected_format": expected_format
        }
        
        return self.log_error(
            error=error_message,
            context="data_validation",
            level=ErrorLevel.WARNING,
            extra_data=extra_data
        )
    
    def log_performance_warning(self,
                              operation: str,
                              duration_seconds: float,
                              threshold_seconds: float,
                              details: Optional[Dict] = None) -> str:
        """성능 경고 로깅"""
        extra_data = {
            "operation": operation,
            "duration_seconds": duration_seconds,
            "threshold_seconds": threshold_seconds,
            "performance_ratio": duration_seconds / threshold_seconds,
            "details": details or {}
        }
        
        warning_msg = f"Performance warning: {operation} took {duration_seconds:.2f}s (threshold: {threshold_seconds}s)"
        
        return self.log_error(
            error=warning_msg,
            context="performance_monitoring",
            level=ErrorLevel.WARNING,
            extra_data=extra_data
        )
    
    def _generate_error_id(self) -> str:
        """고유한 에러 ID 생성"""
        from uuid import uuid4
        return str(uuid4())[:8]
    
    def get_recent_errors(self, hours: int = 24) -> list:
        """최근 에러 로그 조회 (모니터링용)"""
        try:
            if not self.log_file.exists():
                return []
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 간단한 최근 에러 필터링 (실제로는 더 정교한 파싱 필요)
            recent_errors = []
            for line in lines[-100:]:  # 최근 100줄만 확인
                if "ERROR" in line or "CRITICAL" in line:
                    recent_errors.append(line.strip())
            
            return recent_errors[-50:]  # 최근 50개 에러만
        except Exception as e:
            self.logger.error(f"Failed to read recent errors: {e}")
            return []


# 글로벌 에러 로거 인스턴스
error_logger = ErrorLogger()

def log_error(error: Union[BaseException, str], 
              context: str, 
              level: ErrorLevel = ErrorLevel.ERROR,
              **kwargs) -> str:
    """편의 함수: 글로벌 에러 로거 사용"""
    return error_logger.log_error(error, context, level, kwargs if kwargs else None)

def log_exception(context: str, **kwargs) -> str:
    """현재 예외를 로깅하는 데코레이터용 함수"""
    _, exc_value, _ = sys.exc_info()
    if exc_value:
        return error_logger.log_error(exc_value, context, ErrorLevel.ERROR, kwargs if kwargs else None)
    return ""