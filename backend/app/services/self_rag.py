"""
Self-RAG (Self-Reflective Retrieval-Augmented Generation) Service
- On-demand retrieval with self-reflection
- 4 types of reflection tokens for quality control
- Adaptive generation with critique-based selection
- OpenAI API 기반 구현
"""

import logging
from typing import List, Dict, Optional, Tuple, Any, Union
from datetime import datetime
from enum import Enum
import asyncio
from openai import AsyncOpenAI

from ..core.config import get_llm_config

logger = logging.getLogger(__name__)

class ReflectionTokens:
    """Self-RAG Reflection Token definitions"""

    class Retrieve(Enum):
        """검색 필요성 판단"""
        YES = "YES"
        NO = "NO"
        CONTINUE = "CONTINUE"

    class IsRelevant(Enum):
        """검색된 문서의 관련성"""
        RELEVANT = "RELEVANT"
        IRRELEVANT = "IRRELEVANT"

    class IsSupported(Enum):
        """생성된 답변의 지원 정도"""
        FULLY_SUPPORTED = "FULLY_SUPPORTED"
        PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
        NO_SUPPORT = "NO_SUPPORT"

    class IsUseful(Enum):
        """답변의 유용성 (1-5 점수)"""
        EXCELLENT = 5
        GOOD = 4
        ACCEPTABLE = 3
        POOR = 2
        VERY_POOR = 1


class SelfRAGCritic:
    """Self-RAG Critique Model - API 기반 reflection token 생성"""

    def __init__(self, llm_config=None):
        """
        Args:
            llm_config: LLM 설정 (None이면 기본 설정 사용)
        """
        self.config = llm_config or get_llm_config()
        self.client = AsyncOpenAI(api_key=self.config.api_key)
        self.confidence_threshold = 0.7

    async def should_retrieve(self, query: str, context: str = "", threshold: float = 0.2) -> ReflectionTokens.Retrieve:
        """
        검색이 필요한지 판단 (API 기반)

        Args:
            query: 사용자 질문
            context: 이전 컨텍스트
            threshold: Adaptive retrieval threshold (0.0~1.0)

        Returns:
            Retrieve token
        """
        prompt = f"""다음 질문에 답변하기 위해 외부 문서 검색이 필요한지 판단하세요.

질문: {query}
이전 컨텍스트: {context if context else '없음'}

다음 중 하나로만 답변하세요:
- YES: 사실 확인이나 최신 정보가 필요한 질문
- NO: 개인적 경험, 창작, 일반 상식으로 답변 가능
- CONTINUE: 이전 컨텍스트만으로 충분

답변:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=10
            )

            content = response.choices[0].message.content
            result = content.strip().upper() if content else "YES"

            # Adaptive threshold 적용
            if result == "YES":
                return ReflectionTokens.Retrieve.YES
            elif result == "NO":
                return ReflectionTokens.Retrieve.NO
            elif result == "CONTINUE":
                return ReflectionTokens.Retrieve.CONTINUE
            else:
                # 기본값
                return ReflectionTokens.Retrieve.YES

        except Exception as e:
            logger.error(f"검색 필요성 판단 실패: {e}")
            return ReflectionTokens.Retrieve.YES

    async def evaluate_relevance(self, query: str, passage: str) -> ReflectionTokens.IsRelevant:
        """
        검색된 문서의 관련성 평가 (API 기반)

        Args:
            query: 사용자 질문
            passage: 검색된 문서

        Returns:
            IsRelevant token
        """
        prompt = f"""이 문서가 질문에 답변하는데 도움이 되는지 평가하세요.

질문: {query}

문서: {passage[:1000]}

다음 중 하나로만 답변하세요:
- RELEVANT: 문서가 질문과 관련있고 유용한 정보 포함
- IRRELEVANT: 문서가 질문과 무관하거나 도움이 안 됨

