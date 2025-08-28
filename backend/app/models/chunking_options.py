from pydantic import BaseModel, Field
from typing import Optional, List


class ChunkingOptions(BaseModel):
    """문서 청킹 옵션 설정"""
    
    chunk_size: Optional[int] = Field(
        default=1000,
        description="청크 최대 크기 (문자 단위)",
        ge=100,    # 최소 100자
        le=8000    # 최대 8000자
    )
    
    chunk_overlap: Optional[int] = Field(
        default=None,
        description="청크 간 오버랩 크기 (문자 단위). 미설정 시 chunk_size의 10%",
        ge=0,
        le=1000
    )
    
    separators: Optional[List[str]] = Field(
        default=None,
        description="텍스트 분할에 사용할 구분자 목록 (우선순위 순). 미설정 시 기본 구분자 사용",
        max_items=10
    )
    
    def get_chunk_overlap(self) -> int:
        """실제 사용할 chunk_overlap 값을 반환"""
        if self.chunk_overlap is not None:
            return self.chunk_overlap
        return int((self.chunk_size or 1000) * 0.1)
    
    def get_chunk_size(self) -> int:
        """실제 사용할 chunk_size 값을 반환"""
        return self.chunk_size or 1000
    
    def get_separators(self) -> List[str]:
        """실제 사용할 separators 값을 반환"""
        if self.separators is not None:
            return self.separators
        
        # 기본 구분자 (base.py와 동일)
        return [
            "\n\n",  # 문단 구분
            "\n",    # 줄 구분  
            ". ",    # 문장 구분
            " ",     # 공백 구분
            ""       # 문자 구분
        ]


class UploadRequest(BaseModel):
    """파일 업로드 요청 (청킹 옵션 포함)"""
    
    chunking: Optional[ChunkingOptions] = Field(
        default=None,
        description="청킹 옵션 설정. 미설정 시 기본값 사용"
    )


class CrawlRequest(BaseModel):
    """웹 크롤링 요청 (청킹 옵션 포함)"""
    
    url: str = Field(description="크롤링할 웹 페이지 URL")
    max_depth: Optional[int] = Field(default=0, description="크롤링 깊이", ge=0, le=3)
    same_domain: Optional[bool] = Field(default=True, description="동일 도메인만 크롤링")
    
    chunking: Optional[ChunkingOptions] = Field(
        default=None,
        description="청킹 옵션 설정. 미설정 시 기본값 사용"
    )