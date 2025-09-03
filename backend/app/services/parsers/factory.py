from typing import Dict, Type
from pathlib import Path
from urllib.parse import urlparse
import logging

from .base import BaseDocumentParser
from .pdf_parser import PDFParser
from .docx_parser import DOCXParser
from .txt_parser import TXTParser
from .html_parser import HTMLParser
from .markdown_parser import MarkdownParser
from .csv_parser import CSVParser
from .pptx_parser import PPTXParser
from .excel_parser import ExcelParser
from .web_crawler import WebCrawlerParser
from ...core.config import get_parsers_config

logger = logging.getLogger(__name__)

class DocumentParserFactory:
    """문서 파서 팩토리 클래스"""
    
    # 파서 클래스 매핑
    _parser_classes: Dict[str, Type[BaseDocumentParser]] = {
        'PDFParser': PDFParser,
        'DOCXParser': DOCXParser,
        'TXTParser': TXTParser,
        'HTMLParser': HTMLParser,
        'MarkdownParser': MarkdownParser,
        'CSVParser': CSVParser,
        'PPTXParser': PPTXParser,
        'ExcelParser': ExcelParser,
        'WebCrawlerParser': WebCrawlerParser,
    }
    
    _parsers: Dict[str, Type[BaseDocumentParser]] = {}
    _config_loaded = False
    
    @classmethod
    def _load_parser_config(cls) -> None:
        """설정에서 파서 매핑 로드"""
        if cls._config_loaded:
            return
            
        try:
            config = get_parsers_config()
            extensions_mapping = config.parsers.get('extensions', {})
            default_parser_name = config.parsers.get('default_parser', 'TXTParser')
            
            # 확장자별 파서 매핑 구성
            for ext, parser_name in extensions_mapping.items():
                if parser_name in cls._parser_classes:
                    cls._parsers[ext] = cls._parser_classes[parser_name]
                else:
                    logger.warning(f"알 수 없는 파서 클래스: {parser_name}")
            
            # 기본 파서 설정
            if default_parser_name in cls._parser_classes:
                cls._default_parser_class = cls._parser_classes[default_parser_name]
            else:
                logger.warning(f"알 수 없는 기본 파서: {default_parser_name}, TXTParser 사용")
                cls._default_parser_class = TXTParser
                
            cls._config_loaded = True
            logger.info(f"파서 설정 로드 완료: {len(cls._parsers)}개 확장자 매핑")
            
        except Exception as e:
            logger.error(f"파서 설정 로드 실패, 기본 설정 사용: {e}")
            # 기본 파서 매핑 사용
            cls._parsers = {
                '.pdf': PDFParser,
                '.docx': DOCXParser,
                '.doc': DOCXParser,
                '.txt': TXTParser,
                '.text': TXTParser,
                '.html': HTMLParser,
                '.htm': HTMLParser,
                '.md': MarkdownParser,
                '.markdown': MarkdownParser,
                '.csv': CSVParser,
                '.pptx': PPTXParser,
                '.ppt': PPTXParser,
                '.xlsx': ExcelParser,
                '.xls': ExcelParser,
            }
            cls._default_parser_class = TXTParser
            cls._config_loaded = True
    
    @classmethod
    def get_parser(cls, source: str) -> BaseDocumentParser:
        """
        파일 경로나 URL에 따라 적절한 파서 반환
        
        Args:
            source: 파일 경로 또는 URL
            
        Returns:
            BaseDocumentParser: 적절한 파서 인스턴스
        """
        # 설정 로드
        cls._load_parser_config()
        
        # URL인지 확인
        if cls._is_url(source):
            return WebCrawlerParser()
        
        # 파일 확장자 기반 파서 선택
        ext = Path(source).suffix.lower()
        parser_class = cls._parsers.get(ext)
        
        if parser_class:
            return parser_class()
        else:
            # 설정에서 기본 파서 사용
            return cls._default_parser_class()
    
    @classmethod
    def _is_url(cls, source: str) -> bool:
        """문자열이 URL인지 확인"""
        try:
            # 설정에서 URL 감지 설정 로드
            try:
                config = get_parsers_config()
                url_detection = config.parsers.get('url_detection', {})
                schemes = url_detection.get('schemes', ['http', 'https', 'ftp'])
                require_netloc = url_detection.get('require_netloc', True)
            except Exception:
                schemes = ['http', 'https', 'ftp']
                require_netloc = True
            
            result = urlparse(source)
            scheme_valid = result.scheme.lower() in schemes
            netloc_valid = not require_netloc or bool(result.netloc)
            
            return scheme_valid and netloc_valid
        except:
            return False
    
    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """지원하는 모든 파일 확장자 반환"""
        cls._load_parser_config()
        return list(cls._parsers.keys())