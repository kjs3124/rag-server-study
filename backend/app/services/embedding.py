"""
적응형 임베딩 서비스
언어별 최적 모델 선택 및 벡터 임베딩 생성
"""

import logging
import asyncio
import hashlib
from typing import List, Dict, Optional, Tuple, Union, Any
import numpy as np
from sentence_transformers import SentenceTransformer
import torch

from ..services.parsers.base import DocumentChunk
from ..services.language_detector import language_detector
from ..utils.memory import memory_manager

logger = logging.getLogger(__name__)

class AdaptiveEmbeddingService:
    """
    적응형 임베딩 서비스
    
    주요 기능:
    - 언어별 최적 모델 동적 선택
    - 배치 임베딩 처리
    - 모델 메모리 관리 및 캐싱
    - 비동기 처리 지원
    """
    
    def __init__(self):
        # 지원 모델 정의
        self.models_config = {
            'bge-m3': {
                'model_name': 'BAAI/bge-m3',
                'description': 'BGE-M3 - CJK 언어 특화 (한국어, 중국어, 일본어)',
                'dimension': 1024,
                'max_seq_length': 8192,
                'best_for': ['ko', 'ja', 'zh', 'zh-cn', 'zh-tw'],
                'memory_usage_mb': 2400
            },
            'multilingual-e5-large': {
                'model_name': 'intfloat/multilingual-e5-large',
                'description': 'Multilingual-E5-Large - 범용 다국어 모델',
                'dimension': 1024,
                'max_seq_length': 512,
                'best_for': ['en', 'mixed'],
                'memory_usage_mb': 1400
            }
        }
        
        # 로드된 모델 캐시
        self._loaded_models: Dict[str, SentenceTransformer] = {}
        
        # 임베딩 캐시 (선택적)
        self._embedding_cache: Dict[str, np.ndarray] = {}
        self.cache_enabled = True
        self.max_cache_size = 1000
        
        # GPU 사용 설정
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"임베딩 서비스 초기화 - 디바이스: {self.device}")
    
    async def get_model(self, model_key: str) -> SentenceTransformer:
        """
        모델 로드 또는 캐시에서 가져오기
        
        Args:
            model_key: 모델 키 ('bge-m3' 또는 'multilingual-e5-large')
            
        Returns:
            SentenceTransformer: 로드된 모델
        """
        if model_key not in self.models_config:
            raise ValueError(f"지원되지 않는 모델: {model_key}")
            
        if model_key not in self._loaded_models:
            logger.info(f"임베딩 모델 로드 중: {model_key}")
            
            config = self.models_config[model_key]
            model_name = config['model_name']
            
            try:
                # 모델 로드
                model = SentenceTransformer(model_name, device=self.device)
                
                # 모델 설정 최적화
                model.max_seq_length = config['max_seq_length']
                
                self._loaded_models[model_key] = model
                
                # 메모리 사용량 로깅
                memory_usage = memory_manager.get_memory_usage()
                logger.info(f"모델 로드 완료: {model_key} - 메모리: {memory_usage.get('rss_mb', 0):.1f}MB")
                
            except Exception as e:
                logger.error(f"모델 로드 실패 {model_key}: {e}")
                raise
                
        return self._loaded_models[model_key]
    
    def select_optimal_model(self, language_summary: Dict[str, Any]) -> str:
        """
        언어 분석 결과를 바탕으로 최적 모델 선택
        
        Args:
            language_summary: 언어 분석 결과
            
        Returns:
            str: 선택된 모델 키
        """
        return language_summary.get('recommended_model', 'multilingual-e5-large')
    
    def _get_cache_key(self, text: str, model_key: str) -> str:
        """
        임베딩 캐시 키 생성
        
        Args:
            text: 텍스트
            model_key: 모델 키
            
        Returns:
            str: 캐시 키
        """
        content_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        return f"{model_key}:{content_hash}"
    
    def _manage_cache_size(self):
        """캐시 크기 관리 (LRU 방식)"""
        if len(self._embedding_cache) > self.max_cache_size:
            # 오래된 항목부터 제거 (간단한 방식)
            items_to_remove = len(self._embedding_cache) - self.max_cache_size + 100
            keys_to_remove = list(self._embedding_cache.keys())[:items_to_remove]
            
            for key in keys_to_remove:
                del self._embedding_cache[key]
                
            logger.debug(f"임베딩 캐시 정리: {items_to_remove}개 항목 제거")
    
    async def embed_text(self, text: str, model_key: Optional[str] = None) -> np.ndarray:
        """
        단일 텍스트 임베딩
        
        Args:
            text: 임베딩할 텍스트
            model_key: 사용할 모델 (None이면 언어 감지 후 자동 선택)
            
        Returns:
            np.ndarray: 임베딩 벡터
        """
        if not text or not text.strip():
            raise ValueError("빈 텍스트는 임베딩할 수 없습니다")
            
        # 모델 선택
        if not model_key:
            # 언어 감지 기반 모델 선택
            detected_lang = language_detector.detect_language(text)
            if detected_lang in ['ko', 'ja', 'zh']:
                model_key = 'bge-m3'
            else:
                model_key = 'multilingual-e5-large'
        
        # 캐시 확인
        cache_key = None
        if self.cache_enabled:
            cache_key = self._get_cache_key(text, model_key)
            if cache_key in self._embedding_cache:
                logger.debug(f"임베딩 캐시 히트: {model_key}")
                return self._embedding_cache[cache_key]
        
        # 모델로 임베딩 생성
        model = await self.get_model(model_key)
        
        try:
            # 텍스트 전처리
            text = text.strip()
            max_length = self.models_config[model_key]['max_seq_length']
            if len(text) > max_length:
                text = text[:max_length]
                logger.debug(f"텍스트 길이 초과로 자름: {len(text)} -> {max_length}")
            
            # 임베딩 생성
            embedding = model.encode([text], convert_to_numpy=True, normalize_embeddings=True)[0]
            
            # 캐시 저장
            if self.cache_enabled and cache_key is not None:
                self._embedding_cache[cache_key] = embedding
                self._manage_cache_size()
            
            return embedding
            
        except Exception as e:
            logger.error(f"임베딩 생성 실패 - 모델: {model_key}, 오류: {e}")
            raise
    
    async def embed_chunks(self, chunks: List[DocumentChunk], 
                          model_key: Optional[str] = None,
                          batch_size: int = 32) -> List[Tuple[str, np.ndarray]]:
        """
        문서 청크들의 배치 임베딩
        
        Args:
            chunks: 문서 청크 리스트
            model_key: 사용할 모델 (None이면 자동 선택)
            batch_size: 배치 크기
            
        Returns:
            List[Tuple[str, np.ndarray]]: [(chunk_id, embedding), ...]
        """
        if not chunks:
            return []
            
        # 모델 자동 선택
        if not model_key:
            language_ratios = language_detector.analyze_document_languages(chunks)
            language_summary = language_detector.get_language_summary(language_ratios)
            model_key = self.select_optimal_model(language_summary)
            
        logger.info(f"청크 임베딩 시작: {len(chunks)}개 청크, 모델: {model_key}, 배치크기: {batch_size}")
        
        model = await self.get_model(model_key)
        max_length = self.models_config[model_key]['max_seq_length']
        
        results = []
        
        # 배치 단위로 처리
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_texts = []
            batch_chunk_ids = []
            
            for chunk in batch_chunks:
                if not chunk.content or not chunk.content.strip():
                    continue
                    
                text = chunk.content.strip()
                if len(text) > max_length:
                    text = text[:max_length]
                    
                batch_texts.append(text)
                batch_chunk_ids.append(chunk.chunk_id)
            
            if not batch_texts:
                continue
                
            try:
                # 배치 임베딩 생성
                embeddings = model.encode(
                    batch_texts, 
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    batch_size=batch_size,
                    show_progress_bar=False
                )
                
                # 결과 저장
                for chunk_id, embedding in zip(batch_chunk_ids, embeddings):
                    results.append((chunk_id, embedding))
                
                # 진행상황 로깅
                processed = min(i + batch_size, len(chunks))
                logger.debug(f"임베딩 진행: {processed}/{len(chunks)} ({processed/len(chunks)*100:.1f}%)")
                
            except Exception as e:
                logger.error(f"배치 임베딩 실패 (배치 {i//batch_size + 1}): {e}")
                # 개별 처리로 fallback
                for chunk in batch_chunks:
                    try:
                        if chunk.content and chunk.content.strip():
                            embedding = await self.embed_text(chunk.content, model_key)
                            results.append((chunk.chunk_id, embedding))
                    except Exception as individual_error:
                        logger.warning(f"개별 청크 임베딩 실패 {chunk.chunk_id}: {individual_error}")
        
        logger.info(f"청크 임베딩 완료: {len(results)}개 성공 / {len(chunks)}개 총합")
        return results
    
    async def embed_query(self, query: str, model_key: Optional[str] = None) -> np.ndarray:
        """
        검색 쿼리 임베딩
        
        Args:
            query: 검색 쿼리
            model_key: 사용할 모델
            
        Returns:
            np.ndarray: 쿼리 임베딩 벡터
        """
        if not model_key:
            # 쿼리 언어 감지 후 모델 선택
            detected_lang = language_detector.detect_language(query)
            if detected_lang in ['ko', 'ja', 'zh']:
                model_key = 'bge-m3'
            else:
                model_key = 'multilingual-e5-large'
        
        return await self.embed_text(query, model_key)
    
    def get_model_info(self, model_key: str) -> Dict[str, Any]:
        """
        모델 정보 조회
        
        Args:
            model_key: 모델 키
            
        Returns:
            Dict: 모델 정보
        """
        if model_key not in self.models_config:
            return {}
            
        config = self.models_config[model_key].copy()
        config['is_loaded'] = model_key in self._loaded_models
        
        if config['is_loaded']:
            model = self._loaded_models[model_key]
            config['actual_max_seq_length'] = getattr(model, 'max_seq_length', 'unknown')
            config['device'] = str(model.device)
        
        return config
    
    def get_service_status(self) -> Dict[str, Any]:
        """
        서비스 상태 정보
        
        Returns:
            Dict: 서비스 상태
        """
        return {
            'loaded_models': list(self._loaded_models.keys()),
            'available_models': list(self.models_config.keys()),
            'device': self.device,
            'cache_enabled': self.cache_enabled,
            'cache_size': len(self._embedding_cache),
            'max_cache_size': self.max_cache_size,
            'memory_usage': memory_manager.get_memory_usage()
        }
    
    def clear_cache(self):
        """임베딩 캐시 초기화"""
        self._embedding_cache.clear()
        logger.info("임베딩 캐시 초기화 완료")
    
    def unload_model(self, model_key: str):
        """
        모델 언로드 (메모리 절약)
        
        Args:
            model_key: 언로드할 모델 키
        """
        if model_key in self._loaded_models:
            del self._loaded_models[model_key]
            # GPU 메모리 정리
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info(f"모델 언로드 완료: {model_key}")

# 글로벌 임베딩 서비스 인스턴스
embedding_service = AdaptiveEmbeddingService()

async def embed_document_chunks(chunks: List[DocumentChunk]) -> Tuple[List[Tuple[str, np.ndarray]], Dict[str, Any]]:
    """
    문서 청크 임베딩 편의 함수
    
    Args:
        chunks: 문서 청크 리스트
        
    Returns:
        Tuple: (임베딩 결과, 메타데이터)
    """
    # 언어 분석
    language_ratios = language_detector.analyze_document_languages(chunks)
    language_summary = language_detector.get_language_summary(language_ratios)
    
    # 임베딩 생성
    embeddings = await embedding_service.embed_chunks(chunks)
    
    # 메타데이터
    metadata = {
        'language_analysis': language_summary,
        'model_used': language_summary['recommended_model'],
        'total_chunks': len(chunks),
        'successful_embeddings': len(embeddings),
        'embedding_dimension': embedding_service.models_config[language_summary['recommended_model']]['dimension']
    }
    
    return embeddings, metadata