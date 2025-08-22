from typing import List

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class HTMLParser(BaseDocumentParser):
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        if not BS4_AVAILABLE:
            raise ImportError("HTML 파싱을 위해 beautifulsoup4가 필요합니다")
        
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # 스크립트와 스타일 제거
        for script in soup(["script", "style"]):
            script.decompose()
        
        text = soup.get_text()
        clean_text = ' '.join(text.split())
        
        chunks = self._split_text_into_chunks(clean_text, file_path, chunk_size)
        
        return ParsedDocument(
            chunks=chunks,
            metadata={**self._extract_metadata(file_path), "parser": "html_parser"},
            file_type="html"
        )
    
    def _split_text_into_chunks(self, text: str, file_path: str, chunk_size: int) -> List[DocumentChunk]:
        words = text.split()
        chunks: List[DocumentChunk] = []
        current_chunk: List[str] = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1
            if current_size + word_size > chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunks.append(DocumentChunk(
                    content=chunk_text,
                    metadata=self._extract_metadata(file_path),
                    chunk_id=self._create_chunk_id(file_path, len(chunks))
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
                metadata=self._extract_metadata(file_path),
                chunk_id=self._create_chunk_id(file_path, len(chunks))
            ))
        
        return chunks
    
    def get_supported_extensions(self) -> List[str]:
        return ['.html', '.htm']