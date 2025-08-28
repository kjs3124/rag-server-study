from typing import List, Optional
from openpyxl import load_workbook

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class ExcelParser(BaseDocumentParser):
    def parse(self, file_path: str, chunk_size: int = 1000, chunk_overlap: Optional[int] = None, **kwargs) -> ParsedDocument:
        
        chunks: List[DocumentChunk] = []
        
        workbook = load_workbook(file_path, read_only=False, data_only=True)
        sheet_names = workbook.sheetnames
        
        # 모든 시트의 텍스트를 먼저 추출
        all_text_parts = []
        for sheet_name in sheet_names:
            worksheet = workbook[sheet_name]
            sheet_text = self._extract_sheet_text(worksheet, sheet_name)
            if sheet_text.strip():
                all_text_parts.append(sheet_text)
        
        # 전체 텍스트를 LangChain으로 청킹
        full_text = '\n\n'.join(all_text_parts)
        chunks = self._create_langchain_chunks(
            full_text,
            chunk_size,
            file_path,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\nSheet: ",  # 시트 구분
                "\n\n",         # 문단 구분
                "\n",           # 줄 구분
                " | ",          # 열 구분
                " ",            # 공백 구분
                ""              # 문자 구분
            ],
            parser="excel_openpyxl_langchain",
            sheet_count=len(sheet_names)
        )
        
        workbook.close()
        
        return ParsedDocument(
            chunks=chunks,
            metadata={
                **self._extract_metadata(file_path), 
                "parser": "excel_openpyxl_langchain", 
                "sheet_count": len(sheet_names),
                "total_chunks": len(chunks)
            },
            file_type="excel"
        )
    
    def _extract_sheet_text(self, worksheet, sheet_name: str) -> str:
        """시트에서 텍스트 추출"""
        lines = [f"Sheet: {sheet_name}"]
        
        # 헤더 추출
        headers = []
        if worksheet.max_row > 0:
            for cell in worksheet[1]:
                header_value = self._safe_cell_value(cell.value)
                headers.append(header_value)
        
        if headers:
            lines.append(" | ".join(headers))
        
        # 데이터 행 추출
        for row in worksheet.iter_rows(min_row=2, values_only=True):
            row_data = []
            for cell_value in row:
                safe_value = self._safe_cell_value(cell_value)
                row_data.append(safe_value)
            
            # 빈 행 건너뛰기
            if all(not val for val in row_data):
                continue
                
            row_text = " | ".join(row_data)
            lines.append(row_text)
        
        return "\n".join(lines)
    
    def _safe_cell_value(self, cell_value) -> str:
        if cell_value is None:
            return ""
        if isinstance(cell_value, (int, float)):
            return str(cell_value)
        return str(cell_value).strip()
    
    
    def get_supported_extensions(self) -> List[str]:
        return ['.xlsx', '.xls']