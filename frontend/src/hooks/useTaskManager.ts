import { useState, useEffect, useCallback, useRef } from 'react';
import { UploadTask, UploadResponse, TaskStatusResponse } from '../types';
import websocketService from '../services/websocket';
import apiService from '../services/api';

export interface UseTaskManagerOptions {
  onTaskComplete?: (taskId: string, result: UploadResponse) => void;
  onTaskError?: (taskId: string, error: string) => void;
  autoConnect?: boolean;
}

export interface UseTaskManagerReturn {
  tasks: UploadTask[];
  isConnected: boolean;
  connectionState: string;
  
  // Task management
  addTask: (taskId: string, filename: string) => UploadTask;
  removeTask: (taskId: string) => void;
  cancelTask: (taskId: string) => Promise<void>;
  clearCompletedTasks: () => void;
  
  // WebSocket management
  connect: () => Promise<void>;
  disconnect: () => void;
  
  // Utility functions
  getActiveTasksCount: () => number;
  getCompletedTasksCount: () => number;
  getTaskById: (taskId: string) => UploadTask | undefined;
}

export const useTaskManager = (options: UseTaskManagerOptions = {}): UseTaskManagerReturn => {
  const {
    onTaskComplete,
    onTaskError,
    autoConnect = true
  } = options;

  const [tasks, setTasks] = useState<UploadTask[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionState, setConnectionState] = useState<string>('disconnected');
  
  const tasksRef = useRef<Map<string, UploadTask>>(new Map());
  const subscriptionsRef = useRef<Map<string, () => void>>(new Map());

  // WebSocket 이벤트 핸들러
  useEffect(() => {
    const handleConnection = () => {
      setIsConnected(true);
      setConnectionState('connected');
    };

    const handleDisconnection = () => {
      setIsConnected(false);
      setConnectionState('disconnected');
    };

    const handleError = (error: string) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
      setConnectionState('error');
    };

    const unsubscribeConnection = websocketService.onConnection(handleConnection);
    const unsubscribeDisconnection = websocketService.onDisconnection(handleDisconnection);
    const unsubscribeError = websocketService.onError(handleError);

    // 초기 연결 상태 설정
    setIsConnected(websocketService.isConnected());
    setConnectionState(websocketService.getConnectionState());

    // 자동 연결
    if (autoConnect && !websocketService.isConnected()) {
      websocketService.connect().catch(console.error);
    }

    return () => {
      unsubscribeConnection();
      unsubscribeDisconnection();
      unsubscribeError();
      
      // 모든 구독 해제
      subscriptionsRef.current.forEach(unsubscribe => unsubscribe());
      subscriptionsRef.current.clear();
    };
  }, [autoConnect]);

  // tasks 배열을 Map과 동기화
  useEffect(() => {
    setTasks(Array.from(tasksRef.current.values()));
  }, []);

  const updateTask = useCallback((taskId: string, updates: Partial<UploadTask>) => {
    const currentTask = tasksRef.current.get(taskId);
    if (!currentTask) return;

    const updatedTask = { ...currentTask, ...updates };
    tasksRef.current.set(taskId, updatedTask);
    setTasks(Array.from(tasksRef.current.values()));

    // 완료 또는 에러 콜백 호출
    if (updates.status === 'completed' && updates.result && onTaskComplete) {
      onTaskComplete(taskId, updates.result);
    } else if (updates.status === 'failed' && updates.error && onTaskError) {
      onTaskError(taskId, updates.error);
    }
  }, [onTaskComplete, onTaskError]);

  const addTask = useCallback((taskId: string, filename: string): UploadTask => {
    const newTask: UploadTask = {
      task_id: taskId,
      filename,
      status: 'pending',
      progress: 0,
      message: '작업 대기 중...',
      startTime: new Date()
    };

    tasksRef.current.set(taskId, newTask);
    setTasks(Array.from(tasksRef.current.values()));

    // WebSocket 구독 설정
    const handleTaskUpdate = (taskStatus: TaskStatusResponse) => {
      updateTask(taskId, {
        status: taskStatus.status,
        progress: taskStatus.progress,
        message: taskStatus.message,
        result: taskStatus.result,
        error: taskStatus.error
      });
    };

    if (websocketService.isConnected()) {
      websocketService.subscribeToTask(taskId, handleTaskUpdate);
      
      // 구독 해제 함수 저장
      subscriptionsRef.current.set(taskId, () => {
        websocketService.unsubscribeFromTask(taskId, handleTaskUpdate);
      });
    }

    return newTask;
  }, [updateTask]);

  const removeTask = useCallback((taskId: string) => {
    tasksRef.current.delete(taskId);
    setTasks(Array.from(tasksRef.current.values()));

    // 구독 해제
    const unsubscribe = subscriptionsRef.current.get(taskId);
    if (unsubscribe) {
      unsubscribe();
      subscriptionsRef.current.delete(taskId);
    }
  }, []);

  const cancelTask = useCallback(async (taskId: string) => {
    const task = tasksRef.current.get(taskId);
    if (!task || (task.status !== 'pending' && task.status !== 'processing')) {
      return;
    }

    try {
      await apiService.cancelTask(taskId);
      updateTask(taskId, {
        status: 'cancelled',
        message: '작업이 취소되었습니다.'
      });
    } catch (error) {
      console.error('Failed to cancel task:', error);
      updateTask(taskId, {
        status: 'failed',
        error: 'Failed to cancel task',
        message: '작업 취소에 실패했습니다.'
      });
    }
  }, [updateTask]);

  const clearCompletedTasks = useCallback(() => {
    const completedStatuses = ['completed', 'failed', 'cancelled'];
    
    tasksRef.current.forEach((task, taskId) => {
      if (completedStatuses.includes(task.status)) {
        // 구독 해제
        const unsubscribe = subscriptionsRef.current.get(taskId);
        if (unsubscribe) {
          unsubscribe();
          subscriptionsRef.current.delete(taskId);
        }
        
        tasksRef.current.delete(taskId);
      }
    });

    setTasks(Array.from(tasksRef.current.values()));
  }, []);

  const connect = useCallback(async () => {
    setConnectionState('connecting');
    try {
      await websocketService.connect();
    } catch (error) {
      setConnectionState('error');
      throw error;
    }
  }, []);

  const disconnect = useCallback(() => {
    websocketService.disconnect();
    setIsConnected(false);
    setConnectionState('disconnected');
  }, []);

  const getActiveTasksCount = useCallback(() => {
    return Array.from(tasksRef.current.values()).filter(
      task => task.status === 'pending' || task.status === 'processing'
    ).length;
  }, []);

  const getCompletedTasksCount = useCallback(() => {
    return Array.from(tasksRef.current.values()).filter(
      task => task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled'
    ).length;
  }, []);

  const getTaskById = useCallback((taskId: string) => {
    return tasksRef.current.get(taskId);
  }, []);

  return {
    tasks,
    isConnected,
    connectionState,
    addTask,
    removeTask,
    cancelTask,
    clearCompletedTasks,
    connect,
    disconnect,
    getActiveTasksCount,
    getCompletedTasksCount,
    getTaskById
  };
};