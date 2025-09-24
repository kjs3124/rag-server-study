"""
Swagger/OpenAPI 문서 파서
LlamaIndex OpenAPIReader를 사용하여 API 문서를 파싱
"""

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from llama_index.readers.openapi import OpenAPIReader
from .base import BaseDocumentParser, ParsedDocument, DocumentChunk
from typing import List, Optional, Dict, Any
import logging
import requests
import tempfile
import os
import json
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class SwaggerParser(BaseDocumentParser):
    """Swagger/OpenAPI 문서 파서"""
    
    def __init__(self):
        self.reader = OpenAPIReader()
        self.logger = logger
        
    def parse(self, file_path: str, chunk_size: int = 2000, 
              chunk_overlap: Optional[int] = None, **kwargs) -> ParsedDocument:
        """
        Swagger/OpenAPI 문서를 파싱하여 청크로 분할
        
        Args:
            file_path: OpenAPI 문서 URL 또는 파일 경로
            chunk_size: 청크 크기 (사용되지 않음 - 각 엔드포인트별로 청킹)
            chunk_overlap: 청크 중복 크기 (사용되지 않음)
            **kwargs: 추가 파라미터
            
        Returns:
            ParsedDocument: 파싱된 문서 객체
        """
        
        try:
            # URL인지 확인하고 SSL 우회 처리
            if self._is_url(file_path):
                self.logger.info(f"URL에서 OpenAPI 문서 다운로드: {file_path}")
                # SSL 검증 우회하여 다운로드
                response = requests.get(file_path, verify=False)
                response.raise_for_status()
                
                # 임시 파일로 처리 (Windows 호환성을 위해 수동 관리)
                temp_file = None
                try:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                        f.write(response.text)
                        temp_file = f.name
                    
                    # 임시 파일에서 로드
                    llama_docs = self.reader.load_data(input_file=temp_file)
                finally:
                    # 임시 파일 정리
                    if temp_file and os.path.exists(temp_file):
                        try:
                            os.unlink(temp_file)
                        except Exception as cleanup_error:
                            self.logger.warning(f"임시 파일 삭제 실패: {cleanup_error}")
            else:
                # 로컬 파일에서 직접 로드
                llama_docs = self.reader.load_data(input_file=file_path)
            
            self.logger.info(f"OpenAPI 문서 로드 완료: {len(llama_docs)}개 엔드포인트")
            
        except Exception as e:
            error_msg = f"OpenAPI 문서 로드 실패: {str(e)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        chunks: List[DocumentChunk] = []
        
        # LlamaIndex가 반환한 문서들을 청크로 변환
        for i, doc in enumerate(llama_docs):
            # 엔드포인트 정보 추출
            endpoint_info = self._extract_endpoint_info(doc)
            
            chunk = DocumentChunk(
                content=doc.text,  # LlamaIndex가 파싱한 텍스트
                metadata={
                    "source": file_path,
                    "chunk_index": i,
                    "chunk_type": "swagger_endpoint",
                    "api_path": endpoint_info.get("path", ""),
                    "http_method": endpoint_info.get("method", ""),
                    "api_summary": endpoint_info.get("summary", ""),
                    "operation_id": endpoint_info.get("operation_id", ""),
                    "chunk_size": len(doc.text)
                },
                chunk_id=f"swagger_{i:04d}",
                section_title=f"{endpoint_info.get('method', 'GET')} {endpoint_info.get('path', f'API Endpoint {i+1}')}"
            )
            chunks.append(chunk)
        
        # 메타데이터 생성
        metadata = {
            "source": file_path,
            "file_type": "swagger",
            "total_endpoints": len(chunks),
            "parser_used": "SwaggerParser",
            "filename": file_path.split('/')[-1] if '/' in file_path else file_path
        }
        
        self.logger.info(f"Swagger 파싱 완료: {len(chunks)}개 엔드포인트 청크 생성")
        
        # ParsedDocument 반환
        return ParsedDocument(
            chunks=chunks,
            metadata=metadata,
            file_type="swagger"
        )
    
    def _extract_endpoint_info(self, doc) -> Dict[str, Any]:
        """
        LlamaIndex 문서에서 엔드포인트 정보 추출
        
        Args:
            doc: LlamaIndex Document 객체
            
        Returns:
            Dict: 추출된 엔드포인트 정보
        """
        # doc.metadata에서 정보 추출
        metadata = getattr(doc, 'metadata', {})
        
        # 텍스트에서 정보 파싱
        text = doc.text
        lines = text.split('\n')
        
        info = {}
        
        # 첫 줄이 보통 "METHOD /path" 형식
        if lines:
            first_line = lines[0].strip()
            parts = first_line.split(' ', 1)
            if len(parts) >= 2:
                info['method'] = parts[0].upper()
                info['path'] = parts[1] if len(parts) > 1 else ''
                info['title'] = first_line
            elif len(parts) == 1:
                # 메서드만 있는 경우
                info['method'] = parts[0].upper() if parts[0].upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'] else ''
                info['path'] = ''
                info['title'] = first_line
        
        # metadata에서 추가 정보
        info['operation_id'] = metadata.get('operation_id', '')
        info['summary'] = metadata.get('summary', '')
        
        # 제목이 없는 경우 기본 제목 생성
        if not info.get('title'):
            method = info.get('method', 'API')
            path = info.get('path', 'endpoint')
            info['title'] = f"{method} {path}"
        
        return info
    
    def _is_url(self, path: str) -> bool:
        """
        문자열이 URL인지 확인
        
        Args:
            path: 확인할 문자열
            
        Returns:
            bool: URL 여부
        """
        try:
            result = urlparse(path)
            return bool(result.scheme and result.netloc)
        except:
            return False
    
    def get_supported_extensions(self) -> List[str]:
        """
        지원하는 파일 확장자 목록
        
        Returns:
            List[str]: 지원 확장자 리스트
        """
        return ['.json', '.yaml', '.yml']  # OpenAPI 스펙 파일