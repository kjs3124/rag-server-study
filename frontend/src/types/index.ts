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

export interface CrawlOptions {
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