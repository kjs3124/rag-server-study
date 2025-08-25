from typing import List
import trafilatura
import markdownify

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class HTMLParser(BaseDocumentParser):
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        # 1. HTML 파일 읽기
        with open(file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
        
        # 2. trafilatura로 고품질 텍스트 추출
        text_content = self._extract_with_trafilatura(html_content)
        
        # 3. markdownify로 구조화된 텍스트 생성  
        markdown_content = self._convert_to_markdown(html_content)
        
        # 4. LangChain 청킹 (base 클래스 메서드 사용)
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