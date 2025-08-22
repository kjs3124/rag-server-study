# RAG 시스템 아키텍처 및 구현 계획

## 📋 전체 시스템 개요

### 🎯 목표

- **범용 다국어 RAG 시스템**: 한국어, 영어, 혼재 문서 지원
- **확장자별 지능형 파싱**: PDF, DOCX, TXT, HTML, MD, CSV, PPTX, XLSX + URL 크롤링
- **언어 인식 기반 최적화**: 동적 임베딩 모델 선택
- **고성능 벡터 검색**: Qdrant + PostgreSQL+pgvector 지원

## 🏗️ 시스템 아키텍처

### 전체 파이프라인

``` 파이프라인
1. 문서 업로드/URL → 2. 확장자별 파서 → 3. 언어 감지 → 4. 임베딩 모델 선택 
   ↓
5. 청크 임베딩 → 6. 벡터 DB 저장 → 7. 쿼리 처리 → 8. 벡터 검색 (Top-20)
   ↓  
9. 리랭킹 (Top-5) → 10. LLM 컨텍스트 구성 → 11. 답변 생성
```

### 컴포넌트 구조

``` 컴포넌트
RAG-System/
├── app/
│   ├── api/                    # FastAPI 라우터
│   │   ├── documents.py        # 문서 업로드/관리
│   │   ├── query.py           # 질의응답
│   │   └── admin.py           # 관리 기능
│   ├── core/                   # 설정, 보안
│   │   ├── config.py          # 환경 설정
│   │   ├── security.py        # JWT, 인증
│   │   └── dependencies.py    # DI 컨테이너
│   ├── db/                     # 데이터베이스
│   │   ├── qdrant.py          # Qdrant 연결
│   │   ├── postgres.py        # PostgreSQL 연결
│   │   └── models.py          # SQLAlchemy 모델
│   ├── models/                 # Pydantic 모델
│   │   ├── documents.py       # 문서 스키마
│   │   ├── queries.py         # 쿼리 스키마
│   │   └── responses.py       # 응답 스키마
│   └── services/              # 비즈니스 로직
│       ├── parsers/           # 문서 파서들
│       ├── embedding.py       # 임베딩 서비스
│       ├── retrieval.py       # 검색 서비스
│       ├── reranking.py       # 리랭킹 서비스
│       └── llm.py            # LLM 통합
├── data/                      # 업로드 파일
├── tests/                     # 테스트
└── docs/                      # 문서화
```

## 🔧 핵심 컴포넌트 설계

### 1. 문서 파서 시스템

#### 파서 팩토리 패턴

```python
class DocumentParserFactory:
    _parsers = {
        '.pdf': PDFParser,           # Unstructured + PyPDF2
        '.docx': DOCXParser,         # python-docx + XML
        '.txt': TXTParser,           # 인코딩 감지 + 청킹
        '.html': HTMLParser,         # BeautifulSoup
        '.md': MarkdownParser,       # 헤더 기반 섹션 분할
        '.csv': CSVParser,           # CSV 처리
        '.pptx': PPTXParser,         # 슬라이드별 청킹
        '.xlsx': ExcelParser,        # 시트별 처리
        'url': WebCrawlerParser      # requests + Playwright
    }
```

#### 지원 파일 형식

- **문서**: PDF, DOCX, DOC, TXT, HTML, HTM, MD, MARKDOWN
- **스프레드시트**: XLSX, XLS, CSV
- **프레젠테이션**: PPTX, PPT
- **웹**: URL 크롤링 (정적/동적)

#### 특징

- **Fallback 전략**: 각 파서마다 대안 라이브러리 지원
- **메타데이터 보존**: 페이지, 섹션, 테이블 정보 유지
- **청킹 최적화**: 파일 타입별 최적 청킹 전략
- **배치 처리**: 다중 파일 동시 처리

### 2. 임베딩 서비스

#### 언어별 동적 모델 선택

