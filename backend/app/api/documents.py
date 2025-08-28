from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Query
from typing import Optional
import os
import uuid
from datetime import datetime

from ..services.document_processor import DocumentProcessor
from ..services.parsers.base import ParsedDocument
from ..models.chunking_options import ChunkingOptions, UploadRequest, CrawlRequest
from typing import cast

from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlparse
import re

router = APIRouter()
processor = DocumentProcessor()

# 메모리에 문서 정보 저장 (테스트용)
documents_db = {}

# === 응답 모델들 ===

class UploadResponse(BaseModel):
    """문서 업로드 성공 응답"""
    success: bool = Field(True, description="업로드 성공 여부")
    document_id: str = Field(description="생성된 문서 고유 ID")
    chunks_created: int = Field(description="생성된 청크 수")
    model_used: str = Field(description="사용된 모델명")
    file_type: str = Field(description="파일 타입")
    parser_used: str = Field(description="사용된 파서명")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "chunks_created": 15,
                "model_used": "parser_test",
                "file_type": "pdf",
                "parser_used": "pdf_pymupdf_langchain"
            }
        }

class DocumentListResponse(BaseModel):
    """문서 목록 응답"""
    documents: list = Field(description="문서 목록")
    
class ErrorResponse(BaseModel):
    """에러 응답"""
    detail: str = Field(description="에러 메시지")

@router.post("/upload", 
    summary="📄 동기 파일 업로드",
    description="""
    파일을 즉시 업로드하고 파싱을 완료한 후 결과를 반환합니다.
    
    동기 처리:
    • 업로드 완료까지 대기 후 결과 반환
    • 실시간 처리 상태 확인 불가
    • 소용량 파일에 적합
    
    지원 형식: PDF, DOCX, XLSX, PPTX, HTML, MD, TXT, CSV
    
    청킹 옵션:
    • chunk_size: 청크 최대 크기 (100-8000자, 기본값: 1000)
    • chunk_overlap: 청크 간 오버랩 크기 (기본값: chunk_size의 10%)
    """,
    response_model=UploadResponse,
    responses={
        400: {"model": ErrorResponse, "description": "잘못된 요청 (지원되지 않는 파일 형식 등)"},
        500: {"model": ErrorResponse, "description": "서버 내부 오류"}
    })
async def upload_document(
    file: UploadFile = File(..., description="업로드할 문서 파일"),
    chunk_size: Optional[int] = Form(1000, description="청크 최대 크기 (100-8000자)", ge=100, le=8000),
    chunk_overlap: Optional[int] = Form(None, description="청크 간 오버랩 크기 (기본값: chunk_size의 10%)", ge=0),
):
    """파일 업로드 및 파싱 테스트"""
    
    
    # 파일 확장자 검증
    if file.filename is None:
        raise HTTPException(status_code=400, detail="파일명이 없습니다")
    file_info = processor.get_file_info(file.filename)
    if not file_info["is_supported"]:
        raise HTTPException(
            status_code=400, 
            detail=f"지원되지 않는 파일 형식: {file_info['extension']}"
        )
    
    # 파일 저장
    document_id = str(uuid.uuid4())
    upload_dir = "./data"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, f"{document_id}_{file.filename}")
    
    try:
        # 파일 쓰기
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # 청킹 옵션 준비
        chunking_kwargs = {
            'chunk_size': chunk_size,
        }
        if chunk_overlap is not None:
            chunking_kwargs['chunk_overlap'] = chunk_overlap
            
        # 파서로 문서 처리
        parsed_doc = processor.process_file(file_path, **chunking_kwargs)
        
        # 메모리 DB에 저장
        documents_db[document_id] = {
            "id": document_id,
            "filename": file.filename,
            "file_size": len(content),
            "chunks_count": len(parsed_doc.chunks),
            "upload_time": datetime.now().isoformat(),
            "status": "completed",
            "file_path": file_path,
            "parsed_doc": parsed_doc
        }
        
        return UploadResponse(
            success=True,
            document_id=document_id,
            chunks_created=len(parsed_doc.chunks),
            model_used="parser_test",  # 파서 테스트용
            file_type=parsed_doc.file_type or "unknown",
            parser_used=parsed_doc.metadata.get("parser", "unknown")
        )
        
    except Exception as e:
        original_error = str(e)
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except PermissionError:
                pass
        
        raise HTTPException(status_code=500, detail=f"파일 처리 실패: {original_error}")

