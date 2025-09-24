from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Query
from typing import Optional
import os
import uuid
from datetime import datetime

from ..services.document_processor import DocumentProcessor
from ..services.parsers.base import ParsedDocument
from ..models.chunking_options import ChunkingOptions, UploadRequest, CrawlRequest
from ..services.persistence import load_documents, save_documents, auto_save_documents
from ..utils.memory import cleanup_document_memory, get_memory_usage, auto_cleanup
from ..utils.error_logger import error_logger, ErrorLevel
from ..utils.log_monitor import get_system_health
from ..utils.chunking import prepare_chunking_kwargs, format_chunking_summary

# 새로운 RAG 서비스 import
from ..services.embedding import embedding_service, embed_document_chunks
from ..services.vector_store import vector_store
from ..services.rag_service import rag_service
from typing import cast
import logging

from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlparse
import re

logger = logging.getLogger(__name__)

router = APIRouter()
processor = DocumentProcessor()

# 파일에서 문서 정보 로드 (서버 재시작 시에도 유지)
try:
    documents_db = load_documents()
    logger.info(f"📚 기존 문서 데이터 로드 완료: {len(documents_db)}개")
except Exception as e:
    logger.warning(f"문서 데이터 로드 실패, 새로 시작: {e}")
    documents_db = {}

# === 통일된 응답 모델들 ===

from typing import Any

class BaseResponse(BaseModel):
    """모든 API 응답의 기본 구조"""
    success: bool = Field(description="요청 성공 여부")
    message: str = Field(default="", description="응답 메시지")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="응답 시간")
    data: Optional[Any] = Field(default=None, description="응답 데이터")
    error_id: Optional[str] = Field(default=None, description="에러 추적 ID")

class SuccessResponse(BaseResponse):
    """성공 응답"""
    success: bool = Field(default=True, description="성공 표시")

class ErrorResponse(BaseResponse):
    """에러 응답"""
    success: bool = Field(default=False, description="실패 표시")
    error_type: str = Field(default="error", description="에러 타입")

# === 응답 데이터 모델들 ===

class UploadData(BaseModel):
    """업로드 응답 데이터"""
    document_id: str = Field(description="생성된 문서 고유 ID")
    chunks_created: int = Field(description="생성된 청크 수")
    model_used: str = Field(description="사용된 모델명")
    file_type: str = Field(description="파일 타입")
    parser_used: str = Field(description="사용된 파서명")

