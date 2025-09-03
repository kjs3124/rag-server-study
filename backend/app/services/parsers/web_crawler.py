import requests
from urllib.parse import urljoin, urlparse
from typing import List, Optional, Any, Tuple, Union

urllib3: Optional[Any] = None
try:
    import urllib3 as _urllib3  # type: ignore
    urllib3 = _urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    urllib3 = None
import asyncio

try:
    from bs4 import BeautifulSoup, Tag
    BS4_AVAILABLE = True
    BeautifulSoup_TYPE: Optional[Any] = BeautifulSoup
except ImportError:
    BS4_AVAILABLE = False
    BeautifulSoup_TYPE = None

# LangChain HTML splitter
HTMLHeaderTextSplitter: Any = None
HTML_SPLITTER_AVAILABLE = False
try:
    from langchain_text_splitters import HTMLHeaderTextSplitter as _HTMLHeaderTextSplitter
    HTMLHeaderTextSplitter = _HTMLHeaderTextSplitter
    HTML_SPLITTER_AVAILABLE = True
except ImportError:
    HTML_SPLITTER_AVAILABLE = False

trafilatura: Any = None
TRAFILATURA_AVAILABLE = False
try:
    import trafilatura as _trafilatura
    trafilatura = _trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk
from ...core.config import get_crawler_config

