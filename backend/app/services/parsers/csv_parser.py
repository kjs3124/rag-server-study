from typing import List, Optional, Any
import chardet
import polars as pl

# LangChain CSVLoader
CSVLoader: Any = None
CSVLOADER_AVAILABLE = False
try:
    from langchain_community.document_loaders import CSVLoader as _CSVLoader
    CSVLoader = _CSVLoader
    CSVLOADER_AVAILABLE = True
except ImportError:
    CSVLOADER_AVAILABLE = False

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class CSVParser(BaseDocumentParser):
    def parse(self, file_path: str, chunk_size: int = 1000, chunk_overlap: Optional[int] = None, **kwargs) -> ParsedDocument:
        """CSV 파일을 파싱하여 청크로 분할"""
        
        # 1차: LangChain CSVLoader 사용 시도
        if CSVLOADER_AVAILABLE and CSVLoader is not None:
            try:
                encoding = self._detect_encoding(file_path)
                parsed_doc = self._parse_with_csvloader(file_path, encoding, chunk_size, chunk_overlap, **kwargs)
                if parsed_doc is not None and parsed_doc.chunks:
                    print(f"✅ CSVLoader 청킹 성공: {len(parsed_doc.chunks)}개 청크 생성")
                    return parsed_doc
            except Exception as e:
                print(f"CSVLoader 실패: {e}, polars 폴백 시도")
        
        # 2차: 기존 polars 기반 폴백
        return self._parse_with_polars_fallback(file_path, chunk_size, chunk_overlap, **kwargs)
    
    def _parse_with_csvloader(self, file_path: str, encoding: str, chunk_size: int = 1000, chunk_overlap: Optional[int] = None, **kwargs) -> Optional[ParsedDocument]:
        """CSVLoader를 사용한 전용 CSV 청킹"""
        
        if not CSVLOADER_AVAILABLE or CSVLoader is None:
            raise ImportError("CSVLoader를 사용할 수 없습니다")
        
        # CSVLoader로 직접 로드
        loader = CSVLoader(
            file_path=file_path,
            encoding=encoding,
            csv_args={"delimiter": ","}  # 기본 CSV 구분자
        )
        
        docs = loader.load()
        
        if not docs:
            return None
        
        chunks: List[DocumentChunk] = []
        
        # CSVLoader의 각 문서를 DocumentChunk로 변환 (행별 자동 청킹 유지)
        for i, doc in enumerate(docs):
            if doc.page_content.strip():
                chunk = DocumentChunk(
                    content=doc.page_content,
                    metadata={
                        **self._extract_metadata(file_path),
                        **doc.metadata,  # CSVLoader 메타데이터 포함
                        "chunk_index": i,
                        "chunk_size": len(doc.page_content),
                        "parser": "csvloader_csv_parser",
                        "encoding": encoding
                    },
                    chunk_id=self._create_chunk_id(file_path, i)
                )
                chunks.append(chunk)
        
        return ParsedDocument(
            chunks=chunks,
            metadata={
                **self._extract_metadata(file_path), 
                "parser": "csvloader_csv_parser",
                "encoding": encoding,
                "total_chunks": len(chunks),
                "source": "csvloader"
            },
            file_type="csv"
        )
    
    def _parse_with_polars_fallback(self, file_path: str, chunk_size: int = 1000, chunk_overlap: Optional[int] = None, **kwargs) -> ParsedDocument:
        """기존 polars 기반 폴백 처리"""
        
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
            chunk_overlap=chunk_overlap,
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