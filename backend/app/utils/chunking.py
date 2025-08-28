"""
청킹 관련 유틸리티 함수들
문서 청킹 파라미터 처리 및 검증 로직 통합
"""

from typing import Optional, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class ChunkingConstants:
    """청킹 관련 상수 정의"""
    
    # 기본값
    DEFAULT_CHUNK_SIZE = 1000
    DEFAULT_CHUNK_OVERLAP_RATIO = 0.1  # 10%
    
    # 제한값
    MIN_CHUNK_SIZE = 100
    MAX_CHUNK_SIZE = 8000
    MIN_CHUNK_OVERLAP = 0
    MAX_CHUNK_OVERLAP = 1000
    MAX_OVERLAP_RATIO = 0.5  # 청크 크기의 50%까지만
    
    # 에러 메시지
    ERROR_MESSAGES = {
        "chunk_size_range": f"청크 크기는 {MIN_CHUNK_SIZE}-{MAX_CHUNK_SIZE} 범위여야 합니다",
        "chunk_overlap_range": f"청크 오버랩은 {MIN_CHUNK_OVERLAP}-{MAX_CHUNK_OVERLAP} 범위여야 합니다",
        "overlap_ratio": f"청크 오버랩은 청크 크기의 {int(MAX_OVERLAP_RATIO * 100)}%를 초과할 수 없습니다",
        "overlap_larger_than_chunk": "청크 오버랩이 청크 크기보다 클 수 없습니다"
    }

def prepare_chunking_kwargs(
    chunk_size: Optional[int] = None, 
    chunk_overlap: Optional[int] = None,
    validate: bool = True
) -> Dict[str, Any]:
    """
    청킹 옵션을 표준화된 딕셔너리로 변환
    
    Args:
        chunk_size: 청크 최대 크기 (None이면 기본값 사용)
        chunk_overlap: 청크 간 오버랩 크기 (None이면 자동 계산)
        validate: 유효성 검증 수행 여부
        
    Returns:
        Dict: 청킹 옵션 딕셔너리
        
    Raises:
        ValueError: 유효성 검증 실패 시
    """
    # 기본값 적용
    final_chunk_size = chunk_size if chunk_size is not None else ChunkingConstants.DEFAULT_CHUNK_SIZE
    
    # 오버랩 자동 계산 (지정되지 않은 경우)
    if chunk_overlap is None:
        final_chunk_overlap = int(final_chunk_size * ChunkingConstants.DEFAULT_CHUNK_OVERLAP_RATIO)
    else:
        final_chunk_overlap = chunk_overlap
    
    # 유효성 검증
    if validate:
        is_valid, error_message = validate_chunking_options(final_chunk_size, final_chunk_overlap)
        if not is_valid:
            raise ValueError(f"청킹 옵션 오류: {error_message}")
    
    # 결과 딕셔너리 생성
    chunking_kwargs = {
        'chunk_size': final_chunk_size
    }
    
    # 오버랩이 0보다 큰 경우에만 추가 (기본 동작과 호환)
    if final_chunk_overlap > 0:
        chunking_kwargs['chunk_overlap'] = final_chunk_overlap
    
    logger.debug(f"청킹 옵션 준비 완료: {chunking_kwargs}")
    return chunking_kwargs