class WebCrawlerParser(BaseDocumentParser):
    """웹 크롤링 파서"""
    
    def __init__(self, delay: Optional[float] = None):
        # 설정에서 로드
        try:
            crawler_config = get_crawler_config()
            self.delay = delay or crawler_config.defaults.get('delay', 1.0)
            self._cancelled = False  # 중단 플래그
            self.config = crawler_config
        except Exception as e:
            # 설정 로드 실패 시 기본값 사용
            self.delay = delay or 1.0
            self._cancelled = False
            self.config = None
            print(f"크롤러 설정 로드 실패, 기본값 사용: {e}")
        
    def _should_continue(self) -> bool:
        """크롤링 계속 여부 확인"""
        return not self._cancelled
        
    def cancel(self):
        """크롤링 중단"""
        self._cancelled = True
        
    def parse(self, file_path: str, chunk_size: int = 1000, chunk_overlap: Optional[int] = None, 
              max_depth: int = 1, same_domain: bool = True, **kwargs) -> ParsedDocument:
        """웹페이지를 크롤링하여 청크로 분할"""
        
        # nest-asyncio로 이벤트 루프 중첩 허용
        try:
            import nest_asyncio  # type: ignore
            nest_asyncio.apply()
        except ImportError:
            pass  # nest_asyncio가 없으면 무시
        
        # 이벤트 루프 처리
        try:
            loop = asyncio.get_running_loop()
            # 이미 실행 중인 루프가 있으면 새 루프 생성
            import threading
            import concurrent.futures
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(
                        self._async_parse(file_path, chunk_size, chunk_overlap, max_depth, same_domain, **kwargs)
                    )
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
                
        except RuntimeError:
            # 루프가 없으면 새로 생성
            return asyncio.run(self._async_parse(file_path, chunk_size, chunk_overlap, max_depth, same_domain, **kwargs))
    
    async def _async_parse(self, file_path: str, chunk_size: int = 1000, chunk_overlap: Optional[int] = None, max_depth: int = 1, same_domain: bool = True, **kwargs) -> ParsedDocument:
        """실제 비동기 파싱 로직"""
        
        if not BS4_AVAILABLE:
            raise ImportError("웹 크롤링을 위해 beautifulsoup4가 필요합니다")
        
        url = file_path  # URL을 file_path로 받음
        
        # 단일 URL만 크롤링 (링크 따라가기 없음)
        try:
            # 중단 체크
            if not self._should_continue():
                print("크롤링이 중단되었습니다.")
                return ParsedDocument(chunks=[], metadata={"source_type": "web_crawl", "base_url": url}, file_type="web")
                
            chunks, _ = await self._crawl_single_page(url, chunk_size, chunk_overlap, **kwargs)
            
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("크롤링이 사용자에 의해 중단되었습니다.")
            raise
        except Exception as e:
            error_msg = str(e)
            if "Exceeded 0 redirects" in error_msg:
                print(f"리다이렉션 제한으로 실패: {url}")
            else:
                print(f"URL 크롤링 오류 {url}: {error_msg}")
            chunks = []
        
        return ParsedDocument(
            chunks=chunks,
            metadata={
                "source_type": "web_crawl",
                "base_url": url,
                "total_chunks": len(chunks),
                "crawled_urls": 1,
                "max_depth": max_depth
            },
            file_type="web"
        )
    
    async def _crawl_single_page(self, url: str, chunk_size: int = 1000, chunk_overlap: Optional[int] = None, **kwargs) -> Tuple[List[DocumentChunk], List[str]]:
        """단일 웹페이지 크롤링"""
        return await self._crawl_with_trafilatura(url, chunk_size, chunk_overlap, **kwargs)
    
    async def _crawl_with_trafilatura(self, url: str, chunk_size: int = 1000, chunk_overlap: Optional[int] = None, max_depth: int = 1, same_domain: bool = True, **kwargs) -> Tuple[List[DocumentChunk], List[str]]:
        """trafilatura를 사용한 고품질 텍스트 추출"""
        
        # 설정에서 헤더 로드
        if self.config:
            headers = self.config.request.get('headers', {})
        else:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        
        import ssl
            
        # SSL 검증 비활성화 및 urllib3 리다이렉션 비활성화
        import os
        os.environ['PYTHONHTTPSVERIFY'] = '0'
        os.environ['CURL_CA_BUNDLE'] = ''
        
        
        # 중단 체크
        if not self._should_continue():
            return [], []
            
        # trafilatura 크롤링으로 텍스트 추출
        if TRAFILATURA_AVAILABLE and trafilatura is not None:
            try:
                # 크롤링 설정 (trafilatura 기본값들 포함)
                import configparser
                config = configparser.ConfigParser()
                
                # 설정에서 trafilatura 옵션 로드
                if self.config and self.config.trafilatura:
                    trafilatura_settings = self.config.trafilatura
                else:
                    # 기본 설정값들
                    trafilatura_settings = {
                        'MAX_REDIRECTS': '0',
                        'DOWNLOAD_TIMEOUT': '30',
                        'MIN_FILE_SIZE': '10',
                        'MAX_FILE_SIZE': '20000000',
                        'SLEEP_TIME': '5',
                        'COOKIE': '',
                        'USER_AGENTS': '',
                        'MIN_EXTRACTED_SIZE': '250',
                        'MIN_OUTPUT_SIZE': '1',
                        'EXTRACTION_TIMEOUT': '30'
                    }
                
                # trafilatura 설정 적용
                for key, value in trafilatura_settings.items():
                    config.set('DEFAULT', key, str(value))
                
                # trafilatura 크롤링 실행
                from trafilatura.spider import focused_crawler
                
                # 설정에서 크롤링 제한 로드
                if self.config and self.config.limits:
                    url_multiplier = self.config.limits.get('url_multiplier', 10)
                    max_urls_multi = self.config.limits.get('max_urls_multi_depth', 30)
                    max_urls_single = self.config.limits.get('max_urls_single_depth', 1)
                else:
                    url_multiplier = 10
                    max_urls_multi = 30
                    max_urls_single = 1
                    
                # max_depth에 따른 크롤링 URL 개수 결정
                max_urls = min(max_depth * url_multiplier, max_urls_multi) if max_depth > 1 else max_urls_single
                
                if max_depth <= 1:
                    # 단일 페이지만 처리
                    downloaded = trafilatura.fetch_url(url, no_ssl=True, config=config)
                    if downloaded:
                        chunks = self._process_single_page(downloaded, url, chunk_size, chunk_overlap, **kwargs)
                        return chunks, []
                else:
                    # 다중 페이지 크롤링 (trafilatura 공식 API)
                    to_visit, known_links = focused_crawler(
                        url, 
                        max_seen_urls=max_urls,
                        max_known_urls=max_urls * 10
                    )
                    all_chunks = []
                    crawled_count = 0
                    
                    for crawled_url in to_visit:
                        if not self._should_continue() or crawled_count >= max_urls:
                            break
                        
                        print(f"크롤링 중: {crawled_url}")
                        page_content = trafilatura.fetch_url(crawled_url, no_ssl=True, config=config)
                        if page_content:
                            chunks = self._process_single_page(page_content, crawled_url, chunk_size, chunk_overlap, **kwargs)
                            all_chunks.extend(chunks)
                            crawled_count += 1
                    
                    print(f"✅ 크롤링 완료: {crawled_count}개 페이지, {len(all_chunks)}개 청크")
                    return all_chunks, list(to_visit)
                    
                if downloaded:
                    # 1차: HTML 헤더 기반 구조적 청킹 시도
                    if HTML_SPLITTER_AVAILABLE and HTMLHeaderTextSplitter is not None:
                        try:
                            chunks, links = self._create_html_header_chunks(downloaded, url)
                            if chunks:
                                # 중단 체크 
                                if not self._should_continue():
                                    raise asyncio.CancelledError("크롤링 중단")
                                print(f"✅ HTML 헤더 청킹 성공: {len(chunks)}개 청크 생성")
                                return chunks, links
                        except Exception as e:
                            print(f"HTML 헤더 청킹 실패: {e}, 일반 텍스트 청킹으로 폴백")
                    
                    # 2차: trafilatura 텍스트 추출 + 커스텀 청킹
                    clean_text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
                    if clean_text and len(clean_text) > 50:
                        print(f"✅ trafilatura 텍스트 청킹 성공: {len(clean_text)}자 추출")
                        
                        # BeautifulSoup으로 링크 추출
                        links = []
                        if BeautifulSoup_TYPE is not None:
                            soup = BeautifulSoup_TYPE(downloaded, 'html.parser')
                            for a in soup.find_all('a', href=True):
                                href = a.get('href')
                                if href and isinstance(href, str) and href.strip():
                                    links.append(href)
                        
                        chunks = self._create_chunks_from_text(clean_text, url, chunk_size=chunk_size, chunk_overlap=chunk_overlap, **kwargs)
                        return chunks, links
            except Exception as e:
                print(f"trafilatura 실패: {e}, requests 폴백 시도")
        
        # 중단 체크 (폴백 전)
        if not self._should_continue():
            return [], []
            
        # 폴백: requests + BeautifulSoup (SSL 우회 적용)
        import requests
        import ssl
        
        # SSL 컨텍스트 전역 설정
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # requests 세션 SSL 우회 설정 및 리다이렉션 비활성화
        session = requests.Session()
        session.verify = False
        session.trust_env = False
        session.max_redirects = 0  # 리다이렉션 비활성화
        
        # requests 어댑터로 SSL 우회 강화
        from requests.adapters import HTTPAdapter
        from urllib3.util.ssl_ import create_urllib3_context
        
        class SSLNoRedirectAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **pool_kwargs):
                pool_kwargs['ssl_context'] = ssl_context
                return super().init_poolmanager(*args, **pool_kwargs)
            
            def send(self, request, stream=False, timeout=None, verify=None, cert=None, proxies=None):
                # 리다이렉션 완전 비활성화
                from requests import PreparedRequest, Response
                return super().send(request, stream=stream, timeout=timeout, verify=verify, cert=cert, proxies=proxies)
        
        session.mount('https://', SSLNoRedirectAdapter())
        session.mount('http://', SSLNoRedirectAdapter())
        
        # 설정에서 타임아웃 로드
        timeout = self.config.request.get('timeout', 10) if self.config else 10
        response = session.get(url, headers=headers, timeout=timeout, verify=False, allow_redirects=False)
        response.raise_for_status()
        
        if BeautifulSoup_TYPE is None:
            raise ImportError("BeautifulSoup이 설치되지 않았습니다")
        
        soup = BeautifulSoup_TYPE(response.content, 'html.parser')
        
        # 스크립트와 스타일 제거
        for script in soup(["script", "style"]):
            script.decompose()
        
        # 텍스트 추출
        text = soup.get_text()
        clean_text = ' '.join(text.split())
        
        # 링크 추출  
        links = []
        for a in soup.find_all('a', href=True):
            href = a.get('href')
            if href and isinstance(href, str) and href.strip():
                links.append(href)
        
        chunks = self._create_chunks_from_text(clean_text, url, chunk_size=chunk_size, chunk_overlap=chunk_overlap, **kwargs)
        return chunks, links
    
    # Playwright 메소드 제거됨
    
    def _create_chunks_from_text(self, text: str, source_url: str, chunk_size: int = 1000, chunk_overlap: Optional[int] = None, **kwargs) -> List[DocumentChunk]:
        """텍스트에서 청크 생성 (LangChain 기반)"""
        # 기본 매타데이타 준비
        base_metadata = {
            "source_url": source_url,
            "source_type": "web",
            "parser": "web_crawler"
        }
        
        # 기본 클래스의 LangChain 청킹 사용
        chunks = self._create_langchain_chunks(
            text=text,
            chunk_size=chunk_size,
            file_path=source_url,  # URL을 file_path로 사용
            chunk_overlap=chunk_overlap,
            source_url=source_url,
            source_type="web",
            parser="web_crawler"
        )
        
        # 청크 ID를 웹 크롤러용으로 수정
        for i, chunk in enumerate(chunks):
            chunk.chunk_id = f"web_{i:04d}_{urlparse(source_url).netloc}"
        
        return chunks
    
    def _create_html_header_chunks(self, html_content: str, source_url: str) -> Tuple[List[DocumentChunk], List[str]]:
        """HTML 헤더를 이용한 구조적 청킹"""
        
        if not HTML_SPLITTER_AVAILABLE or HTMLHeaderTextSplitter is None:
            raise ImportError("HTMLHeaderTextSplitter를 사용할 수 없습니다")
        
        # 설정에서 HTML 헤더 분할 설정 로드
        if self.config and self.config.html_parsing and 'headers_to_split' in self.config.html_parsing:
            headers_config = self.config.html_parsing['headers_to_split']
            headers_to_split_on = [(h['tag'], h['name']) for h in headers_config]
        else:
            # 기본 설정
            headers_to_split_on = [
                ("h1", "Header 1"),
                ("h2", "Header 2"), 
                ("h3", "Header 3"),
            ]
        
        html_splitter = HTMLHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        html_header_splits = html_splitter.split_text(html_content)
        
        chunks: List[DocumentChunk] = []
        
        # 각 분할된 텍스트를 DocumentChunk로 변환
        for i, split in enumerate(html_header_splits):
            if split.page_content.strip():
                # 헤더 메타데이터 추출
                header_info = split.metadata if hasattr(split, 'metadata') else {}
                
                chunk = DocumentChunk(
                    content=split.page_content,
                    metadata={
                        "source_url": source_url,
                        "source_type": "web_header",
                        "chunk_size": len(split.page_content),
                        "header_structure": header_info
                    },
                    chunk_id=f"web_header_{i:04d}_{urlparse(source_url).netloc}",
                )
                chunks.append(chunk)
        
        # BeautifulSoup으로 링크 추출
        links = []
        if BeautifulSoup_TYPE is not None:
            soup = BeautifulSoup_TYPE(html_content, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a.get('href')
                if href and isinstance(href, str) and href.strip():
                    links.append(href)
        
        return chunks, links
    
    def _process_single_page(self, html_content: str, url: str, chunk_size: int, chunk_overlap: Optional[int], **kwargs) -> List[DocumentChunk]:
        """단일 페이지 HTML 컨텐츠를 처리하여 청크 생성"""
        # 1차: HTML 헤더 기반 구조적 청킹 시도
        if HTML_SPLITTER_AVAILABLE and HTMLHeaderTextSplitter is not None:
            try:
                chunks, _ = self._create_html_header_chunks(html_content, url)
                if chunks:
                    return chunks
            except Exception as e:
                print(f"HTML 헤더 청킹 실패: {e}, 일반 텍스트 청킹으로 폴백")
        
        # 설정에서 trafilatura 추출 옵션 로드
        if self.config and self.config.trafilatura:
            include_comments = self.config.trafilatura.get('include_comments', False)
            include_tables = self.config.trafilatura.get('include_tables', True)
        else:
            include_comments = False
            include_tables = True
            
        # 2차: trafilatura 텍스트 추출 + 커스텀 청킹
        clean_text = trafilatura.extract(html_content, include_comments=include_comments, include_tables=include_tables)
        
        # 설정에서 최소 콘텐츠 길이 로드
        min_content_length = self.config.limits.get('content_min_length', 50) if self.config else 50
        if clean_text and len(clean_text) > min_content_length:
            return self._create_chunks_from_text(clean_text, url, chunk_size=chunk_size, chunk_overlap=chunk_overlap, **kwargs)
        
        return []

    def get_supported_extensions(self) -> List[str]:
        return ['url']