import React from 'react';
import { HealthStatus } from '../types';

interface HeaderProps {
  healthStatus: HealthStatus | null;
}

const Header: React.FC<HeaderProps> = ({ healthStatus }) => {
  const getStatusColor = () => {
    if (!healthStatus) return 'bg-gray-400';
    return healthStatus.success ? 'bg-green-500' : 'bg-red-500';
  };

  const getStatusText = () => {
    if (!healthStatus) return 'Connecting...';
    return healthStatus.success ? 'Connected' : 'Disconnected';
  };

  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-4">
          <div className="flex items-center">
            <h1 className="text-2xl font-bold text-gray-900">
              RAG System Test UI
            </h1>
          </div>
          
          <div className="flex items-center space-x-4">
            {/* API 상태 표시 */}
            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${getStatusColor()}`}></div>
              <span className="text-sm text-gray-600">{getStatusText()}</span>
            </div>
            
            {/* 연결 상태 표시 */}
            {healthStatus && healthStatus.success && (
              <div className="text-sm text-gray-500">
                System: Online
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;