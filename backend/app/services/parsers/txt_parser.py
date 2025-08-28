from typing import List, Optional
from pathlib import Path
import chardet

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class TXTParser(BaseDocumentParser):
    """텍스트 파일 파서 - chardet + LangChain 청킹"""
    
    def parse(self, file_path: str, chunk_size: int = 1000, chunk_overlap: Optional[int] = None, encoding: Optional[str] = None, **kwargs) -> ParsedDocument:
        """텍스트 파일을 파싱하여 청크로 분할"""
        
        # 인코딩 감지
        detected_encoding = encoding or self._detect_encoding(file_path)
        
        with open(file_path, 'r', encoding=detected_encoding) as file:
            content = file.read()
        
        # LangChain 청킹 (base 클래스 메서드 사용)
        chunks = self._create_langchain_chunks(
            content,
            chunk_size,
            file_path,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n\n",  # 섹션 구분
                "\n\n",    # 문단 구분
                "\n",      # 줄 구분
                ". ",      # 문장 구분
                " ",       # 공백 구분
                ""         # 문자 구분
            ],
            parser="txt_chardet_langchain",
            encoding=detected_encoding,
            word_count=len(content.split())
        )
        
        return ParsedDocument(
            chunks=chunks,
            metadata={
                **self._extract_metadata(file_path),
                "parser": "txt_chardet_langchain",
                "encoding": detected_encoding,
                "total_chunks": len(chunks),
                "total_characters": len(content)
            },
            file_type="text"
        )
    
    def _detect_encoding(self, file_path: str) -> str:
        """chardet으로 파일 인코딩 감지 (한국어 지원)"""
        with open(file_path, 'rb') as file:
            raw_data = file.read(10000)  # 10KB 샘플링
            result = chardet.detect(raw_data)
            detected_encoding = result['encoding']
            
            # 한국어 인코딩 우선순위
            if detected_encoding in ['cp949', 'euc-kr']:
                return detected_encoding
            elif detected_encoding and result['confidence'] > 0.8:
                return detected_encoding
            else:
                return 'utf-8'  # 기본값
    
    
    def get_supported_extensions(self) -> List[str]:
        return ['.txt', '.text', '.log', '.rtf']
    
