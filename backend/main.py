from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

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
    
    # 백그라운드 워커 시작
    from app.services.background_worker import start_background_worker
    await start_background_worker()
    logging.info("✅ 백그라운드 워커 시작 완료")

@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 실행"""
    logging.info("⏹️ RAG System API 종료")
    
    # 백그라운드 워커 정지
    from app.services.background_worker import stop_background_worker
    stop_background_worker()
    logging.info("✅ 백그라운드 워커 정지 완료")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8099)