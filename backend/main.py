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

app = FastAPI(
    title="RAG System API",
    description="""
    ## 📚 Retrieval-Augmented Generation System
    
    문서 업로드, 파싱, 벡터 검색을 통한 질의응답 시스템
    
    ### 주요 기능:
    - 📄 다양한 형식 문서 업로드 (PDF, DOCX, Excel, PPT 등)
    - 🌐 웹 크롤링 및 콘텐츠 파싱  
    - 🔍 의미 기반 문서 검색
    - 💬 질의응답 시스템
    
    ### 지원 파일 형식:
    - PDF, DOCX, XLSX, PPTX
    - HTML, Markdown, TXT, CSV
    """,
    version="1.0.0",
    contact={
        "name": "API Support",
        "email": "support@example.com"
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
        "description": "📚 문서 관리 - 업로드, 파싱, 크롤링, 질의응답"
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

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8099)