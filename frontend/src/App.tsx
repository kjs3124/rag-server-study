import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import DocumentUpload from './components/DocumentUpload';
import QuerySection from './components/QuerySection';
import ResultsDisplay from './components/ResultsDisplay';
import DocumentViewer from './components/DocumentViewer';
import { 
  HealthStatus, 
  DocumentInfo, 
  QueryResults, 
  UploadResponse, 
  QueryOptions 
} from './types';
import apiService from './services/api';

const App: React.FC = () => {
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [currentQuery, setCurrentQuery] = useState('');
  const [queryResults, setQueryResults] = useState<QueryResults | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewingDocumentId, setViewingDocumentId] = useState<string | null>(null);

  // 헬스체크 및 초기 데이터 로드
  useEffect(() => {
    const initializeApp = async () => {
      try {
        // 헬스체크
        const health = await apiService.healthCheck();
        setHealthStatus(health);
        
        // 기존 문서 목록 로드
        const docs = await apiService.getDocuments();
        setDocuments(docs);
      } catch (error) {
        console.error('Failed to initialize app:', error);
        setError('API 서버에 연결할 수 없습니다.');
        setHealthStatus({ 
          status: 'unhealthy', 
          database: false, 
          vector_store: false, 
          models_loaded: [] 
        });
      }
    };

    initializeApp();
    
    // 주기적 헬스체크 (30초마다)
    const healthCheckInterval = setInterval(async () => {
      try {
        const health = await apiService.healthCheck();
        setHealthStatus(health);
        setError(null);
      } catch (error) {
        setHealthStatus({ 
          status: 'unhealthy', 
          database: false, 
          vector_store: false, 
          models_loaded: [] 
        });
      }
    }, 30000);

    return () => clearInterval(healthCheckInterval);
  }, []);

  const handleUploadSuccess = async (response: UploadResponse) => {
    // 성공 메시지
    alert(`문서가 성공적으로 업로드되었습니다. (${response.chunks_created}개 청크 생성)`);
    
    // 문서 목록 새로고침
    try {
      const updatedDocs = await apiService.getDocuments();
      setDocuments(updatedDocs);
    } catch (error) {
      console.error('Failed to refresh documents:', error);
    }
  };

  const handleDeleteDocument = async (id: string) => {
    if (confirm('이 문서를 삭제하시겠습니까?')) {
      try {
        await apiService.deleteDocument(id);
        // 문서 목록 새로고침
        const updatedDocs = await apiService.getDocuments();
        setDocuments(updatedDocs);
      } catch (error) {
        console.error('Failed to delete document:', error);
        alert('문서 삭제에 실패했습니다.');
      }
    }
  };

  const handleViewDocument = (id: string) => {
    setViewingDocumentId(id);
  };

  const handleCloseViewer = () => {
    setViewingDocumentId(null);
  };

  const handleQuery = async (query: string, options: QueryOptions) => {
    if (!query.trim() || documents.length === 0) {
      alert('질문을 입력하고 문서를 먼저 업로드해주세요.');
      return;
    }

    setIsLoading(true);
    setError(null);
    
    try {
      const results = await apiService.query(query, options);
      setQueryResults(results);
    } catch (error) {
      console.error('Query failed:', error);
      setError('검색 중 오류가 발생했습니다.');
      setQueryResults(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Header healthStatus={healthStatus} />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 에러 메시지 */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-red-800">{error}</p>
          </div>
        )}
        
        {/* API 연결 상태 경고 */}
        {healthStatus?.status === 'unhealthy' && (
          <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-md p-4">
            <p className="text-yellow-800">
              ⚠️ API 서버와의 연결에 문제가 있습니다. 일부 기능이 제한될 수 있습니다.
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* 왼쪽: 문서 업로드 */}
          <div className="lg:col-span-1">
            <DocumentUpload 
              documents={documents}
              onUploadSuccess={handleUploadSuccess}
              onDeleteDocument={handleDeleteDocument}
              onViewDocument={handleViewDocument}
            />
          </div>
          
          {/* 오른쪽: 질의응답 및 결과 */}
          <div className="lg:col-span-2 space-y-6">
            <QuerySection 
              onQuery={handleQuery}
              isLoading={isLoading}
              currentQuery={currentQuery}
              setCurrentQuery={setCurrentQuery}
            />
            
            <ResultsDisplay 
              results={queryResults}
              isLoading={isLoading}
            />
          </div>
        </div>
      </main>

      {/* 문서 뷰어 모달 */}
      {viewingDocumentId && (
        <DocumentViewer 
          documentId={viewingDocumentId}
          onClose={handleCloseViewer}
        />
      )}
      
      {/* 푸터 */}
      <footer className="border-t border-gray-200 bg-white mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center text-sm text-gray-500">
            <p>RAG System Test UI</p>
            <div className="flex items-center space-x-4">
              <span>Documents: {documents.length}</span>
              {healthStatus && (
                <span>Models: {healthStatus.models_loaded.length}</span>
              )}
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;