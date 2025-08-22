import React, { useState } from 'react';
import { MagnifyingGlassIcon, Cog6ToothIcon } from '@heroicons/react/24/outline';
import { QueryOptions } from '../types';

interface QuerySectionProps {
  onQuery: (query: string, options: QueryOptions) => void;
  isLoading: boolean;
  currentQuery: string;
  setCurrentQuery: (query: string) => void;
}

const QuerySection: React.FC<QuerySectionProps> = ({
  onQuery,
  isLoading,
  currentQuery,
  setCurrentQuery,
}) => {
  const [showOptions, setShowOptions] = useState(false);
  const [options, setOptions] = useState<QueryOptions>({
    top_k: 5,
    model: undefined,
    temperature: 0.7,
  });

  const exampleQueries = [
    "이 문서의 주요 내용을 요약해주세요.",
    "중요한 포인트들을 bullet point로 정리해주세요.",
    "문서에서 언급된 날짜나 숫자 정보를 알려주세요.",
    "이 내용과 관련된 추가 질문이 있다면 무엇인가요?",
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (currentQuery.trim() && !isLoading) {
      onQuery(currentQuery.trim(), options);
    }
  };

  const handleExampleClick = (example: string) => {
    setCurrentQuery(example);
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">질의응답</h3>
        <button
          onClick={() => setShowOptions(!showOptions)}
          className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
        >
          <Cog6ToothIcon className="h-5 w-5" />
        </button>
      </div>

      {/* 검색 옵션 */}
      {showOptions && (
        <div className="mb-4 p-4 bg-gray-50 rounded-md space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              검색 결과 수 (top_k)
            </label>
            <select
              value={options.top_k}
              onChange={(e) => setOptions({ ...options, top_k: parseInt(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
            >
              <option value={3}>3개</option>
              <option value={5}>5개</option>
              <option value={10}>10개</option>
              <option value={15}>15개</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Temperature
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={options.temperature}
              onChange={(e) => setOptions({ ...options, temperature: parseFloat(e.target.value) })}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-500">
              <span>0 (정확)</span>
              <span>{options.temperature}</span>
              <span>1 (창의적)</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              모델 선택
            </label>
            <select
              value={options.model || ''}
              onChange={(e) => setOptions({ ...options, model: e.target.value || undefined })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
            >
              <option value="">자동 선택</option>
              <option value="bge-m3">BGE-M3 (한국어 특화)</option>
              <option value="e5-large">E5-Large (다국어)</option>
            </select>
          </div>
        </div>
      )}

      {/* 질문 입력 폼 */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <textarea
            value={currentQuery}
            onChange={(e) => setCurrentQuery(e.target.value)}
            placeholder="질문을 입력하세요..."
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary resize-none"
            disabled={isLoading}
          />
        </div>

        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-500">
            {currentQuery.length}/500
          </div>
          
          <button
            type="submit"
            disabled={!currentQuery.trim() || isLoading}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            <MagnifyingGlassIcon className="h-4 w-4" />
            <span>{isLoading ? '검색 중...' : '검색'}</span>
          </button>
        </div>
      </form>

      {/* 예시 질문들 */}
      <div className="mt-6">
        <h4 className="text-sm font-medium text-gray-700 mb-2">예시 질문</h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {exampleQueries.map((example, index) => (
            <button
              key={index}
              onClick={() => handleExampleClick(example)}
              className="text-left p-2 text-xs text-gray-600 bg-gray-50 rounded hover:bg-gray-100 transition-colors"
              disabled={isLoading}
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default QuerySection;