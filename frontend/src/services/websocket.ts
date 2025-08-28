import { WebSocketMessage, TaskStatusResponse } from '../types';
import { retry, defaultWebSocketRetryOptions } from '../utils/retry';

type TaskUpdateCallback = (taskStatus: TaskStatusResponse) => void;
type ErrorCallback = (error: string) => void;
type ConnectionCallback = () => void;

export class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 1000;
  private subscriptions = new Set<string>();
  
  // Event callbacks
  private taskUpdateCallbacks = new Map<string, TaskUpdateCallback[]>();
  private errorCallbacks: ErrorCallback[] = [];
  private connectionCallbacks: ConnectionCallback[] = [];
  private disconnectionCallbacks: ConnectionCallback[] = [];

  constructor(baseUrl: string = 'ws://127.0.0.1:8099') {
    this.url = `${baseUrl}/api/v1/ws/client-${this.generateClientId()}`;
  }

  private generateClientId(): string {
    return Math.random().toString(36).substring(2, 15) + 
           Math.random().toString(36).substring(2, 15);
  }

  connect(): Promise<void> {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return Promise.resolve();
    }

    return retry(
      () => this.connectInternal(),
      {
        ...defaultWebSocketRetryOptions,
        onRetry: (attempt, error) => {
          console.warn(`WebSocket connection attempt ${attempt} failed:`, error);
          this.errorCallbacks.forEach(callback => 
            callback(`연결 시도 중... (${attempt}/${defaultWebSocketRetryOptions.maxAttempts})`)
          );
        }
      }
    ).then(result => {
      if (!result.success) {
        throw new Error(`WebSocket connection failed after ${result.attempts} attempts: ${result.error?.message}`);
      }
    });
  }

  private connectInternal(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          this.connectionCallbacks.forEach(callback => callback());
          
          // 기존 구독 재설정
          this.subscriptions.forEach(taskId => {
            this.sendMessage({ type: 'subscribe', task_id: taskId });
          });
          
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            this.handleMessage(JSON.parse(event.data));
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
            this.errorCallbacks.forEach(callback => 
              callback('메시지 파싱 오류가 발생했습니다.')
            );
          }
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket disconnected:', event.code, event.reason);
          this.disconnectionCallbacks.forEach(callback => callback());
          
          // 정상적인 종료가 아닌 경우에만 재연결
          if (!event.wasClean && event.code !== 1000) {
            this.handleReconnect();
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.errorCallbacks.forEach(callback => 
            callback('WebSocket 연결 오류가 발생했습니다.')
          );
          reject(new Error('WebSocket connection failed'));
        };

        // 연결 타임아웃
        setTimeout(() => {
          if (this.ws && this.ws.readyState !== WebSocket.OPEN) {
            this.ws?.close();
            reject(new Error('WebSocket connection timeout'));
          }
        }, 10000);

      } catch (error) {
        reject(error);
      }
    });
  }

  private handleMessage(message: WebSocketMessage) {
    switch (message.type) {
      case 'task_update':
        if (message.task_id) {
          const taskStatus: TaskStatusResponse = {
            task_id: message.task_id,
            task_type: 'upload', // default type
            status: message.status || 'processing',
            progress: message.progress || 0,
            message: message.message || '',
            created_at: new Date().toISOString(),
            result: message.result
          };
          
          this.notifyTaskUpdate(message.task_id, taskStatus);
        }
        break;

      case 'connection':
        console.log('Connection acknowledged:', message.message);
        break;

      case 'error':
        console.error('WebSocket server error:', message.error);
        this.errorCallbacks.forEach(callback => 
          callback(message.error || 'Unknown server error')
        );
        break;

      default:
        console.warn('Unknown message type:', message.type);
    }
  }

  private handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Reconnecting... attempt ${this.reconnectAttempts}`);
      
      setTimeout(() => {
        this.connect().catch(error => {
          console.error('Reconnection failed:', error);
        });
      }, this.reconnectInterval * this.reconnectAttempts);
    } else {
      console.error('Max reconnection attempts reached');
      this.errorCallbacks.forEach(callback => 
        callback('Connection lost. Please refresh the page.')
      );
    }
  }

  private sendMessage(message: Partial<WebSocketMessage>) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected, message not sent:', message);
    }
  }

  subscribeToTask(taskId: string, callback: TaskUpdateCallback) {
    // 콜백 등록
    if (!this.taskUpdateCallbacks.has(taskId)) {
      this.taskUpdateCallbacks.set(taskId, []);
    }
    this.taskUpdateCallbacks.get(taskId)!.push(callback);
    
    // 구독 목록에 추가
    this.subscriptions.add(taskId);
    
    // 서버에 구독 요청
    this.sendMessage({
      type: 'subscribe',
      task_id: taskId
    });
  }

  unsubscribeFromTask(taskId: string, callback?: TaskUpdateCallback) {
    if (callback) {
      // 특정 콜백만 제거
      const callbacks = this.taskUpdateCallbacks.get(taskId);
      if (callbacks) {
        const index = callbacks.indexOf(callback);
        if (index > -1) {
          callbacks.splice(index, 1);
          if (callbacks.length === 0) {
            this.taskUpdateCallbacks.delete(taskId);
            this.subscriptions.delete(taskId);
            this.sendMessage({ type: 'unsubscribe', task_id: taskId });
          }
        }
      }
    } else {
      // 모든 콜백 제거
      this.taskUpdateCallbacks.delete(taskId);
      this.subscriptions.delete(taskId);
      this.sendMessage({ type: 'unsubscribe', task_id: taskId });
    }
  }

  private notifyTaskUpdate(taskId: string, taskStatus: TaskStatusResponse) {
    const callbacks = this.taskUpdateCallbacks.get(taskId);
    if (callbacks) {
      callbacks.forEach(callback => callback(taskStatus));
    }
  }

  // 이벤트 리스너 관리
  onError(callback: ErrorCallback) {
    this.errorCallbacks.push(callback);
    return () => {
      const index = this.errorCallbacks.indexOf(callback);
      if (index > -1) this.errorCallbacks.splice(index, 1);
    };
  }

  onConnection(callback: ConnectionCallback) {
    this.connectionCallbacks.push(callback);
    return () => {
      const index = this.connectionCallbacks.indexOf(callback);
      if (index > -1) this.connectionCallbacks.splice(index, 1);
    };
  }

  onDisconnection(callback: ConnectionCallback) {
    this.disconnectionCallbacks.push(callback);
    return () => {
      const index = this.disconnectionCallbacks.indexOf(callback);
      if (index > -1) this.disconnectionCallbacks.splice(index, 1);
    };
  }

  disconnect() {
    this.subscriptions.clear();
    this.taskUpdateCallbacks.clear();
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  getConnectionState(): string {
    if (!this.ws) return 'disconnected';
    
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING: return 'connecting';
      case WebSocket.OPEN: return 'connected';
      case WebSocket.CLOSING: return 'closing';
      case WebSocket.CLOSED: return 'disconnected';
      default: return 'unknown';
    }
  }
}

// 싱글톤 인스턴스
export const websocketService = new WebSocketService();
export default websocketService;