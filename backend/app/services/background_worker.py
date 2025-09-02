import asyncio
import os
import traceback
from typing import Dict, Any
from datetime import datetime

from .task_manager import task_manager, TaskType, TaskStatus
from .document_processor import DocumentProcessor
from ..api.websocket import task_notifier
from ..utils.chunking import prepare_chunking_kwargs, format_chunking_summary
from ..utils.memory import auto_cleanup
import logging

logger = logging.getLogger(__name__)

class BackgroundWorker:
    """백그라운드 작업 처리기"""
    
    def __init__(self):
        self.processor = DocumentProcessor()
        self.running = False
        
    async def start(self):
        """워커 시작"""
        self.running = True
        logger.info("🚀 백그라운드 워커 시작")
        
        try:
            while self.running:
                try:
                    # 대기 중인 작업 가져오기
                    task_id = task_manager.get_pending_task()
                    if task_id:
                        await self.process_task(task_id)
                    else:
                        # 작업이 없으면 잠시 대기 (더 짧은 간격으로 중단 신호 감지)
                        for _ in range(10):  # 1초를 0.1초씩 분할
                            if not self.running:
                                break
                            await asyncio.sleep(0.1)
                        # 30분마다 자동 메모리 정리
                        auto_cleanup()
                        
                except asyncio.CancelledError:
                    logger.info("📤 백그라운드 워커 취소됨")
                    break
                except KeyboardInterrupt:
                    logger.info("📤 백그라운드 워커 키보드 인터럽트")
                    break
                except Exception as e:
                    if self.running:
                        logger.error(f"워커 에러: {e}")
                        await asyncio.sleep(5)
                    
        except (asyncio.CancelledError, KeyboardInterrupt):
            logger.info("📤 백그라운드 워커 취소됨")
        finally:
            self.running = False
            logger.info("🏁 백그라운드 워커 종료")
                
    def stop(self):
        """워커 정지"""
        self.running = False
        logger.info("⏹️ 백그라운드 워커 정지")
        
    async def process_task(self, task_id: str):
        """작업 처리"""
        try:
            task = task_manager.get_task(task_id)
            if not task:
                logger.warning(f"작업을 찾을 수 없음: {task_id}")
                return
                
            if task.metadata is None:
                raise ValueError(f"작업에 메타데이터가 없습니다: {task_id}")
                
            # 청킹 파라미터 정보 추출 (유틸리티 사용)
            chunk_size = task.metadata.get("chunk_size", 1000)
            chunk_overlap = task.metadata.get("chunk_overlap")
            
            # 기존 chunking_summary가 있으면 사용, 없으면 생성
            chunk_info = task.metadata.get("chunking_summary")
            if not chunk_info:
                chunk_info = format_chunking_summary(chunk_size, chunk_overlap)
            
            logger.info(f"📋 작업 처리 시작: {task_id} ({task.task_type}) - {chunk_info}")
            
            # 작업 시작 알림
            await task_notifier.notify_started(task_id)
            
            # 작업 타입별 처리
            if task.task_type == TaskType.FILE_UPLOAD:
                await self._process_file_upload(task_id, task.metadata)
            elif task.task_type == TaskType.WEB_CRAWL:
                await self._process_web_crawl(task_id, task.metadata)
            elif task.task_type == TaskType.DOCUMENT_PARSE:
                await self._process_document_parse(task_id, task.metadata)
            else:
                raise ValueError(f"지원하지 않는 작업 타입: {task.task_type}")
                
        except Exception as e:
            error_msg = f"작업 처리 실패: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.error(traceback.format_exc())
            await task_notifier.notify_failed(task_id, error_msg)
            
    async def _process_file_upload(self, task_id: str, metadata: Dict[str, Any]):
        """파일 업로드 처리"""
        file_path = metadata.get("file_path")
        filename = metadata.get("filename")
        chunk_size = metadata.get("chunk_size", 1000)
        chunk_overlap = metadata.get("chunk_overlap")
        
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
            
        # 진행상황 업데이트: 파싱 시작
        await task_notifier.notify_progress(task_id, 20, "파일 파싱을 시작합니다")
        
        # 청킹 옵션 준비 (유틸리티 사용)
        try:
            chunking_kwargs = prepare_chunking_kwargs(chunk_size, chunk_overlap)
        except ValueError as e:
            error_msg = f"청킹 옵션 오류: {str(e)}"
            logger.error(f"❌ {error_msg}")
            await task_notifier.notify_failed(task_id, error_msg)
            return
        
        # 문서 처리 (동기 함수를 비동기로 실행)
        loop = asyncio.get_event_loop()
        try:
            parsed_doc = await loop.run_in_executor(
                None, 
                lambda: self.processor.process_file(file_path, **chunking_kwargs)
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("📤 파일 처리 중단됨")
            await task_notifier.notify_failed(task_id, "사용자에 의해 중단됨")
            raise
        
        # 진행상황 업데이트: 파싱 완료, 임베딩 시작
        await task_notifier.notify_progress(task_id, 50, "파싱 완료, 임베딩을 시작합니다")
        
        # 임베딩 처리
        from ..api.documents import embed_document_chunks, vector_store
        try:
            embeddings, embedding_metadata = await embed_document_chunks(parsed_doc.chunks)
            
            # 문서 메타데이터 준비
            doc_metadata = {
                'filename': filename,
                'file_type': parsed_doc.file_type or "unknown",
                'parser_used': parsed_doc.metadata.get("parser", "unknown"),
                'language_info': embedding_metadata['language_analysis']
            }
            
            # 벡터 스토어에 저장
            await task_notifier.notify_progress(task_id, 70, "벡터 데이터베이스에 저장 중")
            await vector_store.store_document_vectors(
                document_id=task_id,
                embeddings=embeddings,
                chunks=parsed_doc.chunks,
                metadata=doc_metadata
            )
            
            await task_notifier.notify_progress(task_id, 85, "임베딩 및 벡터 저장 완료")
            
        except Exception as e:
            logger.error(f"❌ 임베딩 처리 실패 ({task_id}): {str(e)}")
            # 임베딩 실패해도 문서는 저장하되 경고 표시
            await task_notifier.notify_progress(task_id, 80, f"임베딩 실패하였으나 문서 저장은 완료: {str(e)}")
        
        # 결과 준비 (프론트엔드 UploadResponse 구조에 맞춤)
        result = {
            "success": True,
            "message": "업로드 완료",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "document_id": task_id,
                "chunks_created": len(parsed_doc.chunks),
                "model_used": parsed_doc.metadata.get("parser", "unknown"),
                "file_type": parsed_doc.file_type or "unknown",
                "parser_used": parsed_doc.metadata.get("parser", "unknown")
            }
        }
        
        # documents_db에 저장 (동기 API와 동일하게)
        from ..api.documents import documents_db, auto_save_documents
        with auto_save_documents(documents_db):
            documents_db[task_id] = {
                "id": task_id,
                "filename": filename,
                "file_size": metadata.get("file_size", 0),
                "chunks_count": len(parsed_doc.chunks),
                "upload_time": datetime.now().isoformat(),
                "status": "completed",
                "file_path": file_path,
                "parsed_doc": parsed_doc
            }
        
        # 처리된 문서 정보를 메타데이터에 저장
        task_manager.update_task(task_id, metadata={
            **metadata,
            "parsed_doc": {
                "chunks": [{"content": chunk.content, "metadata": chunk.metadata} for chunk in parsed_doc.chunks],
                "file_type": parsed_doc.file_type,
                "metadata": parsed_doc.metadata
            }
        })
        
        # 완료 알림
        await task_notifier.notify_completed(task_id, result)
        
    async def _process_web_crawl(self, task_id: str, metadata: Dict[str, Any]):
        """웹 크롤링 처리"""
        url = metadata.get("url")
        max_depth = metadata.get("max_depth", 0)
        same_domain = metadata.get("same_domain", True)
        
        if not url:
            raise ValueError("URL이 제공되지 않았습니다")
            
        # 진행상황 업데이트: 크롤링 시작
        await task_notifier.notify_progress(task_id, 10, f"웹 페이지 크롤링을 시작합니다: {url}")
        
        # 웹 크롤러 파서 사용
        from ..services.parsers.web_crawler import WebCrawlerParser
        crawler = WebCrawlerParser(delay=1.0)
        
        # 백그라운드 워커가 중단되면 크롤러도 취소
        if not self.running:
            crawler.cancel()
        
        # 크롤링 실행 (동기 함수를 비동기로 실행)
        loop = asyncio.get_event_loop()
        
        # 진행상황 업데이트
        await task_notifier.notify_progress(task_id, 30, "페이지 내용을 분석 중입니다")
        
        # 청킹 파라미터 처리 (유틸리티 사용)
        chunk_size = metadata.get("chunk_size", 1000)
        chunk_overlap = metadata.get("chunk_overlap")
        
        # 청킹 옵션 검증
        try:
            # 검증만 수행 (실제 값은 개별 파라미터로 전달)
            prepare_chunking_kwargs(chunk_size, chunk_overlap)
        except ValueError as e:
            error_msg = f"청킹 옵션 오류: {str(e)}"
            logger.error(f"❌ {error_msg}")
            await task_notifier.notify_failed(task_id, error_msg)
            return
        
        try:
            def crawl_with_cancel_check():
                # 크롤링 시작 전 취소 체크
                if not self.running:
                    crawler.cancel()
                    raise asyncio.CancelledError("백그라운드 워커 중단")
                return crawler.parse(url, chunk_size, chunk_overlap, max_depth, same_domain)
                
            parsed_doc = await loop.run_in_executor(None, crawl_with_cancel_check)
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("📤 웹 크롤링 중단됨")
            crawler.cancel()  # 크롤러 명시적 취소
            await task_notifier.notify_failed(task_id, "사용자에 의해 중단됨")
            raise
        
        # 진행상황 업데이트: 크롤링 완료, 임베딩 시작  
        await task_notifier.notify_progress(task_id, 50, "크롤링 완료, 임베딩을 시작합니다")
        
        # 임베딩 처리
        from ..api.documents import embed_document_chunks, vector_store
        try:
            embeddings, embedding_metadata = await embed_document_chunks(parsed_doc.chunks)
            
            # 문서 메타데이터 준비
            doc_metadata = {
                'filename': f"crawled_{url}",
                'file_type': "html", 
                'parser_used': "web_crawler",
                'language_info': embedding_metadata['language_analysis'],
                'source_url': url,
                'max_depth': max_depth,
                'same_domain': same_domain
            }
            
            # 벡터 스토어에 저장
            await task_notifier.notify_progress(task_id, 70, "벡터 데이터베이스에 저장 중")
            await vector_store.store_document_vectors(
                document_id=task_id,
                embeddings=embeddings,
                chunks=parsed_doc.chunks,
                metadata=doc_metadata
            )
            
            await task_notifier.notify_progress(task_id, 85, "임베딩 및 벡터 저장 완료")
            
        except Exception as e:
            logger.error(f"❌ 임베딩 처리 실패 ({task_id}): {str(e)}")
            # 임베딩 실패해도 문서는 저장하되 경고 표시
            await task_notifier.notify_progress(task_id, 80, f"임베딩 실패하였으나 문서 저장은 완료: {str(e)}")
        
        # 결과 준비 (프론트엔드 UploadResponse 구조에 맞춤)
        result = {
            "success": True,
            "message": "업로드 완료",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "document_id": task_id,
                "chunks_created": len(parsed_doc.chunks),
                "model_used": parsed_doc.metadata.get("parser", "unknown"),
                "file_type": parsed_doc.file_type or "unknown",
                "parser_used": parsed_doc.metadata.get("parser", "unknown")
            }
        }
        
        # documents_db에 저장 (동기 API와 동일하게)
        from ..api.documents import documents_db, auto_save_documents
        with auto_save_documents(documents_db):
            documents_db[task_id] = {
                "id": task_id,
                "filename": f"crawled_{url.replace('://', '_').replace('/', '_')[:50]}",
                "file_size": sum(len(chunk.content) for chunk in parsed_doc.chunks),
                "chunks_count": len(parsed_doc.chunks),
                "upload_time": datetime.now().isoformat(),
                "status": "completed",
                "file_path": url,
                "parsed_doc": parsed_doc
            }
        
        # 처리된 문서 정보를 메타데이터에 저장
        task_manager.update_task(task_id, metadata={
            **metadata,
            "parsed_doc": {
                "chunks": [{"content": chunk.content, "metadata": chunk.metadata} for chunk in parsed_doc.chunks],
                "file_type": parsed_doc.file_type,
                "metadata": parsed_doc.metadata
            }
        })
        
        # 완료 알림
        await task_notifier.notify_completed(task_id, result)
        
    async def _process_document_parse(self, task_id: str, metadata: Dict[str, Any]):
        """문서 파싱 처리"""
        # 추후 구현 (기존 파일이나 URL 재처리 등)
        pass

# 글로벌 워커 인스턴스
background_worker = BackgroundWorker()
worker_task = None

async def start_background_worker():
    """백그라운드 워커 시작 (애플리케이션 시작 시 호출)"""
    global worker_task
    worker_task = asyncio.create_task(background_worker.start())

def stop_background_worker():
    """백그라운드 워커 정지 (애플리케이션 종료 시 호출)"""
    global worker_task
    background_worker.stop()
    
    # 태스크 명시적 취소
    if worker_task and not worker_task.done():
        worker_task.cancel()
        logger.info("✅ 백그라운드 워커 태스크 취소됨")