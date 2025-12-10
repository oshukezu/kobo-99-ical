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
    # 書籍清理函式
    # ------------------------
    @staticmethod
    def clean_summary(text: str) -> str:
        """清理不需要的文字，例如 '查看電子書（HK）'"""
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
    # 取得週次 URL
    # ------------------------
    def generate_weekly_urls(self, start_year: int, start_week: int, end_year: int, end_week: int) -> List[str]:
        """生成週次 URL 列表"""
        if start_year is None or start_week is None:
            today = date.today()
            start_year, start_week, _ = today.isocalendar()
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
            url = f"https://www.kobo.com/zh/blog/weekly-dd99-{y}-w{w}"
            urls.append(url)
            w += 1

        return urls

    # ------------------------
    # 抓取頁面
    # ------------------------
    def fetch_with_playwright(self, url: str) -> Optional[str]:
        """使用 Playwright headless browser 作為 fallback"""
        try:
            from playwright.sync_api import sync_playwright

            logger.info(f"Using Playwright fallback for: {url}")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=get_random_headers()["User-Agent"],
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page()
                page.goto(url, wait_until="networkidle", timeout=60000)
                time.sleep(2)
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
        if use_random_delay:
            delay = random.uniform(1, 3)
            logger.info(f"Random delay: {delay:.2f}s")
            time.sleep(delay)

        for attempt in range(self.max_retries):
            try:
                headers = get_random_headers(referer="https://www.kobo.com/zh/blog")
                if use_random_delay:
                    headers = shuffle_headers_order(headers)

                logger.info(f"Fetching: {url} (attempt {attempt + 1}/{self.max_retries})")
                response = self.client.get(url, headers=headers)
                status_code = response.status_code

                if status_code in [403, 429] or (500 <= status_code < 600):
                    if attempt < self.max_retries - 1:
                        wait_time = random.uniform(2, 5)
                        logger.warning(f"Received {status_code} for {url}, retrying after {wait_time:.2f}s")
                        time.sleep(wait_time)
                        continue
                    else:
                        if self.use_playwright_fallback and status_code == 403:
                            html = self.fetch_with_playwright(url)
                            if html:
                                return html
                        return None

                response.raise_for_status()
                time.sleep(self.settings.rate_limit_seconds)
                return response.text

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                time.sleep(random.uniform(2, 5))
                continue

        return None

    # ------------------------
    # 解析文章日期
    # ------------------------
    def parse_article_date(self, soup: BeautifulSoup, article_url: str) -> Optional[date]:
        date_patterns = [
            r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})[日]?',
            r'(\d{4})-(\d{2})-(\d{2})',
        ]
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
                datetime_attr = elem.get('datetime')
                if datetime_attr:
                    try:
                        dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                        return dt.date()
                    except:
                        pass
                text = elem.get_text(strip=True)
                for pattern in date_patterns:
                    match = re.search(pattern, text)
                    if match:
                        try:
                            year, month, day = map(int, match.groups())
                            return date(year, month, day)
                        except:
                            continue

        week_match = re.search(r'weekly-dd99-(\d{4})-w(\d+)', article_url)
        if week_match:
            year = int(week_match.group(1))
            week = int(week_match.group(2))
            jan1 = date(year, 1, 1)
            days_offset = (week - 1) * 7
            week_start = jan1 + timedelta(days=-jan1.weekday() + days_offset)
            return week_start

        logger.warning(f"Could not parse date from article: {article_url}")
        return None

    # ------------------------
    # 解析單週文章
    # ------------------------
    def parse_weekly_article(self, html: str, article_url: str, year: int, week: int) -> List[BookItem]:
        soup = BeautifulSoup(html, "html.parser")
        books = []

        article_date = self.parse_article_date(soup, article_url)
        if not article_date:
            logger.warning(f"Could not determine date for article {article_url}, skipping")
            return books

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

        for idx, elem in enumerate(elements):
            try:
                title = None
                link_elem = elem.find('a', href=re.compile(r'/ebook/'))
                if link_elem:
                    title = link_elem.get_text(strip=True)

                if not title or len(title) < 2:
                    for sel in ['h2','h3','h4','h5','[class*="title"]','[class*="Title"]']:
                        title_elem = elem.select_one(sel)
                        if title_elem:
                            t = title_elem.get_text(strip=True)
                            if t and len(t) > 2:
                                title = t
                                break

                if not title or len(title) < 2:
                    if link_elem:
                        title = link_elem.get('title', '') or link_elem.get('aria-label', '')

                title = self.clean_summary(title)

                book_url = None
                if link_elem:
                    href = link_elem.get('href', '')
                    if href:
                        book_url = urljoin('https://www.kobo.com', href)

                if title and book_url:
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

    # ------------------------
    # 爬取多週書籍
    # ------------------------
    def crawl_weekly_books(self, start_year: Optional[int] = None, start_week: Optional[int] = None,
                       end_year: Optional[int] = None, end_week: Optional[int] = None,
                       use_random_delay: bool = False) -> List[BookItem]:
        """爬取多個週次的書籍"""
       today = date.today()
        if start_year is None or start_week is None:
            start_year, start_week, _ = today.isocalendar()
        start_year, start_week = int(start_year), int(start_week)

        if end_year is None or end_week is None:
            c_year, c_week, _ = today.isocalendar()
            end_year = int(c_year)
            end_week = int(min(c_week, 49))
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