```python
class AdaptiveEmbeddingService:
    models = {
        'bge-m3': 'BAAI/bge-m3',                    # CJK 특화
        'e5-large': 'intfloat/multilingual-e5-large' # 범용
    }
    
    def select_model(self, language_ratio):
        korean = language_ratio.get('ko', 0)
        cjk_total = korean + language_ratio.get('zh', 0) + language_ratio.get('ja', 0)
        english = language_ratio.get('en', 0)
        
        if korean > 0.6 or cjk_total > 0.4:
            return 'bge-m3'
        elif english > 0.6:
            return 'e5-large'
        else:
            return 'e5-large'  # 기본값
```

#### 선택 기준

- **BGE-M3**: 한국어 > 60% 또는 CJK 언어 > 40%
- **E5-Large**: 영어 > 60% 또는 혼재 문서
- **성능 최적화**: 언어별 최적 모델로 정확도 10-15% 향상

#### 캐싱 전략

- **임베딩 캐시**: Redis 기반 중복 방지
- **배치 처리**: API 호출 최소화
- **지연 로딩**: 필요한 모델만 메모리 로드

### 3. 벡터 데이터베이스

#### Primary: Qdrant

```yaml
장점:
  - 고성능 벡터 검색
  - 메타데이터 필터링 우수
  - 클러스터링 지원
  - HTTP API

설정:
  - 인덱스: HNSW 알고리즘
  - 거리 측정: Cosine Similarity
  - 샤딩: 대용량 데이터 지원
```

#### Alternative: PostgreSQL + pgvector

```yaml
장점:
  - 기존 DB 인프라 활용
  - ACID 트랜잭션
  - SQL 쿼리 지원
  - 관계형 데이터와 통합

설정:
  - 확장: pgvector extension
  - 인덱스: IVFFlat/HNSW
  - 파티셔닝: 성능 최적화
```

### 4. 검색 및 리랭킹

#### 2단계 검색 전략

```python
class HybridRetriever:
    def retrieve(self, query: str, top_k: int = 5):
        # 1단계: 벡터 검색 (넉넉히)
        candidates = vector_db.search(
            query_embedding, 
            limit=top_k * 4  # 20개
        )
        
        # 2단계: 리랭킹으로 정제
        final_docs = reranker.rank(
            query, 
            candidates, 
            top_k=top_k  # 5개
        )
        
        return final_docs
```

#### 리랭킹 모델

- **BGE-Reranker-Large**: 다국어 지원, 높은 정확도
- **목적**: False positive 제거, 관련도 정밀 측정
- **성능**: 벡터 검색 대비 15-20% 정확도 향상

## 🌐 API 설계

### 핵심 엔드포인트

#### 문서 관리

```yaml
POST /api/v1/documents/upload:
  - 파일 업로드 및 벡터화
  - 지원: multipart/form-data
  - 응답: document_id, status, chunks_count

POST /api/v1/documents/url:
  - URL 크롤링 및 벡터화
  - 옵션: depth, same_domain
  - 응답: document_id, crawled_urls

GET /api/v1/documents/{id}:
  - 문서 정보 조회
  - 응답: metadata, chunks, processing_status

DELETE /api/v1/documents/{id}:
  - 문서 및 벡터 삭제
  - 벡터 스토어에서 완전 제거
```

#### 질의응답

```yaml
POST /api/v1/query:
  - RAG 기반 질의응답
  - 파라미터: query, top_k, temperature, model
  - 응답: answer, sources, confidence, metadata

POST /api/v1/query/stream:
  - 스트리밍 응답
  - Server-Sent Events
  - 실시간 답변 생성
```

#### 관리 기능

```yaml
GET /api/v1/stats:
  - 시스템 통계
  - 문서 수, 청크 수, 사용량

GET /api/v1/health:
  - 헬스체크
  - DB 연결, 모델 로드 상태

POST /api/v1/admin/reindex:
  - 벡터 재인덱싱
  - 백그라운드 작업
```

### 응답 형식

