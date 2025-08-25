from typing import List
from openpyxl import load_workbook

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class ExcelParser(BaseDocumentParser):
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        
        chunks: List[DocumentChunk] = []
        
        workbook = load_workbook(file_path, read_only=True, data_only=True)
        sheet_names = workbook.sheetnames
        
        for sheet_name in sheet_names:
            worksheet = workbook[sheet_name]
            sheet_chunks = self._parse_sheet(worksheet, sheet_name, file_path, chunk_size)
            chunks.extend(sheet_chunks)
        
        workbook.close()
        
        return ParsedDocument(
            chunks=chunks,
            metadata={
                **self._extract_metadata(file_path), 
                "parser": "excel_openpyxl_parser", 
                "sheet_count": len(sheet_names)
            },
            file_type="excel"
        )
    
    def _parse_sheet(self, worksheet, sheet_name: str, file_path: str, chunk_size: int) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        
        # 헤더 추출
        headers = []
        if worksheet.max_row > 0:
            for cell in worksheet[1]:
                header_value = self._safe_cell_value(cell.value)
                headers.append(header_value)
        
        # 청킹을 위한 변수
        current_chunk_lines: List[str] = []
        current_size = 0
        chunk_index = 0
        
        # 시트 제목과 헤더를 청크에 추가
        sheet_header = f"Sheet: {sheet_name}"
        header_line = " | ".join(headers) if headers else ""
        
        current_chunk_lines.append(sheet_header)
        current_size += len(sheet_header)
        
        if header_line:
            current_chunk_lines.append(header_line)
            current_size += len(header_line)
        
        row_count = 0
        for row in worksheet.iter_rows(min_row=2, values_only=True):
            row_data = []
            for cell_value in row:
                safe_value = self._safe_cell_value(cell_value)
                row_data.append(safe_value)
            
            # 빈 행 건너뛰기
            if all(not val for val in row_data):
                continue
                
            row_text = " | ".join(row_data)
            row_size = len(row_text) + 1  # +1 for newline
            
            # 청크 크기 체크
            if current_size + row_size > chunk_size and current_chunk_lines:
                # 현재 청크 저장
                chunk = self._create_chunk_from_lines(
                    current_chunk_lines, sheet_name, file_path, chunk_index, row_count, len(headers)
                )
                chunks.append(chunk)
                
                # 새 청크 시작 (헤더 포함)
                current_chunk_lines = [sheet_header]
                current_size = len(sheet_header)
                if header_line:
                    current_chunk_lines.append(header_line)
                    current_size += len(header_line)
                chunk_index += 1
            
            current_chunk_lines.append(row_text)
            current_size += row_size
            row_count += 1
        
        # 마지막 청크 처리
        if current_chunk_lines and len(current_chunk_lines) > (2 if header_line else 1):
            chunk = self._create_chunk_from_lines(
                current_chunk_lines, sheet_name, file_path, chunk_index, row_count, len(headers)
            )
            chunks.append(chunk)
        
        return chunks
    
    def _safe_cell_value(self, cell_value) -> str:
        if cell_value is None:
            return ""
        if isinstance(cell_value, (int, float)):
            return str(cell_value)
        return str(cell_value).strip()
    
    def _create_chunk_from_lines(self, lines: List[str], sheet_name: str, file_path: str, 
                                chunk_index: int, total_rows: int, column_count: int) -> DocumentChunk:
        content = "\n".join(lines)
        
        return DocumentChunk(
            content=content,
            metadata={
                **self._extract_metadata(file_path),
                "sheet_name": sheet_name,
                "chunk_index": chunk_index,
                "total_rows": total_rows,
                "column_count": column_count,
                "content_size": len(content)
            },
            chunk_id=f"{self._create_chunk_id(file_path, chunk_index)}_{sheet_name}"
        )
    
    def get_supported_extensions(self) -> List[str]:
        return ['.xlsx', '.xls']