import React, { useState, useEffect } from 'react';
import { 
  CheckCircleIcon, 
  XCircleIcon, 
  ExclamationTriangleIcon,
  ClockIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';
import { UploadTask } from '../types';
import apiService from '../services/api';

interface TaskProgressProps {
  task: UploadTask;
  onTaskComplete?: (taskId: string, result?: any) => void;
  onTaskError?: (taskId: string, error: string) => void;
  onCancel?: (taskId: string) => void;
  showCancelButton?: boolean;
}

const TaskProgress: React.FC<TaskProgressProps> = ({
  task,
  onTaskComplete,
  onTaskError,
  onCancel,
  showCancelButton = true
}) => {
  const [elapsedTime, setElapsedTime] = useState<number>(0);
  const [estimatedTimeRemaining, setEstimatedTimeRemaining] = useState<string>('');

  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      const elapsed = Math.floor((now.getTime() - task.startTime.getTime()) / 1000);
      setElapsedTime(elapsed);

      // 진행률 기반 예상 시간 계산
      if (task.progress > 0 && task.status === 'processing') {
        const totalEstimated = elapsed / (task.progress / 100);
        const remaining = Math.max(0, totalEstimated - elapsed);
        setEstimatedTimeRemaining(formatTime(remaining));
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [task.startTime, task.progress, task.status]);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getStatusIcon = () => {
    switch (task.status) {
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <XCircleIcon className="h-5 w-5 text-red-500" />;
      case 'cancelled':
        return <XMarkIcon className="h-5 w-5 text-gray-500" />;
      case 'processing':
        return <ClockIcon className="h-5 w-5 text-blue-500 animate-spin" />;
      case 'pending':
        return <ClockIcon className="h-5 w-5 text-yellow-500" />;
      default:
        return <ExclamationTriangleIcon className="h-5 w-5 text-gray-400" />;
    }
  };

  const getStatusColor = () => {
    switch (task.status) {
      case 'completed': return 'text-green-700 bg-green-50';
      case 'failed': return 'text-red-700 bg-red-50';
      case 'cancelled': return 'text-gray-700 bg-gray-50';
      case 'processing': return 'text-blue-700 bg-blue-50';
      case 'pending': return 'text-yellow-700 bg-yellow-50';
      default: return 'text-gray-700 bg-gray-50';
    }
  };

  const getProgressBarColor = () => {
    switch (task.status) {
      case 'completed': return 'bg-green-500';
      case 'failed': return 'bg-red-500';
      case 'cancelled': return 'bg-gray-500';
      case 'processing': return 'bg-blue-500';
      case 'pending': return 'bg-yellow-500';
      default: return 'bg-gray-500';
    }
  };

  const handleCancel = async () => {
    if (onCancel && (task.status === 'pending' || task.status === 'processing')) {
      try {
        await apiService.cancelTask(task.task_id);
        onCancel(task.task_id);
      } catch (error) {
        console.error('Failed to cancel task:', error);
      }
    }
  };

  useEffect(() => {
    if (task.status === 'completed' && task.result && onTaskComplete) {
      onTaskComplete(task.task_id, task.result);
    } else if (task.status === 'failed' && task.error && onTaskError) {
      onTaskError(task.task_id, task.error);
    }
  }, [task.status, task.result, task.error, task.task_id, onTaskComplete, onTaskError]);

  return (
    <div className="border rounded-lg p-4 bg-white shadow-sm">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          {getStatusIcon()}
          <span className="font-medium text-gray-900 truncate">
            {task.filename}
          </span>
        </div>
        
        <div className="flex items-center space-x-2">
          <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor()}`}>
            {task.status.toUpperCase()}
          </span>
          
          {showCancelButton && (task.status === 'pending' || task.status === 'processing') && (
            <button
              onClick={handleCancel}
              className="text-gray-400 hover:text-red-500 transition-colors"
              title="작업 취소"
            >
              <XMarkIcon className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* 진행률 바 */}
      {(task.status === 'processing' || task.status === 'completed') && (
        <div className="mb-3">
          <div className="flex justify-between text-sm text-gray-600 mb-1">
            <span>진행률</span>
            <span>{task.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-300 ${getProgressBarColor()}`}
              style={{ width: `${task.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* 상태 메시지 */}
      <div className="text-sm text-gray-600 mb-2">
        {task.message || '대기 중...'}
      </div>

      {/* 시간 정보 */}
      <div className="flex justify-between text-xs text-gray-500">
        <div className="flex items-center space-x-4">
          <span>경과: {formatTime(elapsedTime)}</span>
          {estimatedTimeRemaining && task.status === 'processing' && (
            <span>예상 잔여: {estimatedTimeRemaining}</span>
          )}
        </div>
        
        {task.status === 'completed' && task.result && (
          <span className="text-green-600">
            ✅ {task.result.data.chunks_created}개 청크 생성 완료
          </span>
        )}
        
        {task.status === 'failed' && task.error && (
          <span className="text-red-600 truncate max-w-xs" title={task.error}>
            오류: {task.error}
          </span>
        )}
      </div>
    </div>
  );
};

export default TaskProgress;