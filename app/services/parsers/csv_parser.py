import csv
from typing import List
from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class CSVParser(BaseDocumentParser):
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        chunks: List[DocumentChunk] = []
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            headers = reader.fieldnames
            
            rows: List[str] = []
            current_size = 0
            
            for row in reader:
                row_text = ' | '.join([f"{k}: {v}" for k, v in row.items()])
                row_size = len(row_text)
                
                if current_size + row_size > chunk_size and rows:
                    chunk_content = '\n'.join(rows)
                    chunks.append(DocumentChunk(
                        content=chunk_content,
                        metadata={**self._extract_metadata(file_path), "headers": headers},
                        chunk_id=self._create_chunk_id(file_path, len(chunks))
                    ))
                    rows = [row_text]
                    current_size = row_size
                else:
                    rows.append(row_text)
                    current_size += row_size
            
            if rows:
                chunk_content = '\n'.join(rows)
                chunks.append(DocumentChunk(
                    content=chunk_content,
                    metadata={**self._extract_metadata(file_path), "headers": headers},
                    chunk_id=self._create_chunk_id(file_path, len(chunks))
                ))
        
        return ParsedDocument(
            chunks=chunks,
            metadata={**self._extract_metadata(file_path), "parser": "csv_parser"},
            file_type="csv"
        )
    
    def get_supported_extensions(self) -> List[str]:
        return ['.csv']