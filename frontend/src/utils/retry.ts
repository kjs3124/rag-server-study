export interface RetryOptions {
  maxAttempts?: number;
  delay?: number;
  backoff?: 'linear' | 'exponential';
  maxDelay?: number;
  retryCondition?: (error: any) => boolean;
  onRetry?: (attempt: number, error: any) => void;
}

export interface RetryResult<T> {
  success: boolean;
  data?: T;
  error?: any;
  attempts: number;
}

/**
 * 비동기 함수를 지정된 조건으로 재시도하는 유틸리티
 */
export async function retry<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<RetryResult<T>> {
  const {
    maxAttempts = 3,
    delay = 1000,
    backoff = 'exponential',
    maxDelay = 10000,
    retryCondition = (_error) => true,
    onRetry
  } = options;

  let lastError: any;
  
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const data = await fn();
      return {
        success: true,
        data,
        attempts: attempt
      };
    } catch (error) {
      lastError = error;
      
      // 마지막 시도인 경우 또는 재시도 조건에 맞지 않는 경우
      if (attempt === maxAttempts || !retryCondition(error)) {
        return {
          success: false,
          error: lastError,
          attempts: attempt
        };
      }
      
      // 재시도 콜백 호출
      if (onRetry) {
        onRetry(attempt, error);
      }
      
      // 재시도 전 대기
      if (attempt < maxAttempts) {
        const waitTime = calculateDelay(attempt, delay, backoff, maxDelay);
        await sleep(waitTime);
      }
    }
  }
  
  return {
    success: false,
    error: lastError,
    attempts: maxAttempts
  };
}

/**
 * 재시도 간격 계산
 */
function calculateDelay(
  attempt: number,
  baseDelay: number,
  backoff: 'linear' | 'exponential',
  maxDelay: number
): number {
  let delay: number;
  
  switch (backoff) {
    case 'linear':
      delay = baseDelay * attempt;
      break;
    case 'exponential':
      delay = baseDelay * Math.pow(2, attempt - 1);
      break;
    default:
      delay = baseDelay;
  }
  
  return Math.min(delay, maxDelay);
}

/**
 * 지정된 시간만큼 대기
 */
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * 네트워크 오류인지 확인
 */
export function isNetworkError(error: any): boolean {
  if (!error) return false;
  
  // Axios 에러 확인
  if (error.code) {
    return ['ECONNABORTED', 'ENOTFOUND', 'ECONNREFUSED', 'ETIMEDOUT'].includes(error.code);
  }
  
  // HTTP 상태 코드 확인
  if (error.response && error.response.status) {
    const status = error.response.status;
    return status >= 500 || status === 408 || status === 429;
  }
  
  // 일반적인 네트워크 오류 메시지 확인
  const message = error.message || '';
  return message.includes('Network Error') || 
         message.includes('timeout') || 
         message.includes('connection');
}

/**
 * 재시도 가능한 오류인지 확인
 */
export function isRetryableError(error: any): boolean {
  // 네트워크 오류는 재시도 가능
  if (isNetworkError(error)) return true;
  
  // 4xx 클라이언트 오류는 일반적으로 재시도하지 않음 (429 제외)
  if (error.response && error.response.status) {
    const status = error.response.status;
    if (status >= 400 && status < 500) {
      return status === 408 || status === 429; // 타임아웃, Too Many Requests
    }
  }
  
  return false;
}

/**
 * API 호출용 기본 재시도 설정
 */
export const defaultApiRetryOptions: RetryOptions = {
  maxAttempts: 3,
  delay: 1000,
  backoff: 'exponential',
  maxDelay: 5000,
  retryCondition: isRetryableError,
  onRetry: (attempt, _error) => {
    console.warn(`API call failed, retrying... (${attempt}/3)`, _error.message || _error);
  }
};

/**
 * WebSocket 연결용 기본 재시도 설정
 */
export const defaultWebSocketRetryOptions: RetryOptions = {
  maxAttempts: 5,
  delay: 1000,
  backoff: 'exponential',
  maxDelay: 10000,
  retryCondition: (_error) => true, // WebSocket 오류는 모두 재시도
  onRetry: (attempt, _error) => {
    console.warn(`WebSocket connection failed, retrying... (${attempt}/5)`, _error);
  }
};

/**
 * 파일 업로드용 기본 재시도 설정
 */
export const defaultUploadRetryOptions: RetryOptions = {
  maxAttempts: 2, // 업로드는 재시도 횟수를 적게
  delay: 2000,
  backoff: 'linear',
  maxDelay: 5000,
  retryCondition: isNetworkError, // 네트워크 오류만 재시도
  onRetry: (attempt, _error) => {
    console.warn(`File upload failed, retrying... (${attempt}/2)`, _error);
  }
};