from typing import List, Dict, Any
import re
import markdown

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class MarkdownParser(BaseDocumentParser):
    """Markdown 파서 - markdown + LangChain 청킹"""
    
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        """Markdown 파일을 파싱하여 청크로 분할"""
        
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # markdown을 HTML로 변환하여 구조 분석
        md = markdown.Markdown(extensions=['toc', 'tables', 'fenced_code'])
        html = md.convert(content)
        
        # LangChain 청킹 (base 클래스 메서드 사용)
        chunks = self._create_langchain_chunks(
            content,
            chunk_size,
            file_path,
            separators=[
                "\n# ",       # H1 헤딩
                "\n## ",      # H2 헤딩
                "\n### ",     # H3 헤딩
                "\n\n```",    # 코드 블록
                "\n\n",       # 문단 구분
                "\n- ",       # 리스트 아이템
                "\n",         # 줄 구분
                ". ",         # 문장 구분
                " ",          # 공백 구분
                ""            # 문자 구분
            ],
            parser="markdown_langchain",
            has_html_conversion=bool(html),
            has_code_block="```" in content,
            has_heading=content.strip().startswith('#')
        )
        
        return ParsedDocument(
            chunks=chunks,
            metadata={
                **self._extract_metadata(file_path), 
                "parser": "markdown_langchain",
                "total_chunks": len(chunks),
                "has_html_conversion": bool(html)
            },
            file_type="markdown"
        )
    
    
    def get_supported_extensions(self) -> List[str]:
        return ['.md', '.markdown']