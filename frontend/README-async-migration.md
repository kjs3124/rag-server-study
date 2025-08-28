# Frontend Async Migration Guide

## 개요
기존 동기 API를 비동기 API로 마이그레이션하여 실시간 진행률 추적 및 사용자 경험을 개선했습니다.

## 주요 변경사항

### 1. 새로운 컴포넌트 구조

#### 핵심 컴포넌트
- **WebSocketService** (`src/services/websocket.ts`): WebSocket 연결 관리 및 실시간 통신
- **TaskManager** (`src/components/TaskManager.tsx`): 다중 작업 진행 상황 관리
- **TaskProgress** (`src/components/TaskProgress.tsx`): 개별 작업 진행 상황 표시
- **useTaskManager** (`src/hooks/useTaskManager.ts`): 작업 관리 React 훅

#### 에러 처리 및 UX 개선
- **ErrorBoundary** (`src/components/ErrorBoundary.tsx`): React 에러 경계 처리
- **NotificationSystem** (`src/components/NotificationSystem.tsx`): 사용자 알림 시스템
- **Retry Utility** (`src/utils/retry.ts`): 실패한 작업 재시도 로직

### 2. API 변경사항

#### 새로운 비동기 메서드
```typescript
// 비동기 파일 업로드
apiService.uploadDocumentAsync(file: File) → AsyncTaskResponse

// 비동기 URL 크롤링  
apiService.crawlUrlAsync(url: string, options?: CrawlOptions) → AsyncTaskResponse

// 작업 상태 조회
apiService.getTaskStatus(taskId: string) → TaskStatusResponse

// 작업 관리
apiService.getTasks(limit?: number, status?: string) → TaskStatusResponse[]
apiService.cancelTask(taskId: string) → { success: boolean; message: string }
```

#### 기존 동기 메서드 유지
기존 동기 메서드들은 하위 호환성을 위해 그대로 유지됩니다.

### 3. 사용법

#### 기본 사용
```typescript
import { DocumentUpload, TaskManager, ErrorBoundary } from './components';
import { useNotifications } from './components/NotificationSystem';

function App() {
  const { showSuccess, showError } = useNotifications();
  
  const handleUploadSuccess = (result) => {
    showSuccess('업로드 완료', `${result.chunks_created}개의 청크가 생성되었습니다.`);
  };

  const handleUploadError = (taskId, error) => {
    showError('업로드 실패', error);
  };

  return (
    <ErrorBoundary>
      <div className="app">
        <DocumentUpload
          documents={documents}
          onUploadSuccess={handleUploadSuccess}
          onUploadError={handleUploadError}
          useAsyncMode={true} // 비동기 모드 활성화
        />
        <TaskManager /> {/* 우측 하단에 작업 진행 상황 표시 */}
      </div>
    </ErrorBoundary>
  );
}
```

#### 수동 작업 관리
```typescript
import { useTaskManager } from './hooks/useTaskManager';

function CustomComponent() {
  const taskManager = useTaskManager({
    onTaskComplete: (taskId, result) => {
      console.log('작업 완료:', result);
    },
    onTaskError: (taskId, error) => {
      console.error('작업 실패:', error);
    }
  });

  const handleFileUpload = async (file) => {
    try {
      const response = await apiService.uploadDocumentAsync(file);
      if (response.success) {
        taskManager.addTask(response.task_id, file.name);
      }
    } catch (error) {
      console.error('Upload failed:', error);
    }
  };

  return (
    <div>
      <p>활성 작업: {taskManager.getActiveTasksCount()}</p>
      <p>연결 상태: {taskManager.connectionState}</p>
    </div>
  );
}
```

### 4. WebSocket 실시간 통신

#### 연결 관리
```typescript
import websocketService from './services/websocket';

// 수동 연결
await websocketService.connect();

// 작업 구독
websocketService.subscribeToTask(taskId, (status) => {
  console.log('작업 업데이트:', status);
});

// 연결 상태 확인
const isConnected = websocketService.isConnected();
const state = websocketService.getConnectionState(); // 'connected' | 'connecting' | 'disconnected'
```

