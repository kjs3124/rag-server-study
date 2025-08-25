from typing import List
import chardet
import polars as pl

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class CSVParser(BaseDocumentParser):
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        # 1. 인코딩 감지 (한국어 지원)
        encoding = self._detect_encoding(file_path)
        
        # 2. Polars로 고속 CSV 읽기
        df = pl.read_csv(file_path, encoding=encoding)
        
        # 3. 텍스트 변환
        text_content = self._dataframe_to_text(df)
        
        # 4. LangChain 청킹 (base 클래스 메서드 사용)
        chunks = self._create_langchain_chunks(
            text_content, 
            chunk_size, 
            file_path,
            separators=[
                "\n\n",  # 문단 구분
                "\n",    # 줄 구분
                " | ",   # CSV 열 구분
                " ",     # 공백 구분
                ""       # 문자 구분
            ],
            parser="polars_langchain_csv_parser",
            encoding=encoding,
            rows=df.height,
            columns=df.width,
            headers=df.columns
        )
        
        return ParsedDocument(
            chunks=chunks,
            metadata={
                **self._extract_metadata(file_path), 
                "parser": "polars_langchain_csv_parser",
                "encoding": encoding,
                "rows": df.height,
                "columns": df.width,
                "total_chunks": len(chunks)
            },
            file_type="csv"
        )
    
    def _detect_encoding(self, file_path: str) -> str:
        """chardet으로 파일 인코딩 감지 (한국어 지원)"""
        with open(file_path, 'rb') as file:
            raw_data = file.read(10000)  # 10KB 샘플링
            result = chardet.detect(raw_data)
            detected_encoding = result['encoding']
            
            # 한국어 인코딩 우선순위
            if detected_encoding in ['cp949', 'euc-kr']:
                return detected_encoding
            elif detected_encoding and result['confidence'] > 0.8:
                return detected_encoding
            else:
                return 'utf-8'  # 기본값
    
    def _dataframe_to_text(self, df: pl.DataFrame) -> str:
        """DataFrame을 텍스트로 변환"""
        lines: List[str] = []
        
        # 헤더 추가
        headers = df.columns
        lines.append("Headers: " + " | ".join(headers))
        
        # 데이터 행 추가
        for row in df.rows():
            row_data = []
            for i, value in enumerate(row):
                if value is not None and str(value).strip():
                    row_data.append(f"{headers[i]}: {value}")
            if row_data:
                lines.append(" | ".join(row_data))
        
        return "\n".join(lines)
    
    
    def get_supported_extensions(self) -> List[str]:
        return ['.csv']