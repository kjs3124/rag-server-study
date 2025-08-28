import React, { useState, useEffect, useCallback } from 'react';
import { XMarkIcon, ChevronUpIcon, ChevronDownIcon } from '@heroicons/react/24/outline';
import { UploadTask, TaskStatusResponse, UploadResponse } from '../types';
import TaskProgress from './TaskProgress';
import websocketService from '../services/websocket';

interface TaskManagerProps {
  onTaskComplete?: (taskId: string, result: UploadResponse) => void;
  onTaskError?: (taskId: string, error: string) => void;
}

const TaskManager: React.FC<TaskManagerProps> = ({
  onTaskComplete,
  onTaskError
}) => {
  const [tasks, setTasks] = useState<Map<string, UploadTask>>(new Map());
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // WebSocket 연결 상태 관리
    const handleConnection = () => setIsConnected(true);
    const handleDisconnection = () => setIsConnected(false);
    const handleError = (error: string) => {
      console.error('WebSocket error in TaskManager:', error);
      setIsConnected(false);
    };

    const unsubscribeConnection = websocketService.onConnection(handleConnection);
    const unsubscribeDisconnection = websocketService.onDisconnection(handleDisconnection);
    const unsubscribeError = websocketService.onError(handleError);

    // 초기 연결 시도
    websocketService.connect().catch(console.error);
    
    return () => {
      unsubscribeConnection();
      unsubscribeDisconnection();
      unsubscribeError();
    };
  }, []);

  const addTask = useCallback((taskId: string, filename: string) => {
    const newTask: UploadTask = {
      task_id: taskId,
      filename,
      status: 'pending',
      progress: 0,
      message: '작업 대기 중...',
      startTime: new Date()
    };

    setTasks(prev => new Map(prev.set(taskId, newTask)));

    // WebSocket 구독
    const handleTaskUpdate = (taskStatus: TaskStatusResponse) => {
      setTasks(prev => {
        const currentTask = prev.get(taskId);
        if (!currentTask) return prev;

        const updatedTask: UploadTask = {
          ...currentTask,
          status: taskStatus.status,
          progress: taskStatus.progress,
          message: taskStatus.message,
          result: taskStatus.result,
          error: taskStatus.error
        };

        return new Map(prev.set(taskId, updatedTask));
      });
    };

    if (isConnected) {
      websocketService.subscribeToTask(taskId, handleTaskUpdate);
    }

    return newTask;
  }, [isConnected]);

  const removeTask = useCallback((taskId: string) => {
    setTasks(prev => {
      const newTasks = new Map(prev);
      newTasks.delete(taskId);
      return newTasks;
    });
    
    // WebSocket 구독 해제
    websocketService.unsubscribeFromTask(taskId);
  }, []);

  const handleTaskComplete = useCallback((taskId: string, result?: any) => {
    if (onTaskComplete && result) {
      onTaskComplete(taskId, result);
    }
    
    // 5초 후 자동 제거
    setTimeout(() => {
      removeTask(taskId);
    }, 5000);
  }, [onTaskComplete, removeTask]);

  const handleTaskError = useCallback((taskId: string, error: string) => {
    if (onTaskError) {
      onTaskError(taskId, error);
    }
  }, [onTaskError]);

  const handleCancel = useCallback((taskId: string) => {
    setTasks(prev => {
      const task = prev.get(taskId);
      if (!task) return prev;

      const updatedTask: UploadTask = {
        ...task,
        status: 'cancelled',
        message: '작업이 취소되었습니다.'
      };

      return new Map(prev.set(taskId, updatedTask));
    });

    // 3초 후 제거
    setTimeout(() => {
      removeTask(taskId);
    }, 3000);
  }, [removeTask]);

  const clearCompletedTasks = () => {
    setTasks(prev => {
      const newTasks = new Map();
      prev.forEach((task, taskId) => {
        if (task.status !== 'completed' && task.status !== 'failed' && task.status !== 'cancelled') {
          newTasks.set(taskId, task);
        } else {
          websocketService.unsubscribeFromTask(taskId);
        }
      });
      return newTasks;
    });
  };

  const activeTasks = Array.from(tasks.values()).filter(
    task => task.status === 'pending' || task.status === 'processing'
  );
  const completedTasks = Array.from(tasks.values()).filter(
    task => task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled'
  );

  // 활성 작업이 없고 완료된 작업도 없으면 렌더링하지 않음
  if (tasks.size === 0) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 w-96 max-w-full z-50">
      <div className="bg-white rounded-lg shadow-lg border border-gray-200">
        {/* 헤더 */}
        <div className="flex items-center justify-between p-3 border-b border-gray-200">
          <div className="flex items-center space-x-2">
            <h3 className="font-medium text-gray-900">작업 진행 상황</h3>
            
            {/* 연결 상태 표시 */}
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400'}`} />
            
            {activeTasks.length > 0 && (
              <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2 py-1 rounded-full">
                {activeTasks.length} 진행 중
              </span>
            )}
          </div>
          
          <div className="flex items-center space-x-1">
            {completedTasks.length > 0 && (
              <button
                onClick={clearCompletedTasks}
                className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 hover:bg-gray-100 rounded"
              >
                완료된 작업 정리
              </button>
            )}
            
            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              {isCollapsed ? (
                <ChevronUpIcon className="h-4 w-4" />
              ) : (
                <ChevronDownIcon className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>

        {/* 작업 목록 */}
        {!isCollapsed && (
          <div className="max-h-80 overflow-y-auto">
            <div className="p-3 space-y-3">
              {/* 활성 작업 */}
              {activeTasks.map(task => (
                <TaskProgress
                  key={task.task_id}
                  task={task}
                  onTaskComplete={handleTaskComplete}
                  onTaskError={handleTaskError}
                  onCancel={handleCancel}
                  showCancelButton={true}
                />
              ))}
              
              {/* 완료된 작업 */}
              {completedTasks.map(task => (
                <TaskProgress
                  key={task.task_id}
                  task={task}
                  onTaskComplete={handleTaskComplete}
                  onTaskError={handleTaskError}
                  onCancel={handleCancel}
                  showCancelButton={false}
                />
              ))}
            </div>
          </div>
        )}

        {/* 연결 상태 메시지 */}
        {!isConnected && (
          <div className="px-3 pb-3">
            <div className="bg-yellow-50 border border-yellow-200 rounded p-2">
              <p className="text-xs text-yellow-800">
                실시간 업데이트 연결이 끊어졌습니다. 페이지를 새로고침해주세요.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export { TaskManager };
export default TaskManager;