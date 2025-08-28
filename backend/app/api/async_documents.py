from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Form
from typing import Optional, List
import os
import uuid
from datetime import datetime

from ..services.task_manager import task_manager, TaskType, TaskStatus
from ..services.document_processor import DocumentProcessor
from ..utils.chunking import prepare_chunking_kwargs, format_chunking_summary, validate_chunking_options
from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlparse
import re
import logging

logger = logging.getLogger(__name__)

# === 응답 모델들 ===

class ErrorResponse(BaseModel):
    """에러 응답"""
    detail: str = Field(description="에러 메시지")

router = APIRouter(prefix="/async", tags=["비동기 문서 처리"])

# 기본 인스턴스들
processor = DocumentProcessor()

# === 요청/응답 모델들 ===

class TaskResponse(BaseModel):
    """작업 생성 응답"""
    success: bool = True
    task_id: str
    message: str
    estimated_time: Optional[str] = None

class TaskStatusResponse(BaseModel):
    """작업 상태 응답"""
    task_id: str
    task_type: str
    status: str
    progress: int
    message: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None

class UrlCrawlRequest(BaseModel):
    """웹 크롤링 요청"""
    url: str = Field(description="크롤링할 웹 페이지 URL")
    max_depth: Optional[int] = Field(0, description="크롤링 깊이", ge=0, le=3)
    same_domain: Optional[bool] = Field(True, description="동일 도메인만 크롤링 여부")
    chunk_size: Optional[int] = Field(1000, description="청크 최대 크기 (문자 단위)", ge=100, le=8000)
    chunk_overlap: Optional[int] = Field(None, description="청크 간 오버랩 크기 (기본값: chunk_size의 10%)")
    
    @field_validator('url')
    def validate_url(cls, v):
        if not v or not v.strip():
            raise ValueError("URL을 입력해주세요")
        
        v = v.strip()
        if not re.match(r'^https?://', v):
            v = f"https://{v}"
        
        try:
            parsed = urlparse(v)
            if not parsed.netloc:
                raise ValueError("올바른 URL 형식이 아닙니다")
        except:
            raise ValueError("올바른 URL 형식이 아닙니다")
            
        return v

# === API 엔드포인트들 ===

@router.post("/upload", 
    summary="📄 비동기 파일 업로드",
    description="""
    파일을 비동기로 업로드하고 파싱 작업을 시작합니다.
    
    비동기 처리:
    • 즉시 task_id 반환
    • WebSocket으로 실시간 진행상황 확인
    • /async/tasks/{task_id} API로 상태 조회
    
    지원 형식: PDF, DOCX, XLSX, PPTX, HTML, MD, TXT, CSV
    
    청킹 옵션:
    • chunk_size: 청크 최대 크기 (100-8000자, 기본값: 1000)
    • chunk_overlap: 청크 간 오버랩 크기 (기본값: chunk_size의 10%)
    """,
    response_model=TaskResponse,
    responses={
        400: {"model": ErrorResponse, "description": "잘못된 요청 (지원되지 않는 파일 형식 등)"},
        500: {"model": ErrorResponse, "description": "서버 내부 오류"}
    })
async def upload_document_async(
    file: UploadFile = File(..., description="업로드할 문서 파일"),
    chunk_size: Optional[int] = Form(1000, description="청크 최대 크기 (100-8000자)", ge=100, le=8000),
    chunk_overlap: Optional[int] = Form(None, description="청크 간 오버랩 크기 (기본값: chunk_size의 10%)", ge=0)
):
    """비동기 파일 업로드"""
    
    # 파일 확장자 검증
    if file.filename is None:
        raise HTTPException(status_code=400, detail="파일명이 없습니다")
        
    file_info = processor.get_file_info(file.filename)
    if not file_info["is_supported"]:
        raise HTTPException(
            status_code=400, 
            detail=f"지원되지 않는 파일 형식: {file_info['extension']}"
        )
    
    # 변수 초기화
    file_path: Optional[str] = None
    
    try:
        # 파일 저장
        document_id = str(uuid.uuid4())
        upload_dir = "./data"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, f"{document_id}_{file.filename}")
        
        # 파일 쓰기
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # 청킹 옵션 준비 및 검증
        try:
            chunking_kwargs = prepare_chunking_kwargs(chunk_size, chunk_overlap)
            chunking_summary = format_chunking_summary(chunk_size, chunk_overlap)
            logger.info(f"📄 비동기 파일 업로드 시작: {file.filename} ({chunking_summary})")
        except ValueError as e:
            # 저장된 파일 삭제
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=400, detail=f"청킹 옵션 오류: {str(e)}")
        
        # 비동기 작업 생성
        task_metadata = {
            "filename": file.filename,
            "file_path": file_path,
            "file_size": len(content),
            "file_type": file_info["extension"],
            **chunking_kwargs,  # 검증된 청킹 옵션
            "chunking_summary": chunking_summary
        }
        
        task_id = task_manager.create_task(
            task_type=TaskType.FILE_UPLOAD,
            metadata=task_metadata
        )
        
        # 예상 처리 시간 계산 (파일 크기 기반)
        file_size_mb = len(content) / (1024 * 1024)
        estimated_minutes = max(1, int(file_size_mb * 0.5))  # MB당 0.5분 추정
        
        return TaskResponse(
            task_id=task_id,
            message=f"파일 업로드가 완료되었습니다. 파싱 작업이 시작됩니다.",
            estimated_time=f"약 {estimated_minutes}분 소요 예상"
        )
        
    except Exception as e:
        # 저장된 파일 정리
        if file_path is not None and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        
        raise HTTPException(status_code=500, detail=f"파일 처리 실패: {str(e)}")

