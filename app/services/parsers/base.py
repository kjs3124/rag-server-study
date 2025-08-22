from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

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
        return {
            "filename": file_path_obj.name,
            "file_size": file_path_obj.stat().st_size if file_path_obj.exists() else 0,
            "file_extension": file_path_obj.suffix.lower(),
            "created_at": file_path_obj.stat().st_ctime if file_path_obj.exists() else None,
        }