#### 이벤트 처리
```typescript
// 연결 이벤트
websocketService.onConnection(() => {
  console.log('WebSocket 연결됨');
});

// 에러 이벤트
websocketService.onError((error) => {
  console.error('WebSocket 에러:', error);
});

// 연결 해제 이벤트
websocketService.onDisconnection(() => {
  console.log('WebSocket 연결 해제됨');
});
```

### 5. 에러 처리 및 재시도

#### 자동 재시도
모든 중요한 작업은 자동 재시도 로직을 포함합니다:
- **파일 업로드**: 네트워크 오류 시 최대 2회 재시도
- **URL 크롤링**: 일반 API 오류 시 최대 3회 재시도
- **WebSocket 연결**: 연결 실패 시 최대 5회 재시도 (지수 백오프)

#### 수동 재시도
```typescript
import { retry, defaultApiRetryOptions } from './utils/retry';

const result = await retry(
  async () => {
    // 재시도할 작업
    return await someApiCall();
  },
  {
    ...defaultApiRetryOptions,
    onRetry: (attempt, error) => {
      console.log(`재시도 ${attempt}:`, error.message);
    }
  }
);

if (!result.success) {
  console.error('최종 실패:', result.error);
}
```

### 6. 알림 시스템

#### 알림 타입
```typescript
const { showSuccess, showError, showWarning, showInfo } = useNotifications();

// 성공 알림 (5초 후 자동 사라짐)
showSuccess('업로드 완료', '파일이 성공적으로 업로드되었습니다.');

// 에러 알림 (수동으로 닫을 때까지 유지)
showError('업로드 실패', '파일 업로드 중 오류가 발생했습니다.');

// 경고 알림 (5초 후 자동 사라짐)
showWarning('주의', '파일 크기가 큽니다.');

// 정보 알림 (5초 후 자동 사라짐)
showInfo('알림', '새로운 기능이 추가되었습니다.');
```

#### 액션 포함 알림
```typescript
showError('연결 실패', '서버에 연결할 수 없습니다.', {
  action: {
    label: '다시 시도',
    onClick: () => reconnect()
  }
});
```

## 마이그레이션 체크리스트

### 기본 설정
- [ ] `useAsyncMode={true}` 속성을 DocumentUpload 컴포넌트에 추가
- [ ] TaskManager 컴포넌트를 앱에 추가
- [ ] ErrorBoundary로 앱 감싸기
- [ ] NotificationSystem 컴포넌트 및 훅 설정

### 고급 설정 (선택사항)
- [ ] 커스텀 에러 처리 로직 구현
- [ ] 작업 완료/실패 콜백 설정
- [ ] WebSocket 이벤트 핸들러 커스터마이즈
- [ ] 재시도 정책 커스터마이즈

## 성능 고려사항

1. **동시 작업 제한**: UI에서 최대 3개의 동시 작업으로 제한
2. **WebSocket 연결 관리**: 자동 재연결 및 연결 상태 모니터링
3. **메모리 관리**: 완료된 작업 자동 정리 (5초 후)
4. **에러 복구**: 네트워크 오류 및 서버 오류에 대한 강건한 처리

## 문제 해결

### WebSocket 연결 문제
```typescript
// 연결 상태 확인
if (!websocketService.isConnected()) {
  await websocketService.connect();
}
```

### 작업 진행 상황이 업데이트되지 않는 경우
1. WebSocket 연결 상태 확인
2. 서버의 WebSocket 엔드포인트 상태 확인
3. 브라우저 개발자 도구에서 WebSocket 메시지 확인

### 파일 업로드 실패
1. 네트워크 연결 확인
2. 파일 크기 및 형식 확인
3. 서버 로그에서 에러 메시지 확인

## 개발 모드 디버깅

개발 모드에서는 다음과 같은 추가 정보를 확인할 수 있습니다:
- ErrorBoundary에서 상세한 에러 스택 트레이스
- 콘솔에서 WebSocket 연결 상태 및 메시지
- 재시도 로직의 상세한 로그
- 작업 진행 상황의 실시간 업데이트

## 프로덕션 배포 고려사항

1. **환경 변수**: WebSocket URL을 환경변수로 설정
2. **에러 리포팅**: 프로덕션에서 에러 리포팅 서비스 연동
3. **성능 모니터링**: 작업 완료율 및 에러율 모니터링
4. **사용자 피드백**: 사용자가 문제를 쉽게 보고할 수 있는 방법 제공