class UrlCrawlRequest(BaseModel):
    """웹 크롤링 요청 모델"""
    
    url: str = Field(description="크롤링할 웹 페이지 URL", examples=["https://example.com"])
    max_depth: Optional[int] = Field(0, description="크롤링 깊이 (0: 현재 페이지만, 1: 링크 1단계)", ge=0, le=3)
    same_domain: Optional[bool] = Field(True, description="동일 도메인만 크롤링 여부")
    chunk_size: Optional[int] = Field(1000, description="청크 최대 크기 (문자 단위)", ge=100, le=8000)
    chunk_overlap: Optional[int] = Field(None, description="청크 간 오버랩 크기 (기본값: chunk_size의 10%)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/article",
                "max_depth": 0,
                "same_domain": True,
                "chunk_size": 1000,
                "chunk_overlap": 100
            }
        }
    
    @field_validator('url')
    def validate_url(cls, v):
        if not v or not v.strip():
            raise ValueError("URL을 입력해주세요")
        
        v = v.strip()
        
        # 스키마가 없으면 https:// 추가
        if not re.match(r'^https?://', v):
            v = f"https://{v}"
        
        # URL 형식 검증
        try:
            parsed = urlparse(v)
            if not parsed.netloc:
                raise ValueError("올바른 URL 형식이 아닙니다")
        except:
            raise ValueError("올바른 URL 형식이 아닙니다")
            
        return v

@router.post("/url",
    summary="🌐 동기 웹 크롤링",
    description="""
    웹 페이지를 즉시 크롤링하고 파싱을 완료한 후 결과를 반환합니다.
    
    동기 처리:
    • 크롤링 완료까지 대기 후 결과 반환
    • 실시간 처리 상태 확인 불가
    • 단일 페이지 크롤링에 적합
    
    크롤링 옵션:
    • max_depth: 크롤링 깊이 (0-3단계, 기본값: 0)
    • same_domain: 동일 도메인만 크롤링 (기본값: true)
    
    청킹 옵션:
    • chunk_size: 청크 최대 크기 (100-8000자, 기본값: 1000)
    • chunk_overlap: 청크 간 오버랩 크기 (기본값: chunk_size의 10%)
    """,
    response_model=UploadResponse,
    responses={
        400: {"model": ErrorResponse, "description": "잘못된 URL 또는 콘텐츠 없음"},
        500: {"model": ErrorResponse, "description": "크롤링 실패"}
    })
