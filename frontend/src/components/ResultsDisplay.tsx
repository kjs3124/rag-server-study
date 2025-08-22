import React, { useState } from 'react';
import { 
  DocumentTextIcon, 
  ChevronDownIcon, 
  ChevronUpIcon,
  ClockIcon,
  CpuChipIcon,
  GlobeAltIcon
} from '@heroicons/react/24/outline';
import { QueryResults, SourceDocument } from '../types';

interface ResultsDisplayProps {
  results: QueryResults | null;
  isLoading: boolean;
}

const ResultsDisplay: React.FC<ResultsDisplayProps> = ({ results, isLoading }) => {
  const [showMetadata, setShowMetadata] = useState(false);
  const [expandedSources, setExpandedSources] = useState<Set<number>>(new Set());

  const toggleSource = (index: number) => {
    const newExpanded = new Set(expandedSources);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedSources(newExpanded);
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'bg-green-500';
    if (score >= 0.6) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getScoreText = (score: number) => {
    if (score >= 0.8) return 'High';
    if (score >= 0.6) return 'Medium';
    return 'Low';
  };

  const formatTime = (timeStr: string) => {
    try {
      const time = parseFloat(timeStr.replace('s', ''));
      return `${(time * 1000).toFixed(0)}ms`;
    } catch {
      return timeStr;
    }
  };

  if (isLoading) {
    return (
      <div className="card">
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          <span className="ml-3 text-gray-600">검색 중...</span>
        </div>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="card">
        <div className="text-center py-12 text-gray-500">
          <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-300" />
          <p className="mt-4">질문을 입력하여 검색을 시작하세요.</p>
        </div>
      </div>
    );
  }

  if (!results.success) {
    return (
      <div className="card">
        <div className="text-center py-12 text-red-600">
          <p>검색 중 오류가 발생했습니다.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 답변 섹션 */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">답변</h3>
          <div className="flex items-center space-x-2 text-sm text-gray-500">
            <ClockIcon className="h-4 w-4" />
            <span>{formatTime(results.metadata.query_time)}</span>
          </div>
        </div>
        
        <div className="prose max-w-none">
          <div className="bg-blue-50 border-l-4 border-primary p-4 rounded-r">
            <p className="text-gray-800 leading-relaxed whitespace-pre-wrap">
              {results.data.answer}
            </p>
          </div>
        </div>
      </div>

      {/* 소스 문서들 */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">
          참조 문서 ({results.data.sources.length}개)
        </h3>
        
        <div className="space-y-3">
          {results.data.sources.map((source, index) => (
            <div key={index} className="border border-gray-200 rounded-lg">
              <div
                className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50"
                onClick={() => toggleSource(index)}
              >
                <div className="flex items-center space-x-3">
                  <DocumentTextIcon className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="font-medium text-gray-900">
                      {source.metadata?.filename || source.document_id}
                    </p>
                    {source.section_title && (
                      <p className="text-sm text-gray-500">{source.section_title}</p>
                    )}
                    {source.page && (
                      <p className="text-xs text-gray-400">Page {source.page}</p>
                    )}
                  </div>
                </div>
                
                <div className="flex items-center space-x-3">
                  {/* 유사도 점수 */}
                  <div className="flex items-center space-x-2">
                    <div className="w-16 bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${getScoreColor(source.similarity)}`}
                        style={{ width: `${source.similarity * 100}%` }}
                      ></div>
                    </div>
                    <span className="text-xs text-gray-500">
                      {(source.similarity * 100).toFixed(0)}%
                    </span>
                    <span className={`
                      px-2 py-1 text-xs rounded-full
                      ${source.similarity >= 0.8 ? 'bg-green-100 text-green-800' : ''}
                      ${source.similarity >= 0.6 && source.similarity < 0.8 ? 'bg-yellow-100 text-yellow-800' : ''}
                      ${source.similarity < 0.6 ? 'bg-red-100 text-red-800' : ''}
                    `}>
                      {getScoreText(source.similarity)}
                    </span>
                  </div>
                  
                  {expandedSources.has(index) ? (
                    <ChevronUpIcon className="h-5 w-5 text-gray-400" />
                  ) : (
                    <ChevronDownIcon className="h-5 w-5 text-gray-400" />
                  )}
                </div>
              </div>
              
              {expandedSources.has(index) && (
                <div className="px-4 pb-4">
                  <div className="bg-gray-50 p-3 rounded text-sm text-gray-700 leading-relaxed">
                    {source.content}
                  </div>
                  
                  {/* 메타데이터 */}
                  <div className="mt-2 text-xs text-gray-500">
                    <p>Chunk ID: {source.chunk_id}</p>
                    {source.metadata && Object.keys(source.metadata).length > 0 && (
                      <details className="mt-1">
                        <summary className="cursor-pointer hover:text-gray-700">
                          Additional metadata
                        </summary>
                        <pre className="mt-1 text-xs bg-gray-100 p-2 rounded overflow-x-auto">
                          {JSON.stringify(source.metadata, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 메타데이터 섹션 */}
      <div className="card">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setShowMetadata(!showMetadata)}
        >
          <h3 className="text-lg font-semibold">검색 정보</h3>
          {showMetadata ? (
            <ChevronUpIcon className="h-5 w-5 text-gray-400" />
          ) : (
            <ChevronDownIcon className="h-5 w-5 text-gray-400" />
          )}
        </div>
        
        {showMetadata && (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="flex items-center space-x-2">
              <ClockIcon className="h-5 w-5 text-gray-400" />
              <div>
                <p className="text-sm text-gray-600">Response Time</p>
                <p className="font-medium">{formatTime(results.metadata.query_time)}</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              <CpuChipIcon className="h-5 w-5 text-gray-400" />
              <div>
                <p className="text-sm text-gray-600">Model Used</p>
                <p className="font-medium">{results.metadata.model_used}</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              <GlobeAltIcon className="h-5 w-5 text-gray-400" />
              <div>
                <p className="text-sm text-gray-600">Language</p>
                <p className="font-medium">{results.metadata.language_detected}</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              <DocumentTextIcon className="h-5 w-5 text-gray-400" />
              <div>
                <p className="text-sm text-gray-600">Retrieved</p>
                <p className="font-medium">{results.metadata.retrieval_count} docs</p>
              </div>
            </div>
            
            {results.metadata.rerank_applied && (
              <div className="md:col-span-2 lg:col-span-4">
                <div className="bg-green-50 border border-green-200 rounded p-3">
                  <p className="text-sm text-green-800">
                    ✓ Re-ranking applied for improved accuracy
                  </p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ResultsDisplay;