def validate_chunking_options(
    chunk_size: int, 
    chunk_overlap: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    청킹 옵션 유효성 검증
    
    Args:
        chunk_size: 청크 크기
        chunk_overlap: 청크 오버랩 (None 허용)
        
    Returns:
        Tuple[bool, Optional[str]]: (유효 여부, 에러 메시지)
    """
    constants = ChunkingConstants
    
    # 청크 크기 범위 검증
    if not (constants.MIN_CHUNK_SIZE <= chunk_size <= constants.MAX_CHUNK_SIZE):
        return False, constants.ERROR_MESSAGES["chunk_size_range"]
    
    # 오버랩이 지정된 경우만 검증
    if chunk_overlap is not None:
        # 오버랩 범위 검증
        if not (constants.MIN_CHUNK_OVERLAP <= chunk_overlap <= constants.MAX_CHUNK_OVERLAP):
            return False, constants.ERROR_MESSAGES["chunk_overlap_range"]
        
        # 오버랩이 청크 크기보다 큰지 검증
        if chunk_overlap >= chunk_size:
            return False, constants.ERROR_MESSAGES["overlap_larger_than_chunk"]
        
        # 오버랩 비율 검증 (청크 크기의 50%까지만)
        if chunk_overlap > chunk_size * constants.MAX_OVERLAP_RATIO:
            return False, constants.ERROR_MESSAGES["overlap_ratio"]
    
    return True, None

def calculate_optimal_chunk_overlap(chunk_size: Optional[int], overlap_ratio: Optional[float] = None) -> int:
    """
    최적의 청크 오버랩 크기 계산
    
    Args:
        chunk_size: 청크 크기
        overlap_ratio: 오버랩 비율 (기본값: 10%)
        
    Returns:
        int: 계산된 오버랩 크기
    """
    # 타입 검증 및 변환
    try:
        if chunk_size is None:
            chunk_size = ChunkingConstants.DEFAULT_CHUNK_SIZE
        else:
            chunk_size = int(chunk_size)
    except (ValueError, TypeError):
        logger.warning(f"Invalid chunk_size type: {type(chunk_size)}, using default")
        chunk_size = ChunkingConstants.DEFAULT_CHUNK_SIZE
    
    if overlap_ratio is None:
        overlap_ratio = ChunkingConstants.DEFAULT_CHUNK_OVERLAP_RATIO
    
    # 비율 제한 (최대 50%)
    overlap_ratio = min(overlap_ratio, ChunkingConstants.MAX_OVERLAP_RATIO)
    
    overlap = int(chunk_size * overlap_ratio)
    
    # 최소/최대값 적용
    overlap = max(overlap, ChunkingConstants.MIN_CHUNK_OVERLAP)
    overlap = min(overlap, ChunkingConstants.MAX_CHUNK_OVERLAP)
    
    return overlap

def get_chunking_info(chunk_size: int, chunk_overlap: Optional[int] = None) -> Dict[str, Any]:
    """
    청킹 설정 정보 반환 (로깅/디버깅용)
    
    Args:
        chunk_size: 청크 크기
        chunk_overlap: 청크 오버랩
        
    Returns:
        Dict: 청킹 정보 딕셔너리
    """
    actual_overlap = chunk_overlap if chunk_overlap is not None else calculate_optimal_chunk_overlap(chunk_size)
    
    info = {
        "chunk_size": chunk_size,
        "chunk_overlap": actual_overlap,
        "overlap_ratio": round(actual_overlap / chunk_size * 100, 1),
        "effective_chunk_size": chunk_size - actual_overlap,
        "is_default_overlap": chunk_overlap is None,
        "validation": validate_chunking_options(chunk_size, actual_overlap)
    }
    
    return info

def format_chunking_summary(chunk_size: Optional[int], chunk_overlap: Optional[int] = None) -> str:
    """
    청킹 설정 요약 문자열 생성 (로깅용)
    
    Args:
        chunk_size: 청크 크기
        chunk_overlap: 청크 오버랩
        
    Returns:
        str: 요약 문자열
    """
    # 타입 검증 및 변환
    try:
        if chunk_size is None:
            chunk_size = ChunkingConstants.DEFAULT_CHUNK_SIZE
        else:
            chunk_size = int(chunk_size)
        
        if chunk_overlap is not None:
            chunk_overlap = int(chunk_overlap)
    except (ValueError, TypeError):
        return f"청크크기:{chunk_size}, 오버랩:{chunk_overlap}(타입오류)"
    
    actual_overlap = chunk_overlap if chunk_overlap is not None else calculate_optimal_chunk_overlap(chunk_size)
    overlap_type = "자동" if chunk_overlap is None else "수동"
    
    return f"청크크기:{chunk_size}, 오버랩:{actual_overlap}({overlap_type})"

# 하위 호환성을 위한 별칭
prepare_chunking_parameters = prepare_chunking_kwargs  # 구버전 호환