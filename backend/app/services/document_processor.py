from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import logging
from .parsers.factory import DocumentParserFactory
from .parsers.base import ParsedDocument
from .parsers.web_crawler import WebCrawlerParser
from ..utils.memory import memory_manager

# 로거 설정
logger = logging.getLogger(__name__)

class DocumentProcessor:
    """
    문서 처리 메인 클래스
    """
    
    def __init__(self):
        self.parser_factory = DocumentParserFactory()
        self.web_crawler = WebCrawlerParser()
        self.supported_extensions = self.parser_factory.get_supported_extensions()
        
        # 메모리 관리자에 파서 인스턴스 등록
        memory_manager.register_parser(self.parser_factory)
        memory_manager.register_parser(self.web_crawler)
    
    def process_file(self, file_path: str, **kwargs) -> ParsedDocument:
        """
        파일 처리 메인 메서드
        
        Args:
            file_path: 처리할 파일 경로
            **kwargs: 파서별 추가 옵션
            
        Returns:
            ParsedDocument: 파싱된 문서
            
        Raises:
            ValueError: 지원되지 않는 파일 형식
            FileNotFoundError: 파일이 존재하지 않음
        """
        file_path_obj = Path(file_path)
        
        # 파일 존재 확인
        if not file_path_obj.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
        
        # 지원 형식 확인
        if file_path_obj.suffix.lower() not in self.supported_extensions:
            raise ValueError(f"지원되지 않는 파일 형식: {file_path_obj.suffix}")
        
        # 파서 가져오기 및 처리
        parser = self.parser_factory.get_parser(file_path)
        parsed_doc = parser.parse(file_path, **kwargs)
        
        logger.info(f"파일 처리 완료: {file_path} ({len(parsed_doc.chunks)}개 청크)")
        return parsed_doc
    
    def process_url(self, url: str, max_depth: int = 1, same_domain: bool = True, **kwargs) -> ParsedDocument:
        """
        URL 크롤링 및 처리
        
        Args:
            url: 크롤링할 URL
            max_depth: 크롤링 깊이
            same_domain: 동일 도메인만 크롤링 여부
            **kwargs: 크롤러 추가 옵션
            
        Returns:
            ParsedDocument: 파싱된 웹 문서
        """
        crawled_content = self.web_crawler.parse(
            url, 
            max_depth=max_depth, 
            same_domain=same_domain,
            **kwargs
        )
        
        logger.info(f"URL 크롤링 완료: {url} ({len(crawled_content.chunks)}개 청크)")
        return crawled_content
    
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        파일 정보 및 지원 여부 확인
        
        Args:
            file_path: 확인할 파일 경로
            
        Returns:
            Dict: 파일 정보 및 지원 여부
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        is_supported = extension in self.supported_extensions
        parser_class = None
        
        if is_supported:
            parser = self.parser_factory.get_parser(file_path)
            parser_class = parser.__class__.__name__
        
        return {
            "filename": path.name,
            "extension": extension,
            "is_supported": is_supported,
            "parser_class": parser_class,
            "file_size": path.stat().st_size if path.exists() else 0,
            "exists": path.exists()
        }
    
    
