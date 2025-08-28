# 비동기 문서 처리 API 가이드

RAG 시스템의 새로운 비동기 문서 처리 API 사용법을 설명합니다.

## 🔄 아키텍처 개요

### 기존 동기 방식의 문제점
- **HTTP 연결 대기**: 파일 파싱 완료까지 연결 유지 (최대 몇 분)
- **타임아웃 위험**: 큰 파일이나 웹 크롤링 시 요청 타임아웃
- **확장성 제한**: 동시 처리 불가능, 서버 리소스 과부하
- **사용자 경험 저하**: 진행상황을 알 수 없음

### 새로운 비동기 방식
```
Client → API → Task Queue → Background Worker → Status Update
          ↓                                           ↑
      Task ID 즉시 반환                    WebSocket/Polling으로 실시간 상태 확인
```

## 🚀 빠른 시작

### 1. 비동기 파일 업로드

**요청**:
```bash
curl -X POST "http://localhost:8099/api/v1/documents/async/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf"
```

**응답**:
```json
{
  "success": true,
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "파일 업로드가 완료되었습니다. 파싱 작업이 시작됩니다.",
  "estimated_time": "약 2분 소요 예상"
}
```

### 2. 비동기 웹 크롤링

**요청**:
```bash
curl -X POST "http://localhost:8099/api/v1/documents/async/crawl" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/article",
    "max_depth": 1,
    "same_domain": true
  }'
```

**응답**:
```json
{
  "success": true,
  "task_id": "660e8400-e29b-41d4-a716-446655440001",
  "message": "웹 크롤링 작업이 시작됩니다: https://example.com/article",
  "estimated_time": "약 4분 소요 예상"
}
```

### 3. 작업 상태 조회

**요청**:
```bash
curl "http://localhost:8099/api/v1/documents/async/tasks/550e8400-e29b-41d4-a716-446655440000"
```

**응답**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_type": "file_upload",
  "status": "processing",
  "progress": 45,
  "message": "파일 파싱 중입니다",
  "created_at": "2024-08-27T10:30:00",
  "started_at": "2024-08-27T10:30:05",
  "completed_at": null,
  "result": null,
  "error": null
}
```

## 📡 WebSocket 실시간 업데이트

### JavaScript WebSocket 연결

```javascript
// WebSocket 연결
const clientId = 'user-' + Date.now();
const ws = new WebSocket(`ws://localhost:8099/api/v1/ws/${clientId}`);

// 연결 성공
ws.onopen = function() {
    console.log('WebSocket 연결됨');
    
    // 특정 작업 구독
    ws.send(JSON.stringify({
        type: 'subscribe',
        task_id: '550e8400-e29b-41d4-a716-446655440000'
    }));
};

// 메시지 수신
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    if (data.type === 'task_update') {
        console.log(`작업 ${data.task_id} 상태:`, data.status);
        console.log(`진행률: ${data.progress}%`);
        console.log(`메시지: ${data.message}`);
        
        // UI 업데이트
        updateProgressBar(data.progress);
        updateStatusMessage(data.message);
        
        if (data.status === 'completed') {
            console.log('작업 완료:', data.result);
            handleTaskComplete(data.result);
        } else if (data.status === 'failed') {
            console.log('작업 실패:', data.error);
            handleTaskError(data.error);
        }
    }
};

// 연결 해제
ws.onclose = function() {
    console.log('WebSocket 연결 해제됨');
};

// 에러 처리
ws.onerror = function(error) {
    console.error('WebSocket 에러:', error);
};
```

### Python WebSocket 클라이언트

```python
import asyncio
import websockets
import json

async def watch_task(task_id):
    uri = f"ws://localhost:8099/api/v1/ws/python-client-{int(time.time())}"
    
    async with websockets.connect(uri) as websocket:
        # 작업 구독
        await websocket.send(json.dumps({
            "type": "subscribe",
            "task_id": task_id
        }))
        
        # 메시지 수신
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                if data["type"] == "task_update":
                    print(f"상태: {data['status']}, 진행률: {data['progress']}%")
                    print(f"메시지: {data['message']}")
                    
                    if data["status"] in ["completed", "failed"]:
                        break
                        
            except websockets.exceptions.ConnectionClosed:
                break

