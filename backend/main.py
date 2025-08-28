from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import asyncio
import signal
import sys

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Import routers
from app.api.documents import router as documents_router
from app.api.async_documents import router as async_documents_router
from app.api.websocket import router as websocket_router

app = FastAPI(
    title="RAG System API",
    description="""
    📚 Retrieval-Augmented Generation System
    
    문서 업로드, 파싱, 벡터 검색을 통한 질의응답 시스템
    
    주요 기능:
    • 다양한 형식 문서 업로드 (PDF, DOCX, Excel, PPT 등)
    • 웹 크롤링 및 콘텐츠 파싱
    • 청킹 파라미터 사용자 정의
    • 동기/비동기 처리 지원
    • 실시간 작업 상태 추적
    
    지원 파일 형식:
    PDF, DOCX, XLSX, PPTX, HTML, Markdown, TXT, CSV
    """,
    version="1.0.0",
    contact={
        "name": "API Support",
        "email": "js_kim@dfocus.net"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Tags metadata for OpenAPI documentation
tags_metadata = [
    {
        "name": "Root",
        "description": "시스템 기본 정보 및 헬스 체크"
    },
    {
        "name": "documents", 
        "description": "📚 동기 문서 관리 - 업로드, 파싱, 크롤링 (기존 방식)"
    },
    {
        "name": "비동기 문서 처리",
        "description": "⚡ 비동기 문서 처리 - 백그라운드 작업, 실시간 상태 업데이트"
    },
    {
        "name": "WebSocket",
        "description": "🔄 실시간 통신 - 작업 상태 실시간 업데이트"
    }
]

# Add tags metadata to FastAPI app
app.openapi_tags = tags_metadata


@app.get("/health", tags=["Root"])
async def health_check():
    return {
        "status": "healthy",
        "database": True,
        "vector_store": True,
        "models_loaded": ["parser_test"]
    }

@app.get("/api/v1/health", tags=["Root"])
async def api_health_check():
    return {
        "status": "healthy",
        "database": True,
        "vector_store": True,
        "models_loaded": ["parser_test"]
    }

# Router registration
app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(async_documents_router, prefix="/api/v1/documents", tags=["비동기 문서 처리"])
app.include_router(websocket_router, prefix="/api/v1", tags=["WebSocket"])

# Application startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행"""
    logging.info("🚀 RAG System API 시작")
    
    # 데이터 영속성 확인
    from app.api.documents import documents_db
    from app.services.task_manager import task_manager
    
    logging.info(f"📚 저장된 데이터 로드 완료:")
    logging.info(f"  - 문서: {len(documents_db)}개")
    logging.info(f"  - 작업: {len(task_manager.tasks)}개")
    
    # 백그라운드 워커 시작
    from app.services.background_worker import start_background_worker
    await start_background_worker()
    logging.info("✅ 백그라운드 워커 시작 완료")

@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 실행"""
    logging.info("⏹️ RAG System API 종료")
    
    # 백그라운드 워커 정지
    from app.services.background_worker import stop_background_worker, worker_task
    stop_background_worker()
    
    # 워커 태스크가 완전히 종료될 때까지 대기
    if worker_task and not worker_task.done():
        try:
            await asyncio.wait_for(worker_task, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
    
    logging.info("✅ 백그라운드 워커 정지 완료")
    
    # 데이터 최종 저장 확인
    from app.api.documents import documents_db
    from app.services.task_manager import task_manager
    from app.services.persistence import save_documents, save_tasks
    
    try:
        save_documents(documents_db)
        save_tasks(task_manager.tasks)
        logging.info("💾 데이터 최종 저장 완료:")
        logging.info(f"  - 문서: {len(documents_db)}개")
        logging.info(f"  - 작업: {len(task_manager.tasks)}개")
    except Exception as e:
        logging.error(f"⚠️ 데이터 저장 오류: {str(e)}")
    
    # 오래된 작업 정리 (선택적)
    cleaned = task_manager.cleanup_old_tasks(hours=72)  # 3일 이상 오래된 작업
    if cleaned > 0:
        logging.info(f"🗑️ 오래된 작업 {cleaned}개 정리")
    
    logging.info("🏁 애플리케이션 종료 완료")

if __name__ == "__main__":
    def signal_handler(sig, frame):
        logging.info("🛑 강제 종료 신호 수신")
        sys.exit(0)
    
    # Signal handler 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        uvicorn.run(app, host="127.0.0.1", port=8099)
    except KeyboardInterrupt:
        logging.info("🛑 KeyboardInterrupt 수신, 종료")
        sys.exit(0)