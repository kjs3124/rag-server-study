import uuid
from typing import List
from pathlib import Path

try:
    from unstructured.partition.pdf import partition_pdf
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class PDFParser(BaseDocumentParser):
    """PDF 문서 파서"""
    
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        """PDF 파일을 파싱하여 청크로 분할"""
        
        if UNSTRUCTURED_AVAILABLE:
            return self._parse_with_unstructured(file_path, chunk_size, **kwargs)
        elif PYPDF2_AVAILABLE:
            return self._parse_with_pypdf2(file_path, chunk_size, **kwargs)
        else:
            raise ImportError("PDF 파싱을 위해 unstructured 또는 PyPDF2가 필요합니다")
    
    def _parse_with_unstructured(self, file_path: str, chunk_size: int, **kwargs) -> ParsedDocument:
        """Unstructured를 사용한 고급 PDF 파싱"""
        try:
            # PDF 파티션
            elements = partition_pdf(
                file_path,
                strategy="hi_res",  # 고해상도 파싱
                infer_table_structure=True
            )
            
            # 수동으로 청크 분할 (최신 unstructured에서는 별도 청킹 필요)
            elements = self._chunk_elements(elements, chunk_size)  # type: ignore
            
            chunks: List[DocumentChunk] = []
            for i, element in enumerate(elements):
                chunk = DocumentChunk(
                    content=str(element),
                    metadata={
                        **self._extract_metadata(file_path),
                        "element_type": element.category if hasattr(element, 'category') else 'text',
                        "page_number": getattr(element, 'metadata', {}).get('page_number', 1)
                    },
                    chunk_id=self._create_chunk_id(file_path, i),
                    page_number=getattr(element, 'metadata', {}).get('page_number', 1)
                )
                chunks.append(chunk)
            
            return ParsedDocument(
                chunks=chunks,
                metadata={
                    **self._extract_metadata(file_path),
                    "parser": "unstructured",
                    "total_chunks": len(chunks)
                },
                file_type="pdf"
            )
            
        except Exception as e:
            raise Exception(f"PDF 파싱 중 오류 발생: {str(e)}")
    
    def _parse_with_pypdf2(self, file_path: str, chunk_size: int, **kwargs) -> ParsedDocument:
        """PyPDF2를 사용한 기본 PDF 파싱"""
        try:
            chunks: List[DocumentChunk] = []
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text = page.extract_text()
                    
                    # 텍스트를 청크 크기로 분할
                    page_chunks = self._split_text(text, chunk_size)
                    
                    for i, chunk_text in enumerate(page_chunks):
                        if chunk_text.strip():  # 빈 청크 제외
                            chunk = DocumentChunk(
                                content=chunk_text,
                                metadata={
                                    **self._extract_metadata(file_path),
                                    "page_number": page_num,
                                    "chunk_in_page": i + 1
                                },
                                chunk_id=self._create_chunk_id(file_path, len(chunks)),
                                page_number=page_num
                            )
                            chunks.append(chunk)
                
                return ParsedDocument(
                    chunks=chunks,
                    metadata={
                        **self._extract_metadata(file_path),
                        "parser": "pypdf2",
                        "total_chunks": len(chunks)
                    },
                    total_pages=total_pages,
                    file_type="pdf"
                )
                
        except Exception as e:
            raise Exception(f"PDF 파싱 중 오류 발생: {str(e)}")
    
    def _split_text(self, text: str, chunk_size: int) -> List[str]:
        """텍스트를 청크 크기로 분할"""
        words = text.split()
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1  # 공백 포함
            if current_size + word_size > chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_size = word_size
            else:
                current_chunk.append(word)
                current_size += word_size
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _chunk_elements(self, elements: List, chunk_size: int) -> List[object]:
        """Unstructured elements를 청크 크기에 맞게 분할"""
        chunked_elements: List[object] = []
        current_chunk_text = ""
        current_chunk_size = 0
        
        for element in elements:
            element_text = str(element)
            element_size = len(element_text)
            
            # 청크 크기 초과시 분할
            if current_chunk_size + element_size > chunk_size and current_chunk_text:
                # 현재 청크를 새로운 element로 생성
                class ChunkedElement:
                    def __init__(self, text, metadata=None):
                        self.text = text
                        self.metadata = metadata or {}
                        self.category = 'text'
                    
                    def __str__(self):
                        return self.text
                
                chunked_elements.append(ChunkedElement(
                    current_chunk_text,
                    getattr(element, 'metadata', {})
                ))
                current_chunk_text = element_text
                current_chunk_size = element_size
            else:
                if current_chunk_text:
                    current_chunk_text += "\n" + element_text
                else:
                    current_chunk_text = element_text
                current_chunk_size += element_size
        
        # 마지막 청크 처리
        if current_chunk_text:
            class ChunkedElementFinal:
                def __init__(self, text, metadata=None):
                    self.text = text
                    self.metadata = metadata or {}
                    self.category = 'text'
                
                def __str__(self):
                    return self.text
            
            chunked_elements.append(ChunkedElementFinal(
                current_chunk_text,
                getattr(elements[-1], 'metadata', {}) if elements else {}
            ))
        
        return chunked_elements
    
    def get_supported_extensions(self) -> List[str]:
        return ['.pdf']