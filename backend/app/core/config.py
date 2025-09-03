"""
통합 설정 관리 시스템
환경별 설정 로드, 유효성 검증, 설정 오버라이드 지원
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union, List, Literal
from dataclasses import dataclass, field
from functools import lru_cache
import warnings

logger = logging.getLogger(__name__)

@dataclass
class ServerConfig:
    """서버 설정"""
    host: str = "127.0.0.1"
    port: int = 8099
    log_level: str = "info"
    loop: Literal["none", "auto", "asyncio", "uvloop"] = "asyncio"
    timeout_graceful_shutdown: float = 2.0

@dataclass 
class AppConfig:
    """FastAPI 애플리케이션 설정"""
    title: str = "RAG System API"
    version: str = "1.0.0"
    description: str = ""
    contact: Dict[str, str] = field(default_factory=dict)
    license_info: Dict[str, str] = field(default_factory=dict)

@dataclass
class CorsConfig:
    """CORS 설정"""
    allow_origins: List[str] = field(default_factory=lambda: ["*"])
    allow_credentials: bool = True
    allow_methods: List[str] = field(default_factory=lambda: ["*"])
    allow_headers: List[str] = field(default_factory=lambda: ["*"])

@dataclass
class EmbeddingModelConfig:
    """임베딩 모델 설정"""
    model_name: str
    description: str
    dimension: int
    max_seq_length: int
    best_for: List[str]
    memory_usage_mb: int

@dataclass
class EmbeddingCacheConfig:
    """임베딩 캐시 설정"""
    enabled: bool = True
    max_size: int = 1000
    cleanup_threshold: int = 100

@dataclass
class EmbeddingProcessingConfig:
    """임베딩 처리 설정"""
    batch_size: int = 32
    device: str = "auto"
    normalize_embeddings: bool = True
    show_progress_bar: bool = False
    convert_to_numpy: bool = True

@dataclass
class EmbeddingConfig:
    """임베딩 서비스 설정"""
    models: Dict[str, EmbeddingModelConfig] = field(default_factory=dict)
    language_model_mapping: Dict[str, Union[float, str]] = field(default_factory=dict)
    processing: EmbeddingProcessingConfig = field(default_factory=EmbeddingProcessingConfig)
    cache: EmbeddingCacheConfig = field(default_factory=EmbeddingCacheConfig)
    batch_size: int = 32  # 호환성을 위한 직접 접근

@dataclass
class QdrantConfig:
    """Qdrant 설정"""
    connection: Dict[str, Any] = field(default_factory=dict)
    collections: Dict[str, Any] = field(default_factory=dict)
    search: Dict[str, Any] = field(default_factory=dict)
    vector_processing: Dict[str, Any] = field(default_factory=dict)
    batch: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DatabaseConfig:
    """데이터베이스 설정"""
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)
    postgresql: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CrawlerConfig:
    """웹 크롤러 설정"""
    defaults: Dict[str, Any] = field(default_factory=dict)
    request: Dict[str, Any] = field(default_factory=dict)
    ssl: Dict[str, Any] = field(default_factory=dict)
    trafilatura: Dict[str, Any] = field(default_factory=dict)
    limits: Dict[str, Any] = field(default_factory=dict)
    html_parsing: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ParsersConfig:
    """파서 설정"""
    parsers: Dict[str, Any] = field(default_factory=dict)
    pdf_parser: Dict[str, Any] = field(default_factory=dict)
    docx_parser: Dict[str, Any] = field(default_factory=dict)
    excel_parser: Dict[str, Any] = field(default_factory=dict)
    pptx_parser: Dict[str, Any] = field(default_factory=dict)
    csv_parser: Dict[str, Any] = field(default_factory=dict)
    html_parser: Dict[str, Any] = field(default_factory=dict)
    txt_parser: Dict[str, Any] = field(default_factory=dict)
    markdown_parser: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LoggingConfig:
    """로깅 설정"""
    logging: Dict[str, Any] = field(default_factory=dict)
    directories: Dict[str, Any] = field(default_factory=dict)
    monitoring: Dict[str, Any] = field(default_factory=dict)

class ConfigManager:
    """통합 설정 관리자"""
    
    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        """
        설정 관리자 초기화
        
        Args:
            config_dir: 설정 파일 디렉토리 경로
        """
        if config_dir is None:
            # 현재 파일의 상위 디렉토리에서 config 디렉토리 찾기
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent  # backend/ 디렉토리
            config_dir = project_root / "config"
            
        self.config_dir = Path(config_dir)
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # 설정 객체들
        self.server: Optional[ServerConfig] = None
        self.app: Optional[AppConfig] = None
        self.cors: Optional[CorsConfig] = None
        self.embedding: Optional[EmbeddingConfig] = None
        self.database: Optional[DatabaseConfig] = None
        self.crawler: Optional[CrawlerConfig] = None
        self.parsers: Optional[ParsersConfig] = None
        self.logging: Optional[LoggingConfig] = None
        
        # 태그 메타데이터 (YAML에서 로드)
        self.tags_metadata: List[Dict[str, str]] = []
        
        # 원본 설정 데이터 (백업용)
        self._raw_configs: Dict[str, Dict] = {}
    
    def load_all_configs(self) -> None:
        """모든 설정 파일 로드"""
        try:
            logger.info(f"설정 파일 로드 시작: {self.config_dir} (환경: {self.environment})")
            
            # 설정 디렉토리 존재 확인
            if not self.config_dir.exists():
                raise FileNotFoundError(f"설정 디렉토리를 찾을 수 없습니다: {self.config_dir}")
            
            # 각 설정 파일 로드
            config_files = {
                'server': 'server.yaml',
                'embedding': 'embedding.yaml', 
                'database': 'database.yaml',
                'crawler': 'crawler.yaml',
                'parsers': 'parsers.yaml',
                'logging': 'logging.yaml'
            }
            
            for config_name, filename in config_files.items():
                config_path = self.config_dir / filename
                if config_path.exists():
                    try:
                        config_data = self._load_yaml_file(config_path)
                        self._raw_configs[config_name] = config_data
                        self._parse_config(config_name, config_data)
                        logger.info(f"✅ {filename} 로드 완료")
                    except Exception as e:
                        logger.error(f"❌ {filename} 로드 실패: {e}")
                        raise
                else:
                    logger.warning(f"⚠️ 설정 파일 없음: {filename}")
                    
            # 환경변수 오버라이드 적용
            self._apply_environment_overrides()
            
            logger.info("✅ 모든 설정 로드 완료")
            
        except Exception as e:
            logger.error(f"❌ 설정 로드 실패: {e}")
            raise
    
    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """YAML 파일 로드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 파싱 오류 ({file_path}): {e}")
        except Exception as e:
            raise IOError(f"파일 읽기 오류 ({file_path}): {e}")
    
    def _parse_config(self, config_name: str, config_data: Dict[str, Any]) -> None:
        """설정 데이터를 파싱하여 객체로 변환"""
        try:
            if config_name == 'server':
                self.server = ServerConfig(**config_data.get('server', {}))
                self.app = AppConfig(**config_data.get('app', {}))
                self.cors = CorsConfig(**config_data.get('cors', {}))
                self.tags_metadata = config_data.get('tags_metadata', [])
                
            elif config_name == 'embedding':
                # 모델 설정 파싱
                models = {}
                for model_key, model_data in config_data.get('models', {}).items():
                    models[model_key] = EmbeddingModelConfig(**model_data)
                
                # 처리 설정 파싱
                processing_data = config_data.get('processing', {})
                processing_config = EmbeddingProcessingConfig(
                    batch_size=processing_data.get('batch_size', 32),
                    device=processing_data.get('device', 'auto'),
                    normalize_embeddings=processing_data.get('normalize_embeddings', True),
                    show_progress_bar=processing_data.get('show_progress_bar', False),
                    convert_to_numpy=processing_data.get('convert_to_numpy', True)
                )
                
                # 캐시 설정 파싱
                cache_config = EmbeddingCacheConfig(
                    enabled=processing_data.get('cache_enabled', True),
                    max_size=processing_data.get('max_cache_size', 1000),
                    cleanup_threshold=processing_data.get('cache_cleanup_threshold', 100)
                )
                
                self.embedding = EmbeddingConfig(
                    models=models,
                    language_model_mapping=config_data.get('language_model_mapping', {}),
                    processing=processing_config,
                    cache=cache_config,
                    batch_size=processing_data.get('batch_size', 32)
                )
                
            elif config_name == 'database':
                qdrant_data = config_data.get('qdrant', {})
                self.database = DatabaseConfig(
                    qdrant=QdrantConfig(
                        connection=qdrant_data.get('connection', {}),
                        collections=qdrant_data.get('collections', {}),
                        search=qdrant_data.get('search', {}),
                        vector_processing=qdrant_data.get('vector_processing', {}),
                        batch=qdrant_data.get('batch', {})
                    ),
                    postgresql=config_data.get('postgresql', {})
                )
                
            elif config_name == 'crawler':
                self.crawler = CrawlerConfig(
                    defaults=config_data.get('crawler', {}).get('defaults', {}),
                    request=config_data.get('crawler', {}).get('request', {}),
                    ssl=config_data.get('crawler', {}).get('ssl', {}),
                    trafilatura=config_data.get('crawler', {}).get('trafilatura', {}),
                    limits=config_data.get('crawler', {}).get('limits', {}),
                    html_parsing=config_data.get('crawler', {}).get('html_parsing', {})
                )
                
            elif config_name == 'parsers':
                self.parsers = ParsersConfig(
                    parsers=config_data.get('parsers', {}),
                    pdf_parser=config_data.get('pdf_parser', {}),
                    docx_parser=config_data.get('docx_parser', {}),
                    excel_parser=config_data.get('excel_parser', {}),
                    pptx_parser=config_data.get('pptx_parser', {}),
                    csv_parser=config_data.get('csv_parser', {}),
                    html_parser=config_data.get('html_parser', {}),
                    txt_parser=config_data.get('txt_parser', {}),
                    markdown_parser=config_data.get('markdown_parser', {})
                )
                
            elif config_name == 'logging':
                self.logging = LoggingConfig(
                    logging=config_data.get('logging', {}),
                    directories=config_data.get('directories', {}),
                    monitoring=config_data.get('monitoring', {})
                )
                
        except Exception as e:
            logger.error(f"설정 파싱 실패 ({config_name}): {e}")
            raise
    
    def _apply_environment_overrides(self) -> None:
        """환경변수로 설정 오버라이드"""
        try:
            # 서버 설정 오버라이드
            if self.server:
                self.server.host = os.getenv("SERVER_HOST", self.server.host)
                self.server.port = int(os.getenv("SERVER_PORT", str(self.server.port)))
                self.server.log_level = os.getenv("LOG_LEVEL", self.server.log_level)
            
            # 데이터베이스 설정 오버라이드  
            if self.database and self.database.qdrant:
                self.database.qdrant.connection["url"] = os.getenv(
                    "QDRANT_URL", 
                    self.database.qdrant.connection.get("url", "http://localhost:6333")
                )
                api_key = os.getenv("QDRANT_API_KEY")
                if api_key:
                    self.database.qdrant.connection["api_key"] = api_key
                    
            logger.debug("환경변수 오버라이드 적용 완료")
            
        except Exception as e:
            logger.warning(f"환경변수 오버라이드 적용 중 오류: {e}")
    
    def get_config_value(self, key_path: str, default: Any = None) -> Any:
        """
        점 표기법으로 설정 값 조회
        
        Args:
            key_path: 설정 키 경로 (예: "server.host", "embedding.processing.batch_size")
            default: 기본값
            
        Returns:
            설정 값
        """
        try:
            keys = key_path.split('.')
            
            # 첫 번째 키로 설정 객체 찾기
            if keys[0] == 'server' and self.server:
                obj = self.server
            elif keys[0] == 'app' and self.app:
                obj = self.app
            elif keys[0] == 'cors' and self.cors:
                obj = self.cors
            elif keys[0] == 'embedding' and self.embedding:
                obj = self.embedding
            elif keys[0] == 'database' and self.database:
                obj = self.database
            elif keys[0] == 'crawler' and self.crawler:
                obj = self.crawler
            elif keys[0] == 'parsers' and self.parsers:
                obj = self.parsers
            elif keys[0] == 'logging' and self.logging:
                obj = self.logging
            else:
                return default
            
            # 나머지 키로 값 탐색
            for key in keys[1:]:
                if hasattr(obj, key):
                    obj = getattr(obj, key)
                elif isinstance(obj, dict) and key in obj:
                    obj = obj[key]
                else:
                    return default
                    
            return obj
            
        except Exception as e:
            logger.warning(f"설정 값 조회 실패 ({key_path}): {e}")
            return default
    
    def validate_configs(self) -> List[str]:
        """설정 유효성 검증"""
        warnings = []
        
        try:
            # 필수 설정 확인
            if not self.server:
                warnings.append("서버 설정이 로드되지 않았습니다")
            elif self.server.port < 1 or self.server.port > 65535:
                warnings.append(f"잘못된 포트 번호: {self.server.port}")
                
            if not self.embedding or not self.embedding.models:
                warnings.append("임베딩 모델 설정이 없습니다")
                
            if not self.database or not self.database.qdrant:
                warnings.append("데이터베이스 설정이 로드되지 않았습니다")
                
            if not self.parsers:
                warnings.append("파서 설정이 로드되지 않았습니다")
                
            # CORS 보안 경고
            if self.cors and "*" in self.cors.allow_origins:
                warnings.append("CORS에서 모든 출처를 허용합니다 (프로덕션에서는 보안상 위험)")
                
            logger.info(f"설정 유효성 검증 완료: {len(warnings)}개 경고")
            for warning in warnings:
                logger.warning(f"⚠️ {warning}")
                
        except Exception as e:
            logger.error(f"설정 유효성 검증 중 오류: {e}")
            warnings.append(f"유효성 검증 중 오류: {e}")
            
        return warnings
    
    def get_status(self) -> Dict[str, Any]:
        """설정 관리자 상태 정보"""
        return {
            'config_dir': str(self.config_dir),
            'environment': self.environment,
            'loaded_configs': {
                'server': self.server is not None,
                'app': self.app is not None,
                'cors': self.cors is not None,
                'embedding': self.embedding is not None,
                'database': self.database is not None,
                'crawler': self.crawler is not None,
                'parsers': self.parsers is not None,
                'logging': self.logging is not None
            },
            'config_files_found': len(self._raw_configs),
            'validation_warnings': len(self.validate_configs())
        }

