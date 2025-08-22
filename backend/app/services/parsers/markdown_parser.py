from typing import List, Dict, Any
import re

try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False
    markdown = None  # type: ignore

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class MarkdownParser(BaseDocumentParser):
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        if not MARKDOWN_AVAILABLE or markdown is None:
            # Fallback to regex parsing
            return self._parse_with_regex(file_path, chunk_size, **kwargs)
        
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # markdown 라이브러리로 HTML 변환 후 구조 분석
        md = markdown.Markdown(extensions=['toc'])
        html = md.convert(content)
        
        # TOC 정보가 있으면 활용, 없으면 정규식 fallback
        toc_tokens = getattr(md, 'toc_tokens', None)
        if toc_tokens:
            sections = self._extract_sections_from_toc(content, toc_tokens)
        else:
            sections = self._extract_headers_simple(content)
        
        chunks: List[DocumentChunk] = []
        for section in sections:
            if len(section['content']) > chunk_size:
                sub_chunks = self._split_large_section(section, file_path, chunk_size)
                chunks.extend(sub_chunks)
            else:
                chunk = DocumentChunk(
                    content=section['content'],
                    metadata={
                        **self._extract_metadata(file_path),
                        "section_title": section['title'],
                        "header_level": section['level']
                    },
                    chunk_id=self._create_chunk_id(file_path, len(chunks)),
                    section_title=section['title']
                )
                chunks.append(chunk)
        
        return ParsedDocument(
            chunks=chunks,
            metadata={**self._extract_metadata(file_path), "parser": "markdown_library"},
            file_type="markdown"
        )
    
    def _extract_headers_simple(self, content: str) -> List[dict]:
        """간단한 헤더 추출 (라이브러리 없이)"""
        return self._split_by_headers_regex(content)
    
    def _extract_sections_from_toc(self, content: str, toc_tokens: List) -> List[dict]:
        """TOC 토큰에서 섹션 정보 추출"""
        if not toc_tokens:
            # TOC가 없으면 전체 텍스트를 하나의 섹션으로
            return [{'title': 'Content', 'level': 1, 'content': content}]
        
        lines = content.split('\n')
        sections = []
        
        for i, token in enumerate(toc_tokens):
            title = token.get('title', 'Untitled')
            level = token.get('level', 1)
            
            # 현재 헤더부터 다음 헤더까지의 내용 추출
            start_line = self._find_header_line(lines, title)
            if i + 1 < len(toc_tokens):
                next_title = toc_tokens[i + 1].get('title', '')
                end_line = self._find_header_line(lines, next_title)
            else:
                end_line = len(lines)
            
            if start_line != -1:
                section_content = '\n'.join(lines[start_line:end_line]).strip()
                sections.append({
                    'title': title,
                    'level': level,
                    'content': section_content
                })
        
        return sections
    
    def _find_header_line(self, lines: List[str], title: str) -> int:
        """헤더 제목으로 라인 번호 찾기"""
        for i, line in enumerate(lines):
            if title in line and line.strip().startswith('#'):
                return i
        return -1
    
    def _parse_with_regex(self, file_path: str, chunk_size: int, **kwargs) -> ParsedDocument:
        """Fallback: 정규식 파싱"""
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        sections = self._split_by_headers_regex(content)
        chunks: List[DocumentChunk] = []
        
        for section in sections:
            if len(section['content']) > chunk_size:
                sub_chunks = self._split_large_section(section, file_path, chunk_size)
                chunks.extend(sub_chunks)
            else:
                chunk = DocumentChunk(
                    content=section['content'],
                    metadata={
                        **self._extract_metadata(file_path),
                        "section_title": section['title'],
                        "header_level": section['level']
                    },
                    chunk_id=self._create_chunk_id(file_path, len(chunks)),
                    section_title=section['title']
                )
                chunks.append(chunk)
        
        return ParsedDocument(
            chunks=chunks,
            metadata={**self._extract_metadata(file_path), "parser": "markdown_regex_fallback"},
            file_type="markdown"
        )

    def _split_by_headers_regex(self, content: str) -> List[dict]:
        lines = content.split('\n')
        sections = []
        current_section: Dict[str, Any] = {'title': None, 'level': 0, 'content': []}
        
        for line in lines:
            header_match = re.match(r'^(#{1,6})\s+(.+)', line)
            if header_match:
                if current_section['content']:
                    current_section['content'] = '\n'.join(current_section['content'])
                    sections.append(current_section)
                
                level = len(header_match.group(1))
                title = header_match.group(2)
                current_section = {'title': title, 'level': level, 'content': [line]}
            else:
                current_section['content'].append(line)
        
        if current_section['content']:
            current_section['content'] = '\n'.join(current_section['content'])
            sections.append(current_section)
        
        return sections
    
    def _split_large_section(self, section: dict, file_path: str, chunk_size: int) -> List[DocumentChunk]:
        content = section['content']
        chunks: List[DocumentChunk] = []
        words = content.split()
        
        current_chunk: List[str] = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1
            if current_size + word_size > chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunks.append(DocumentChunk(
                    content=chunk_text,
                    metadata={
                        **self._extract_metadata(file_path),
                        "section_title": section['title'],
                        "header_level": section['level']
                    },
                    chunk_id=self._create_chunk_id(file_path, len(chunks)),
                    section_title=section['title']
                ))
                current_chunk = [word]
                current_size = word_size
            else:
                current_chunk.append(word)
                current_size += word_size
        
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(DocumentChunk(
                content=chunk_text,
                metadata={
                    **self._extract_metadata(file_path),
                    "section_title": section['title'],
                    "header_level": section['level']
                },
                chunk_id=self._create_chunk_id(file_path, len(chunks)),
                section_title=section['title']
            ))
        
        return chunks
    
    def get_supported_extensions(self) -> List[str]:
        return ['.md', '.markdown']