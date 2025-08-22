from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import List, Optional
import os
import uuid
from datetime import datetime

from ..services.document_processor import DocumentProcessor
from ..services.parsers.base import ParsedDocument
from typing import cast

from pydantic import BaseModel, validator
from urllib.parse import urlparse
import re

router = APIRouter()
processor = DocumentProcessor()

# 메모리에 문서 정보 저장 (테스트용)
documents_db = {}

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
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
        
        # 파서로 문서 처리
        parsed_doc = processor.process_file(file_path)
        
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
        
        return {
            "success": True,
            "document_id": document_id,
            "chunks_created": len(parsed_doc.chunks),
            "model_used": "parser_test",  # 파서 테스트용
            "file_type": parsed_doc.file_type,
            "parser_used": parsed_doc.metadata.get("parser", "unknown")
        }
        
    except Exception as e:
        # 실패시 파일 삭제
        if os.path.exists(file_path):
            os.remove(file_path)
        
        raise HTTPException(status_code=500, detail=f"파일 처리 실패: {str(e)}")

class UrlCrawlRequest(BaseModel):
    url: str
    max_depth: Optional[int] = 1
    same_domain: Optional[bool] = True
    
    @validator('url')
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

@router.post("/url")
async def crawl_url(request: UrlCrawlRequest):
    """URL 크롤링 및 파싱 테스트"""
    
    try:
        # URL 크롤링 (실패하면 여기서 예외 발생)
        parsed_doc = processor.process_url(
            request.url, 
            max_depth=request.max_depth or 1, 
            same_domain=request.same_domain or True
        )
        
        # 크롤링 성공한 경우만 문서 추가
        if not parsed_doc.chunks:
            raise HTTPException(status_code=400, detail="크롤링된 내용이 없습니다")
            
    except HTTPException:
        # HTTPException은 그대로 다시 발생
        raise
    except Exception as e:
        # 다른 예외는 500 에러로 변환
        raise HTTPException(status_code=500, detail=f"URL 크롤링 실패: {str(e)}")
    
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
    
    return {
        "success": True,
        "document_id": document_id,
        "chunks_created": len(parsed_doc.chunks),
        "model_used": "web_crawler",
        "file_type": "web",
        "crawled_urls": parsed_doc.metadata.get("crawled_urls", 1)
    }

@router.get("")
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

@router.get("/{document_id}")
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

@router.delete("/{document_id}")
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
    query: str
    top_k: Optional[int] = 5

@router.post("/query")
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