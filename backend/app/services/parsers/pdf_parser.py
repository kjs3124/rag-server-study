from typing import List
import logging

logger = logging.getLogger(__name__)

try:
    from unstructured.partition.pdf import partition_pdf
    from unstructured.chunking.title import chunk_by_title
    UNSTRUCTURED_AVAILABLE = True
    CHUNK_BY_TITLE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Unstructured 라이브러리 import 실패: {e}")
    UNSTRUCTURED_AVAILABLE = False
    CHUNK_BY_TITLE_AVAILABLE = False
    partition_pdf = None  # type: ignore
    chunk_by_title = None  # type: ignore

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    PyPDF2 = None  # type: ignore

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class PDFParser(BaseDocumentParser):
    """PDF 문서 파서 - Unstructured + PyPDF2 Fallback"""
    
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        """PDF 파일을 파싱하여 청크로 분할
        
        Architecture.md 기반:
        - Primary: Unstructured (고급 파싱, 테이블 구조 유지)
        - Fallback: PyPDF2 (기본 텍스트 추출)
        """
        
        # Unstructured 시도 (architecture.md 설계)
        if UNSTRUCTURED_AVAILABLE and partition_pdf is not None:
            try:
                logger.info(f"Using Unstructured for PDF parsing: {file_path}")
                return self._parse_with_unstructured(file_path, chunk_size, **kwargs)
            except (ValueError, Exception) as e:
                logger.warning(f"Unstructured 파싱 실패, PyPDF2로 fallback: {e}")
        
        # PyPDF2 fallback (architecture.md 설계)
        if PYPDF2_AVAILABLE:
            logger.info(f"Using PyPDF2 for PDF parsing: {file_path}")
            return self._parse_with_pypdf2(file_path, chunk_size, **kwargs)
        
        # 모든 파서 사용 불가
        raise ImportError("PDF 파싱을 위해 unstructured 또는 PyPDF2가 필요합니다")
    
    def _parse_with_unstructured(self, file_path: str, chunk_size: int, **kwargs) -> ParsedDocument:
        """Unstructured를 사용한 고급 PDF 파싱
        
        Features:
        - 테이블 구조 인식
        - 이미지 텍스트 추출 (OCR)
        - 섹션별 메타데이터 보존
        - 라이브러리 내장 청킹 활용
        """
        if not UNSTRUCTURED_AVAILABLE or partition_pdf is None:
            logger.error("Unstructured 라이브러리가 설치되지 않았습니다.")
            raise ImportError("unstructured 라이브러리가 필요합니다. pip install unstructured 명령으로 설치해주세요.")
            
        try:
            # Strategy 선택: hi_res (정확도 우선) vs fast (속도 우선)
            strategy = kwargs.get('strategy', 'fast')  # fast로 기본값 변경
            
            # PDF 파티션 - 구조화된 요소로 분할
            elements = partition_pdf(
                filename=file_path,
                strategy=strategy,
                infer_table_structure=True,  # 테이블 구조 추론
                extract_images_in_pdf=False,  # 이미지 추출 (필요시 True)
                include_page_breaks=True,  # 페이지 구분 유지
            )
            
            # elements가 빈 리스트이면 PyPDF2로 fallback
            if not elements:
                logger.warning("partition_pdf에서 요소를 추출하지 못함, PyPDF2로 fallback")
                raise ValueError("No elements extracted from PDF")
            
            # Unstructured의 내장 청킹 기능 사용
            if CHUNK_BY_TITLE_AVAILABLE and chunk_by_title is not None:
                try:
                    chunked_elements = chunk_by_title(
                        elements,
                        max_characters=chunk_size,
                        new_after_n_chars=int(chunk_size * 0.8),  # 80%에서 새 청크 시작 고려
                        combine_text_under_n_chars=100,  # 짧은 텍스트는 병합
                    )
                except Exception as e:
                    logger.warning(f"chunk_by_title 실패, 원본 elements 사용: {e}")
                    chunked_elements = elements
            else:
                # Fallback: chunk_by_title이 없거나 실패시 요소를 그대로 사용
                logger.info("chunk_by_title 사용 불가, 원본 elements 사용")
                chunked_elements = elements
            
            chunks: List[DocumentChunk] = []
            for i, element in enumerate(chunked_elements):
                # 메타데이터 추출
                metadata = {
                    **self._extract_metadata(file_path),
                    "element_type": element.category if hasattr(element, 'category') else 'text',
                    "page_number": element.metadata.page_number if hasattr(element, 'metadata') else 1,
                }
                
                # 테이블인 경우 특별 처리
                if hasattr(element, 'category') and element.category == 'Table':
                    metadata['is_table'] = True
                    metadata['table_format'] = 'structured'
                
                # 제목/헤더인 경우 섹션 정보 추가
                if hasattr(element, 'category') and element.category in ['Title', 'Header']:
                    metadata['is_header'] = True
                    metadata['section_title'] = str(element)
                
                chunk = DocumentChunk(
                    content=str(element),
                    metadata=metadata,
                    chunk_id=self._create_chunk_id(file_path, i),
                    page_number=metadata['page_number']
                )
                chunks.append(chunk)
            
            return ParsedDocument(
                chunks=chunks,
                metadata={
                    **self._extract_metadata(file_path),
                    "parser": "unstructured",
                    "strategy": strategy,
                    "total_chunks": len(chunks),
                    "total_pages": max([c.page_number or 1 for c in chunks]) if chunks else 0
                },
                file_type="pdf"
            )
            
        except Exception as e:
            logger.error(f"Unstructured PDF 파싱 오류: {str(e)}")
            raise
    
    def _parse_with_pypdf2(self, file_path: str, chunk_size: int, **kwargs) -> ParsedDocument:
        """PyPDF2를 사용한 기본 PDF 파싱 (Fallback)
        
        Features:
        - 기본 텍스트 추출
        - 페이지 정보 유지
        - 오버랩 청킹 지원
        """
        if not PYPDF2_AVAILABLE or PyPDF2 is None:
            logger.error("PyPDF2 라이브러리가 설치되지 않았습니다.")
            raise ImportError("PyPDF2 라이브러리가 필요합니다. pip install PyPDF2 명령으로 설치해주세요.")
            
        try:
            chunks: List[DocumentChunk] = []
            overlap_size = kwargs.get('overlap', 100)  # 청크 간 오버랩
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                # 메타데이터 추출
                pdf_metadata = {}
                if pdf_reader.metadata:
                    pdf_metadata = {
                        'title': pdf_reader.metadata.get('/Title', ''),
                        'author': pdf_reader.metadata.get('/Author', ''),
                        'subject': pdf_reader.metadata.get('/Subject', ''),
                        'creator': pdf_reader.metadata.get('/Creator', ''),
                    }
                
                all_text: List[str] = []  # 전체 텍스트 수집 (오버랩 청킹용)
                page_boundaries: List[tuple] = []  # 페이지 경계 추적
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text = page.extract_text()
                    if text.strip():
                        page_start = len(''.join(all_text))
                        all_text.append(text)
                        page_boundaries.append((page_start, page_start + len(text), page_num))
                
                # 전체 텍스트를 오버랩 청킹
                full_text = '\n'.join(all_text)
                text_chunks = self._split_text_with_overlap(
                    full_text, chunk_size, overlap_size
                )
                
                # 각 청크에 페이지 정보 매핑
                for i, chunk_text in enumerate(text_chunks):
                    if chunk_text.strip():
                        # 청크가 속한 페이지 찾기
                        chunk_start = full_text.find(chunk_text)
                        page_num = self._find_page_number(
                            chunk_start, page_boundaries
                        )
                        
                        chunk = DocumentChunk(
                            content=chunk_text,
                            metadata={
                                **self._extract_metadata(file_path),
                                **pdf_metadata,
                                "page_number": page_num,
                                "chunk_index": i,
                                "parser": "pypdf2"
                            },
                            chunk_id=self._create_chunk_id(file_path, i),
                            page_number=page_num
                        )
                        chunks.append(chunk)
                
                return ParsedDocument(
                    chunks=chunks,
                    metadata={
                        **self._extract_metadata(file_path),
                        **pdf_metadata,
                        "parser": "pypdf2",
                        "total_chunks": len(chunks),
                        "total_pages": total_pages
                    },
                    file_type="pdf"
                )
                
        except Exception as e:
            logger.error(f"PyPDF2 PDF 파싱 오류: {str(e)}")
            raise
    
    def _split_text_with_overlap(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """텍스트를 오버랩을 포함하여 청크로 분할
        
        Args:
            text: 분할할 텍스트
            chunk_size: 청크 크기
            overlap: 청크 간 오버랩 크기
        """
        if not text:
            return []
        
        chunks: List[str] = []
        sentences = text.replace('\n', ' ').split('. ')
        
        current_chunk: List[str] = []
        current_size = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            sentence_with_period = sentence if sentence.endswith('.') else sentence + '.'
            sentence_size = len(sentence_with_period) + 1
            
            if current_size + sentence_size > chunk_size and current_chunk:
                # 현재 청크 저장
                chunk_text = ' '.join(current_chunk)
                chunks.append(chunk_text)
                
                # 오버랩 처리: 마지막 몇 문장을 다음 청크에 포함
                overlap_text: List[str] = []
                overlap_size = 0
                for sent in reversed(current_chunk):
                    if overlap_size + len(sent) <= overlap:
                        overlap_text.insert(0, sent)
                        overlap_size += len(sent) + 1
                    else:
                        break
                
                current_chunk = overlap_text + [sentence_with_period]
                current_size = sum(len(s) + 1 for s in current_chunk)
            else:
                current_chunk.append(sentence_with_period)
                current_size += sentence_size
        
        # 마지막 청크 처리
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _find_page_number(self, position: int, page_boundaries: List[tuple]) -> int:
        """텍스트 위치에서 페이지 번호 찾기"""
        for start, end, page_num in page_boundaries:
            if start <= position < end:
                return page_num
        return 1  # 기본값
    
    
    def get_supported_extensions(self) -> List[str]:
        """지원하는 파일 확장자 목록"""
        return ['.pdf']