class DocumentData(BaseModel):
    """문서 정보 데이터"""
    id: str
    filename: str
    file_size: int
    chunks_count: int
    upload_time: str
    status: str

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
    response_model=SuccessResponse,
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
        return ErrorResponse(
            message="유효하지 않은 파일",
            error_type="validation_error",
            data={"detail": "파일명이 없습니다"}
        )
    file_info = processor.get_file_info(file.filename)
    if not file_info["is_supported"]:
        return ErrorResponse(
            message="지원되지 않는 파일 형식",
            error_type="validation_error",
            data={"detail": f"지원되지 않는 파일 형식: {file_info['extension']}"}
        )
    
    # 파일 저장
    document_id = str(uuid.uuid4())
    upload_dir = "./data"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, f"{document_id}_{file.filename}")
    content = None
    
    try:
        # 파일 쓰기
        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
            # 청킹 옵션 준비 (유틸리티 사용)
        chunking_kwargs = prepare_chunking_kwargs(chunk_size, chunk_overlap)
        
        # 로깅용 요약 정보
        chunking_summary = format_chunking_summary(chunk_size, chunk_overlap)
        logger.info(f"📝 문서 업로드 시작: {file.filename} ({chunking_summary})")
            
        # 파서로 문서 처리
        parsed_doc = processor.process_file(file_path, **chunking_kwargs)
        
        # 임베딩 및 벡터 저장 수행
        embeddings, embedding_metadata = await embed_document_chunks(parsed_doc.chunks)
        
        # 문서 메타데이터 준비
        doc_metadata = {
            'filename': file.filename,
            'file_type': parsed_doc.file_type or "unknown",
            'parser_used': parsed_doc.metadata.get("parser", "unknown"),
            'language_info': embedding_metadata['language_analysis']
        }
        
        # 벡터 스토어에 저장
        vector_stored = await vector_store.store_document_vectors(
            document_id=document_id,
            embeddings=embeddings,
            chunks=parsed_doc.chunks,
            metadata=doc_metadata
        )
        
        # DB에 저장 및 파일로 영속화
        with auto_save_documents(documents_db):
            documents_db[document_id] = {
                "id": document_id,
                "filename": file.filename,
                "file_size": len(content),
                "chunks_count": len(parsed_doc.chunks),
                "upload_time": datetime.now().isoformat(),
                "status": "completed",
                "file_path": file_path,
                "parsed_doc": parsed_doc,
                "embedding_metadata": embedding_metadata,
                "vector_stored": vector_stored
            }
        
        return SuccessResponse(
            message="파일 업로드 및 벡터화 성공",
            data=UploadData(
                document_id=document_id,
                chunks_created=len(parsed_doc.chunks),
                model_used=embedding_metadata['model_used'],
                file_type=parsed_doc.file_type or "unknown",
                parser_used=parsed_doc.metadata.get("parser", "unknown")
            )
        )
        
    except Exception as e:
        error_id = error_logger.log_processing_error(
            file_path=file.filename,
            parser_name="unknown",
            error=e,
            file_size=len(content) if content is not None else 0
        )
        
        original_error = str(e)
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except PermissionError:
                pass
        
        return ErrorResponse(
            message="파일 처리 실패",
            error_id=error_id,
            error_type="processing_error",
            data={"detail": original_error}
        )

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
    response_model=SuccessResponse,
    responses={
        400: {"model": ErrorResponse, "description": "잘못된 URL 또는 콘텐츠 없음"},
        500: {"model": ErrorResponse, "description": "크롤링 실패"}
    })
async def crawl_url(request: UrlCrawlRequest):
    """URL 크롤링 및 파싱 테스트"""
    
    # 요청 파라미터 로깅 (개선된 형식)
    chunking_summary = format_chunking_summary(request.chunk_size, request.chunk_overlap)
    logger.info(f"🌐 크롤링 요청: {request.url} (depth: {request.max_depth}, same_domain: {request.same_domain}, {chunking_summary})")
    
    try:
        # 청킹 옵션 준비 (유틸리티 사용)
        chunking_kwargs = prepare_chunking_kwargs(request.chunk_size, request.chunk_overlap)
        
        # 로깅용 요약 정보
        chunking_summary = format_chunking_summary(request.chunk_size, request.chunk_overlap)
        logger.info(f"🌐 웹 크롤링 시작: {request.url} ({chunking_summary})")
            
        # URL 크롤링 (실패하면 여기서 예외 발생)
        parsed_doc = processor.process_url(
            request.url, 
            max_depth=request.max_depth or 0, 
            same_domain=request.same_domain or True,
            **chunking_kwargs
        )
        
        # 크롤링 성공한 경우만 문서 추가
        if not parsed_doc.chunks:
            return ErrorResponse(
                message="크롤링된 내용이 없음",
                error_type="validation_error",
                data={"detail": "크롤링된 내용이 없습니다"}
            )
            
    except HTTPException:
        # HTTPException은 그대로 다시 발생
        raise
    except Exception as e:
        error_id = error_logger.log_processing_error(
            file_path=request.url,
            parser_name="web_crawler",
            error=e,
            file_size=None
        )
        
        error_detail = f"[{error_id}] URL 크롤링 실패: {str(e)}"
        logger.error(f"[{error_id}] ❌ 크롤링 오류: {request.url}")
        
        # 다른 예외는 500 에러로 변환
        return ErrorResponse(
            message="URL 크롤링 실패",
            error_id=error_id,
            error_type="crawling_error",
            data={"detail": str(e)}
        )
    
    # 성공한 경우만 여기 도달
    document_id = str(uuid.uuid4())
    
    # 임베딩 및 벡터 저장 수행
    embeddings, embedding_metadata = await embed_document_chunks(parsed_doc.chunks)
    
    # 문서 메타데이터 준비
    doc_metadata = {
        'filename': f"crawled_{request.url.replace('://', '_').replace('/', '_')[:50]}",
        'file_type': 'web',
        'parser_used': 'web_crawler',
        'source_url': request.url,
        'language_info': embedding_metadata['language_analysis']
    }
    
    # 벡터 스토어에 저장
    vector_stored = await vector_store.store_document_vectors(
        document_id=document_id,
        embeddings=embeddings,
        chunks=parsed_doc.chunks,
        metadata=doc_metadata
    )
    
    # DB에 저장 및 파일로 영속화
    with auto_save_documents(documents_db):
        documents_db[document_id] = {
            "id": document_id,
            "filename": f"crawled_{request.url.replace('://', '_').replace('/', '_')[:50]}",
            "file_size": sum(len(chunk.content) for chunk in parsed_doc.chunks),
            "chunks_count": len(parsed_doc.chunks),
            "upload_time": datetime.now().isoformat(),
            "status": "completed",
            "file_path": request.url,
            "parsed_doc": parsed_doc,
            "embedding_metadata": embedding_metadata,
            "vector_stored": vector_stored
        }
    
    return SuccessResponse(
        message="웹 크롤링 성공",
        data=UploadData(
            document_id=document_id,
            chunks_created=len(parsed_doc.chunks),
            model_used="web_crawler",
            file_type="web",
            parser_used=f"web_crawler (crawled: {parsed_doc.metadata.get('crawled_urls', 1)} urls)"
        )
    )

