from typing import List
try:
    from pptx import Presentation
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class PPTXParser(BaseDocumentParser):
    def parse(self, file_path: str, chunk_size: int = 1000, **kwargs) -> ParsedDocument:
        if not PPTX_AVAILABLE:
            raise ImportError("PPTX 파싱을 위해 python-pptx가 필요합니다")
        
        prs = Presentation(file_path)
        chunks = []
        
        for slide_idx, slide in enumerate(prs.slides):
            slide_text = []
            
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_text.append(shape.text)
            
            if slide_text:
                content = '\n'.join(slide_text)
                chunk = DocumentChunk(
                    content=content,
                    metadata={
                        **self._extract_metadata(file_path),
                        "slide_number": slide_idx + 1,
                        "slide_layout": slide.slide_layout.name if hasattr(slide.slide_layout, 'name') else 'Unknown'
                    },
                    chunk_id=self._create_chunk_id(file_path, slide_idx),
                    page_number=slide_idx + 1
                )
                chunks.append(chunk)
        
        return ParsedDocument(
            chunks=chunks,
            metadata={**self._extract_metadata(file_path), "parser": "pptx_parser", "total_slides": len(prs.slides)},
            file_type="pptx"
        )
    
    def get_supported_extensions(self) -> List[str]:
        return ['.pptx', '.ppt']