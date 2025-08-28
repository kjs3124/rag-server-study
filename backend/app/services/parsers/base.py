from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter

@dataclass
class DocumentChunk:
    """문서 청크 데이터 클래스"""
    content: str
    metadata: Dict[str, Any]
    chunk_id: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None

@dataclass
class ParsedDocument:
    """파싱된 문서 결과"""
    chunks: List[DocumentChunk]
    metadata: Dict[str, Any]
    total_pages: Optional[int] = None
    file_type: Optional[str] = None

class BaseDocumentParser(ABC):
    """문서 파서 기본 클래스"""
    
    @abstractmethod
    def parse(self, file_path: str, **kwargs) -> ParsedDocument:
        """문서를 파싱하여 청크들로 분할"""
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """지원하는 파일 확장자 목록 반환"""
        pass
    
    def _create_chunk_id(self, file_path: str, chunk_index: int) -> str:
        """청크 ID 생성"""
        file_stem = Path(file_path).stem
        return f"{file_stem}_{chunk_index:04d}"
    
    def _extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """기본 메타데이터 추출"""
        file_path_obj = Path(file_path)
        if file_path_obj.exists():
            stat_info = file_path_obj.stat()
            return {
                "filename": file_path_obj.name,
                "file_size": stat_info.st_size,
                "file_extension": file_path_obj.suffix.lower(),
            }
        else:
            return {
                "filename": file_path_obj.name,
                "file_size": 0,
                "file_extension": file_path_obj.suffix.lower(),
            }
    
    def _create_langchain_chunks(self, text: str, chunk_size: int, file_path: str, 
                                chunk_overlap: Optional[int] = None,
                                separators: Optional[List[str]] = None, **metadata) -> List[DocumentChunk]:
        """LangChain RecursiveCharacterTextSplitter를 사용한 공통 청킹 메서드"""
        
        # 기본 separator (모든 파일 타입에 적용 가능한 범용 설정)
        default_separators = [
            "\n\n",  # 문단 구분
            "\n",    # 줄 구분
            ". ",    # 문장 구분
            " ",     # 공백 구분
            ""       # 문자 구분
        ]
        
        # chunk_overlap이 지정되지 않으면 기본값(10%) 사용
        actual_chunk_overlap = chunk_overlap if chunk_overlap is not None else int(chunk_size * 0.1)
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=actual_chunk_overlap,
            length_function=len,
            separators=separators or default_separators
        )
        
        text_chunks = text_splitter.split_text(text)
        chunks: List[DocumentChunk] = []
        
        for i, chunk_text in enumerate(text_chunks):
            if chunk_text.strip():
                chunk_metadata = {
                    **self._extract_metadata(file_path),
                    "chunk_index": i,
                    "chunk_size": len(chunk_text),
                    **metadata  # 파서별 추가 메타데이터
                }
                
                chunk = DocumentChunk(
                    content=chunk_text,
                    metadata=chunk_metadata,
                    chunk_id=self._create_chunk_id(file_path, i)
                )
                chunks.append(chunk)
        
        return chunks