답변:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=10
            )

            content = response.choices[0].message.content
            result = content.strip().upper() if content else "IRRELEVANT"

            if "RELEVANT" in result:
                return ReflectionTokens.IsRelevant.RELEVANT
            else:
                return ReflectionTokens.IsRelevant.IRRELEVANT

        except Exception as e:
            logger.error(f"관련성 평가 실패: {e}")
            return ReflectionTokens.IsRelevant.IRRELEVANT

    async def evaluate_support(self, query: str, passage: str, answer: str) -> ReflectionTokens.IsSupported:
        """
        답변이 문서에 의해 얼마나 지원되는지 평가 (API 기반)

        Args:
            query: 사용자 질문
            passage: 검색된 문서
            answer: 생성된 답변

        Returns:
            IsSupported token
        """
        prompt = f"""답변이 문서의 정보로 뒷받침되는지 평가하세요.

질문: {query}

문서: {passage[:1000]}

답변: {answer}

다음 중 하나로만 답변하세요:
- FULLY_SUPPORTED: 답변의 모든 주장이 문서에서 확인됨
- PARTIALLY_SUPPORTED: 답변의 일부만 문서에서 확인됨
- NO_SUPPORT: 답변이 문서로 뒷받침되지 않음

답변:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=20
            )

            content = response.choices[0].message.content
            result = content.strip().upper() if content else "NO_SUPPORT"

            if "FULLY" in result:
                return ReflectionTokens.IsSupported.FULLY_SUPPORTED
            elif "PARTIALLY" in result:
                return ReflectionTokens.IsSupported.PARTIALLY_SUPPORTED
            else:
                return ReflectionTokens.IsSupported.NO_SUPPORT

        except Exception as e:
            logger.error(f"지원도 평가 실패: {e}")
            return ReflectionTokens.IsSupported.NO_SUPPORT

    async def evaluate_usefulness(self, query: str, answer: str) -> ReflectionTokens.IsUseful:
        """
        답변의 유용성 평가 (API 기반)

        Args:
            query: 사용자 질문
            answer: 생성된 답변

        Returns:
            IsUseful token (1-5 점수)
        """
        prompt = f"""답변의 유용성을 1~5점으로 평가하세요.

질문: {query}

답변: {answer}

평가 기준:
- 5점: 완벽하고 상세한 답변
- 4점: 좋은 답변이지만 개선 여지 있음
- 3점: 수용 가능한 답변
- 2점: 불완전하거나 부정확한 답변
- 1점: 매우 불충분하거나 관련 없는 답변

점수만 답변하세요 (1, 2, 3, 4, 또는 5):"""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=5
            )

            content = response.choices[0].message.content
            result = content.strip() if content else "3"
            score = int(result)

            score_mapping = {
                5: ReflectionTokens.IsUseful.EXCELLENT,
                4: ReflectionTokens.IsUseful.GOOD,
                3: ReflectionTokens.IsUseful.ACCEPTABLE,
                2: ReflectionTokens.IsUseful.POOR,
                1: ReflectionTokens.IsUseful.VERY_POOR
            }

            return score_mapping.get(score, ReflectionTokens.IsUseful.ACCEPTABLE)

        except Exception as e:
            logger.error(f"유용성 평가 실패: {e}")
            return ReflectionTokens.IsUseful.ACCEPTABLE


class SelfRAGGenerator:
    """Self-RAG Generator - API 기반 답변 생성"""

    def __init__(self, llm_config=None):
        """
        Args:
            llm_config: LLM 설정 (None이면 기본 설정 사용)
        """
        self.config = llm_config or get_llm_config()
        self.client = AsyncOpenAI(api_key=self.config.api_key)
        self.max_passages = 5
        self.beam_size = 2  # 논문의 beam search size

    async def generate_with_citation(self, query: str, passage: str) -> str:
        """
        단일 passage 기반 답변 생성 (API 기반)

        Args:
            query: 사용자 질문
            passage: 참고 문서

        Returns:
            생성된 답변
        """
        prompt = f"""다음 문서를 참고하여 질문에 답변하세요.

질문: {query}

참고 문서:
{passage}

