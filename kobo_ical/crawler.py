"""Kobo 99 元書單爬蟲（支援 Cloudflare 繞過）"""
import logging
import random
import re
import time
from datetime import date, datetime, timedelta
from typing import List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .config import Settings
from .models import BookItem
from utils.headers import get_random_headers, shuffle_headers_order

logger = logging.getLogger(__name__)


class KoboCrawler:
    """Kobo 99 元書單爬蟲（支援 Cloudflare 繞過）"""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.max_retries = 5
        self.use_playwright_fallback = True
        
        # 初始化 httpx client（使用 HTTP2）
        try:
            transport = httpx.HTTPTransport(http2=True)
            self.client = httpx.Client(
                transport=transport,
                timeout=30.0,
                follow_redirects=True,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize HTTP2 transport: {e}, falling back to HTTP/1.1")
            self.client = httpx.Client(
                timeout=30.0,
                follow_redirects=True,
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

    def get_current_week_info(self) -> tuple[int, int]:
        """取得當前年份和週數"""
        today = date.today()
        year, week, _ = today.isocalendar()
        return year, week

    def generate_weekly_urls(self, start_year: int, start_week: int, end_year: int, end_week: int) -> List[str]:
        """生成週次 URL 列表"""
        urls = []
        current_year = start_year
        current_week = start_week
        # 限制最大週數為 49（根據用戶需求，w50 以上暫時沒有）
        MAX_WEEK = 52

        while (current_year < end_year) or (current_year == end_year and current_week <= end_week):
            # 確保週數不超過 49
            if current_week > MAX_WEEK:
                break
            url = f"https://www.kobo.com/zh/blog/weekly-dd99-{current_year}-w{current_week}"
            urls.append(url)
            current_week += 1
            if current_week > 52:
                current_week = 1
                current_year += 1

        return urls

    def fetch_with_playwright(self, url: str) -> Optional[str]:
        """使用 Playwright headless browser 作為 fallback"""
        try:
            from playwright.sync_api import sync_playwright
            from utils.headers import get_random_headers
            
            logger.info(f"Using Playwright fallback for: {url}")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=get_random_headers()["User-Agent"],
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page()
                
                # 訪問頁面
                page.goto(url, wait_until="networkidle", timeout=60000)
                
                # 等待頁面載入完成
                time.sleep(2)
                
                # 獲取 HTML
                html = page.content()
                
                browser.close()
                return html
        except ImportError:
            logger.error("Playwright not installed. Install with: pip install playwright && playwright install chromium")
            return None
        except Exception as e:
            logger.error(f"Playwright fallback failed: {e}")
            return None

    def fetch_page(self, url: str, use_random_delay: bool = False) -> Optional[str]:
        """抓取單一頁面（支援 Cloudflare 繞過）"""
        # GitHub Actions 中的隨機延遲
        if use_random_delay:
            delay = random.uniform(1, 3)
            logger.info(f"Random delay: {delay:.2f}s")
            time.sleep(delay)
        
        for attempt in range(self.max_retries):
            try:
                # 生成隨機 headers
                headers = get_random_headers(referer="https://www.kobo.com/zh/blog")
                
                # 在 GitHub Actions 中隨機排序 headers
                if use_random_delay:
                    headers = shuffle_headers_order(headers)
                
                logger.info(f"Fetching: {url} (attempt {attempt + 1}/{self.max_retries})")
                
                response = self.client.get(url, headers=headers)
                status_code = response.status_code
                
                # 檢查是否需要重試
                if status_code in [403, 429] or (500 <= status_code < 600):
                    if attempt < self.max_retries - 1:
                        wait_time = random.uniform(2, 5)
                        logger.warning(
                            f"Received {status_code} for {url}, retrying after {wait_time:.2f}s "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        # 最後一次嘗試失敗，使用 Playwright fallback
                        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts (status: {status_code})")
                        if self.use_playwright_fallback and status_code == 403:
                            logger.info("Attempting Playwright fallback...")
                            html = self.fetch_with_playwright(url)
                            if html:
                                return html
                        return None
                
                # 成功取得回應
                response.raise_for_status()
                time.sleep(self.settings.rate_limit_seconds)
                return response.text
                
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code if e.response else 0
                if status_code in [403, 429] or (500 <= status_code < 600):
                    if attempt < self.max_retries - 1:
                        wait_time = random.uniform(2, 5)
                        logger.warning(
                            f"HTTP {status_code} error for {url}, retrying after {wait_time:.2f}s "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts (status: {status_code})")
                        if self.use_playwright_fallback and status_code == 403:
                            logger.info("Attempting Playwright fallback...")
                            html = self.fetch_with_playwright(url)
                            if html:
                                return html
                        return None
                else:
                    logger.error(f"HTTP error {status_code} for {url}: {e}")
                    return None
                    
            except httpx.RequestError as e:
                logger.warning(f"Request error for {url}: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = random.uniform(2, 5)
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
                    return None
            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = random.uniform(2, 5)
                    time.sleep(wait_time)
                    continue
                return None
        
        return None

    def parse_article_date(self, soup: BeautifulSoup, article_url: str) -> Optional[date]:
        """從文章頁面解析日期"""
        # 嘗試多種日期格式
        date_patterns = [
            r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})[日]?',  # 2024年12月1日
            r'(\d{4})-(\d{2})-(\d{2})',  # 2024-12-01
        ]

        # 查找日期相關的元素
        date_selectors = [
            'time[datetime]',
            '.date',
            '.published-date',
            '[class*="date"]',
            '[class*="Date"]',
        ]

        for selector in date_selectors:
            elements = soup.select(selector)
            for elem in elements:
                # 嘗試從 datetime 屬性取得
                datetime_attr = elem.get('datetime')
                if datetime_attr:
                    try:
                        dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                        return dt.date()
                    except (ValueError, AttributeError):
                        pass

                # 嘗試從文字內容解析
                text = elem.get_text(strip=True)
                for pattern in date_patterns:
                    match = re.search(pattern, text)
                    if match:
                        try:
                            year, month, day = map(int, match.groups())
                            return date(year, month, day)
                        except (ValueError, TypeError):
                            continue

        # 如果找不到，嘗試從 URL 解析（備用方案）
        week_match = re.search(r'weekly-dd99-(\d{4})-w(\d+)', article_url)
        if week_match:
            year = int(week_match.group(1))
            week = int(week_match.group(2))
            # 計算該週的第一天（週一）
            jan1 = date(year, 1, 1)
            days_offset = (week - 1) * 7
            week_start = jan1 + timedelta(days=-jan1.weekday() + days_offset)
            return week_start

        logger.warning(f"Could not parse date from article: {article_url}")
        return None

    def parse_weekly_article(self, html: str, article_url: str, year: int, week: int) -> List[BookItem]:
        """解析單一週次文章，提取書籍資訊"""
        soup = BeautifulSoup(html, "html.parser")
        books = []

        # 解析文章日期
        article_date = self.parse_article_date(soup, article_url)
        if not article_date:
            logger.warning(f"Could not determine date for article {article_url}, skipping")
            return books

        # 查找所有包含「查看電子書」連結的區塊
        # 先找到所有包含 /ebook/ 的連結
        ebook_links = soup.find_all('a', href=re.compile(r'/ebook/'))
        
        if not ebook_links:
            logger.warning(f"No ebook links found in article: {article_url}")
            return books

        # 為每個連結找到對應的書籍區塊
        elements = []
        seen_links = set()
        for link_elem in ebook_links:
            href = link_elem.get('href', '')
            if href in seen_links:
                continue
            seen_links.add(href)
            
            # 向上查找包含書籍資訊的父元素
            parent = link_elem.find_parent(['div', 'article', 'section', 'li', 'p'])
            if parent and parent not in elements:
                elements.append(parent)

        # 解析每個書籍區塊
        for idx, elem in enumerate(elements):
            try:
                # 查找標題
                title = None
                
                # 先從連結文字取得（通常最準確）
                link_elem = elem.find('a', href=re.compile(r'/ebook/'))
                if link_elem:
                    title = link_elem.get_text(strip=True)
                
                # 如果連結文字為空，嘗試從標題元素取得
                if not title or len(title) < 2:
                    title_selectors = ['h2', 'h3', 'h4', 'h5', '[class*="title"]', '[class*="Title"]']
                    for title_sel in title_selectors:
                        title_elem = elem.select_one(title_sel)
                        if title_elem:
                            title_text = title_elem.get_text(strip=True)
                            if title_text and len(title_text) > 2:
                                title = title_text
                                break
                
                # 如果還是找不到，嘗試從連結的 title 屬性取得
                if not title or len(title) < 2:
                    if link_elem:
                        title = link_elem.get('title', '') or link_elem.get('aria-label', '')

                # 查找「查看電子書」連結
                book_url = None
                link_elem = elem.find('a', href=re.compile(r'/ebook/'))
                if link_elem:
                    href = link_elem.get('href', '')
                    if href:
                        book_url = urljoin('https://www.kobo.com', href)

                # 如果標題和連結都存在，創建 BookItem
                if title and book_url and len(title.strip()) > 0:
                    # 計算該書籍對應的日期（假設每週有7本書，每天一本）
                    # 如果文章日期是週一，則第0本是週一，第1本是週二，以此類推
                    # 確保日期在該週內（週一到週日）
                    days_offset = idx % 7
                    book_date = article_date + timedelta(days=days_offset)

                    book = BookItem(
                        title=title.strip(),
                        book_url=book_url,
                        article_url=article_url,
                        date=book_date,
                        week=week,
                        year=year,
                    )
                    books.append(book)
                    logger.info(f"Found book: {title} ({book_date})")

            except Exception as e:
                logger.warning(f"Error parsing book element {idx}: {e}")
                continue

        return books

    def crawl_weekly_books(self, start_year: Optional[int] = None, start_week: Optional[int] = None,
                           end_year: Optional[int] = None, end_week: Optional[int] = None,
                           use_random_delay: bool = False) -> List[BookItem]:
        """爬取多個週次的書籍"""
        if start_year is None or start_week is None:
            # 預設從 2025 年第 1 週開始（Kobo 99 元書單大約從 2025 年開始）
            start_year = 2025
            start_week = 1

        if end_year is None or end_week is None:
            # 預設到當前週，但不超過 w49（根據用戶需求，w50 以上暫時沒有）
            current_year, current_week, _ = date.today().isocalendar()
            # 限制最大週數為 49
            if current_week <= 49:
                end_year = current_year
                end_week = current_week
            else:
                # 如果當前週超過 49，則結束於當前年份的 w49
                end_year = current_year
                end_week = 49

        urls = self.generate_weekly_urls(start_year, start_week, end_year, end_week)
        all_books = []

        for url in urls:
            # 從 URL 提取年份和週數
            match = re.search(r'weekly-dd99-(\d{4})-w(\d+)', url)
            if not match:
                continue
            year = int(match.group(1))
            week = int(match.group(2))

            html = self.fetch_page(url, use_random_delay=use_random_delay)
            if html:
                books = self.parse_weekly_article(html, url, year, week)
                all_books.extend(books)
                time.sleep(self.settings.request_delay_seconds)
            else:
                logger.warning(f"Skipping {url} due to fetch failure")

        logger.info(f"Total books crawled: {len(all_books)}")
        return all_books
