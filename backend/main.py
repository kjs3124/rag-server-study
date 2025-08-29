from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
import asyncio
from typing import Dict, Any
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

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # Startup
    logging.info("🚀 RAG System API 시작")
    
    # 데이터 영속성 확인
    from app.api.documents import documents_db
    from app.services.task_manager import task_manager
    
    logging.info(f"📚 저장된 데이터 로드 완료:")
    logging.info(f"  - 문서: {len(documents_db)}개")
    logging.info(f"  - 작업: {len(task_manager.tasks)}개")
    
    # RAG 서비스 초기화
    from app.services.rag_service import rag_service
    rag_initialized = await rag_service.initialize()
    if rag_initialized:
        logging.info("✅ RAG 서비스 초기화 완료")
    else:
        logging.warning("⚠️ RAG 서비스 초기화 실패 - 벡터 검색 비활성화")
    
    # 백그라운드 워커 시작
    from app.services.background_worker import start_background_worker
    await start_background_worker()
    logging.info("✅ 백그라운드 워커 시작 완료")
    
    # 기존 문서들의 임베딩 처리 확인 및 재처리
    #await check_and_reprocess_embeddings()
    
    yield  # 여기서 애플리케이션 실행
    
    # Shutdown
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

app = FastAPI(
    title="RAG System API",
    lifespan=lifespan,  # lifespan 이벤트 핸들러 등록
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
    # RAG 서비스 상태 확인
    try:
        from app.services.rag_service import rag_service
        rag_status = rag_service.get_service_status()
        vector_ready = rag_status.get('dependencies', {}).get('vector_store_ready', False)
        models_loaded = rag_status.get('embedding_service', {}).get('loaded_models', [])
    except:
        vector_ready = False
        models_loaded = []
    
    return {
        "status": "healthy",
        "database": True,
        "vector_store": vector_ready,
        "models_loaded": models_loaded or ["parser_only"]
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

# 임베딩 재처리 함수
async def check_and_reprocess_embeddings():
    """기존 문서들의 임베딩 처리 확인 및 재처리"""
    try:
        from app.api.documents import documents_db, embed_document_chunks
        from app.services.vector_store import vector_store
        from app.services.parsers.base import DocumentChunk
        
        reprocessed_count = 0
        
        for doc_id, doc_data in documents_db.items():
            # Qdrant에서 해당 문서의 벡터가 있는지 확인
            try:
                # 벡터 존재 여부 확인
                document_has_vectors = await vector_store.document_exists(doc_id)
                
                # 벡터가 없는 경우 재처리
                if not document_has_vectors:
                    logging.info(f"📄 임베딩 재처리 시작: {doc_data.get('filename', 'Unknown')}")
                    
                    # ParsedDocument에서 chunks 추출
                    parsed_doc = doc_data.get("parsed_doc")
                    if parsed_doc and hasattr(parsed_doc, 'chunks'):
                        chunks = parsed_doc.chunks
                    elif isinstance(parsed_doc, dict) and 'chunks' in parsed_doc:
                        # dict 형태로 저장된 경우 DocumentChunk 객체로 복원
                        chunks = []
                        for i, chunk_data in enumerate(parsed_doc['chunks']):
                            chunk = DocumentChunk(
                                content=chunk_data['content'],
                                metadata=chunk_data['metadata'],
                                chunk_id=chunk_data.get('chunk_id', f"{doc_id}_{i:04d}"),
                                page_number=chunk_data.get('page_number'),
                                section_title=chunk_data.get('section_title')
                            )
                            chunks.append(chunk)
                    else:
                        logging.warning(f"⚠️ 문서 {doc_id}의 청크 정보를 찾을 수 없어 스킵합니다")
                        continue
                    
                    # 임베딩 처리
                    embeddings, embedding_metadata = await embed_document_chunks(chunks)
                    
                    # 문서 메타데이터 준비
                    doc_metadata = {
                        'filename': doc_data.get('filename', 'Unknown'),
                        'file_type': doc_data.get('file_type', 'unknown'),
                        'parser_used': 'reprocessed',
                        'language_info': embedding_metadata.get('language_analysis', {})
                    }
                    
                    # 벡터 스토어에 저장
                    vector_stored = await vector_store.store_document_vectors(
                        document_id=doc_id,
                        embeddings=embeddings,
                        chunks=chunks,
                        metadata=doc_metadata
                    )
                    
                    if vector_stored:
                        reprocessed_count += 1
                        logging.info(f"✅ 임베딩 재처리 완료: {doc_data.get('filename', 'Unknown')}")
                    else:
                        logging.error(f"❌ 임베딩 재처리 실패: {doc_data.get('filename', 'Unknown')}")
                        
            except Exception as e:
                logging.warning(f"⚠️ 문서 {doc_id} 임베딩 확인/처리 중 오류: {str(e)}")
                continue
        
        if reprocessed_count > 0:
            logging.info(f"✅ 임베딩 재처리 완료: {reprocessed_count}개 문서")
        else:
            logging.info("✅ 모든 문서의 임베딩이 이미 처리되어 있습니다")
            
    except Exception as e:
        logging.error(f"❌ 임베딩 재처리 중 오류: {str(e)}")

# Old on_event handlers removed - using lifespan context manager instead

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