"""
Qdrant 벡터 데이터베이스 서비스
"""

import logging
import os
from typing import List, Dict, Optional, Tuple, Any, cast
import numpy as np
from datetime import datetime
import uuid
import hashlib

# Qdrant 임포트 처리
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct, 
        Filter, FieldCondition, MatchValue, PointIdsList
    )
    QDRANT_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.error(f"Qdrant 클라이언트를 사용할 수 없습니다: {e}")
    logger.info("다음 명령으로 설치하세요: pip install qdrant-client")
    
    QDRANT_AVAILABLE = False
    
    # 런타임 에러를 발생시키는 더미 클래스
    class _QdrantNotAvailable:
        def __init__(self, *args, **kwargs):
            raise ImportError("Qdrant 클라이언트가 설치되지 않았습니다")
        
        def __getattr__(self, name):
            raise ImportError("Qdrant 클라이언트가 설치되지 않았습니다")
    
    QdrantClient = _QdrantNotAvailable
    Distance = _QdrantNotAvailable
    VectorParams = _QdrantNotAvailable
    PointStruct = _QdrantNotAvailable
    Filter = _QdrantNotAvailable
    FieldCondition = _QdrantNotAvailable
    MatchValue = _QdrantNotAvailable
    PointIdsList = _QdrantNotAvailable

from ..services.parsers.base import DocumentChunk
from ..core.config import get_database_config

logger = logging.getLogger(__name__)

