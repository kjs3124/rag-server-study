import axios, { AxiosResponse } from 'axios';
import {
  UploadResponse,
  QueryResults,
  DocumentInfo,
  HealthStatus,
  QueryOptions,
  CrawlOptions
} from '../types';

class RAGApiService {
  private baseURL = '/api/v1';
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

  // 문서 삭제
  async deleteDocument(id: string): Promise<void> {
    await this.api.delete(`/documents/${id}`);
  }

  // 질의응답
  async query(query: string, options: QueryOptions = { top_k: 5 }): Promise<QueryResults> {
    const response: AxiosResponse<QueryResults> = await this.api.post('/query', {
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

  // 시스템 통계
  async getStats(): Promise<any> {
    const response = await this.api.get('/stats');
    return response.data;
  }
}

export const apiService = new RAGApiService();
export default apiService;