# 전역 설정 관리자 인스턴스
@lru_cache(maxsize=1)
def get_config_manager() -> ConfigManager:
    """설정 관리자 싱글톤 인스턴스 반환"""
    config_manager = ConfigManager()
    config_manager.load_all_configs()
    return config_manager

# 편의 함수들
def get_server_config() -> ServerConfig:
    """서버 설정 반환"""
    manager = get_config_manager()
    if not manager.server:
        raise RuntimeError("서버 설정이 로드되지 않았습니다")
    return manager.server

def get_app_config() -> AppConfig:
    """앱 설정 반환"""
    manager = get_config_manager()
    if not manager.app:
        raise RuntimeError("앱 설정이 로드되지 않았습니다")
    return manager.app

def get_embedding_config() -> EmbeddingConfig:
    """임베딩 설정 반환"""
    manager = get_config_manager()
    if not manager.embedding:
        raise RuntimeError("임베딩 설정이 로드되지 않았습니다")
    return manager.embedding

def get_database_config() -> DatabaseConfig:
    """데이터베이스 설정 반환"""
    manager = get_config_manager()
    if not manager.database:
        raise RuntimeError("데이터베이스 설정이 로드되지 않았습니다")
    return manager.database

def get_crawler_config() -> CrawlerConfig:
    """크롤러 설정 반환"""
    manager = get_config_manager()
    if not manager.crawler:
        raise RuntimeError("크롤러 설정이 로드되지 않았습니다")
    return manager.crawler

def get_parsers_config() -> ParsersConfig:
    """파서 설정 반환"""
    manager = get_config_manager()
    if not manager.parsers:
        raise RuntimeError("파서 설정이 로드되지 않았습니다")
    return manager.parsers