import React, { useState, useEffect } from 'react';
import { XMarkIcon, DocumentTextIcon, ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';
import apiService from '../services/api';

interface DocumentChunk {
  chunk_id: string;
  content: string;
  metadata: any;
  page_number?: number;
  section_title?: string;
}

interface DocumentDetail {
  id: string;
  filename: string;
  file_size: number;
  chunks_count: number;
  upload_time: string;
  status: string;
  file_type: string;
  metadata: any;
}

interface DocumentViewerProps {
  documentId: string;
  onClose: () => void;
}

const DocumentViewer: React.FC<DocumentViewerProps> = ({ documentId, onClose }) => {
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchDocument();
  }, [documentId]);

  const fetchDocument = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiService.getDocument(documentId);
      setDocument(data.document);
      setChunks(data.chunks);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '문서를 불러올 수 없습니다');
    } finally {
      setLoading(false);
    }
  };

  const toggleChunk = (chunkId: string) => {
    const newExpanded = new Set(expandedChunks);
    if (newExpanded.has(chunkId)) {
      newExpanded.delete(chunkId);
    } else {
      newExpanded.add(chunkId);
    }
    setExpandedChunks(newExpanded);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('ko-KR');
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6 w-11/12 max-w-4xl max-h-5/6 overflow-hidden">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">문서 로딩 중...</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            <span className="ml-3 text-gray-600">문서를 불러오는 중...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6 w-11/12 max-w-4xl max-h-5/6 overflow-hidden">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-red-600">오류</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
          <div className="space-y-3">
            <p className="text-gray-600">{error}</p>
            <button 
              onClick={fetchDocument}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              다시 시도
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!document) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6 w-11/12 max-w-4xl max-h-5/6 overflow-hidden">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">문서 없음</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
          <p className="text-gray-600">문서를 찾을 수 없습니다.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-11/12 max-w-4xl max-h-5/6 overflow-hidden flex flex-col">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">문서 상세보기</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <XMarkIcon className="h-6 w-6" />
          </button>
        </div>

        <div className="bg-gray-50 rounded-lg p-4 mb-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h3 className="font-medium text-gray-900">{document.filename}</h3>
              <p className="text-sm text-gray-500 mt-1">
                {formatFileSize(document.file_size)} • {document.file_type}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">
                업로드: {formatDate(document.upload_time)}
              </p>
              <p className="text-sm text-gray-600">
                청크 수: {document.chunks_count}개
              </p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto max-h-96">
          <h3 className="text-lg font-semibold mb-3">청크 목록 ({chunks.length}개)</h3>
          
          {chunks.length === 0 ? (
            <p className="text-gray-500 text-center py-8">청크가 없습니다.</p>
          ) : (
            <div className="space-y-3 pr-2">
              {chunks.map((chunk, index) => (
                <div key={chunk.chunk_id} className="border border-gray-200 rounded-lg">
                  <div
                    className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50"
                    onClick={() => toggleChunk(chunk.chunk_id)}
                  >
                    <div className="flex items-center space-x-3">
                      <DocumentTextIcon className="h-5 w-5 text-gray-400" />
                      <div>
                        <p className="font-medium text-gray-900">
                          청크 #{index + 1}
                        </p>
                        {chunk.section_title && (
                          <p className="text-sm text-gray-500">{chunk.section_title}</p>
                        )}
                        {chunk.page_number && (
                          <p className="text-xs text-gray-400">페이지 {chunk.page_number}</p>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-3">
                      <span className="text-xs text-gray-500">
                        {chunk.content.length} 글자
                      </span>
                      {expandedChunks.has(chunk.chunk_id) ? (
                        <ChevronUpIcon className="h-5 w-5 text-gray-400" />
                      ) : (
                        <ChevronDownIcon className="h-5 w-5 text-gray-400" />
                      )}
                    </div>
                  </div>
                  
                  {expandedChunks.has(chunk.chunk_id) && (
                    <div className="px-4 pb-4">
                      <div className="bg-gray-50 p-3 rounded text-sm text-gray-700 leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto">
                        {chunk.content}
                      </div>
                      
                      <div className="mt-2 text-xs text-gray-500">
                        <p>청크 ID: {chunk.chunk_id}</p>
                        {chunk.metadata && Object.keys(chunk.metadata).length > 0 && (
                          <details className="mt-1">
                            <summary className="cursor-pointer hover:text-gray-700">
                              메타데이터 보기
                            </summary>
                            <pre className="mt-1 text-xs bg-gray-100 p-2 rounded overflow-x-auto">
                              {JSON.stringify(chunk.metadata, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DocumentViewer;