async def crawl_url(request: UrlCrawlRequest):
    """URL 크롤링 및 파싱 테스트"""
    
    # 요청 파라미터 로깅
    print(f"=== 크롤링 요청 파라미터 ===")
    print(f"URL: {request.url}")
    print(f"max_depth: {request.max_depth}")
    print(f"same_domain: {request.same_domain}")
    print("=" * 30)
    
    try:
        # 청킹 옵션 준비
        chunking_kwargs = {
            'chunk_size': request.chunk_size or 1000,
        }
        if request.chunk_overlap is not None:
            chunking_kwargs['chunk_overlap'] = request.chunk_overlap
            
        # URL 크롤링 (실패하면 여기서 예외 발생)
        parsed_doc = processor.process_url(
            request.url, 
            max_depth=request.max_depth or 0, 
            same_domain=request.same_domain or True,
            **chunking_kwargs
        )
        
        # 크롤링 성공한 경우만 문서 추가
        if not parsed_doc.chunks:
            raise HTTPException(status_code=400, detail="크롤링된 내용이 없습니다")
            
    except HTTPException:
        # HTTPException은 그대로 다시 발생
        raise
    except Exception as e:
        # 상세한 오류 로깅
        import traceback
        error_detail = f"URL 크롤링 실패: {str(e)}"
        print(f"=== 크롤링 오류 상세 ===")
        print(f"URL: {request.url}")
        print(f"오류: {error_detail}")
        print(f"스택 트레이스: {traceback.format_exc()}")
        print("=" * 50)
        
        # 다른 예외는 500 에러로 변환
        raise HTTPException(status_code=500, detail=error_detail)
    
    # 성공한 경우만 여기 도달
    document_id = str(uuid.uuid4())
    
    # 메모리 DB에 저장
    documents_db[document_id] = {
        "id": document_id,
        "filename": f"crawled_{request.url.replace('://', '_').replace('/', '_')[:50]}",
        "file_size": sum(len(chunk.content) for chunk in parsed_doc.chunks),
        "chunks_count": len(parsed_doc.chunks),
        "upload_time": datetime.now().isoformat(),
        "status": "completed",
        "file_path": request.url,
        "parsed_doc": parsed_doc
    }
    
    return UploadResponse(
        success=True,
        document_id=document_id,
        chunks_created=len(parsed_doc.chunks),
        model_used="web_crawler",
        file_type="web",
        parser_used=f"web_crawler (crawled: {parsed_doc.metadata.get('crawled_urls', 1)} urls)"
    )

@router.get("",
    summary="📋 문서 목록 조회",
    description="""
    시스템에 업로드된 모든 문서의 목록을 조회합니다.
    
    반환 정보:
    • 문서 ID 및 파일명
    • 파일 크기 및 청크 개수
    • 업로드 시간 및 처리 상태
    • 동기/비동기 업로드 구분 없이 모든 문서 표시
    """,
    response_model=DocumentListResponse)
async def get_documents():
    """업로드된 문서 목록 조회"""
    
    documents = []
    for doc_data in documents_db.values():
        documents.append({
            "id": doc_data["id"],
            "filename": doc_data["filename"],
            "file_size": doc_data["file_size"],
            "chunks_count": doc_data["chunks_count"],
            "upload_time": doc_data["upload_time"],
            "status": doc_data["status"]
        })
    
    return {"documents": documents}

@router.get("/{document_id}",
    summary="📄 문서 상세 조회",
    description="""
    특정 문서의 상세 정보와 청크 데이터를 조회합니다.
    
    반환 정보:
    • 문서 메타데이터 (ID, 파일명, 크기, 업로드 시간 등)
    • 파싱된 모든 청크의 내용과 메타데이터
    • 페이지 번호 및 섹션 정보 (해당되는 경우)
    """)
async def get_document(document_id: str):
    """특정 문서 정보 및 청크 조회"""
    
    if document_id not in documents_db:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
    
    doc_data = documents_db[document_id]
    parsed_doc = cast(ParsedDocument, doc_data["parsed_doc"])
    
    # 청크 정보를 JSON 형태로 변환
    chunks = []
    for chunk in parsed_doc.chunks:
        chunks.append({
            "chunk_id": chunk.chunk_id,
            "content": chunk.content,
            "metadata": chunk.metadata,
            "page_number": chunk.page_number,
            "section_title": chunk.section_title
        })
    
    return {
        "document": {
            "id": doc_data["id"],
            "filename": doc_data["filename"],
            "file_size": doc_data["file_size"],
            "chunks_count": doc_data["chunks_count"],
            "upload_time": doc_data["upload_time"],
            "status": doc_data["status"],
            "file_type": parsed_doc.file_type,
            "metadata": parsed_doc.metadata
        },
        "chunks": chunks
    }

