import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { DocumentIcon, CloudArrowUpIcon, XMarkIcon, EyeIcon } from '@heroicons/react/24/outline';
import { DocumentInfo, UploadResponse, CrawlOptions, AsyncTaskResponse } from '../types';
import apiService from '../services/api';
import { useTaskManager } from '../hooks/useTaskManager';
import TaskManager from './TaskManager';

interface DocumentUploadProps {
  documents: DocumentInfo[];
  onUploadSuccess: (response: UploadResponse) => void;
  onDeleteDocument: (id: string) => void;
  onViewDocument: (id: string) => void;
  useAsyncMode?: boolean;
}

const DocumentUpload: React.FC<DocumentUploadProps> = ({
  documents,
  onUploadSuccess,
  onDeleteDocument,
  onViewDocument,
  useAsyncMode = true,
}) => {
  const [isUploading, setIsUploading] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [isCrawling, setIsCrawling] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  
  // Task Manager 훅 사용
  const taskManager = useTaskManager({
    onTaskComplete: (taskId: string, result: UploadResponse) => {
      console.log('Task completed:', taskId, result);
      alert(`문서가 성공적으로 업로드되었습니다. (${result.chunks_created}개 청크 생성)`);
      onUploadSuccess(result); // 부모에서 문서 목록 업데이트 필요
    },
    onTaskError: (taskId: string, error: string) => {
      console.error('Task failed:', taskId, error);
      alert(`작업 실패: ${error}`);
    }
  });

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (useAsyncMode) {
      // 비동기 모드: 각 파일을 개별 작업으로 처리
      for (const file of acceptedFiles) {
        try {
          const response: AsyncTaskResponse = await apiService.uploadDocumentAsync(file);
          if (response.success && response.task_id) {
            taskManager.addTask(response.task_id, file.name);
            console.log(`Task created for ${file.name}:`, response.task_id);
            // 비동기 모드에서는 즉시 성공 메시지를 표시하지 않음 (WebSocket으로 나중에 전달됨)
          } else {
            alert(`${file.name} 업로드 시작에 실패했습니다: ${response.message}`);
          }
        } catch (error) {
          console.error('Async upload failed:', error);
          alert(`${file.name} 업로드에 실패했습니다.`);
        }
      }
    } else {
      // 동기 모드: 기존 방식 유지
      for (const file of acceptedFiles) {
        setIsUploading(true);
        setUploadProgress(0);
        
        try {
          const response = await apiService.uploadDocument(file);
          onUploadSuccess(response);
          setUploadProgress(100);
        } catch (error) {
          console.error('Upload failed:', error);
          alert('파일 업로드에 실패했습니다.');
        } finally {
          setIsUploading(false);
          setTimeout(() => setUploadProgress(0), 1000);
        }
      }
    }
  }, [onUploadSuccess, useAsyncMode, taskManager]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
      'text/plain': ['.txt'],
      'text/html': ['.html'],
      'text/markdown': ['.md'],
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    },
    multiple: true,
  });

  const handleUrlCrawl = async () => {
    if (!urlInput.trim()) return;
    
    setIsCrawling(true);
    
    try {
      const options: CrawlOptions = {
        max_depth: 1,
        same_domain: true,
      };
      
      if (useAsyncMode) {
        // 비동기 모드: 작업 생성 후 실시간 추적
        const response: AsyncTaskResponse = await apiService.crawlUrlAsync(urlInput, options);
        
        if (response.success && response.task_id) {
          taskManager.addTask(response.task_id, `웹 크롤링: ${urlInput}`);
          console.log(`Crawl task created for ${urlInput}:`, response.task_id);
          setUrlInput(''); // 입력 초기화
          // 비동기 모드에서는 즉시 성공 메시지를 표시하지 않음 (WebSocket으로 나중에 전달됨)
        } else {
          alert(`URL 크롤링 시작에 실패했습니다: ${response.message}`);
        }
      } else {
        // 동기 모드: 기존 방식 유지
        const response = await apiService.crawlUrl(urlInput, options);
        onUploadSuccess(response);
        setUrlInput('');
      }
    } catch (error) {
      console.error('URL crawling failed:', error);
      alert('URL 크롤링에 실패했습니다.');
    } finally {
      setIsCrawling(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="space-y-6">
      {/* 파일 업로드 영역 */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">문서 업로드</h3>
        
        <div
          {...getRootProps()}
          className={`
            border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
            ${isDragActive 
              ? 'border-primary bg-blue-50' 
              : 'border-gray-300 hover:border-gray-400'
            }
            ${(isUploading || (useAsyncMode && taskManager.getActiveTasksCount() > 0)) ? 'pointer-events-none opacity-50' : ''}
          `}
        >
          <input {...getInputProps()} />
          <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
          
          {isDragActive ? (
            <p className="mt-2 text-sm text-primary">파일을 여기에 놓으세요...</p>
          ) : (
            <div>
              <p className="mt-2 text-sm text-gray-600">
                파일을 드래그하거나 클릭하여 업로드
              </p>
              <p className="text-xs text-gray-500 mt-1">
                PDF, DOCX, TXT, HTML, MD, CSV, PPTX, XLSX 지원
              </p>
            </div>
          )}
        </div>

        {/* 업로드 진행률 - 동기 모드일 때만 표시 */}
        {!useAsyncMode && uploadProgress > 0 && (
          <div className="mt-4">
            <div className="bg-gray-200 rounded-full h-2">
              <div
                className="bg-primary h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
            <p className="text-sm text-gray-600 mt-1">업로드 중... {uploadProgress}%</p>
          </div>
        )}
        
        {/* 비동기 모드 안내 메시지 */}
        {useAsyncMode && taskManager.getActiveTasksCount() > 0 && (
          <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
            <p className="text-sm text-blue-800">
              📊 {taskManager.getActiveTasksCount()}개의 작업이 진행 중입니다. 
              우측 하단에서 실시간 진행 상황을 확인하세요.
            </p>
          </div>
        )}
      </div>

      {/* URL 크롤링 */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">웹 크롤링</h3>
        
        <div className="flex space-x-2">
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="https://example.com"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
            disabled={isCrawling}
          />
          <button
            onClick={handleUrlCrawl}
            disabled={!urlInput.trim() || isCrawling || (useAsyncMode && taskManager.getActiveTasksCount() >= 3)}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            title={useAsyncMode && taskManager.getActiveTasksCount() >= 3 ? '동시 작업은 최대 3개까지 가능합니다.' : ''}
          >
            {isCrawling ? 'Crawling...' : 'Crawl'}
          </button>
        </div>
      </div>

      {/* 업로드된 문서 목록 */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">업로드된 문서 ({documents.length})</h3>
        
        {documents.length === 0 ? (
          <p className="text-gray-500 text-center py-4">업로드된 문서가 없습니다.</p>
        ) : (
          <div className="space-y-2">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-md"
              >
                <div className="flex items-center space-x-3 min-w-0 flex-1">
                  <DocumentIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 truncate">{doc.filename}</p>
                    <p className="text-xs text-gray-500">
                      {formatFileSize(doc.file_size)} • {doc.chunks_count} chunks
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center space-x-2 flex-shrink-0">
                  <span className={`
                    px-2 py-1 text-xs rounded-full whitespace-nowrap
                    ${doc.status === 'completed' ? 'bg-green-100 text-green-800' : ''}
                    ${doc.status === 'processing' ? 'bg-yellow-100 text-yellow-800' : ''}
                    ${doc.status === 'error' ? 'bg-red-100 text-red-800' : ''}
                  `}>
                    {doc.status}
                  </span>
                  
                  <button
                    onClick={() => onViewDocument(doc.id)}
                    className="px-2 py-1 text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded whitespace-nowrap"
                  >
                    보기
                  </button>
                  
                  <button
                    onClick={() => onDeleteDocument(doc.id)}
                    className="px-2 py-1 text-xs text-red-600 hover:text-red-800 hover:bg-red-50 rounded whitespace-nowrap"
                  >
                    삭제
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Task Manager - 비동기 모드일 때만 표시 */}
      {useAsyncMode && <TaskManager />}
    </div>
  );
};

export default DocumentUpload;