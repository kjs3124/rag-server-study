import axios, { AxiosResponse } from 'axios';
import {
  UploadResponse,
  QueryResults,
  DocumentInfo,
  HealthStatus,
  QueryOptions,
  CrawlOptions,
  AsyncTaskResponse,
  TaskStatusResponse
} from '../types';
import { retry, defaultApiRetryOptions, defaultUploadRetryOptions } from '../utils/retry';

class RAGApiService {
  private baseURL = 'http://127.0.0.1:8099/api/v1';
  private api;

  constructor() {
    this.api = axios.create({
      baseURL: this.baseURL,
      timeout: 30000, // 30초 타임아웃
    });

    // 응답 인터셉터
    this.api.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error('API Error:', error);
        throw error;
      }
    );
  }

  // 문서 업로드
  async uploadDocument(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response: AxiosResponse<UploadResponse> = await this.api.post(
      '/documents/upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );

    return response.data;
  }

  // URL 크롤링
  async crawlUrl(url: string, options?: CrawlOptions): Promise<UploadResponse> {
    const response: AxiosResponse<UploadResponse> = await this.api.post(
      '/documents/url',
      {
        url,
        ...options,
      }
    );

    return response.data;
  }

  // 문서 목록 조회
  async getDocuments(): Promise<DocumentInfo[]> {
    const response: AxiosResponse<{ documents: DocumentInfo[] }> = await this.api.get(
      '/documents'
    );

    return response.data.documents;
  }

  // 문서 상세 조회
  async getDocument(id: string): Promise<any> {
    const response: AxiosResponse<any> = await this.api.get(`/documents/${id}`);
    return response.data;
  }

  // 문서 삭제
  async deleteDocument(id: string): Promise<void> {
    await this.api.delete(`/documents/${id}`);
  }

  // 질의응답
  async query(query: string, options: QueryOptions = { top_k: 5 }): Promise<QueryResults> {
    const response: AxiosResponse<QueryResults> = await this.api.post('/documents/query', {
      query,
      ...options,
    });

    return response.data;
  }

  // 헬스체크
  async healthCheck(): Promise<HealthStatus> {
    const response: AxiosResponse<HealthStatus> = await this.api.get('/health');
    return response.data;
  }

  // =========================
  // 비동기 API 메서드들
  // =========================

  // 비동기 문서 업로드
  async uploadDocumentAsync(file: File): Promise<AsyncTaskResponse> {
    const result = await retry(
      async () => {
        const formData = new FormData();
        formData.append('file', file);

        const response: AxiosResponse<AsyncTaskResponse> = await this.api.post(
          '/documents/async/upload',
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
            timeout: 10000, // 10초로 단축 (즉시 응답)
          }
        );

        return response.data;
      },
      {
        ...defaultUploadRetryOptions,
        onRetry: (attempt, error) => {
          console.warn(`File upload retry attempt ${attempt} for ${file.name}:`, error.message);
        }
      }
    );

    if (!result.success) {
      throw new Error(`파일 업로드 실패: ${result.error?.message || '알 수 없는 오류'}`);
    }

    return result.data!;
  }

  // 비동기 URL 크롤링
  async crawlUrlAsync(url: string, options?: CrawlOptions): Promise<AsyncTaskResponse> {
    const result = await retry(
      async () => {
        const response: AxiosResponse<AsyncTaskResponse> = await this.api.post(
          '/documents/async/crawl',
          {
            url,
            max_depth: options?.max_depth || 0,
            same_domain: options?.same_domain !== false,
          },
          {
            timeout: 10000, // 10초로 단축 (즉시 응답)
          }
        );

        return response.data;
      },
      {
        ...defaultApiRetryOptions,
        onRetry: (attempt, error) => {
          console.warn(`URL crawl retry attempt ${attempt} for ${url}:`, error.message);
        }
      }
    );

    if (!result.success) {
      throw new Error(`URL 크롤링 실패: ${result.error?.message || '알 수 없는 오류'}`);
    }

    return result.data!;
  }

  // 작업 상태 조회
  async getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
    const response: AxiosResponse<TaskStatusResponse> = await this.api.get(
      `/documents/async/tasks/${taskId}`
    );

    return response.data;
  }

  // 작업 목록 조회
  async getTasks(limit: number = 50, status?: string): Promise<TaskStatusResponse[]> {
    const params: Record<string, any> = { limit };
    if (status) {
      params.status = status;
    }

    const response: AxiosResponse<TaskStatusResponse[]> = await this.api.get(
      '/documents/async/tasks',
      { params }
    );

    return response.data;
  }

  // 작업 취소
  async cancelTask(taskId: string): Promise<{ success: boolean; message: string }> {
    const response: AxiosResponse<{ success: boolean; message: string }> = await this.api.delete(
      `/documents/async/tasks/${taskId}`
    );

    return response.data;
  }

  // 작업 결과 상세 조회
  async getTaskResult(taskId: string): Promise<{
    task_id: string;
    result: UploadResponse;
    chunks: any[];
    metadata: Record<string, any>;
    completed_at: string;
  }> {
    const response = await this.api.get(`/documents/async/tasks/${taskId}/result`);
    return response.data;
  }

}

export const apiService = new RAGApiService();
export default apiService;