답변:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )

            content = response.choices[0].message.content
            return content.strip() if content else f"답변을 생성할 수 없습니다."

        except Exception as e:
            logger.error(f"답변 생성 실패: {e}")
            return f"답변 생성 중 오류가 발생했습니다: {str(e)}"

    async def generate_without_retrieval(self, query: str) -> str:
        """
        검색 없이 답변 생성

        Args:
            query: 사용자 질문

        Returns:
            생성된 답변
        """
        prompt = f"""다음 질문에 답변하세요.

질문: {query}

답변:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )

            content = response.choices[0].message.content
            return content.strip() if content else f"답변을 생성할 수 없습니다."

        except Exception as e:
            logger.error(f"답변 생성 실패: {e}")
            return f"답변 생성 중 오류가 발생했습니다: {str(e)}"


class SelfRAGService:
    """Self-RAG 메인 서비스"""

    def __init__(self, rag_service, vector_store, embedding_service):
        self.rag_service = rag_service
        self.vector_store = vector_store
        self.embedding_service = embedding_service

        # LLM 설정 로드
        self.llm_config = get_llm_config()

        # Critic과 Generator 초기화
        self.critic = SelfRAGCritic(self.llm_config)
        self.generator = SelfRAGGenerator(self.llm_config)

        # Self-RAG 설정
        self.max_iterations = 3
        self.reflection_weights = {
            'relevance': 1.0,
            'support': 1.0,
            'usefulness': 0.5
        }

    async def self_rag_query(self, query: str,
                           top_k: int = 5,
                           document_filter: Optional[str] = None,
                           retrieval_threshold: float = 0.2) -> Dict[str, Any]:
        """
        Self-RAG 기반 질의응답

        Args:
            query: 사용자 질문
            top_k: 검색할 문서 수
            document_filter: 문서 필터
            retrieval_threshold: Adaptive retrieval threshold (0.0~1.0)

        Returns:
            Self-RAG 결과
        """
        start_time = datetime.now()

        # Step 1: 검색 필요성 판단
        retrieve_decision = await self.critic.should_retrieve(
            query,
            threshold=retrieval_threshold
        )

        result = {
            'query': query,
            'retrieve_decision': retrieve_decision.value,
            'passages': [],
            'candidates': [],
            'selected_answer': '',
            'reflection_tokens': {},
            'metadata': {
                'llm_model': self.llm_config.model,
                'llm_provider': self.llm_config.provider,
                'retrieval_threshold': retrieval_threshold,
                'processing_time': 0.0,
                'steps_performed': []
            }
        }

        # 검색이 필요하지 않은 경우
        if retrieve_decision == ReflectionTokens.Retrieve.NO:
            answer = await self.generator.generate_without_retrieval(query)
            usefulness = await self.critic.evaluate_usefulness(query, answer)

            result.update({
                'selected_answer': answer,
                'reflection_tokens': {
                    'retrieve': retrieve_decision.value,
                    'usefulness': usefulness.value
                }
            })
            result['metadata']['steps_performed'] = ['generate_without_retrieval', 'evaluate_usefulness']

        else:
            # Step 2: 검색 수행
            search_result = await self.rag_service.search_documents(
                query=query,
                top_k=top_k,
                document_filter=document_filter
            )

            if not search_result['success'] or not search_result['results']:
                # 검색 실패 시 기본 답변
                answer = "죄송합니다. 관련 정보를 찾을 수 없습니다."
                usefulness = ReflectionTokens.IsUseful.POOR

                result.update({
                    'selected_answer': answer,
                    'reflection_tokens': {
                        'retrieve': retrieve_decision.value,
                        'usefulness': usefulness.value
                    }
                })
            else:
                # Step 3: 병렬로 답변 후보 생성 및 평가
                passages = [r['metadata'].get('content', '') for r in search_result['results']]
                result['passages'] = passages

                candidates = await self._generate_and_evaluate_candidates(query, passages)
                result['candidates'] = candidates

                # Step 4: 최적 답변 선택
                selected_candidate = self._select_best_candidate(candidates)
                result['selected_answer'] = selected_candidate['answer']
                result['reflection_tokens'] = selected_candidate['reflection_tokens']

                result['metadata']['steps_performed'] = [
                    'retrieve_passages',
                    'generate_candidates',
                    'evaluate_candidates',
                    'select_best'
                ]

        # 처리 시간 계산
        end_time = datetime.now()
        result['metadata']['processing_time'] = (end_time - start_time).total_seconds()

        return result

    async def _generate_and_evaluate_candidates(self, query: str,
                                              passages: List[str]) -> List[Dict[str, Any]]:
        """
        각 passage에 대해 답변 후보를 병렬로 생성하고 reflection token으로 평가
        """
        # 병렬 처리를 위한 tasks 생성
        tasks = []
        for i, passage in enumerate(passages[:self.generator.max_passages]):
            tasks.append(self._evaluate_single_passage(query, passage, i))

        # 병렬 실행
        candidates = await asyncio.gather(*tasks)

        # None이 아닌 후보만 필터링하고 점수순으로 정렬
        valid_candidates = [c for c in candidates if c is not None]
        valid_candidates.sort(key=lambda x: x['score'], reverse=True)

        return valid_candidates

    async def _evaluate_single_passage(self, query: str, passage: str, index: int) -> Optional[Dict[str, Any]]:
        """단일 passage에 대한 답변 생성 및 평가"""
        try:
            # 관련성 평가
            relevance = await self.critic.evaluate_relevance(query, passage)

            # 관련성이 없으면 건너뛰기
            if relevance == ReflectionTokens.IsRelevant.IRRELEVANT:
                return None

            # 답변 생성
            answer = await self.generator.generate_with_citation(query, passage)

            # 지원 정도 평가
            support = await self.critic.evaluate_support(query, passage, answer)

            # 유용성 평가
            usefulness = await self.critic.evaluate_usefulness(query, answer)

            # 종합 점수 계산
            score = self._calculate_candidate_score(relevance, support, usefulness)

            return {
                'passage_index': index,
                'passage': passage[:200] + "..." if len(passage) > 200 else passage,
                'answer': answer,
                'reflection_tokens': {
                    'relevance': relevance.value,
                    'support': support.value,
                    'usefulness': usefulness.value
                },
                'score': score
            }

        except Exception as e:
            logger.error(f"Passage {index} 평가 실패: {e}")
            return None

    def _calculate_candidate_score(self, relevance: ReflectionTokens.IsRelevant,
                                 support: ReflectionTokens.IsSupported,
                                 usefulness: ReflectionTokens.IsUseful) -> float:
        """
        Reflection token들을 기반으로 후보 점수 계산
        """
        relevance_score = 1.0 if relevance == ReflectionTokens.IsRelevant.RELEVANT else 0.0

        support_scores = {
            ReflectionTokens.IsSupported.FULLY_SUPPORTED: 1.0,
            ReflectionTokens.IsSupported.PARTIALLY_SUPPORTED: 0.6,
            ReflectionTokens.IsSupported.NO_SUPPORT: 0.0
        }
        support_score = support_scores[support]

        usefulness_score = usefulness.value / 5.0  # 1-5를 0-1로 정규화

        # 가중 평균
        total_score = (
            relevance_score * self.reflection_weights['relevance'] +
            support_score * self.reflection_weights['support'] +
            usefulness_score * self.reflection_weights['usefulness']
        )

        return total_score

    def _select_best_candidate(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        최고 점수의 후보 선택
        """
        if not candidates:
            return {
                'answer': "죄송합니다. 적절한 답변을 생성할 수 없습니다.",
                'reflection_tokens': {
                    'relevance': 'IRRELEVANT',
                    'support': 'NO_SUPPORT',
                    'usefulness': 1
                }
            }

        return candidates[0]  # 이미 점수순으로 정렬됨

    def update_reflection_weights(self, weights: Dict[str, float]):
        """
        Reflection token 가중치 업데이트
        """
        self.reflection_weights.update(weights)
        logger.info(f"Reflection weights updated: {self.reflection_weights}")

    def get_service_status(self) -> Dict[str, Any]:
        """
        Self-RAG 서비스 상태 정보
        """
        return {
            'self_rag_service': {
                'llm_provider': self.llm_config.provider,
                'llm_model': self.llm_config.model,
                'max_iterations': self.max_iterations,
                'reflection_weights': self.reflection_weights,
                'critic_available': self.critic is not None,
                'generator_available': self.generator is not None
            },
            'base_rag_service': self.rag_service.get_service_status() if self.rag_service else None
        }


# 글로벌 Self-RAG 서비스 인스턴스
self_rag_service: Optional['SelfRAGService'] = None