@router.get("",
    summary="📋 문서 목록 조회 (Qdrant 기준)",
    description="""
    Qdrant 벡터 스토어에 실제 저장된 문서들을 기준으로 목록을 조회합니다.
    
    반환 정보:
    • 실제 Qdrant에 벡터가 있는 문서만 표시
    • 문서 ID 및 파일명 (벡터 메타데이터 기준)
    • 청크 개수 (실제 저장된 벡터 수)
    • 업로드 시간 및 처리 상태
    """,
    response_model=SuccessResponse)
async def get_documents():
    """Qdrant 기준 문서 목록 조회"""
    
    try:
        # Qdrant에서 실제 저장된 벡터들을 기준으로 문서 목록 생성
        from qdrant_client.models import Filter as QFilter, FieldCondition as QFieldCondition, MatchValue as QMatchValue
        
        # Qdrant에서 모든 포인트 조회 (메타데이터만)
        if not vector_store.store or not vector_store.store.client:
            return SuccessResponse(
                message="벡터 스토어가 초기화되지 않음",
                data={"documents": []}
            )
        
        # 모든 포인트를 스크롤해서 가져오기
        all_points = []
        offset = None
        
        while True:
            scroll_result = vector_store.store.client.scroll(
                collection_name=vector_store.default_collection,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            if scroll_result is None:
                break

            points, next_offset = scroll_result
            all_points.extend(points)
            
            if next_offset is None:
                break
            offset = next_offset
        
        # 문서 ID별로 그룹핑
        documents_info = {}
        for point in all_points:
            payload = point.payload
            doc_id = payload.get('document_id')
            filename = payload.get('filename', 'Unknown')
            created_at = payload.get('created_at', 'Unknown')
            
            if doc_id not in documents_info:
                documents_info[doc_id] = {
                    'id': doc_id,
                    'filename': filename,
                    'chunks_count': 0,
                    'upload_time': created_at,
                    'status': 'completed',
                    'file_size': 0
                }
            
            documents_info[doc_id]['chunks_count'] += 1
            # 콘텐츠 길이로 대략적인 파일 크기 계산
            content_length = len(payload.get('content', ''))
            documents_info[doc_id]['file_size'] += content_length
        
        # DocumentData 객체로 변환
        documents = []
        for doc_info in documents_info.values():
            documents.append(DocumentData(
                id=doc_info['id'],
                filename=doc_info['filename'],
                file_size=doc_info['file_size'],
                chunks_count=doc_info['chunks_count'],
                upload_time=doc_info['upload_time'],
                status=doc_info['status']
            ))
        
        return SuccessResponse(
            message=f"Qdrant 기준 문서 목록 조회 성공 ({len(documents)}개 문서)",
            data={"documents": documents}
        )
        
    except Exception as e:
        logger.error(f"Qdrant 기준 문서 목록 조회 실패: {e}")
        # Fallback 없이 오류 반환 - 실제 벡터가 있는 문서만 표시
        return ErrorResponse(
            message="문서 목록 조회 실패",
            error_type="vector_store_error",
            data={"detail": f"벡터 스토어 조회 실패: {str(e)}"}
        )

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
        return ErrorResponse(
            message="문서를 찾을 수 없음",
            error_type="not_found_error",
            data={"detail": f"문서 ID '{document_id}'를 찾을 수 없습니다"}
        )
    
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
    
    return SuccessResponse(
        message="문서 상세 조회 성공",
        data={
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
    )

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
    
    # 디버깅용 로그 (개선된 형식)
    logger.info(f"🗑️ 문서 삭제 요청: {document_id} (현재 {len(documents_db)}개 문서 저장됨)")
    
    if document_id not in documents_db:
        return ErrorResponse(
            message="문서를 찾을 수 없음",
            error_type="not_found_error",
            data={"detail": f"문서 ID '{document_id}'를 찾을 수 없습니다"}
        )
    
    doc_data = documents_db[document_id]
    
    # 벡터 스토어에서 문서 벡터 삭제
    try:
        vector_deleted = await vector_store.delete_document_vectors(document_id)
        if vector_deleted:
            logger.info(f"벡터 삭제 성공: {document_id}")
        else:
            logger.warning(f"벡터 삭제 실패 또는 없음: {document_id}")
    except Exception as e:
        logger.error(f"벡터 삭제 오류 {document_id}: {e}")
    
    # 메모리에서 파싱된 데이터 정리
    cleanup_success = cleanup_document_memory(doc_data)
    logger.debug(f"메모리 정리 {'성공' if cleanup_success else '실패'}: {document_id}")
    
    # 파일 삭제 (URL 크롤링이 아닌 경우)
    file_path = doc_data["file_path"]
    if file_path and isinstance(file_path, str) and os.path.exists(file_path) and not file_path.startswith("http"):
        try:
            os.remove(file_path)
        except:
            pass  # 파일 삭제 실패해도 DB에서는 제거
    
    # DB에서 제거 및 파일로 영속화
    with auto_save_documents(documents_db):
        del documents_db[document_id]
    
    # 자동 메모리 정리 (필요시)
    auto_cleanup(documents_db)
    
    logger.info(f"✅ 문서 삭제 완료: {document_id} (남은 문서: {len(documents_db)}개)")
    return SuccessResponse(
        message="문서가 삭제되었습니다",
        data={"deleted_document_id": document_id}
    )

@router.get("/memory/status",
    summary="🧠 메모리 상태 조회",
    description="현재 시스템의 메모리 사용량과 상태를 조회합니다.")
async def get_memory_status():
    """메모리 상태 조회"""
    from ..utils.memory import memory_manager
    
    status = memory_manager.get_memory_status()
    status["total_documents"] = len(documents_db)
    
    return status

@router.post("/memory/cleanup",
    summary="🧹 수동 메모리 정리",
    description="수동으로 메모리 정리를 실행합니다.")
async def manual_memory_cleanup():
    """수동 메모리 정리"""
    cleanup_results = auto_cleanup(documents_db)
    return SuccessResponse(
        message="메모리 정리 완료",
        data={"cleanup_results": cleanup_results}
    )

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
    summary="🔍 RAG 기반 문서 질의응답",
    description="""
    업로드된 문서들을 대상으로 RAG 기반 질의응답을 수행합니다.
    
    RAG 파이프라인:
    • 쿼리 언어 감지 및 최적 모델 선택
    • 벡터 임베딩 생성 및 유사도 검색
    • 관련 문서 청크 추출 및 답변 생성
    
    검색 옵션:
    • top_k: 반환할 최대 청크 수 (1-20개, 기본값: 5)
    • similarity_threshold: 유사도 임계값 (기본값: 0.1)
    • document_filter: 특정 문서로 제한 (선택사항)
    
    지원 언어: 한국어, 영어, 일본어, 중국어 및 혼재 문서
    """,
    response_description="RAG 기반 답변과 관련 문서 청크들 반환")
async def rag_query(request: QueryRequest, 
                   similarity_threshold: float = Query(0.1, ge=0.0, le=1.0, description="유사도 임계값"),
                   document_filter: Optional[str] = Query(None, description="특정 문서 ID로 검색 제한")):
    """RAG 기반 실제 질의응답"""
    
    if not documents_db:
        return ErrorResponse(
            message="업로드된 문서가 없음",
            error_type="validation_error",
            data={"detail": "질의응답을 위한 문서가 없습니다"}
        )
    
    try:
        # RAG 서비스를 통한 검색 및 답변 생성
        result = await rag_service.rag_search_and_answer(
            query=request.query,
            top_k=request.top_k,
            document_filter=document_filter,
            similarity_threshold=similarity_threshold,
            context_only=False
        )
        
        if not result['success']:
            return ErrorResponse(
                message="RAG 검색 실패",
                error_type="search_error",
                data={"detail": result.get('error', 'Unknown error')}
            )
        
        return SuccessResponse(
            message="RAG 질의응답 성공",
            data={
                "answer": result['answer'],
                "sources": result['sources'],
                "metadata": result['metadata']
            }
        )
        
    except Exception as e:
        logger.error(f"RAG 질의응답 실패: {e}")
        error_id = error_logger.log_processing_error(
            file_path="query",
            parser_name="rag_service",
            error=e,
            file_size=None
        )
        
        return ErrorResponse(
            message="RAG 질의응답 처리 실패",
            error_id=error_id,
            error_type="rag_error",
            data={"detail": str(e)}
        )

@router.get("/system/health", tags=["시스템"])
async def get_system_status():
    """시스템 상태 및 에러 로그 요약"""
    try:
        health_data = get_system_health()
        memory_info = get_memory_usage()
        
        return SuccessResponse(
            message="시스템 상태 조회 성공",
            data={
                "system_health": health_data,
                "memory_usage": memory_info,
                "documents_count": len(documents_db),
                "total_chunks": sum(
                    doc.get("chunks_count", 0) if isinstance(doc, dict) else 0
                    for doc in documents_db.values()
                )
            }
        )
    except Exception as e:
        error_id = error_logger.log_api_error(
            endpoint="/system/health",
            method="GET",
            error=e
        )
        return ErrorResponse(
            message="시스템 상태 조회 실패",
            error_id=error_id,
            error_type="system_error",
            data={"detail": str(e)}
        )

@router.get("/system/errors", tags=["시스템"])
async def get_recent_errors(hours: int = Query(24, ge=1, le=168, description="조회할 시간 (1-168시간)")):
    """최근 에러 로그 조회"""
    try:
        from ..utils.log_monitor import log_monitor
        error_summary = log_monitor.get_error_summary(hours=hours)
        
        return SuccessResponse(
            message="에러 로그 조회 성공",
            data={
                "error_summary": error_summary,
                "query_hours": hours
            }
        )
    except Exception as e:
        error_id = error_logger.log_api_error(
            endpoint="/system/errors",
            method="GET",
            error=e,
            request_data={"hours": hours}
        )
        return ErrorResponse(
            message="에러 로그 조회 실패",
            error_id=error_id,
            error_type="system_error",
            data={"detail": str(e)}
        )

# Self-RAG 관련 모델들
class SelfRAGQueryRequest(BaseModel):
    """Self-RAG 질의응답 요청 모델"""

    query: str = Field(description="질문 내용", examples=["이 문서의 주요 내용은 무엇인가요?"], min_length=1)
    top_k: Optional[int] = Field(5, description="반환할 최대 청크 수", ge=1, le=20)
    reflection_mode: str = Field("adaptive", description="Reflection 모드", pattern="^(adaptive|always|never)$")
    reflection_weights: Optional[dict[str, float]] = Field(
        None,
        description="Reflection token 가중치",
        example={"relevance": 1.0, "support": 1.0, "usefulness": 0.5}
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "프로젝트의 주요 기능은 무엇인가요?",
                "top_k": 5,
                "reflection_mode": "adaptive",
                "reflection_weights": {
                    "relevance": 1.0,
                    "support": 1.0,
                    "usefulness": 0.5
                }
            }
        }

