import requests
from urllib.parse import urljoin, urlparse
from typing import List, Optional, Any, Tuple

urllib3: Any = None
try:
    import urllib3 as _urllib3  # type: ignore
    urllib3 = _urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass
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

class WebCrawlerParser(BaseDocumentParser):
    """웹 크롤링 파서"""
    
    def __init__(self, delay: float = 1.0):
        self.delay = delay  # 요청 간 지연시간
        
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
        
        visited_urls = set()
        all_chunks: List[DocumentChunk] = []
        url = file_path  # URL을 file_path로 받음
        urls_to_visit = [(url, 0)]  # (url, depth)
        
        base_domain = urlparse(url).netloc if same_domain else None
        
        while urls_to_visit:
            current_url, depth = urls_to_visit.pop(0)
            
            if current_url in visited_urls or depth > max_depth:
                continue
                
            try:
                chunks, links = await self._crawl_single_page(current_url, chunk_size, chunk_overlap, **kwargs)
                all_chunks.extend(chunks)
                visited_urls.add(current_url)
                
                # 링크 추가 (깊이 제한 및 도메인 제한 확인)
                if depth < max_depth:
                    for link in links:
                        absolute_link = urljoin(current_url, link)
                        link_domain = urlparse(absolute_link).netloc
                        
                        if (not same_domain or link_domain == base_domain) and \
                           absolute_link not in visited_urls:
                            urls_to_visit.append((absolute_link, depth + 1))
                
                # 요청 간 지연
                if self.delay > 0:
                    await asyncio.sleep(self.delay)
                    
            except Exception as e:
                print(f"URL 크롤링 오류 {current_url}: {str(e)}")
                continue
        
        return ParsedDocument(
            chunks=all_chunks,
            metadata={
                "source_type": "web_crawl",
                "base_url": url,
                "total_chunks": len(all_chunks),
                "crawled_urls": len(visited_urls),
                "max_depth": max_depth
            },
            file_type="web"
        )
    
    async def _crawl_single_page(self, url: str, chunk_size: int = 1000, chunk_overlap: Optional[int] = None, **kwargs) -> Tuple[List[DocumentChunk], List[str]]:
        """단일 웹페이지 크롤링"""
        return await self._crawl_with_trafilatura(url, chunk_size, chunk_overlap, **kwargs)
    
    async def _crawl_with_trafilatura(self, url: str, chunk_size: int = 1000, chunk_overlap: Optional[int] = None, **kwargs) -> Tuple[List[DocumentChunk], List[str]]:
        """trafilatura를 사용한 고품질 텍스트 추출"""
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # trafilatura로 텍스트 추출
        if TRAFILATURA_AVAILABLE and trafilatura is not None:
            try:
                # trafilatura SSL 검증 우회 설정
                try:
                    # trafilatura config에 SSL 검증 비활성화 설정
                    config = trafilatura.settings.DEFAULT_CONFIG
                    config['VERIFY_SSL'] = False
                    downloaded = trafilatura.fetch_url(url, config=config)
                except:
                    # 폴백: 기본 설정으로 시도
                    downloaded = trafilatura.fetch_url(url)
                if downloaded:
                    # 1차: HTML 헤더 기반 구조적 청킹 시도
                    if HTML_SPLITTER_AVAILABLE and HTMLHeaderTextSplitter is not None:
                        try:
                            chunks, links = self._create_html_header_chunks(downloaded, url)
                            if chunks:
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
        
        # 폴백: requests + BeautifulSoup (동기 메서드를 비동기에서 호출하므로 직접 구현)
        response = requests.get(url, headers=headers, timeout=10, verify=False)
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
        
        # HTML 헤더 기반 분할 설정
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
    
    def get_supported_extensions(self) -> List[str]:
        return ['url']