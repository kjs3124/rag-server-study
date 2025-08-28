"""로그 모니터링 및 분석 유틸리티"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import Counter
import re

class LogMonitor:
    """에러 로그 모니터링 및 분석"""
    
    def __init__(self, log_file: str = "logs/app_errors.log"):
        self.log_file = Path(log_file)
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """최근 에러 요약 통계"""
        if not self.log_file.exists():
            return {"status": "no_logs", "total_errors": 0}
        
        # 로그 파싱
        errors = self._parse_recent_errors(hours)
        
        if not errors:
            return {"status": "no_recent_errors", "total_errors": 0}
        
        # 통계 생성
        error_types = Counter(error.get("error_type", "Unknown") for error in errors)
        contexts = Counter(error.get("context", "Unknown") for error in errors)
        levels = Counter(error.get("level", "Unknown") for error in errors)
        
        return {
            "status": "active_errors",
            "total_errors": len(errors),
            "time_range_hours": hours,
            "error_types": dict(error_types.most_common(10)),
            "contexts": dict(contexts.most_common(10)),
            "levels": dict(levels),
            "latest_errors": errors[:5],  # 최신 5개
            "most_common_error": error_types.most_common(1)[0] if error_types else None
        }
    
    def get_error_trends(self, days: int = 7) -> Dict[str, Any]:
        """에러 트렌드 분석 (시간대별)"""
        if not self.log_file.exists():
            return {"status": "no_logs"}
        
        # 일별 에러 수 집계
        daily_counts = {}
        hourly_counts = {}
        
        errors = self._parse_recent_errors(days * 24)
        
        for error in errors:
            timestamp_str = error.get("timestamp", "")
            if not timestamp_str:
                continue
                
            try:
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                date_key = dt.date().isoformat()
                hour_key = dt.hour
                
                daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
                hourly_counts[hour_key] = hourly_counts.get(hour_key, 0) + 1
                
            except ValueError:
                continue
        
        return {
            "status": "success",
            "daily_errors": dict(sorted(daily_counts.items())),
            "hourly_distribution": dict(sorted(hourly_counts.items())),
            "peak_hour": max(hourly_counts.items(), key=lambda x: x[1]) if hourly_counts else None,
            "total_days_analyzed": days,
            "total_errors": len(errors)
        }
    
    def find_similar_errors(self, error_message: str, limit: int = 10) -> List[Dict]:
        """유사한 에러 패턴 검색"""
        if not self.log_file.exists():
            return []
        
        errors = self._parse_recent_errors(24 * 30)  # 30일간
        similar_errors = []
        
        # 간단한 텍스트 유사도 체크
        search_terms = error_message.lower().split()[:5]  # 처음 5단어만
        
        for error in errors:
            error_msg = error.get("error_message", "").lower()
            
            # 검색어가 모두 포함된 에러 찾기
            if all(term in error_msg for term in search_terms):
                similar_errors.append(error)
                
            if len(similar_errors) >= limit:
                break
        
        return similar_errors
    
    def get_performance_alerts(self, threshold_seconds: float = 5.0) -> List[Dict]:
        """성능 경고 조회"""
        if not self.log_file.exists():
            return []
        
        performance_warnings = []
        errors = self._parse_recent_errors(24)  # 24시간
        
        for error in errors:
            if error.get("context") == "performance_monitoring":
                extra_data = error.get("extra_data", {})
                duration = extra_data.get("duration_seconds", 0)
                
                if duration >= threshold_seconds:
                    performance_warnings.append({
                        "timestamp": error.get("timestamp"),
                        "operation": extra_data.get("operation"),
                        "duration_seconds": duration,
                        "threshold_seconds": extra_data.get("threshold_seconds"),
                        "performance_ratio": extra_data.get("performance_ratio", 1.0),
                        "error_id": error.get("error_id")
                    })
        
        return sorted(performance_warnings, key=lambda x: x["duration_seconds"], reverse=True)
    
    def _parse_recent_errors(self, hours: int) -> List[Dict]:
        """최근 에러 로그 파싱"""
        if not self.log_file.exists():
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        errors = []
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    # JSON 부분 추출 (로그 메시지에서)
                    json_match = re.search(r'\{.*\}', line)
                    if not json_match:
                        continue
                    
                    try:
                        error_data = json.loads(json_match.group())
                        
                        # 시간 필터링
                        timestamp_str = error_data.get("timestamp", "")
                        if timestamp_str:
                            error_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            if error_time >= cutoff_time:
                                errors.append(error_data)
                                
                    except (json.JSONDecodeError, ValueError):
                        continue
                        
        except Exception as e:
            print(f"로그 파싱 에러: {e}")
            return []
        
        # 최신 순 정렬
        errors.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return errors

# 글로벌 로그 모니터 인스턴스
log_monitor = LogMonitor()

def get_system_health() -> Dict[str, Any]:
    """시스템 상태 종합 요약"""
    error_summary = log_monitor.get_error_summary(hours=1)  # 최근 1시간
    performance_alerts = log_monitor.get_performance_alerts(threshold_seconds=3.0)
    
    # 상태 판정
    if error_summary["total_errors"] == 0:
        health_status = "healthy"
    elif error_summary["total_errors"] < 5:
        health_status = "warning"
    else:
        health_status = "critical"
    
    return {
        "health_status": health_status,
        "error_summary": error_summary,
        "performance_alerts": performance_alerts[:5],  # 상위 5개만
        "timestamp": datetime.now().isoformat()
    }