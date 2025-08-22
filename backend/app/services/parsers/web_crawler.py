import requests
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any
import time
import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .base import BaseDocumentParser, ParsedDocument, DocumentChunk

class WebCrawlerParser(BaseDocumentParser):
    """웹 크롤링 파서"""
    
    def __init__(self, use_playwright: bool = False, delay: float = 1.0):
        self.use_playwright = use_playwright and PLAYWRIGHT_AVAILABLE
        self.delay = delay  # 요청 간 지연시간
        
    def parse(self, file_path: str, max_depth: int = 1, same_domain: bool = True, **kwargs) -> ParsedDocument:
        """웹페이지를 크롤링하여 청크로 분할"""
        
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
                chunks, links = self._crawl_single_page(current_url)
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
                    time.sleep(self.delay)
                    
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
    
    def _crawl_single_page(self, url: str) -> tuple[List[DocumentChunk], List[str]]:
        """단일 웹페이지 크롤링"""
        
        if self.use_playwright:
            return self._crawl_with_playwright(url)
        else:
            return self._crawl_with_requests(url)
    
    def _crawl_with_requests(self, url: str) -> tuple[List[DocumentChunk], List[str]]:
        """requests + BeautifulSoup을 사용한 크롤링"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 스크립트와 스타일 제거
        for script in soup(["script", "style"]):
            script.decompose()
        
        # 텍스트 추출
        text = soup.get_text()
        clean_text = ' '.join(text.split())
        
        # 링크 추출  
        links = []
        for a in soup.find_all('a', href=True):
            if hasattr(a, 'get'):
                href = a.get('href')
                if href and isinstance(href, str):
                    links.append(href)
        
        # 청크 생성
        chunks = self._create_chunks_from_text(clean_text, url)
        
        return chunks, links
    
    def _crawl_with_playwright(self, url: str) -> tuple[List[DocumentChunk], List[str]]:
        """Playwright를 사용한 동적 콘텐츠 크롤링"""
        chunks: List[DocumentChunk] = []
        links = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(url, wait_until='networkidle')
                
                # 텍스트 추출
                text_content = page.evaluate('() => document.body.innerText')
                
                # 링크 추출
                links = page.evaluate('''
                    () => Array.from(document.querySelectorAll('a[href]'))
                           .map(a => a.href)
                           .filter(href => href.startsWith('http'))
                ''')
                
                # 청크 생성
                chunks = self._create_chunks_from_text(text_content, url)
                
            finally:
                browser.close()
        
        return chunks, links
    
    def _create_chunks_from_text(self, text: str, source_url: str, chunk_size: int = 1000) -> List[DocumentChunk]:
        """텍스트에서 청크 생성"""
        chunks: List[DocumentChunk] = []
        words = text.split()
        
        current_chunk: List[str] = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1
            if current_size + word_size > chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunk = DocumentChunk(
                    content=chunk_text,
                    metadata={
                        "source_url": source_url,
                        "source_type": "web",
                        "chunk_size": len(chunk_text)
                    },
                    chunk_id=f"web_{len(chunks):04d}_{urlparse(source_url).netloc}",
                )
                chunks.append(chunk)
                current_chunk = [word]
                current_size = word_size
            else:
                current_chunk.append(word)
                current_size += word_size
        
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunk = DocumentChunk(
                content=chunk_text,
                metadata={
                    "source_url": source_url,
                    "source_type": "web",
                    "chunk_size": len(chunk_text)
                },
                chunk_id=f"web_{len(chunks):04d}_{urlparse(source_url).netloc}",
            )
            chunks.append(chunk)
        
        return chunks
    
    def get_supported_extensions(self) -> List[str]:
        return ['url', 'http', 'https']