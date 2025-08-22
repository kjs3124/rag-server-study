# RAG 시스템 구현 계획서

## 🎯 구현 상태 현황

### ✅ 완료된 작업

1. **프로젝트 구조 설정**
   - 디렉토리 구조 생성
   - Docker 환경 구성 (docker-compose.yml)
   - 의존성 정의 (requirements.txt)
   - 환경 설정 (.env.example)

2. **문서 파서 시스템**
   - 팩토리 패턴 기반 파서 아키텍처
   - 10개 파일 형식 지원 (PDF, DOCX, TXT, HTML, MD, CSV, PPTX, XLSX)
   - 웹 크롤링 지원 (정적/동적)
   - 통합 문서 처리 파이프라인
   - Fallback 전략 구현

### ⏳ 진행 중인 작업

- Unstructured 라이브러리 호환성 수정 (완료)

## 📋 다음 구현 단계

### Phase 1: 임베딩 및 벡터 DB (1-2주)

#### 1.1 언어별 임베딩 서비스 구현

```python
# 구현할 파일들
app/services/embedding.py          # 메인 임베딩 서비스
app/services/language_detector.py  # 언어 감지
app/core/model_manager.py          # 모델 로드/캐시 관리
```

**상세 작업**:

- [ ] 언어 감지 서비스 (`langdetect` 기반)
- [ ] BGE-M3 임베딩 클래스
- [ ] Multilingual-E5-Large 임베딩 클래스  
- [ ] 동적 모델 선택 로직
- [ ] 임베딩 캐시 시스템 (Redis)
- [ ] 배치 처리 최적화

#### 1.2 벡터 데이터베이스 연동

```python
# 구현할 파일들  
app/db/qdrant.py              # Qdrant 클라이언트
app/db/postgres_vector.py     # PostgreSQL+pgvector
app/services/vector_store.py  # 벡터 스토어 추상화
```

**상세 작업**:

- [ ] Qdrant 연결 및 컬렉션 관리
- [ ] PostgreSQL+pgvector 스키마 설계
- [ ] 벡터 CRUD 연산
- [ ] 메타데이터 필터링
- [ ] 인덱스 최적화

### Phase 2: 검색 및 API (1-2주)

#### 2.1 검색 서비스 구현

```python
# 구현할 파일들
app/services/retrieval.py     # 벡터 검색
app/services/reranking.py     # BGE-Reranker 통합
app/services/rag_pipeline.py  # 전체 RAG 파이프라인
```

**상세 작업**:

- [ ] 하이브리드 검색 (벡터 + 키워드)
- [ ] BGE-Reranker 통합
- [ ] 검색 결과 후처리
- [ ] 성능 최적화 (배치, 캐싱)

#### 2.2 FastAPI 라우터 구현

```python  
# 구현할 파일들
app/api/documents.py          # 문서 업로드/관리  
app/api/query.py             # 질의응답
app/api/admin.py             # 관리 기능
app/models/schemas.py        # Pydantic 모델들
```

**상세 작업**:

- [ ] 문서 업로드 엔드포인트
- [ ] URL 크롤링 엔드포인트  
- [ ] 질의응답 엔드포인트
- [ ] 문서 관리 CRUD
- [ ] API 문서화 (OpenAPI)

### Phase 3: LLM 통합 및 고도화 (1주)

#### 3.1 LLM 서비스 통합

```python
# 구현할 파일들
app/services/llm.py           # LLM 통합 (OpenAI, Anthropic)
app/services/prompt_manager.py # 프롬프트 관리
app/services/response_formatter.py # 응답 포맷팅
```

**상세 작업**:

- [ ] OpenAI GPT-4 통합
- [ ] Anthropic Claude 통합  
- [ ] 프롬프트 템플릿 시스템
- [ ] 스트리밍 응답 지원
- [ ] 토큰 사용량 추적

#### 3.2 성능 최적화 및 모니터링

```python
# 구현할 파일들  
app/core/monitoring.py        # 메트릭 수집
app/core/caching.py          # 캐싱 전략
app/core/rate_limiter.py     # 요청 제한
```

**상세 작업**:

- [ ] 응답 시간 최적화
- [ ] 메모리 사용량 최적화
- [ ] 로깅 시스템 구축
- [ ] 에러 핸들링 개선

### Phase 4: 보안 및 배포 (1주)

#### 4.1 보안 시스템

```python
# 구현할 파일들
app/core/security.py         # JWT, API Key 인증
app/core/validation.py       # 입력 검증  
app/core/sanitization.py     # 데이터 정화
```

**상세 작업**:

- [ ] JWT 토큰 인증
- [ ] API Key 관리
- [ ] Rate Limiting
- [ ] 파일 업로드 보안 검증
- [ ] CORS 설정

#### 4.2 배포 환경 구성

```yaml
# 구현할 파일들
docker-compose.prod.yml       # 프로덕션 설정
k8s/                         # Kubernetes 매니페스트  
nginx/                       # nginx 설정
monitoring/                  # Prometheus/Grafana 설정
```

**상세 작업**:

- [ ] 프로덕션 Docker 설정
- [ ] Nginx 리버스 프록시
- [ ] SSL/TLS 인증서 설정  
- [ ] CI/CD 파이프라인 (GitHub Actions)
- [ ] 모니터링 대시보드 구축

## 🔧 구체적인 구현 가이드

### 1. 언어별 임베딩 서비스 구현 예시

```python
# app/services/embedding.py
from typing import List, Dict, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
import langdetect
import redis

class AdaptiveEmbeddingService:
    def __init__(self):
        self.models = {}  # 지연 로딩
        self.cache = redis.Redis(host='localhost', port=6379)
        
    def get_model(self, model_name: str) -> SentenceTransformer:
        """모델 지연 로딩"""
        if model_name not in self.models:
            if model_name == 'bge-m3':
                self.models[model_name] = SentenceTransformer('BAAI/bge-m3')
            elif model_name == 'e5-large':  
                self.models[model_name] = SentenceTransformer('intfloat/multilingual-e5-large')
        return self.models[model_name]
    
    def detect_language(self, text: str) -> Dict[str, float]:
        """텍스트 언어 감지"""
        try:
            detected = langdetect.detect_langs(text)
            return {lang.lang: lang.prob for lang in detected}
        except:
            return {'unknown': 1.0}
    
    def select_optimal_model(self, language_ratio: Dict[str, float]) -> str:
        """최적 모델 선택"""
        korean = language_ratio.get('ko', 0)
        chinese = language_ratio.get('zh-cn', 0) + language_ratio.get('zh-tw', 0)
        japanese = language_ratio.get('ja', 0)
        english = language_ratio.get('en', 0)
        
        cjk_total = korean + chinese + japanese
        
        if korean > 0.6 or cjk_total > 0.4:
            return 'bge-m3'
        elif english > 0.6:
            return 'e5-large'
        else:
            return 'e5-large'  # 기본값
    
    async def embed_texts(self, texts: List[str]) -> Tuple[List[np.ndarray], str]:
        """텍스트 배치 임베딩"""
        # 언어 감지 (첫 번째 텍스트 기준)
        if texts:
            lang_ratio = self.detect_language(texts[0])
            model_name = self.select_optimal_model(lang_ratio)
        else:
            model_name = 'e5-large'
        
        # 모델 로드 및 임베딩
        model = self.get_model(model_name)
        embeddings = model.encode(texts)
        
        return embeddings, model_name
```

### 2. Qdrant 벡터 스토어 구현 예시

```python
# app/db/qdrant.py
from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Any
import uuid

class QdrantVectorStore:
    def __init__(self, url: str = "http://localhost:6333"):
        self.client = QdrantClient(url=url)
        self.collection_name = "documents"
        
    def create_collection(self, vector_size: int = 1024):
        """컬렉션 생성"""
        try:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                )
            )
        except Exception as e:
            print(f"컬렉션 이미 존재하거나 생성 실패: {e}")
    
    def upsert_vectors(self, 
                      vectors: List[List[float]], 
                      metadatas: List[Dict[str, Any]]) -> List[str]:
        """벡터 업서트"""
        points = []
        ids = []
        
        for vector, metadata in zip(vectors, metadatas):
            point_id = str(uuid.uuid4())
            ids.append(point_id)
            
            points.append(models.PointStruct(
                id=point_id,
                vector=vector,
                payload=metadata
            ))
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        return ids
    
    def search(self, 
               query_vector: List[float], 
               limit: int = 10,
               filter_dict: Dict = None) -> List[Dict]:
        """벡터 검색"""
        search_filter = None
        if filter_dict:
            search_filter = models.Filter(**filter_dict)
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=search_filter
        )
        
        return [{
            'id': result.id,
            'score': result.score,
            'payload': result.payload
        } for result in results]
```