@router.delete("/{document_id}",
    summary="🗑️ 문서 삭제",
    description="""
    시스템에서 문서와 관련 데이터를 삭제합니다.
    
    삭제 대상:
    • 문서 메타데이터 및 청크 데이터
    • 저장된 파일 (해당되는 경우)
    • 문서 목록에서 제거
    """)
async def delete_document(document_id: str):
    """문서 삭제"""
    
    # 디버깅용 로그 
    print("=" * 50)
    print("🚨 DELETE 엔드포인트 호출됨!")
    print(f"🔍 삭제 요청된 문서 ID: {document_id}")
    print(f"📋 현재 저장된 문서 IDs: {list(documents_db.keys())}")
    print(f"📊 총 문서 개수: {len(documents_db)}")
    print("=" * 50)
    
    if document_id not in documents_db:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
    
    doc_data = documents_db[document_id]
    
    # 파일 삭제 (URL 크롤링이 아닌 경우)
    file_path = doc_data["file_path"]
    if file_path and isinstance(file_path, str) and os.path.exists(file_path) and not file_path.startswith("http"):
        try:
            os.remove(file_path)
        except:
            pass  # 파일 삭제 실패해도 DB에서는 제거
    
    # 메모리 DB에서 제거
    del documents_db[document_id]
    
    return {"success": True, "message": "문서가 삭제되었습니다"}

class QueryRequest(BaseModel):
    """질의응답 요청 모델"""
    
    query: str = Field(description="질문 내용", examples=["이 문서의 주요 내용은 무엇인가요?"], min_length=1)
    top_k: Optional[int] = Field(5, description="반환할 최대 청크 수", ge=1, le=20)
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "프로젝트의 주요 기능은 무엇인가요?",
                "top_k": 5
            }
        }

@router.post("/query",
    summary="🔍 문서 질의응답",
    description="""
    업로드된 문서들을 대상으로 질의응답을 수행합니다.
    
    동기 처리:
    • 즉시 검색 수행 후 결과 반환
    • 실시간 검색 상태 확인 불가
    • 간단한 질의응답에 적합
    
    검색 옵션:
    • top_k: 반환할 최대 청크 수 (1-20개, 기본값: 5)
    • 의미 기반 유사도 검색
    
    현재 상태: 파서 테스트용 구현 (실제 벡터 검색 미구현)
    """,
    response_description="질문에 대한 답변과 관련 문서 청크들 반환",
    deprecated=True)
async def test_query(request: QueryRequest):
    """파서 테스트용 가짜 질의응답 (실제 검색 없이 청크 반환)"""
    
    if not documents_db:
        raise HTTPException(status_code=400, detail="업로드된 문서가 없습니다")
    
    # 모든 문서의 청크를 수집
    all_chunks = []
    for doc_data in documents_db.values():
        parsed_doc = cast(ParsedDocument, doc_data["parsed_doc"])
        for chunk in parsed_doc.chunks:
            all_chunks.append({
                "document_id": doc_data["id"],
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "similarity": 0.8,  # 가짜 유사도
                "page": chunk.page_number,
                "section_title": chunk.section_title,
                "metadata": {
                    **chunk.metadata,
                    "filename": doc_data["filename"]
                }
            })
    
    # top_k 개만 반환
    selected_chunks = all_chunks[:request.top_k or 5]
    
    # 가짜 답변 생성
    answer = f"질문 '{request.query}'에 대한 답변입니다. (파서 테스트용 가짜 응답)\n\n"
    answer += f"총 {len(documents_db)}개 문서에서 {len(all_chunks)}개 청크를 찾았습니다."
    
    return {
        "success": True,
        "data": {
            "answer": answer,
            "sources": selected_chunks
        },
        "metadata": {
            "query_time": "0.1s",
            "model_used": "parser_test",
            "language_detected": "ko",
            "retrieval_count": len(selected_chunks)
        }
    }