@router.post("/self-rag/query",
    summary="🔮 Self-RAG 기반 질의응답",
    description="""
    Self-Reflective Retrieval-Augmented Generation을 통한 고급 질의응답

    Self-RAG 특징:
    • On-demand retrieval: 필요할 때만 검색 수행
    • Reflection tokens: 자체 평가를 통한 품질 제어
    • Adaptive generation: 상황에 맞는 적응형 답변 생성

    Reflection Tokens:
    • Retrieve: 검색 필요성 (yes/no/continue)
    • IsRelevant: 문서 관련성 (relevant/irrelevant)
    • IsSupported: 답변 지원도 (fully/partially/no support)
    • IsUseful: 답변 유용성 (1-5 점수)

    Reflection 모드:
    • adaptive: 자동으로 최적 전략 선택
    • always: 항상 reflection 수행
    • never: reflection 없이 기본 RAG 사용
    """,
    response_description="Self-RAG 기반 답변과 reflection token 분석 결과 반환")
async def self_rag_query(request: SelfRAGQueryRequest,
                        similarity_threshold: float = Query(0.1, ge=0.0, le=1.0, description="유사도 임계값"),
                        document_filter: Optional[str] = Query(None, description="특정 문서 ID로 검색 제한")):
    """Self-RAG 기반 질의응답"""

    if not documents_db:
        return ErrorResponse(
            message="업로드된 문서가 없음",
            error_type="validation_error",
            data={"detail": "질의응답을 위한 문서가 없습니다"}
        )

    try:
        # Self-RAG 서비스 확인
        from app.services.self_rag import self_rag_service
        if not self_rag_service:
            return ErrorResponse(
                message="Self-RAG 서비스 초기화 오류",
                error_type="service_error",
                data={"detail": "Self-RAG 서비스가 초기화되지 않았습니다"}
            )

        # reflection weights 설정
        if request.reflection_weights:
            self_rag_service.update_reflection_weights(request.reflection_weights)

        # Self-RAG 검색 및 답변 생성
        result = await self_rag_service.self_rag_query(
            query=request.query,
            top_k=request.top_k,
            document_filter=document_filter,
            reflection_mode=request.reflection_mode
        )

        # 로깅
        error_logger.log_user_activity(
            activity_type="self_rag_query",
            file_path="self_rag_query",
            operation_details={
                "query": request.query,
                "mode": request.reflection_mode,
                "top_k": request.top_k,
                "candidates_count": len(result.get('candidates', [])),
                "retrieve_decision": result.get('retrieve_decision')
            }
        )

        return SuccessResponse(
            message="Self-RAG 질의응답 완료",
            data=result
        )

    except Exception as e:
        # 에러 처리
        error_id = error_logger.log_api_error(
            endpoint="/self-rag/query",
            method="POST",
            error=e,
            request_data={
                "query": request.query,
                "mode": request.reflection_mode,
                "top_k": request.top_k
            }
        )

        logging.error(f"Self-RAG 질의응답 실패: {str(e)}")
        return ErrorResponse(
            message="Self-RAG 질의응답 실패",
            error_id=error_id,
            error_type="processing_error",
            data={"detail": str(e)}
        )

@router.get("/self-rag/status",
    summary="📊 Self-RAG 서비스 상태",
    description="Self-RAG 서비스의 현재 상태와 설정 정보를 조회합니다")
async def get_self_rag_status():
    """Self-RAG 서비스 상태 조회"""
    try:
        from app.services.self_rag import self_rag_service

        if not self_rag_service:
            return ErrorResponse(
                message="Self-RAG 서비스가 초기화되지 않음",
                error_type="service_error"
            )

        status = self_rag_service.get_service_status()

        return SuccessResponse(
            message="Self-RAG 상태 조회 성공",
            data=status
        )

    except Exception as e:
        error_id = error_logger.log_api_error(
            endpoint="/self-rag/status",
            method="GET",
            error=e
        )

        return ErrorResponse(
            message="Self-RAG 상태 조회 실패",
            error_id=error_id,
            error_type="system_error",
            data={"detail": str(e)}
        )