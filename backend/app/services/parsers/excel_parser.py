from typing import List
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None  # type: ignore

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class ExcelParser(BaseDocumentParser):
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        if not PANDAS_AVAILABLE or pd is None:
            raise ImportError("Excel 파싱을 위해 pandas가 필요합니다")
        
        chunks: List[DocumentChunk] = []
        xl_file = pd.ExcelFile(file_path)
        
        for sheet_name in xl_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # 데이터프레임을 텍스트로 변환
            sheet_text = []
            sheet_text.append(f"Sheet: {sheet_name}")
            sheet_text.append(' | '.join(df.columns.tolist()))
            
            for _, row in df.iterrows():
                row_text = ' | '.join([str(val) for val in row.values])
                sheet_text.append(row_text)
            
            content = '\n'.join(sheet_text)
            
            chunk = DocumentChunk(
                content=content,
                metadata={
                    **self._extract_metadata(file_path),
                    "sheet_name": sheet_name,
                    "row_count": len(df),
                    "column_count": len(df.columns)
                },
                chunk_id=self._create_chunk_id(file_path, len(chunks))
            )
            chunks.append(chunk)
        
        return ParsedDocument(
            chunks=chunks,
            metadata={**self._extract_metadata(file_path), "parser": "excel_parser", "sheet_count": len(xl_file.sheet_names)},
            file_type="excel"
        )
    
    def get_supported_extensions(self) -> List[str]:
        return ['.xlsx', '.xls']