"""
RAG (Retrieval-Augmented Generation) 검색 서비스
벡터 검색과 LLM 통합을 통한 질의응답 시스템
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
import asyncio
from datetime import datetime

from .embedding import embedding_service
from .vector_store import vector_store
from .language_detector import language_detector
from ..services.parsers.base import DocumentChunk

logger = logging.getLogger(__name__)

class RAGService:
    """
    RAG 검색 서비스
    
    주요 기능:
    - 쿼리 임베딩 및 벡터 검색
    - 검색 결과 후처리 및 랭킹
    - 컨텍스트 생성 및 답변 준비
    """
    
    def __init__(self):
        self.max_context_tokens = 8000  # 컨텍스트 최대 토큰 수
        self.default_top_k = 20  # 1차 검색 결과 수
        self.final_top_k = 5     # 최종 반환 결과 수
        
    async def initialize(self) -> bool:
        """
        RAG 서비스 초기화
        
        Returns:
            bool: 초기화 성공 여부
        """
        try:
            # 벡터 스토어 초기화
            vector_initialized = await vector_store.initialize()
            
            if not vector_initialized:
                logger.error("벡터 스토어 초기화 실패")
                return False
            
            logger.info("RAG 서비스 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"RAG 서비스 초기화 실패: {e}")
            return False
    
    async def search_documents(self, query: str, 
                             top_k: Optional[int] = None,
                             document_filter: Optional[str] = None,
                             similarity_threshold: float = 0.1) -> Dict[str, Any]:
        """
        문서 검색 수행
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 결과 수
            document_filter: 특정 문서로 제한
            similarity_threshold: 유사도 임계값 (이 값 이하는 제외)
            
        Returns:
            Dict: 검색 결과 및 메타데이터
        """
        if not query or not query.strip():
            return {
                'success': False,
                'error': '검색 쿼리가 비어있습니다',
                'results': []
            }
        
        start_time = datetime.now()
        
        try:
            # 1단계: 쿼리 언어 감지 및 임베딩
            detected_language = language_detector.detect_language(query)
            logger.debug(f"쿼리 언어 감지: {detected_language}")
            
            # 쿼리 임베딩 생성
            query_vector = await embedding_service.embed_query(query)
            
            # 2단계: 벡터 검색
            search_top_k = top_k or self.default_top_k
            search_results = await vector_store.search_similar_chunks(
                query_vector=query_vector,
                top_k=search_top_k,
                document_filter=document_filter
            )
            
            # 3단계: 결과 후처리 및 필터링
            filtered_results = []
            for result in search_results:
                # 유사도 임계값 필터링
                if result['score'] < similarity_threshold:
                    continue
                    
                filtered_results.append(result)
            
            # 4단계: 최종 결과 준비
            final_top_k = min(top_k or self.final_top_k, len(filtered_results))
            final_results = filtered_results[:final_top_k]
            
            # 5단계: 메타데이터 생성
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # 모델 정보 가져오기
            model_key = 'bge-m3' if detected_language in ['ko', 'ja', 'zh'] else 'multilingual-e5-large'
            model_info = embedding_service.get_model_info(model_key)
            
            return {
                'success': True,
                'query': query,
                'results': final_results,
                'metadata': {
                    'query_language': detected_language,
                    'model_used': model_key,
                    'model_info': model_info,
                    'search_time_seconds': round(processing_time, 3),
                    'total_candidates': len(search_results),
                    'filtered_results': len(filtered_results),
                    'final_results': len(final_results),
                    'similarity_threshold': similarity_threshold,
                    'document_filter': document_filter
                }
            }
            
        except Exception as e:
            logger.error(f"문서 검색 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
    
    def _prepare_context_chunks(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        검색 결과를 컨텍스트 청크로 변환
        
        Args:
            search_results: 벡터 검색 결과
            
        Returns:
            List[Dict]: 컨텍스트용 청크 정보
        """
        context_chunks = []
        total_tokens = 0  # 대략적인 토큰 수 추정
        
        for i, result in enumerate(search_results):
            metadata = result.get('metadata', {})
            content = metadata.get('content', '')
            
            # 토큰 수 추정 (1토큰 ≈ 4자)
            estimated_tokens = len(content) // 4
            
            # 최대 컨텍스트 토큰 수 초과 시 중단
            if total_tokens + estimated_tokens > self.max_context_tokens:
                logger.debug(f"컨텍스트 토큰 한계 도달: {total_tokens} + {estimated_tokens} > {self.max_context_tokens}")
                break
            
            chunk_info = {
                'rank': i + 1,
                'chunk_id': metadata.get('chunk_id', result['id']),  # 원본 chunk_id 사용 (payload에 저장된 값)
                'document_id': metadata.get('document_id', ''),
                'content': content,
                'similarity_score': result['score'],
                'page_number': metadata.get('page_number'),
                'section_title': metadata.get('section_title', ''),
                'chunk_index': metadata.get('chunk_index', 0)
            }
            
            context_chunks.append(chunk_info)
            total_tokens += estimated_tokens
        
        logger.debug(f"컨텍스트 준비 완료: {len(context_chunks)}개 청크, 약 {total_tokens} 토큰")
        return context_chunks
    
    async def generate_answer(self, query: str, search_results: List[Dict[str, Any]],
                            context_only: bool = False) -> Dict[str, Any]:
        """
        검색 결과 기반 답변 생성 (LLM 연동 준비)
        
        Args:
            query: 사용자 질문
            search_results: 벡터 검색 결과
            context_only: True이면 컨텍스트만 반환, False이면 실제 답변 생성
            
        Returns:
            Dict: 답변 및 메타데이터
        """
        if not search_results:
            return {
                'success': False,
                'error': '검색 결과가 없습니다',
                'answer': '',
                'sources': []
            }
        
        try:
            # 컨텍스트 청크 준비
            context_chunks = self._prepare_context_chunks(search_results)
            
            if context_only:
                # 컨텍스트만 반환 (LLM 연동 전)
                context_text = self._build_context_text(context_chunks)
                
                return {
                    'success': True,
                    'answer': f"질문 '{query}'에 대한 관련 문서를 찾았습니다.\n\n{context_text}",
                    'sources': context_chunks,
                    'metadata': {
                        'generation_type': 'context_only',
                        'context_chunks': len(context_chunks),
                        'llm_used': None
                    }
                }
            else:
                # TODO: 실제 LLM 연동 구현 예정
                # 현재는 단순 요약 답변 생성
                answer = self._generate_simple_answer(query, context_chunks)
                
                return {
                    'success': True,
                    'answer': answer,
                    'sources': context_chunks,
                    'metadata': {
                        'generation_type': 'simple_summary',
                        'context_chunks': len(context_chunks),
                        'llm_used': 'built_in_simple'
                    }
                }
                
        except Exception as e:
            logger.error(f"답변 생성 실패: {e}")
            return {
                'success': False,
                'error': str(e),
                'answer': '',
                'sources': []
            }
    
    def _build_context_text(self, context_chunks: List[Dict[str, Any]]) -> str:
        """컨텍스트 청크들을 텍스트로 결합"""
        context_parts = []
        
        for chunk in context_chunks:
            part = f"[문서 {chunk['rank']}]"
            
            if chunk.get('page_number'):
                part += f" (페이지 {chunk['page_number']})"
            
            if chunk.get('section_title'):
                part += f" - {chunk['section_title']}"
                
            part += f" (유사도: {chunk['similarity_score']:.3f})"
            part += f"\n{chunk['content']}\n"
            
            context_parts.append(part)
        
        return "\n".join(context_parts)
    
    def _generate_simple_answer(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """간단한 답변 생성 (LLM 대신 임시 구현)"""
        if not context_chunks:
            return "관련 정보를 찾을 수 없습니다."
        
        # 가장 유사도가 높은 청크의 내용을 기반으로 답변
        top_chunk = context_chunks[0]
        content = top_chunk['content']
        
        # 간단한 요약 (첫 2문장)
        sentences = content.split('.')
        summary_sentences = sentences[:2] if len(sentences) >= 2 else sentences
        summary = '. '.join(s.strip() for s in summary_sentences if s.strip())
        
        if summary and not summary.endswith('.'):
            summary += '.'
        
        answer = f"질문 '{query}'에 대한 답변입니다.\n\n{summary}\n\n"
        answer += f"이 정보는 {len(context_chunks)}개의 관련 문서에서 추출되었습니다."
        
        return answer
    
    async def rag_search_and_answer(self, query: str,
                                  top_k: Optional[int] = None,
                                  document_filter: Optional[str] = None,
                                  similarity_threshold: float = 0.1,
                                  context_only: bool = False) -> Dict[str, Any]:
        """
        RAG 통합 검색 및 답변 생성
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 결과 수
            document_filter: 특정 문서로 제한
            similarity_threshold: 유사도 임계값
            context_only: True이면 컨텍스트만 반환
            
        Returns:
            Dict: 통합 결과
        """
        start_time = datetime.now()
        
        # 1단계: 문서 검색
        search_result = await self.search_documents(
            query=query,
            top_k=top_k,
            document_filter=document_filter,
            similarity_threshold=similarity_threshold
        )
        
        if not search_result['success']:
            return search_result
        
        # 2단계: 답변 생성
        answer_result = await self.generate_answer(
            query=query,
            search_results=search_result['results'],
            context_only=context_only
        )
        
        if not answer_result['success']:
            return answer_result
        
        # 3단계: 통합 결과
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        return {
            'success': True,
            'query': query,
            'answer': answer_result['answer'],
            'sources': answer_result['sources'],
            'metadata': {
                **search_result['metadata'],
                **answer_result['metadata'],
                'total_processing_time': round(total_time, 3),
                'pipeline_steps': ['search', 'generate_answer']
            }
        }
    
    def get_service_status(self) -> Dict[str, Any]:
        """RAG 서비스 상태 정보 조회"""
        vector_info = vector_store.get_store_info()
        embedding_info = embedding_service.get_service_status()
        
        return {
            'rag_service': {
                'max_context_tokens': self.max_context_tokens,
                'default_top_k': self.default_top_k,
                'final_top_k': self.final_top_k
            },
            'vector_store': vector_info,
            'embedding_service': embedding_info,
            'dependencies': {
                'vector_store_ready': vector_info['initialized'],
                'embedding_models_loaded': len(embedding_info['loaded_models']) > 0
            }
        }

# 글로벌 RAG 서비스 인스턴스
rag_service = RAGService()