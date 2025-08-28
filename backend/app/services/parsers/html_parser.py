from typing import List, Any, Optional
import trafilatura

markdownify: Any = None
MARKDOWNIFY_AVAILABLE = False
try:
    import markdownify as _markdownify  # type: ignore
    markdownify = _markdownify
    MARKDOWNIFY_AVAILABLE = True
except ImportError:
    MARKDOWNIFY_AVAILABLE = False

# LangChain HTML splitter
HTMLHeaderTextSplitter: Any = None
HTML_SPLITTER_AVAILABLE = False
try:
    from langchain_text_splitters import HTMLHeaderTextSplitter as _HTMLHeaderTextSplitter
    HTMLHeaderTextSplitter = _HTMLHeaderTextSplitter
    HTML_SPLITTER_AVAILABLE = True
except ImportError:
    HTML_SPLITTER_AVAILABLE = False

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class HTMLParser(BaseDocumentParser):
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        """HTML 파일을 파싱하여 청크로 분할"""
        
        # 1. HTML 파일 읽기
        with open(file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
        
        # 2. 1차: HTMLHeaderTextSplitter 구조적 청킹 시도
        if HTML_SPLITTER_AVAILABLE and HTMLHeaderTextSplitter is not None:
            try:
                chunks = self._parse_with_html_header_splitter(html_content, file_path, chunk_size)
                if chunks:
                    print(f"✅ HTML 헤더 청킹 성공: {len(chunks)}개 청크 생성")
                    return ParsedDocument(
                        chunks=chunks,
                        metadata={
                            **self._extract_metadata(file_path),
                            "parser": "html_header_splitter",
                            "source_type": "html_file",
                            "content_quality": "structured",
                            "total_chunks": len(chunks)
                        },
                        file_type="html"
                    )
            except Exception as e:
                print(f"HTML 헤더 청킹 실패: {e}, trafilatura 폴백 시도")
        
        # 3. 2차: trafilatura + markdownify 폴백 (기존 방식)
        return self._parse_with_trafilatura_fallback(html_content, file_path, chunk_size, **kwargs)
    
    def _parse_with_html_header_splitter(self, html_content: str, file_path: str, chunk_size: int) -> List[DocumentChunk]:
        """HTMLHeaderTextSplitter를 사용한 구조적 청킹"""
        
        if not HTML_SPLITTER_AVAILABLE or HTMLHeaderTextSplitter is None:
            raise ImportError("HTMLHeaderTextSplitter를 사용할 수 없습니다")
        
        # HTML 헤더 기반 분할 설정
        headers_to_split_on = [
            ("h1", "Header 1"),
            ("h2", "Header 2"), 
            ("h3", "Header 3"),
        ]
        
        html_splitter = HTMLHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        html_header_splits = html_splitter.split_text(html_content)
        
        chunks: List[DocumentChunk] = []
        
        # 각 분할된 텍스트를 DocumentChunk로 변환
        for i, split in enumerate(html_header_splits):
            if split.page_content.strip():
                # 헤더 메타데이터 추출
                header_info = split.metadata if hasattr(split, 'metadata') else {}
                
                chunk = DocumentChunk(
                    content=split.page_content,
                    metadata={
                        **self._extract_metadata(file_path),
                        "chunk_index": i,
                        "chunk_size": len(split.page_content),
                        "source_type": "html_file",
                        "parser": "html_header_splitter",
                        "header_structure": header_info
                    },
                    chunk_id=self._create_chunk_id(file_path, i)
                )
                chunks.append(chunk)
        
        return chunks
    
    def _parse_with_trafilatura_fallback(self, html_content: str, file_path: str, chunk_size: int, **kwargs) -> ParsedDocument:
        """기존 trafilatura + markdownify 방식 폴백"""
        
        # trafilatura로 고품질 텍스트 추출
        text_content = self._extract_with_trafilatura(html_content)
        
        # markdownify로 구조화된 텍스트 생성  
        markdown_content = self._convert_to_markdown(html_content)
        
        # LangChain 청킹 (base 클래스 메서드 사용)
        primary_content = markdown_content if markdown_content else text_content
        chunks = self._create_langchain_chunks(
            primary_content,
            chunk_size,
            file_path,
            separators=[
                "\n\n",    # 문단 구분
                "\n# ",    # Markdown 헤딩
                "\n## ",   # Markdown 서브헤딩  
                "\n",      # 줄 구분
                ". ",      # 문장 구분
                " ",       # 공백 구분
                ""         # 문자 구분
            ],
            parser="trafilatura_markdownify_parser",
            has_markdown=bool(markdown_content),
            is_markdown=bool(markdown_content)
        )
        
        return ParsedDocument(
            chunks=chunks,
            metadata={
                **self._extract_metadata(file_path), 
                "parser": "trafilatura_markdownify_parser",
                "total_chunks": len(chunks),
                "has_markdown": bool(markdown_content)
            },
            file_type="html"
        )
    
    def _extract_with_trafilatura(self, html_content: str) -> str:
        """trafilatura로 고품질 텍스트 추출"""
        text = trafilatura.extract(html_content, include_comments=False, include_tables=True)
        return text.strip() if text else ""
    
    def _convert_to_markdown(self, html_content: str) -> str:
        """markdownify로 구조화된 텍스트 생성"""
        if not MARKDOWNIFY_AVAILABLE or markdownify is None:
            return ""
            
        try:
            markdown = markdownify.markdownify(
                html_content, 
                heading_style="ATX",  # # 스타일 헤딩
                bullets="-",          # - 리스트
                strip=["script", "style"]
            )
            return markdown.strip() if markdown else ""
        except Exception:
            return ""
    
    
    
    def get_supported_extensions(self) -> List[str]:
        return ['.html', '.htm']