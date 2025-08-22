# RAG System Frontend

RAG 시스템 테스트를 위한 React 기반 웹 인터페이스입니다.

## 기능

- 📁 **문서 업로드**: 드래그앤드롭으로 10가지 파일 형식 지원
- 🌐 **웹 크롤링**: URL 입력으로 웹페이지 크롤링
- 🔍 **질의응답**: 자연어 질문으로 문서 검색
- 📊 **결과 표시**: 답변, 소스 문서, 메타데이터 시각화

## 지원 파일 형식

- PDF, DOCX, DOC, TXT, HTML, MD, CSV, PPTX, XLSX

## 개발 환경

### 요구사항
- Node.js 18+
- npm or yarn

### 설치 및 실행

```bash
# 의존성 설치
npm install

# 개발 서버 시작 (포트 3000)
npm run dev

# 프로덕션 빌드
npm run build
```

### 백엔드 연동

프론트엔드는 `http://localhost:8000`에서 실행되는 RAG API 서버와 통신합니다.

```bash
# 백엔드 서버 실행 (별도 터미널)
cd ../
uvicorn main:app --reload --port 8000
```

## 기술 스택

- **Framework**: React 18 + TypeScript
- **Bundler**: Vite
- **Styling**: Tailwind CSS
- **Icons**: Heroicons
- **HTTP Client**: Axios
- **File Upload**: react-dropzone

## 프로젝트 구조

```
src/
├── components/           # React 컴포넌트
│   ├── Header.tsx       # 헤더 및 상태 표시
│   ├── DocumentUpload.tsx # 파일 업로드
│   ├── QuerySection.tsx  # 질의응답 섹션
│   └── ResultsDisplay.tsx # 결과 표시
├── services/
│   └── api.ts           # API 통신 서비스
├── types/
│   └── index.ts         # TypeScript 타입 정의
├── App.tsx              # 메인 앱 컴포넌트
└── main.tsx             # 앱 진입점
```

## API 엔드포인트

- `POST /api/v1/documents/upload` - 파일 업로드
- `POST /api/v1/documents/url` - URL 크롤링
- `GET /api/v1/documents` - 문서 목록
- `DELETE /api/v1/documents/{id}` - 문서 삭제
- `POST /api/v1/query` - 질의응답
- `GET /api/v1/health` - 헬스체크

## 주요 기능

### 문서 업로드
- 드래그앤드롭 인터페이스
- 다중 파일 업로드 지원
- 업로드 진행률 표시
- 파일 형식 자동 감지

### 웹 크롤링
- URL 입력으로 웹페이지 크롤링
- 크롤링 옵션 설정 (깊이, 도메인 제한)

### 질의응답
- 자연어 질문 입력
- 검색 옵션 설정 (top_k, temperature, 모델 선택)
- 예시 질문 제공
- 실시간 검색 상태 표시

### 결과 표시
- 구조화된 답변 표시
- 소스 문서 카드 (유사도 점수 포함)
- 메타데이터 (응답시간, 모델, 언어 감지)
- 접기/펼치기 기능

## 사용법

1. **백엔드 서버 실행**: `uvicorn main:app --reload`
2. **프론트엔드 실행**: `npm run dev`
3. **브라우저 접속**: `http://localhost:3000`
4. **문서 업로드**: 파일을 드래그하거나 URL 입력
5. **질문하기**: 질문을 입력하고 검색 버튼 클릭
6. **결과 확인**: 답변과 참조 문서 확인