# 사용 예시
asyncio.run(watch_task("550e8400-e29b-41d4-a716-446655440000"))
```

## 🔧 API 엔드포인트 상세

### 파일 업로드 
- **POST** `/api/v1/documents/async/upload`
- **Form Data**: `file` (파일)
- **응답**: `TaskResponse` (task_id 포함)

### 웹 크롤링
- **POST** `/api/v1/documents/async/crawl`
- **Body**: `UrlCrawlRequest`
- **응답**: `TaskResponse` (task_id 포함)

### 작업 상태 조회
- **GET** `/api/v1/documents/async/tasks/{task_id}`
- **응답**: `TaskStatusResponse`

### 작업 목록 조회
- **GET** `/api/v1/documents/async/tasks`
- **Query Params**: `limit`, `status`
- **응답**: `List[TaskStatusResponse]`

### 작업 취소
- **DELETE** `/api/v1/documents/async/tasks/{task_id}`
- **응답**: 취소 결과

### 작업 결과 조회
- **GET** `/api/v1/documents/async/tasks/{task_id}/result`
- **응답**: 완료된 작업의 상세 결과 (청크 데이터 포함)

## 📊 작업 상태

### 상태 종류
- `pending`: 대기 중 (작업 큐에서 대기)
- `processing`: 처리 중 (백그라운드에서 실행 중)
- `completed`: 완료 (성공적으로 완료됨)
- `failed`: 실패 (에러 발생)
- `cancelled`: 취소됨 (사용자가 취소)

### 진행률 (0-100%)
- **파일 업로드**: 20% (파싱 시작) → 80% (파싱 완료) → 100% (저장 완료)
- **웹 크롤링**: 10% (시작) → 30% (분석) → 90% (완료) → 100% (저장)

## 🌟 프론트엔드 통합 예시

### React Hook 예시

```javascript
import { useState, useEffect } from 'react';

function useAsyncTask(taskId) {
    const [task, setTask] = useState(null);
    const [ws, setWs] = useState(null);
    
    useEffect(() => {
        if (!taskId) return;
        
        // WebSocket 연결
        const clientId = 'react-' + Date.now();
        const websocket = new WebSocket(`ws://localhost:8099/api/v1/ws/${clientId}`);
        
        websocket.onopen = () => {
            // 작업 구독
            websocket.send(JSON.stringify({
                type: 'subscribe',
                task_id: taskId
            }));
        };
        
        websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'task_update') {
                setTask(data);
            }
        };
        
        setWs(websocket);
        
        return () => {
            websocket.close();
        };
    }, [taskId]);
    
    return task;
}

// 사용 예시
function DocumentUpload() {
    const [taskId, setTaskId] = useState(null);
    const task = useAsyncTask(taskId);
    
    const handleUpload = async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/api/v1/documents/async/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        setTaskId(result.task_id);
    };
    
    return (
        <div>
            <input type="file" onChange={(e) => handleUpload(e.target.files[0])} />
            
            {task && (
                <div>
                    <div>상태: {task.status}</div>
                    <div>진행률: {task.progress}%</div>
                    <div>메시지: {task.message}</div>
                    <progress value={task.progress} max="100" />
                </div>
            )}
        </div>
    );
}
```

## ⚙️ 설정 및 배포

### 메모리 기반 작업 관리
Redis 대신 메모리 기반 작업 관리 시스템을 사용합니다:

- **장점**: 별도 설치 불필요, 간단한 구성
- **단점**: 서버 재시작 시 작업 상태 손실
- **권장 사항**: 프로덕션 환경에서는 Redis 또는 데이터베이스 사용 고려

### Docker Compose 예시
```yaml
version: '3.8'
services:
  rag-api:
    build: .
    ports:
      - "8099:8099"
    environment:
      - PYTHONUNBUFFERED=1
```

## 🚨 에러 처리 및 모니터링

### 에러 유형
- **작업 생성 실패**: 잘못된 파라미터, 파일 오류
- **처리 중 실패**: 파싱 에러, 네트워크 오류
- **시스템 에러**: Redis 연결 실패, 디스크 공간 부족

### 모니터링 대상
- 작업 큐 크기
- 평균 처리 시간  
- 실패율
- Redis 메모리 사용량

## 📈 성능 최적화 팁

1. **작업 큐 모니터링**: 큐가 너무 길어지면 워커 추가
2. **Redis 메모리 관리**: TTL 설정으로 완료된 작업 자동 정리
3. **WebSocket 연결 관리**: 불필요한 구독 해제
4. **파일 크기 제한**: 너무 큰 파일은 분할 처리
5. **백그라운드 워커 확장**: 여러 인스턴스로 병렬 처리

## 🔗 참고 링크

- [FastAPI WebSocket 문서](https://fastapi.tiangolo.com/advanced/websockets/)
- [Redis Python 클라이언트](https://redis-py.readthedocs.io/)
- [Swagger UI 접속](http://localhost:8099/docs)