```json
{
  "success": true,
  "data": {
    "answer": "답변 내용",
    "sources": [
      {
        "document_id": "doc_123",
        "chunk_id": "chunk_456", 
        "content": "관련 내용",
        "similarity": 0.89,
        "page": 1,
        "section_title": "섹션명"
      }
    ]
  },
  "metadata": {
    "query_time": "0.85s",
    "model_used": "bge-m3",
    "language_detected": "ko",
    "retrieval_count": 5,
    "rerank_applied": true
  }
}
```

## 🔒 보안 및 인증

### 인증 시스템

- **JWT 토큰**: stateless 인증
- **API 키**: 외부 서비스 연동
- **Rate Limiting**: 분당 요청 제한
- **CORS**: 출처 제한

### 데이터 보안

- **파일 검증**: 악성 파일 차단
- **샌드박싱**: 파서 실행 격리  
- **암호화**: 민감 데이터 보호
- **접근 제어**: 문서별 권한 관리

## 📊 성능 목표

### 응답 시간

- **벡터 검색**: < 200ms
- **리랭킹**: < 300ms  
- **전체 쿼리**: < 3초
- **문서 처리**: < 30초 (10MB PDF 기준)

### 처리량

- **동시 쿼리**: 100 req/min
- **문서 업로드**: 50 files/hour
- **크롤링**: 10 URLs/min

### 정확도

- **검색 정확도**: > 85% (평가 기준 필요)
- **언어 감지**: > 95%
- **파서 성공률**: > 98%

## 🚀 배포 및 운영

### 컨테이너화

```yaml
Services:
  - rag-api: FastAPI 앱
  - qdrant: 벡터 데이터베이스  
  - postgres: 메타데이터 저장
  - redis: 캐싱
  - nginx: 로드밸런서

Volumes:
  - 업로드 파일 영구 저장
  - 모델 캐시 저장
  - 로그 저장
```

### 모니터링

- **메트릭**: Prometheus + Grafana
- **로깅**: 구조화된 로그 (JSON)
- **알림**: 장애 시 슬랙/이메일
- **헬스체크**: 주기적 상태 확인

### 확장성

- **수평 확장**: API 서버 멀티 인스턴스
- **벡터 DB 샤딩**: 대용량 데이터 분산
- **로드밸런싱**: 트래픽 분산
- **CDN**: 정적 파일 캐싱

## 📝 개발 우선순위

### Phase 1: 핵심 기능

1. ✅ 파서 시스템 구현
2. ⏳ 임베딩 서비스 구현  
3. ⏳ 벡터 DB 연동
4. ⏳ 기본 API 구현

### Phase 2: 고도화

1. 리랭킹 시스템 추가
2. 언어별 동적 모델 선택
3. 웹 UI 구현
4. 성능 최적화

### Phase 3: 운영 기능

1. 모니터링 시스템 구축
2. 관리자 대시보드
3. A/B 테스트 프레임워크
4. 자동 스케일링

## 🔗 기술 스택 요약

### Backend

- **Framework**: FastAPI + Pydantic + SQLAlchemy
- **Language**: Python 3.11+
- **Authentication**: JWT + OAuth2

### AI/ML

- **Embedding**: BGE-M3 + Multilingual-E5-Large
- **Reranking**: BGE-Reranker-Large
- **LLM Integration**: OpenAI GPT-4, Claude-3
- **Framework**: Sentence-Transformers, LangChain

### Database

- **Vector**: Qdrant + PostgreSQL+pgvector
- **Cache**: Redis
- **Search**: Elasticsearch (선택사항)

### DevOps

- **Container**: Docker + Docker Compose
- **Orchestration**: Kubernetes (Production)
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus + Grafana + Sentry

### Frontend (향후)

- **Framework**: React + TypeScript
- **State**: Zustand
- **UI**: Tailwind CSS + Shadcn/UI
- **Build**: Vite

---

**문서 작성일**: 2024-08-20  
**최종 업데이트**: 현재 진행 상황에 따라 업데이트 예정
