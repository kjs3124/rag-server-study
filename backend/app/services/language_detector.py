"""
언어 감지 서비스
다국어 텍스트에서 언어별 비율을 계산하여 최적 임베딩 모델 선택을 지원
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from langdetect import detect, detect_langs, LangDetectException
import re
from ..services.parsers.base import DocumentChunk

logger = logging.getLogger(__name__)

class LanguageDetector:
    """
    언어 감지 및 분석 서비스
    
    주요 기능:
    - 텍스트 청크별 언어 감지
    - 문서 전체 언어 비율 계산
    - CJK(한중일) 언어 특별 처리
    - 최적 임베딩 모델 추천
    """
    
    def __init__(self):
        self.supported_languages = {
            'ko': '한국어',
            'en': '영어', 
            'ja': '일본어',
            'zh': '중국어',
            'zh-cn': '중국어(간체)',
            'zh-tw': '중국어(번체)'
        }
        
        # CJK 언어 그룹
        self.cjk_languages = {'ko', 'ja', 'zh', 'zh-cn', 'zh-tw'}
        
        # 최소 텍스트 길이 (너무 짧으면 정확도 떨어짐)
        self.min_text_length = 50
        
    def detect_language(self, text: str) -> Optional[str]:
        """
        단일 텍스트의 언어 감지
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            Optional[str]: 감지된 언어 코드 (실패 시 None)
        """
        if not text or len(text.strip()) < 10:
            return None
            
        try:
            # 텍스트 전처리 - 특수문자, 숫자 제거
            clean_text = self._clean_text_for_detection(text)
            if len(clean_text) < 10:
                return None
                
            detected = detect(clean_text)
            return detected
            
        except LangDetectException as e:
            logger.debug(f"언어 감지 실패: {e}")
            return None
        except Exception as e:
            logger.warning(f"언어 감지 오류: {e}")
            return None
    
    def detect_language_probabilities(self, text: str) -> List[Tuple[str, float]]:
        """
        텍스트의 언어별 확률 분석
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            List[Tuple[str, float]]: [(언어코드, 확률), ...] 내림차순 정렬
        """
        if not text or len(text.strip()) < 10:
            return []
            
        try:
            clean_text = self._clean_text_for_detection(text)
            if len(clean_text) < 10:
                return []
                
            detected_langs = detect_langs(clean_text)
            return [(lang.lang, lang.prob) for lang in detected_langs]
            
        except LangDetectException:
            return []
        except Exception as e:
            logger.warning(f"언어 확률 감지 오류: {e}")
            return []
    
    def analyze_document_languages(self, chunks: List[DocumentChunk]) -> Dict[str, float]:
        """
        문서 청크들의 전체 언어 분포 분석
        
        Args:
            chunks: 문서 청크 리스트
            
        Returns:
            Dict[str, float]: 언어별 비율 (0.0~1.0)
        """
        if not chunks:
            return {}
            
        language_counts = {}
        total_chunks = 0
        
        for chunk in chunks:
            if not chunk.content or len(chunk.content.strip()) < self.min_text_length:
                continue
                
            detected_lang = self.detect_language(chunk.content)
            if detected_lang:
                language_counts[detected_lang] = language_counts.get(detected_lang, 0) + 1
                total_chunks += 1
        
        if total_chunks == 0:
            return {}
            
        # 비율 계산
        language_ratios = {}
        for lang, count in language_counts.items():
            language_ratios[lang] = count / total_chunks
            
        # 정렬 (비율 높은 순)
        sorted_ratios = dict(sorted(language_ratios.items(), key=lambda x: x[1], reverse=True))
        
        logger.info(f"문서 언어 분석 완료: {sorted_ratios} (총 {total_chunks}개 청크)")
        return sorted_ratios
    
    def recommend_embedding_model(self, language_ratios: Dict[str, float]) -> str:
        """
        언어 비율 기반 최적 임베딩 모델 추천
        
        Args:
            language_ratios: 언어별 비율
            
        Returns:
            str: 추천 모델명 ('bge-m3' or 'multilingual-e5-large')
        """
        if not language_ratios:
            return 'multilingual-e5-large'  # 기본값
            
        korean_ratio = language_ratios.get('ko', 0)
        english_ratio = language_ratios.get('en', 0)
        
        # CJK 언어 총 비율 계산
        cjk_ratio = sum(
            language_ratios.get(lang, 0) 
            for lang in self.cjk_languages
        )
        
        # 모델 선택 로직 (ARCHITECTURE.md 기준)
        if korean_ratio > 0.6:
            model = 'bge-m3'
            reason = f"한국어 비율 높음 ({korean_ratio:.1%})"
        elif cjk_ratio > 0.4:
            model = 'bge-m3'  
            reason = f"CJK 언어 비율 높음 ({cjk_ratio:.1%})"
        elif english_ratio > 0.6:
            model = 'multilingual-e5-large'
            reason = f"영어 비율 높음 ({english_ratio:.1%})"
        else:
            model = 'multilingual-e5-large'  # 혼재 문서
            reason = "다국어 혼재 문서"
            
        logger.info(f"임베딩 모델 추천: {model} - {reason}")
        return model
    
    def get_language_summary(self, language_ratios: Dict[str, float]) -> Dict[str, Any]:
        """
        언어 분석 결과 요약 정보 생성
        
        Args:
            language_ratios: 언어별 비율
            
        Returns:
            Dict: 요약 정보
        """
        if not language_ratios:
            return {
                'primary_language': 'unknown',
                'language_count': 0,
                'is_multilingual': False,
                'cjk_dominant': False,
                'recommended_model': 'multilingual-e5-large'
            }
            
        primary_lang = max(language_ratios.items(), key=lambda x: x[1])
        cjk_ratio = sum(language_ratios.get(lang, 0) for lang in self.cjk_languages)
        
        return {
            'primary_language': primary_lang[0],
            'primary_language_ratio': primary_lang[1],
            'primary_language_name': self.supported_languages.get(primary_lang[0], primary_lang[0]),
            'language_count': len(language_ratios),
            'is_multilingual': len(language_ratios) > 1,
            'cjk_dominant': cjk_ratio > 0.5,
            'cjk_ratio': cjk_ratio,
            'english_ratio': language_ratios.get('en', 0),
            'korean_ratio': language_ratios.get('ko', 0),
            'recommended_model': self.recommend_embedding_model(language_ratios),
            'all_languages': language_ratios
        }
    
    def _clean_text_for_detection(self, text: str) -> str:
        """
        언어 감지를 위한 텍스트 전처리
        
        Args:
            text: 원본 텍스트
            
        Returns:
            str: 정리된 텍스트
        """
        # URL, 이메일, 숫자 제거
        text = re.sub(r'https?://\S+|www\.\S+', '', text)
        text = re.sub(r'\S+@\S+\.\S+', '', text)
        text = re.sub(r'\d+', '', text)
        
        # 과도한 특수문자 제거 (일부 구두점은 보존)
        text = re.sub(r'[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ一-龯ひらがなカタカナ.,!?;:]', ' ', text)
        
        # 중복 공백 제거
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

# 글로벌 언어 감지기 인스턴스
language_detector = LanguageDetector()

def detect_document_language(chunks: List[DocumentChunk]) -> Dict[str, Any]:
    """
    문서 언어 감지 편의 함수
    
    Args:
        chunks: 문서 청크 리스트
        
    Returns:
        Dict: 언어 분석 결과 요약
    """
    language_ratios = language_detector.analyze_document_languages(chunks)
    return language_detector.get_language_summary(language_ratios)