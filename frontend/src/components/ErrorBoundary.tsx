import { Component, ErrorInfo, ReactNode } from 'react';
import { ExclamationTriangleIcon, ArrowPathIcon } from '@heroicons/react/24/outline';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorInfo: null
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({
      error,
      errorInfo
    });

    // 에러 로깅
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    
    // 외부 에러 핸들러 호출
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleRetry = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
          <div className="sm:mx-auto sm:w-full sm:max-w-md">
            <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
              <div className="flex flex-col items-center text-center">
                <ExclamationTriangleIcon className="h-12 w-12 text-red-500 mb-4" />
                
                <h2 className="text-lg font-medium text-gray-900 mb-2">
                  문제가 발생했습니다
                </h2>
                
                <p className="text-sm text-gray-600 mb-6">
                  예상치 못한 오류가 발생했습니다. 잠시 후 다시 시도해주세요.
                </p>

                <div className="flex flex-col space-y-3 w-full">
                  <button
                    onClick={this.handleRetry}
                    className="w-full flex justify-center items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <ArrowPathIcon className="h-4 w-4 mr-2" />
                    다시 시도
                  </button>
                  
                  <button
                    onClick={this.handleReload}
                    className="w-full flex justify-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    페이지 새로고침
                  </button>
                </div>

                {/* 개발 모드에서는 에러 세부 정보 표시 */}
                {this.state.error && (
                  <details className="mt-6 w-full">
                    <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
                      개발자 정보 (클릭하여 확장)
                    </summary>
                    <div className="mt-2 p-3 bg-gray-100 rounded text-left">
                      <p className="text-xs text-red-600 font-mono mb-2">
                        {this.state.error.toString()}
                      </p>
                      {this.state.errorInfo && (
                        <pre className="text-xs text-gray-600 font-mono whitespace-pre-wrap overflow-x-auto">
                          {this.state.errorInfo.componentStack}
                        </pre>
                      )}
                    </div>
                  </details>
                )}
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;