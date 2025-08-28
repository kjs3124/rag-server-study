// API 응답 타입들
export interface UploadResponse {
  success: boolean;
  document_id: string;
  chunks_created: number;
  model_used: string;
  vector_ids?: string[];
}

export interface QueryResults {
  success: boolean;
  data: {
    answer: string;
    sources: SourceDocument[];
  };
  metadata: {
    query_time: string;
    model_used: string;
    language_detected: string;
    retrieval_count: number;
    rerank_applied?: boolean;
  };
}

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

export interface HealthStatus {
  status: 'healthy' | 'unhealthy';
  database: boolean;
  vector_store: boolean;
  models_loaded: string[];
}

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
  type: 'task_update' | 'connection' | 'error';
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