class QdrantVectorStore:
    """Qdrant 벡터 스토어 구현"""
    
    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None):
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant 클라이언트가 설치되지 않았습니다")
        
        # 설정 로드
        try:
            config = get_database_config()
            connection_config = config.qdrant.connection
            self.timeout = connection_config.get('timeout', 30)
            self.prefer_grpc = connection_config.get('prefer_grpc', False)
            default_url = connection_config.get('url', 'http://localhost:6333')
        except Exception as e:
            logger.warning(f"데이터베이스 설정 로드 실패, 기본값 사용: {e}")
            self.timeout = 30
            self.prefer_grpc = False
            default_url = 'http://localhost:6333'
        
        # URL과 API 키 설정
        self.url = url or default_url
        self.api_key = api_key
            
        # 버전 호환성 체크 비활성화
        self.client = QdrantClient(
            url=self.url, 
            api_key=self.api_key,
            prefer_grpc=self.prefer_grpc,
            timeout=self.timeout
        )
        logger.info(f"Qdrant 클라이언트 초기화: {self.url}")
    
    async def create_collection(self, collection_name: str, dimension: int) -> bool:
        """
        Qdrant 컬렉션 생성
        
        Args:
            collection_name: 컬렉션명
            dimension: 벡터 차원
            
        Returns:
            bool: 생성 성공 여부
        """
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant 클라이언트가 설치되지 않았습니다")
            
        try:
            # 이미 존재하는지 확인
            collections = self.client.get_collections().collections
            existing_names = [col.name for col in collections]
            
            if collection_name in existing_names:
                logger.info(f"Qdrant 컬렉션 이미 존재: {collection_name}")
                return True
            
            # 컬렉션 생성
            if QDRANT_AVAILABLE:
                from qdrant_client.models import VectorParams as QVectorParams, Distance as QDistance
                
                # 설정에서 거리 메트릭 가져오기
                try:
                    config = get_database_config()
                    distance_metric_name = config.qdrant.collections.get('distance_metric', 'COSINE')
                    distance_metric = getattr(QDistance, distance_metric_name.upper(), QDistance.COSINE)
                except Exception:
                    distance_metric = QDistance.COSINE
                
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=QVectorParams(
                        size=dimension,
                        distance=distance_metric
                    )
                )
            else:
                raise ImportError("Qdrant 클라이언트가 설치되지 않았습니다")
            
            logger.info(f"Qdrant 컬렉션 생성 성공: {collection_name} (차원: {dimension})")
            return True
            
        except Exception as e:
            logger.error(f"Qdrant 컬렉션 생성 실패 {collection_name}: {e}")
            return False
    
    async def insert_vectors(self, collection_name: str, 
                           vectors: List[Tuple[str, np.ndarray, Dict[str, Any]]]) -> bool:
        """
        Qdrant 벡터 삽입
        
        Args:
            collection_name: 컬렉션명
            vectors: [(id, vector, metadata), ...] 리스트
            
        Returns:
            bool: 삽입 성공 여부
        """
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant 클라이언트가 설치되지 않았습니다")
            
        try:
            points = []
            for vector_id, vector, metadata in vectors:
                # 벡터 데이터 형식 확인 및 변환
                if isinstance(vector, np.ndarray):
                    vector_data = vector.tolist()
                elif isinstance(vector, list):
                    vector_data = vector
                else:
                    vector_data = list(vector)
                
                # 벡터 차원 및 데이터 타입 확인
                if len(vector_data) == 0:
                    logger.warning(f"빈 벡터 감지: {vector_id}")
                    continue
                    
                # 모든 요소가 float로 변환 가능한지 확인
                try:
                    vector_data = [float(x) for x in vector_data]
                except (TypeError, ValueError) as e:
                    logger.error(f"벡터 데이터 변환 실패 {vector_id}: {e}")
                    continue
                
                # Qdrant ID 처리
                # Qdrant는 UUID 형식(하이픈 포함)이나 정수만 허용
                # 문자열 chunk_id를 해시하여 정수 ID 생성
                
                # 원본 chunk_id 저장
                original_chunk_id = str(vector_id)
                if metadata:
                    metadata['chunk_id'] = original_chunk_id
                
                # chunk_id를 해시하여 정수 ID 생성 (64비트 정수)
                hash_obj = hashlib.sha256(original_chunk_id.encode())
                # 해시의 처음 8바이트를 정수로 변환
                point_id = int.from_bytes(hash_obj.digest()[:8], 'big') % (2**63)  # 양수로 제한
                
                # PointStruct 객체 생성
                if QDRANT_AVAILABLE:
                    from qdrant_client.models import PointStruct
                    point = PointStruct(
                        id=point_id,
                        vector=vector_data,
                        payload=metadata or {}
                    )
                    points.append(point)
                    
                    # 첫 번째 포인트의 정보를 로그로 출력 (디버깅용)
                    if len(points) == 1:
                        logger.info(f"첫 번째 벡터 정보:")
                        logger.info(f"  - ID: {point_id}, 타입: {type(point_id)}")
                        logger.info(f"  - 벡터 차원: {len(vector_data)}, 첫 요소 타입: {type(vector_data[0])}")
                        logger.info(f"  - 페이로드 키: {list(metadata.keys()) if metadata else 'None'}")
                        logger.info(f"  - PointStruct 타입: {type(point)}")
            
            # 포인트가 없으면 반환
            if not points:
                logger.warning("삽입할 벡터가 없습니다")
                return True
            
            # 벡터 차원 확인 (첫 번째 벡터 기준)
            if points:
                first_point = points[0]
                if hasattr(first_point, 'vector'):
                    vector_dim = len(first_point.vector)
                else:
                    vector_dim = 0
            else:
                vector_dim = 0
            logger.info(f"벡터 삽입 시작 - 개수: {len(points)}, 차원: {vector_dim}")
            
            # Qdrant에 배치 삽입
            try:
                # Qdrant API 형식에 맞게 upsert
                operation_info = self.client.upsert(
                    collection_name=collection_name,
                    points=points,
                    wait=True  # 변경사항이 실제로 적용될 때까지 대기
                )
                logger.debug(f"Qdrant 응답: {operation_info}")
            except Exception as batch_error:
                logger.warning(f"배치 삽입 실패, 개별 삽입 시도: {batch_error}")
                
                # 개별 삽입 시도
                success_count = 0
                for point in points:
                    try:
                        self.client.upsert(
                            collection_name=collection_name,
                            points=[point],
                            wait=True
                        )
                        success_count += 1
                    except Exception as single_error:
                        # 에러 로깅 시 원본 chunk_id 표시
                        point_id = point.id if hasattr(point, 'id') else str(point)
                        original_id = point.payload.get('chunk_id', point_id) if hasattr(point, 'payload') else point_id
                        logger.error(f"개별 벡터 삽입 실패 {original_id} (Qdrant ID: {point_id}): {single_error}")
                
                if success_count > 0:
                    logger.info(f"부분 성공: {success_count}/{len(points)}개 벡터 삽입")
                    return True
                else:
                    raise batch_error
            
            logger.info(f"Qdrant 벡터 삽입 성공: {collection_name} - {len(vectors)}개")
            return True
            
        except Exception as e:
            logger.error(f"Qdrant 벡터 삽입 실패 {collection_name}: {e}")
            return False
    
    async def search_vectors(self, collection_name: str, query_vector: np.ndarray,
                           top_k: int = 5, filter_conditions: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Qdrant 벡터 검색
        
        Args:
            collection_name: 컬렉션명
            query_vector: 쿼리 벡터
            top_k: 반환할 최대 개수
            filter_conditions: 필터 조건
            
        Returns:
            List[Dict]: 검색 결과
        """
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant 클라이언트가 설치되지 않았습니다")
            
        try:
            # 필터 변환
            query_filter = None
            if filter_conditions and QDRANT_AVAILABLE:
                from qdrant_client.models import Filter as QFilter, FieldCondition as QFieldCondition, MatchValue as QMatchValue
                conditions = []
                for key, value in filter_conditions.items():
                    conditions.append(QFieldCondition(key=key, match=QMatchValue(value=value)))
                if conditions:
                    query_filter = QFilter(must=conditions)
            
            # 검색 실행
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector.tolist() if isinstance(query_vector, np.ndarray) else query_vector,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,  # 메타데이터 포함
                with_vectors=False  # 벡터는 제외 (필요시 True)
            )
            
            # 결과 변환
            results = []
            for result in search_results:
                results.append({
                    'id': result.id,
                    'score': result.score,
                    'metadata': result.payload
                })
            
            logger.debug(f"Qdrant 검색 완료: {collection_name} - {len(results)}개 결과")
            return results
            
        except Exception as e:
            logger.error(f"Qdrant 벡터 검색 실패 {collection_name}: {e}")
            return []
    
    async def delete_vectors(self, collection_name: str, vector_ids: List[str]) -> bool:
        """Qdrant 벡터 삭제"""
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant 클라이언트가 설치되지 않았습니다")
            
        try:
            from qdrant_client import models
            from typing import Union
            
            point_ids: List[Union[int, str]] = []
            for vid in vector_ids:
                point_ids.append(vid)  # 문자열 그대로 추가
            
            self.client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(
                    points=point_ids  # List[Union[int, str]] 타입
                ),
                wait=True
            )
            
            logger.info(f"Qdrant 벡터 삭제 성공: {collection_name} - {len(vector_ids)}개")
            return True
            
        except Exception as e:
            logger.error(f"Qdrant 벡터 삭제 실패 {collection_name}: {e}")
            return False
    
    async def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Qdrant 컬렉션 정보 조회"""
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant 클라이언트가 설치되지 않았습니다")
            
        try:
            collection_info = self.client.get_collection(collection_name)
            return {
                'name': collection_name,
                'vectors_count': collection_info.vectors_count or 0,
                'points_count': collection_info.points_count or 0,
                'status': collection_info.status.name if collection_info.status else 'unknown',
                'vector_size': getattr(collection_info.config.params.vectors, 'size', 0) if collection_info.config and collection_info.config.params and collection_info.config.params.vectors else 0
            }
        except Exception as e:
            logger.error(f"Qdrant 컬렉션 정보 조회 실패 {collection_name}: {e}")
            return {}

class VectorStoreManager:
    """벡터 스토어 매니저 (Qdrant 전용)"""
    
    def __init__(self):
        self.store: Optional[QdrantVectorStore] = None
        
        # 설정 로드
        try:
            config = get_database_config()
            collections_config = config.qdrant.collections
            self.default_collection = collections_config.get('default_name', 'documents')
            self.vector_dimension = collections_config.get('default_dimension', 1024)
            self.distance_metric = collections_config.get('distance_metric', 'COSINE')
        except Exception as e:
            logger.warning(f"데이터베이스 설정 로드 실패, 기본값 사용: {e}")
            self.default_collection = "documents"
            self.vector_dimension = 1024
            self.distance_metric = 'COSINE'
        
    async def initialize(self, qdrant_url: Optional[str] = None, api_key: Optional[str] = None) -> bool:
        """
        Qdrant 벡터 스토어 초기화
        
        Args:
            qdrant_url: Qdrant 서버 URL
            api_key: API 키 (선택사항)
            
        Returns:
            bool: 초기화 성공 여부
        """
        try:
            # 설정에서 환경변수 키 가져오기
            try:
                config = get_database_config()
                connection_config = config.qdrant.connection
                env_url_key = connection_config.get('env_url_key', 'QDRANT_URL')
                env_api_key_key = connection_config.get('env_api_key_key', 'QDRANT_API_KEY')
                default_url = connection_config.get('url', 'http://localhost:6333')
            except Exception:
                env_url_key = 'QDRANT_URL'
                env_api_key_key = 'QDRANT_API_KEY'
                default_url = 'http://localhost:6333'
            
            if not qdrant_url:
                qdrant_url = os.getenv(env_url_key, default_url)
            
            if not api_key:
                api_key = os.getenv(env_api_key_key)
            
            self.store = QdrantVectorStore(url=qdrant_url, api_key=api_key)
            
            # 기본 컬렉션 생성
            await self.store.create_collection(self.default_collection, self.vector_dimension)
            
            logger.info(f"Qdrant 벡터 스토어 초기화 성공: {qdrant_url}")
            return True
            
        except Exception as e:
            logger.error(f"Qdrant 벡터 스토어 초기화 실패: {e}")
            return False
    
    async def store_document_vectors(self, document_id: str, 
                                   embeddings: List[Tuple[str, np.ndarray]],
                                   chunks: List[DocumentChunk],
                                   metadata: Dict[str, Any]) -> bool:
        """
        문서 벡터 저장
        
        Args:
            document_id: 문서 ID
            embeddings: 청크 임베딩 [(chunk_id, vector), ...]
            chunks: 문서 청크들
            metadata: 문서 메타데이터
            
        Returns:
            bool: 저장 성공 여부
        """
        if not self.store:
            logger.error("벡터 스토어가 초기화되지 않았습니다")
            return False
        
        try:
            # 청크 정보를 dict로 변환
            chunk_dict = {chunk.chunk_id: chunk for chunk in chunks}
            
            # 벡터 데이터 준비
            vectors = []
            for chunk_id, vector in embeddings:
                chunk = chunk_dict.get(chunk_id)
                if not chunk:
                    continue
                    
                # 설정에서 콘텐츠 길이 제한 가져오기
                try:
                    config = get_database_config()
                    content_limit = config.qdrant.vector_processing.get('content_preview_length', 500)
                except Exception:
                    content_limit = 500
                
                vector_metadata = {
                    'document_id': document_id,
                    'chunk_id': chunk_id,
                    'content': chunk.content[:content_limit],  # 검색 결과 표시용 (길이 제한)
                    'page_number': chunk.page_number,
                    'section_title': chunk.section_title or "",
                    'chunk_index': chunk.metadata.get('index', 0),
                    'created_at': datetime.now().isoformat(),
                    **metadata  # 문서 메타데이터 추가
                }
                
                vectors.append((chunk_id, vector, vector_metadata))
            
            # 벡터 차원 동적 업데이트
            if vectors and len(vectors[0][1]) != self.vector_dimension:
                self.vector_dimension = len(vectors[0][1])
                logger.info(f"벡터 차원 업데이트: {self.vector_dimension}")
                # 컬렉션 재생성 필요 시 처리
                await self.store.create_collection(self.default_collection, self.vector_dimension)
            
            # 벡터 스토어에 저장
            success = await self.store.insert_vectors(
                self.default_collection, 
                vectors
            )
            
            if success:
                logger.info(f"문서 벡터 저장 성공: {document_id} - {len(vectors)}개 벡터")
            
            return success
            
        except Exception as e:
            logger.error(f"문서 벡터 저장 실패 {document_id}: {e}")
            return False
    
    async def document_exists(self, document_id: str) -> bool:
        """
        문서의 벡터가 존재하는지 확인
        
        Args:
            document_id: 문서 ID
            
        Returns:
            bool: 벡터 존재 여부
        """
        if not self.store:
            return False
            
        if not QDRANT_AVAILABLE:
            return False
            
        try:
            # 해당 문서의 벡터 개수 확인
            from qdrant_client.models import Filter as QFilter, FieldCondition as QFieldCondition, MatchValue as QMatchValue
            result = self.store.client.scroll(
                collection_name=self.default_collection,
                scroll_filter=QFilter(
                    must=[
                        QFieldCondition(
                            key="document_id",
                            match=QMatchValue(value=document_id)
                        )
                    ]
                ),
                limit=1
            )
            
            # 결과가 있으면 문서 존재
            return len(result[0]) > 0
            
        except Exception as e:
            logger.warning(f"문서 존재 여부 확인 중 오류 {document_id}: {e}")
            return False
    
    async def search_similar_chunks(self, query_vector: np.ndarray,
                                  top_k: Optional[int] = None,
                                  document_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        유사한 청크 검색
        
        Args:
            query_vector: 쿼리 벡터
            top_k: 반환할 최대 개수 (None이면 설정에서 로드)
            document_filter: 특정 문서로 제한
            
        Returns:
            List[Dict]: 검색 결과
        """
        if not self.store:
            logger.warning("벡터 스토어가 초기화되지 않았습니다")
            return []
        
        # top_k 기본값 설정
        if top_k is None:
            try:
                config = get_database_config()
                top_k = config.qdrant.search.get('default_top_k', 20)
            except Exception:
                top_k = 20
        
        # top_k가 여전히 None이면 기본값 사용 (타입 안전성)
        if top_k is None:
            top_k = 20
        
        # 필터 조건
        filter_conditions = {}
        if document_filter:
            filter_conditions['document_id'] = document_filter
        
        results = await self.store.search_vectors(
            self.default_collection,
            query_vector,
            top_k,
            filter_conditions if filter_conditions else None
        )
        
        logger.debug(f"벡터 검색 완료: {len(results)}개 결과 (top_k={top_k})")
        return results
    
    async def delete_document_vectors(self, document_id: str) -> bool:
        """
        문서의 모든 벡터 삭제
        
        Args:
            document_id: 문서 ID
            
        Returns:
            bool: 삭제 성공 여부
        """
        if not self.store:
            return False
        
        try:
            # Qdrant의 필터 기반 삭제 사용
            if not QDRANT_AVAILABLE:
                return False
                
            from qdrant_client import models
            
            # FilterSelector를 사용한 필터 기반 삭제
            self.store.client.delete(
                collection_name=self.default_collection,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id)
                            )
                        ]
                    )
                ),
                wait=True  # 삭제가 완료될 때까지 대기
            )
            
            logger.info(f"문서 벡터 삭제 성공: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"문서 벡터 삭제 실패 {document_id}: {e}")
            return False
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """컬렉션 통계 정보 조회"""
        if not self.store:
            return {}
        
        return await self.store.get_collection_info(self.default_collection)
    
    def get_store_info(self) -> Dict[str, Any]:
        """벡터 스토어 정보 조회"""
        return {
            'type': 'qdrant',
            'initialized': self.store is not None,
            'default_collection': self.default_collection,
            'qdrant_available': QDRANT_AVAILABLE,
            'url': self.store.url if self.store else None
        }

# 글로벌 벡터 스토어 매니저 인스턴스
vector_store = VectorStoreManager()