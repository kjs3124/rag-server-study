from typing import List, Dict, Any
import re
from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class MarkdownParser(BaseDocumentParser):
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # 헤더별로 섹션 분할
        sections = self._split_by_headers(content)
        chunks: List[DocumentChunk] = []
        
        for section in sections:
            if len(section['content']) > chunk_size:
                # 큰 섹션은 더 작게 분할
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
            metadata={**self._extract_metadata(file_path), "parser": "markdown_parser"},
            file_type="markdown"
        )
    
    def _split_by_headers(self, content: str) -> List[dict]:
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