### 3. FastAPI 라우터 구현 예시

```python
# app/api/documents.py
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from typing import List
from ..services.document_processor import DocumentProcessor
from ..services.embedding import AdaptiveEmbeddingService  
from ..db.qdrant import QdrantVectorStore

router = APIRouter()

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    processor: DocumentProcessor = Depends(),
    embedder: AdaptiveEmbeddingService = Depends(),
    vector_store: QdrantVectorStore = Depends()
):
    """문서 업로드 및 벡터화"""
    
    # 파일 저장
    file_path = f"./data/{file.filename}"
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    try:
        # 문서 파싱
        parsed_doc = await processor.process_file(file_path)
        
        # 청크 텍스트 추출
        chunk_texts = [chunk.content for chunk in parsed_doc.chunks]
        
        # 임베딩 생성
        embeddings, model_used = await embedder.embed_texts(chunk_texts)
        
        # 메타데이터 준비
        metadatas = []
        for chunk in parsed_doc.chunks:
            metadata = {
                **chunk.metadata,
                'chunk_id': chunk.chunk_id,
                'document_filename': file.filename,
                'model_used': model_used
            }
            metadatas.append(metadata)
        
        # 벡터 스토어에 저장
        vector_ids = vector_store.upsert_vectors(embeddings.tolist(), metadatas)
        
        return {
            "success": True,
            "document_id": parsed_doc.metadata.get('filename'),
            "chunks_created": len(parsed_doc.chunks),
            "model_used": model_used,
            "vector_ids": vector_ids
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문서 처리 실패: {str(e)}")

@router.post("/query")  
async def query_documents(
    query: str,
    top_k: int = 5,
    embedder: AdaptiveEmbeddingService = Depends(),
    vector_store: QdrantVectorStore = Depends()
):
    """문서 질의응답"""
    
    try:
        # 쿼리 임베딩
        query_embeddings, model_used = await embedder.embed_texts([query])
        query_vector = query_embeddings[0].tolist()
        
        # 벡터 검색  
        search_results = vector_store.search(
            query_vector=query_vector,
            limit=top_k * 2  # 리랭킹을 위해 더 많이 검색
        )
        
        # 결과 포맷팅
        sources = []
        for result in search_results[:top_k]:
            sources.append({
                'content': result['payload'].get('content', ''),
                'similarity': result['score'],
                'document': result['payload'].get('document_filename', ''),
                'chunk_id': result['payload'].get('chunk_id', ''),
                'metadata': result['payload']
            })
        
        return {
            "success": True,
            "query": query,
            "model_used": model_used, 
            "sources": sources,
            "total_found": len(search_results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")
```

## ⏰ 타임라인

### Week 1-2: Core Infrastructure

- 임베딩 서비스 구현
- 벡터 DB 연동
- 기본 API 구조

### Week 3-4: Advanced Features  

- 리랭킹 시스템
- LLM 통합
- 성능 최적화

### Week 5: Production Ready

- 보안 강화
- 모니터링 구축
- 배포 환경 설정

## 🎯 성공 기준

### 기능적 요구사항

- [ ] 10가지 파일 형식 지원
- [ ] 한/영/혼재 문서 처리
- [ ] < 3초 쿼리 응답시간  
- [ ] > 85% 검색 정확도

### 비기능적 요구사항  

- [ ] 100 req/min 처리 가능
- [ ] 99.9% 가용성
- [ ] Docker 기반 배포
- [ ] API 문서화 완료

---

**다음 구현 단계**: 임베딩 서비스 구현부터 시작  
**예상 완료 기간**: 4-5주  
**핵심 우선순위**: 성능과 정확도 균형