@router.post("/crawl",
    summary="🌐 비동기 웹 크롤링", 
    description="""
    웹 페이지를 비동기로 크롤링하고 파싱 작업을 시작합니다.
    
    비동기 처리:
    • 즉시 task_id 반환
    • WebSocket으로 실시간 진행상황 확인
    • /async/tasks/{task_id} API로 상태 조회
    
    크롤링 옵션:
    • max_depth: 크롤링 깊이 (0-3단계, 기본값: 0)
    • same_domain: 동일 도메인만 크롤링 (기본값: true)
    
    청킹 옵션:
    • chunk_size: 청크 최대 크기 (100-8000자, 기본값: 1000)
    • chunk_overlap: 청크 간 오버랩 크기 (기본값: chunk_size의 10%)
    """,
    response_model=TaskResponse,
    responses={
        400: {"model": ErrorResponse, "description": "잘못된 URL 또는 매개변수"},
        500: {"model": ErrorResponse, "description": "서버 내부 오류"}
    })
async def crawl_url_async(request: UrlCrawlRequest):
    """비동기 웹 크롤링"""
    
    try:
        # 청킹 옵션 준비 및 검증
        try:
            chunking_kwargs = prepare_chunking_kwargs(request.chunk_size, request.chunk_overlap)
            chunking_summary = format_chunking_summary(request.chunk_size, request.chunk_overlap)
            logger.info(f"🌐 비동기 웹 크롤링 시작: {request.url} ({chunking_summary})")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"청킹 옵션 오류: {str(e)}")
        
        # 비동기 작업 생성
        task_metadata = {
            "url": request.url,
            "max_depth": request.max_depth,
            "same_domain": request.same_domain,
            **chunking_kwargs,  # 검증된 청킹 옵션
            "chunking_summary": chunking_summary
        }
        
        task_id = task_manager.create_task(
            task_type=TaskType.WEB_CRAWL,
            metadata=task_metadata
        )
        
        # 예상 처리 시간 계산 (깊이 기반)
        depth = request.max_depth if request.max_depth is not None else 0
        estimated_minutes = max(1, (depth + 1) * 2)  # 깊이당 2분 추정
        
        return TaskResponse(
            task_id=task_id,
            message=f"웹 크롤링 작업이 시작됩니다: {request.url}",
            estimated_time=f"약 {estimated_minutes}분 소요 예상"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"크롤링 작업 생성 실패: {str(e)}")

@router.get("/tasks/{task_id}",
    summary="📊 작업 상태 조회",
    description="""
    작업의 현재 상태를 조회합니다.
    
    **상태 종류**:
    - `pending`: 대기 중
    - `processing`: 처리 중  
    - `completed`: 완료
    - `failed`: 실패
    - `cancelled`: 취소됨
    """,
    response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """작업 상태 조회"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    return TaskStatusResponse(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status,
        progress=task.progress,
        message=task.message,
        created_at=task.created_at.isoformat(),
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        result=task.result,
        error=task.error
    )

@router.get("/tasks",
    summary="📋 작업 목록 조회",
    description="사용자의 모든 작업 목록을 조회합니다.",
    response_model=List[TaskStatusResponse])
async def get_tasks(
    limit: int = Query(50, description="조회할 작업 수", ge=1, le=100),
    status: Optional[TaskStatus] = Query(None, description="상태별 필터링")
):
    """작업 목록 조회"""
    tasks = task_manager.get_user_tasks(limit=limit)
    
    # 상태별 필터링
    if status:
        tasks = [task for task in tasks if task.status == status]
    
    return [
        TaskStatusResponse(
            task_id=task.task_id,
            task_type=task.task_type,
            status=task.status,
            progress=task.progress,
            message=task.message,
            created_at=task.created_at.isoformat(),
            started_at=task.started_at.isoformat() if task.started_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            result=task.result,
            error=task.error
        )
        for task in tasks
    ]

@router.delete("/tasks/{task_id}",
    summary="❌ 작업 취소",
    description="실행 중이거나 대기 중인 작업을 취소합니다.")
async def cancel_task(task_id: str):
    """작업 취소"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    if task.status not in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
        raise HTTPException(
            status_code=400, 
            detail=f"취소할 수 없는 작업 상태입니다: {task.status}"
        )
    
    success = task_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=500, detail="작업 취소에 실패했습니다")
    
    return {"success": True, "message": "작업이 취소되었습니다"}

@router.get("/tasks/{task_id}/result",
    summary="📄 작업 결과 조회", 
    description="완료된 작업의 상세 결과를 조회합니다.")
async def get_task_result(task_id: str):
    """작업 결과 상세 조회"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"완료되지 않은 작업입니다: {task.status}"
        )
    
    # 상세 결과 반환 (파싱된 청크 정보 등)
    parsed_doc = task.metadata.get("parsed_doc") if task.metadata else None
    
    return {
        "task_id": task_id,
        "result": task.result,
        "chunks": parsed_doc.get("chunks", []) if parsed_doc else [],
        "metadata": parsed_doc.get("metadata", {}) if parsed_doc else {},
        "completed_at": task.completed_at.isoformat() if task.completed_at else None
    }