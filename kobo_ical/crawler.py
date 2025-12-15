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

    # ------------------------
    # 清理書籍文字
    # ------------------------
    @staticmethod
    def clean_summary(text: str) -> str:
        if not text:
            return ""
        remove_list = [
            "查看電子書（HK）",
            "查看電子書 (HK)",
            "查看電子書",
            "閱讀電子書",
            "電子書",
        ]
        for rm in remove_list:
            text = text.replace(rm, "")
        return text.strip()

    # ------------------------
    # 解析單篇文章書籍
    # ------------------------
    def parse_weekly_article(self, html: str, article_url: str, year: int, week: int) -> List[BookItem]:
        soup = BeautifulSoup(html, "html.parser")
        books = []

        article_date = self.parse_article_date(soup, article_url)
        if not article_date:
            logger.warning(f"Could not determine date for article {article_url}, skipping")
            return books

        # 解析文章標題
        article_title = ""
        h1 = soup.find('h1')
        if h1:
            article_title = h1.get_text(strip=True)
        if not article_title:
            title_tag = soup.find('title')
            if title_tag:
                article_title = title_tag.get_text(strip=True)

        ebook_links = soup.find_all('a', href=re.compile(r'/ebook/'))
        if not ebook_links:
            logger.warning(f"No ebook links found in article: {article_url}")
            return books

        elements = []
        seen_links = set()
        for link_elem in ebook_links:
            href = link_elem.get('href', '')
            if href in seen_links:
                continue
            seen_links.add(href)
            parent = link_elem.find_parent(['div', 'article', 'section', 'li', 'p'])
            if parent and parent not in elements:
                elements.append(parent)

        assigned_dates = set()
        for idx, elem in enumerate(elements):
            try:
                title = None
                link_elem = elem.find('a', href=re.compile(r'/ebook/'))
                if link_elem:
                    title = link_elem.get_text(strip=True)
                if not title or len(title) < 2:
                    title_selectors = ['h2', 'h3', 'h4', 'h5', '[class*="title"]', '[class*="Title"]']
                    for sel in title_selectors:
                        t_elem = elem.select_one(sel)
                        if t_elem:
                            t_text = t_elem.get_text(strip=True)
                            if t_text and len(t_text) > 2:
                                title = t_text
                                break
                if not title or len(title) < 2:
                    if link_elem:
                        title = link_elem.get('title', '') or link_elem.get('aria-label', '')

                title = self.clean_summary(title)
                # 過濾不需要的標題
                if not title or re.fullmatch(r'(查看電子書（HK）|查看電子書|閱讀電子書|電子書)', title):
                    continue

                book_url = None
                if link_elem:
                    href = link_elem.get('href', '')
                    if href:
                        book_url = urljoin('https://www.kobo.com', href)

                # 額外過濾：排除 HK 網域與非 99 清單來源
                if book_url and ('/hk/zh/ebook/' in book_url or 'twblog-hksite' in book_url):
                    continue
                # 優先保留含 99 清單來源標記的連結
                if book_url and ('coin99_' not in book_url and 'utm_source=twblog' not in book_url):
                    continue

                if title and book_url and len(title.strip()) > 0:
                    days_offset = idx % 7
                    book_date = article_date + timedelta(days=days_offset)
                    # W49 特例：固定至 2025-12-04..2025-12-10
                    if re.search(r'weekly-dd99-2025-w49', article_url):
                        base = date(2025,12,4)
                        book_date = base + timedelta(days=days_offset)
                    if book_date in assigned_dates:
                        continue
                    assigned_dates.add(book_date)
                    # 擷取核心內容（移除連結與價格字樣）
                    raw_text = elem.get_text(" ", strip=True)
                    raw_text = re.sub(r'https?://\S+', '', raw_text)
                    raw_text = re.sub(r'99元|NT\$?\s*99|HK\$?\s*99|購買|查看電子書（HK）|查看電子書', '', raw_text)
                    content = raw_text.strip()
                    # 限長
                    if len(content) > 400:
                        content = content[:380] + '…'
                    book = BookItem(
                        title=title.strip(),
                        book_url=book_url,
                        article_url=article_url,
                        article_title=article_title,
                        content=content,
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

    def get_current_week_info(self) -> tuple[int, int]:
        today = date.today()
        y, w, _ = today.isocalendar()
        return int(y), int(w)

    # ------------------------
    # 從文章或 URL 解析日期
    # ------------------------
    def parse_article_date(self, soup: BeautifulSoup, article_url: str) -> Optional[date]:
        date_patterns = [
            r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})[日]?',
            r'(\d{4})-(\d{2})-(\d{2})',
        ]
        date_selectors = [
            'time[datetime]', '.date', '.published-date', '[class*="date"]', '[class*="Date"]'
        ]
        for sel in date_selectors:
            elems = soup.select(sel)
            for elem in elems:
                dt_attr = elem.get('datetime')
                if dt_attr:
                    try:
                        dt = datetime.fromisoformat(dt_attr.replace('Z', '+00:00'))
                        return dt.date()
                    except (ValueError, AttributeError):
                        pass
                text = elem.get_text(strip=True)
                for pattern in date_patterns:
                    m = re.search(pattern, text)
                    if m:
                        try:
                            y, mth, d = map(int, m.groups())
                            return date(y, mth, d)
                        except (ValueError, TypeError):
                            continue
        # 從 URL 解析
        # W49 特例：固定回指定週起始日
        if re.search(r'weekly-dd99-2025-w49', article_url):
            return date(2025,12,4)
        m = re.search(r'weekly-dd99-(\d{4})-w(\d+)', article_url)
        if m:
            y, w = int(m.group(1)), int(m.group(2))
            jan1 = date(y, 1, 1)
            days_offset = (w - 1) * 7
            week_start = jan1 + timedelta(days=-jan1.weekday() + days_offset)
            return week_start
        logger.warning(f"Could not parse date from article: {article_url}")
        return None

    # ------------------------
    # 生成週次 URL
    # ------------------------
    def generate_weekly_urls(self, start_year: int, start_week: int, end_year: int, end_week: int) -> List[str]:
        start_year, start_week = int(start_year), int(start_week)
        end_year, end_week = int(end_year), int(end_week)
        urls = []
        y, w = start_year, start_week
        MAX_WEEK = 52
        while (y < end_year) or (y == end_year and w <= end_week):
            if w > MAX_WEEK:
                w = 1
                y += 1
                continue
            urls.append(f"https://www.kobo.com/zh/blog/weekly-dd99-{y}-w{w}")
            w += 1
        return urls

    # ------------------------
    # 抓取單頁面
    # ------------------------
    def fetch_page(self, url: str, use_random_delay: bool = False) -> Optional[str]:
        if use_random_delay:
            time.sleep(random.uniform(1, 3))
        for attempt in range(self.max_retries):
            try:
                headers = get_random_headers(referer="https://www.kobo.com/zh/blog")
                if use_random_delay:
                    headers = shuffle_headers_order(headers)
                response = self.client.get(url, headers=headers)
                if response.status_code in [403, 429] or (500 <= response.status_code < 600):
                    if attempt < self.max_retries - 1:
                        time.sleep(random.uniform(2, 5))
                        continue
                    else:
                        if self.use_playwright_fallback and response.status_code == 403:
                            try:
                                from playwright.sync_api import sync_playwright
                                logger.info(f"Using Playwright fallback for: {url}")
                                with sync_playwright() as p:
                                    browser = p.chromium.launch(headless=True)
                                    context = browser.new_context()
                                    page = context.new_page()
                                    page.goto(url, wait_until="networkidle", timeout=60000)
                                    time.sleep(2)
                                    html = page.content()
                                    browser.close()
                                    if html:
                                        return html
                            except Exception as e:
                                logger.error(f"Playwright fallback failed: {e}")
                        return None
                response.raise_for_status()
                time.sleep(self.settings.rate_limit_seconds)
                return response.text
            except Exception as e:
                logger.warning(f"Fetch error {url}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(random.uniform(2, 5))
                    continue
                return None

    # ------------------------
    # 爬取多週書籍
    # ------------------------
    def crawl_weekly_books(self, start_year: Optional[int] = None, start_week: Optional[int] = None,
                           end_year: Optional[int] = None, end_week: Optional[int] = None,
                           use_random_delay: bool = False) -> List[BookItem]:
        today = date.today()
        if start_year is None or start_week is None:
            start_year, start_week, _ = today.isocalendar()
        start_year, start_week = int(start_year), int(start_week)

        if end_year is None or end_week is None:
            c_year, c_week, _ = today.isocalendar()
            end_year = int(c_year)
            end_week = int(min(c_week, 52))
        end_year, end_week = int(end_year), int(end_week)

        urls = self.generate_weekly_urls(start_year, start_week, end_year, end_week)
        all_books = []

        for url in urls:
            m = re.search(r'weekly-dd99-(\d{4})-w(\d+)', url)
            if not m:
                continue
            y, w = int(m.group(1)), int(m.group(2))
            html = self.fetch_page(url, use_random_delay)
            if html:
                books = self.parse_weekly_article(html, url, y, w)
                all_books.extend(books)
                time.sleep(self.settings.request_delay_seconds)
            else:
                logger.warning(f"Skipping {url} due to fetch failure")

        logger.info(f"Total books crawled: {len(all_books)}")
        return all_books
