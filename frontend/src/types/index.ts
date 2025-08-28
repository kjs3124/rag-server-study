// 통일된 API 응답 타입들
export interface BaseResponse {
  success: boolean;
  message: string;
  timestamp: string;
  data?: any;
  error_id?: string;
}

export interface SuccessResponse<T = any> extends BaseResponse {
  success: true;
  data: T;
}

export interface ErrorResponse extends BaseResponse {
  success: false;
  error_type: string;
}

// 업로드 응답 데이터
export interface UploadData {
  document_id: string;
  chunks_created: number;
  model_used: string;
  file_type: string;
  parser_used: string;
}

// 업로드 응답 (통일된 형식)
export type UploadResponse = SuccessResponse<UploadData>;

// 질의응답 응답 데이터
export interface QueryData {
  answer: string;
  sources: SourceDocument[];
  metadata: {
    query_time: string;
    model_used: string;
    language_detected: string;
    retrieval_count: number;
    rerank_applied?: boolean;
  };
}

// 질의응답 응답 (통일된 형식)
export type QueryResults = SuccessResponse<QueryData>;

export interface SourceDocument {
  document_id: string;
  chunk_id: string;
  content: string;
  similarity: number;
  page?: number;
  section_title?: string;
  metadata?: Record<string, any>;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  file_size: number;
  chunks_count: number;
  upload_time: string;
  status: 'processing' | 'completed' | 'error';
}

// 문서 목록 응답 데이터
export interface DocumentListData {
  documents: DocumentInfo[];
}

// 문서 목록 응답 (통일된 형식)
export type DocumentListResponse = SuccessResponse<DocumentListData>;

// 시스템 상태 데이터
export interface SystemHealthData {
  system_health: any;
  memory_usage: any;
  documents_count: number;
  total_chunks: number;
}

// 시스템 상태 응답 (통일된 형식) - 성공/실패 모두 허용
export type HealthStatus = SuccessResponse<SystemHealthData> | ErrorResponse;

// UI 상태 타입들
export interface QueryOptions {
  top_k: number;
  model?: string;
  temperature?: number;
}

// URL 크롤링 요청
export interface CrawlRequest extends ChunkingOptions {
  url: string;
  max_depth?: number;
  same_domain?: boolean;
}

// 청킹 옵션
export interface ChunkingOptions {
  chunk_size?: number;  // 기본값: 1000 (100-8000)
  chunk_overlap?: number;  // 기본값: chunk_size의 10%
  separators?: string[];  // 텍스트 분할 구분자
}

// 파일 업로드 요청 옵션
export interface UploadOptions extends ChunkingOptions {
  // 추후 추가 옵션들...
}

export interface CrawlOptions extends ChunkingOptions {
  max_depth?: number;
  same_domain?: boolean;
}

export interface AppState {
  documents: DocumentInfo[];
  currentQuery: string;
  queryResults: QueryResults | null;
  isLoading: boolean;
  uploadProgress: number;
  apiStatus: 'connected' | 'disconnected' | 'error';
  error: string | null;
}

// 비동기 API 관련 타입들
export interface AsyncTaskResponse {
  success: boolean;
  task_id: string;
  message: string;
  estimated_time?: string;
}

export interface TaskStatusResponse {
  task_id: string;
  task_type: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  message: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  result?: UploadResponse;
  error?: string;
}

// WebSocket 메시지 타입들
export interface WebSocketMessage {
  type: 'task_update' | 'connection' | 'error' | 'subscribe' | 'unsubscribe';
  task_id?: string;
  status?: TaskStatusResponse['status'];
  progress?: number;
  message?: string;
  result?: UploadResponse;
  error?: string;
}

// 업로드 작업 상태 추적
export interface UploadTask {
  task_id: string;
  filename: string;
  status: TaskStatusResponse['status'];
  progress: number;
  message: string;
  startTime: Date;
  result?: UploadResponse;
  error?: string;
}