from typing import Dict, Type
from pathlib import Path
from urllib.parse import urlparse

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

class DocumentParserFactory:
    """문서 파서 팩토리 클래스"""
    
    _parsers: Dict[str, Type[BaseDocumentParser]] = {
        '.pdf': PDFParser,
        '.docx': DOCXParser,
        '.doc': DOCXParser,  # legacy Word format
        '.txt': TXTParser,
        '.text': TXTParser,
        '.html': HTMLParser,
        '.htm': HTMLParser,
        '.md': MarkdownParser,
        '.markdown': MarkdownParser,
        '.csv': CSVParser,
        '.pptx': PPTXParser,
        '.ppt': PPTXParser,  # legacy PowerPoint
        '.xlsx': ExcelParser,
        '.xls': ExcelParser,  # legacy Excel
    }
    
    @classmethod
    def get_parser(cls, source: str) -> BaseDocumentParser:
        """
        파일 경로나 URL에 따라 적절한 파서 반환
        
        Args:
            source: 파일 경로 또는 URL
            
        Returns:
            BaseDocumentParser: 적절한 파서 인스턴스
        """
        # URL인지 확인
        if cls._is_url(source):
            return WebCrawlerParser()
        
        # 파일 확장자 기반 파서 선택
        ext = Path(source).suffix.lower()
        parser_class = cls._parsers.get(ext)
        
        if parser_class:
            return parser_class()
        else:
            # 기본적으로 텍스트 파서 사용
            return TXTParser()
    
    @classmethod
    def _is_url(cls, source: str) -> bool:
        """문자열이 URL인지 확인"""
        try:
            result = urlparse(source)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """지원하는 모든 파일 확장자 반환"""
        return list(cls._parsers.keys())
    
    @classmethod
    def register_parser(cls, extension: str, parser_class: Type[BaseDocumentParser]):
        """새로운 파서 등록"""
        if not extension.startswith('.'):
            extension = f'.{extension}'
        cls._parsers[extension] = parser_class