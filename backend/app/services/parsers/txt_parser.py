from typing import List
from pathlib import Path

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class TXTParser(BaseDocumentParser):
    """텍스트 파일 파서"""
    
    def parse(self, file_path: str, chunk_size: int = 1000, encoding: str = 'utf-8', **kwargs) -> ParsedDocument:
        """텍스트 파일을 파싱하여 청크로 분할"""
        
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                content = file.read()
        except UnicodeDecodeError:
            # UTF-8 실패시 다른 인코딩 시도
            encodings = ['cp949', 'euc-kr', 'latin-1']
            content = None
            
            for enc in encodings:
                try:
                    with open(file_path, 'r', encoding=enc) as file:
                        content = file.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                raise Exception("파일 인코딩을 감지할 수 없습니다")
        
        # 청크로 분할
        if content is None:
            raise Exception("파일 내용을 읽을 수 없습니다")
        chunks = self._split_text_into_chunks(content, file_path, chunk_size)
        
        return ParsedDocument(
            chunks=chunks,
            metadata={
                **self._extract_metadata(file_path),
                "parser": "txt_parser",
                "encoding": encoding,
                "total_chunks": len(chunks),
                "total_characters": len(content)
            },
            file_type="text"
        )
    
    def _split_text_into_chunks(self, text: str, file_path: str, chunk_size: int) -> List[DocumentChunk]:
        """텍스트를 청크로 분할"""
        chunks: List[DocumentChunk] = []
        
        # 먼저 문단으로 분할 시도
        paragraphs = text.split('\n\n')
        
        current_chunk: List[str] = []
        current_size = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            para_size = len(para)
            
            # 문단이 청크 크기보다 크면 별도 처리
            if para_size > chunk_size:
                # 현재 청크가 있으면 먼저 저장
                if current_chunk:
                    chunks.append(self._create_chunk(
                        '\n\n'.join(current_chunk),
                        file_path,
                        len(chunks)
                    ))
                    current_chunk = []
                    current_size = 0
                
                # 큰 문단을 문장 단위로 분할
                sentences = self._split_by_sentences(para)
                temp_chunk: List[str] = []
                temp_size = 0
                
                for sentence in sentences:
                    sentence_size = len(sentence)
                    if temp_size + sentence_size > chunk_size and temp_chunk:
                        chunks.append(self._create_chunk(
                            ' '.join(temp_chunk),
                            file_path,
                            len(chunks)
                        ))
                        temp_chunk = [sentence]
                        temp_size = sentence_size
                    else:
                        temp_chunk.append(sentence)
                        temp_size += sentence_size
                
                if temp_chunk:
                    chunks.append(self._create_chunk(
                        ' '.join(temp_chunk),
                        file_path,
                        len(chunks)
                    ))
            
            # 일반적인 문단 처리
            elif current_size + para_size > chunk_size and current_chunk:
                chunks.append(self._create_chunk(
                    '\n\n'.join(current_chunk),
                    file_path,
                    len(chunks)
                ))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size
        
        # 남은 청크 처리
        if current_chunk:
            chunks.append(self._create_chunk(
                '\n\n'.join(current_chunk),
                file_path,
                len(chunks)
            ))
        
        return chunks
    
    def _split_by_sentences(self, text: str) -> List[str]:
        """텍스트를 문장 단위로 분할"""
        import re
        # 한국어와 영어 문장 구분점 고려
        sentences = re.split(r'[.!?]+\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _create_chunk(self, content: str, file_path: str, chunk_index: int) -> DocumentChunk:
        """DocumentChunk 객체 생성"""
        return DocumentChunk(
            content=content,
            metadata={
                **self._extract_metadata(file_path),
                "chunk_index": chunk_index,
                "character_count": len(content),
                "word_count": len(content.split())
            },
            chunk_id=self._create_chunk_id(file_path, chunk_index)
        )
    
    def get_supported_extensions(self) -> List[str]:
        return ['.txt', '.text', '.log', '.rtf']