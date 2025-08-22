from typing import List, Any, Dict, Optional
import logging

try:
    from docx import Document
    from docx.shared import Inches
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False
    Document = None  # type: ignore

logger = logging.getLogger(__name__)

try:
    from unstructured.partition.docx import partition_docx
    from unstructured.chunking.title import chunk_by_title
    UNSTRUCTURED_AVAILABLE = True
    CHUNK_BY_TITLE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Unstructured 라이브러리 import 실패: {e}")
    UNSTRUCTURED_AVAILABLE = False
    CHUNK_BY_TITLE_AVAILABLE = False
    partition_docx = None  # type: ignore
    chunk_by_title = None  # type: ignore

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class DOCXParser(BaseDocumentParser):
    """DOCX 문서 파서 - Unstructured + python-docx Fallback"""
    
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        """DOCX 파일을 파싱하여 청크로 분할
        
        Architecture.md 설계:
        - Primary: Unstructured (고급 구조 인식)  
        - Fallback: python-docx (기본 텍스트 추출)
        """
        
        # 1. Unstructured 우선 시도
        if UNSTRUCTURED_AVAILABLE and partition_docx is not None:
            try:
                logger.info(f"Using Unstructured for DOCX parsing: {file_path}")
                return self._parse_with_unstructured(file_path, chunk_size, **kwargs)
            except Exception as e:
                logger.warning(f"Unstructured 파싱 실패, python-docx로 fallback: {e}")
        
        # 2. python-docx fallback
        if PYTHON_DOCX_AVAILABLE and Document is not None:
            logger.info(f"Using python-docx for DOCX parsing: {file_path}")
            return self._parse_with_python_docx(file_path, chunk_size, **kwargs)
        
        # 라이브러리가 없으면 오류
        raise ImportError("DOCX 파싱을 위해 unstructured 또는 python-docx 라이브러리가 필요합니다")
    
    def _parse_with_unstructured(self, file_path: str, chunk_size: int, **kwargs) -> ParsedDocument:
        """Unstructured를 사용한 고급 DOCX 파싱
        
        Features:
        - 스타일 및 구조 인식
        - 테이블 구조 보존
        - 리스트 및 헤더 인식
        """
        if not UNSTRUCTURED_AVAILABLE or partition_docx is None:
            logger.error("Unstructured 라이브러리가 설치되지 않았습니다.")
            raise ImportError("unstructured 라이브러리가 필요합니다. pip install unstructured 명령으로 설치해주세요.")
            
        try:
            from unstructured.chunking.title import chunk_by_title
            
            # DOCX 파티션
            elements = partition_docx(
                filename=file_path,
                include_page_breaks=True,
                infer_table_structure=True
            )
            
            # Unstructured 내장 청킹
            if CHUNK_BY_TITLE_AVAILABLE and chunk_by_title is not None:
                try:
                    chunked_elements = chunk_by_title(
                        elements,
                        max_characters=chunk_size,
                        new_after_n_chars=int(chunk_size * 0.8),
                        combine_text_under_n_chars=100
                    )
                except Exception as e:
                    logger.warning(f"chunk_by_title 실패, 원본 elements 사용: {e}")
                    chunked_elements = elements
            else:
                # Fallback: chunk_by_title이 없거나 실패시 요소를 그대로 사용
                logger.info("chunk_by_title 사용 불가, 원본 elements 사용")
                chunked_elements = elements
            
            chunks: List[DocumentChunk] = []
            current_section = None
            
            for i, element in enumerate(chunked_elements):
                # 섹션 타이틀 추적
                if hasattr(element, 'category') and element.category in ['Title', 'Header']:
                    current_section = str(element)
                
                metadata = {
                    **self._extract_metadata(file_path),
                    "element_type": element.category if hasattr(element, 'category') else 'text',
                    "section_title": current_section
                }
                
                # 테이블 메타데이터
                if hasattr(element, 'category') and element.category == 'Table':
                    metadata.update({
                        'is_table': True,
                        'table_format': 'structured'
                    })
                
                # 리스트 메타데이터
                if hasattr(element, 'category') and 'List' in element.category:
                    metadata['is_list'] = True
                
                chunk = DocumentChunk(
                    content=str(element),
                    metadata=metadata,
                    chunk_id=self._create_chunk_id(file_path, i),
                    section_title=current_section
                )
                chunks.append(chunk)
            
            return ParsedDocument(
                chunks=chunks,
                metadata={
                    **self._extract_metadata(file_path),
                    "parser": "unstructured",
                    "total_chunks": len(chunks)
                },
                file_type="docx"
            )
            
        except Exception as e:
            logger.error(f"Unstructured DOCX 파싱 오류: {str(e)}")
            raise
    
    def _parse_with_python_docx(self, file_path: str, chunk_size: int, **kwargs) -> ParsedDocument:
        """python-docx를 사용한 고급 DOCX 파싱 (Fallback)"""
        if not PYTHON_DOCX_AVAILABLE or Document is None:
            logger.error("python-docx 라이브러리가 설치되지 않았습니다.")
            raise ImportError("python-docx 라이브러리가 필요합니다. pip install python-docx 명령으로 설치해주세요.")
            
        try:
            doc = Document(file_path)
            
            chunks: List[DocumentChunk] = []
            current_chunk: List[Dict[str, Any]] = []
            current_size = 0
            current_section = None
            
            # 문서 메타데이터 추출
            doc_properties = {
                'title': doc.core_properties.title or '',
                'author': doc.core_properties.author or '',
                'subject': doc.core_properties.subject or '',
                'created': str(doc.core_properties.created) if doc.core_properties.created else '',
                'modified': str(doc.core_properties.modified) if doc.core_properties.modified else ''
            }
            
            # 문단별로 처리
            for para in doc.paragraphs:
                if not para.text.strip():
                    continue
                
                # 스타일 정보 추출
                style_name = para.style.name if para.style else 'Normal'
                is_heading = (style_name and 
                            (style_name.startswith('Heading') or style_name.startswith('Title')))
                
                # 헤더인 경우 섹션 업데이트
                if is_heading:
                    current_section = para.text.strip()
                
                para_text = para.text
                para_size = len(para_text)
                
                # 청크 크기 초과시 분할
                if current_size + para_size > chunk_size and current_chunk:
                    chunk_content = '\n'.join([p['text'] for p in current_chunk])
                    chunks.append(self._create_chunk_with_metadata(
                        chunk_content,
                        file_path,
                        len(chunks),
                        current_chunk,
                        current_section,
                        doc_properties
                    ))
                    current_chunk = []
                    current_size = 0
                
                current_chunk.append({
                    'text': para_text,
                    'style': style_name,
                    'is_heading': is_heading
                })
                current_size += para_size
            
            # 남은 청크 처리
            if current_chunk:
                chunk_content = '\n'.join([p['text'] for p in current_chunk])
                chunks.append(self._create_chunk_with_metadata(
                    chunk_content,
                    file_path,
                    len(chunks),
                    current_chunk,
                    current_section,
                    doc_properties
                ))
            
            # 테이블 처리
            table_chunks = self._extract_tables(doc, file_path, len(chunks))
            chunks.extend(table_chunks)
            
            return ParsedDocument(
                chunks=chunks,
                metadata={
                    **self._extract_metadata(file_path),
                    **doc_properties,
                    "parser": "python-docx",
                    "total_chunks": len(chunks),
                    "has_tables": len(table_chunks) > 0
                },
                file_type="docx"
            )
            
        except Exception as e:
            logger.error(f"python-docx DOCX 파싱 오류: {str(e)}")
            raise
    
    def _extract_tables(self, doc, file_path: str, start_index: int) -> List[DocumentChunk]:
        """문서에서 테이블 추출"""
        table_chunks: List[DocumentChunk] = []
        
        for table_idx, table in enumerate(doc.tables):
            table_text = []
            
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    row_text.append(cell_text)
                table_text.append(' | '.join(row_text))
            
            if table_text:
                table_content = '\n'.join(table_text)
                chunk = DocumentChunk(
                    content=table_content,
                    metadata={
                        **self._extract_metadata(file_path),
                        "content_type": "table",
                        "table_index": table_idx,
                        "row_count": len(table.rows),
                        "column_count": len(table.columns)
                    },
                    chunk_id=self._create_chunk_id(file_path, start_index + table_idx)
                )
                table_chunks.append(chunk)
        
        return table_chunks
    
    def _create_chunk_with_metadata(self, content: str, file_path: str, 
                                   chunk_index: int, para_info: List[Dict[str, Any]], 
                                   section_title: Optional[str] = None,
                                   doc_properties: Optional[Dict[str, Any]] = None) -> DocumentChunk:
        """메타데이터가 포함된 청크 생성"""
        
        # 헤딩 정보 추출
        headings = [p['text'] for p in para_info if p.get('is_heading', False)]
        styles = list(set(p['style'] for p in para_info))
        
        metadata = {
            **self._extract_metadata(file_path),
            "chunk_index": chunk_index,
            "character_count": len(content),
            "paragraph_count": len(para_info),
            "headings": headings,
            "styles_used": styles,
            "has_headings": len(headings) > 0,
            "section_title": section_title
        }
        
        # 문서 메타데이터 추가
        if doc_properties:
            metadata.update(doc_properties)
        
        return DocumentChunk(
            content=content,
            metadata=metadata,
            chunk_id=self._create_chunk_id(file_path, chunk_index),
            section_title=section_title or (headings[0] if headings else None)
        )
    
    def _split_text_into_chunks(self, text: str, file_path: str, chunk_size: int) -> List[DocumentChunk]:
        """텍스트를 청크로 분할 (fallback)"""
        chunks: List[DocumentChunk] = []
        words = text.split()
        
        current_chunk: List[Any] = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1
            if current_size + word_size > chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunk = DocumentChunk(
                    content=chunk_text,
                    metadata={
                        **self._extract_metadata(file_path),
                        "chunk_index": len(chunks),
                        "character_count": len(chunk_text)
                    },
                    chunk_id=self._create_chunk_id(file_path, len(chunks))
                )
                chunks.append(chunk)
                current_chunk = [word]
                current_size = word_size
            else:
                current_chunk.append(word)
                current_size += word_size
        
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunk = DocumentChunk(
                content=chunk_text,
                metadata={
                    **self._extract_metadata(file_path),
                    "chunk_index": len(chunks),
                    "character_count": len(chunk_text)
                },
                chunk_id=self._create_chunk_id(file_path, len(chunks))
            )
            chunks.append(chunk)
        
        return chunks
    
    def get_supported_extensions(self) -> List[str]:
        return ['.docx', '.doc']