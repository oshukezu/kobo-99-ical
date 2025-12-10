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

    def extract_books_from_blog(self, soup):
        ebook_links = set()
        for a in soup.select("a[href*='/zh/ebook/']"):
            href = a.get("href")
            if href and "/zh/ebook/" in href:
                ebook_links.add(href.split("?")[0])  # 去除 UTMs
        return list(ebook_links)

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
    # 範例 parse_weekly_article 縮排修正
    # ------------------------
    def parse_weekly_article(self, html: str, article_url: str, year: int, week: int) -> List[BookItem]:
        """解析單一週次文章，提取書籍資訊"""
        soup = BeautifulSoup(html, "html.parser")
        books = []

        # 解析文章日期
        article_date = self.parse_article_date(soup, article_url)
        if not article_date:
            logger.warning(f"Could not determine date for article {article_url}, skipping")
            return books

        # 查找所有包含 /ebook/ 的連結
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
                link_elem = elem.find('a', href=re.compile(r'/ebook/'))
                if link_elem:
                    title = link_elem.get_text(strip=True)

                if not title or len(title) < 2:
                    title_selectors = ['h2', 'h3', 'h4', 'h5', '[class*="title"]', '[class*="Title"]']
                    for title_sel in title_selectors:
                        title_elem = elem.select_one(title_sel)
                        if title_elem:
                            title_text = title_elem.get_text(strip=True)
                            if title_text and len(title_text) > 2:
                                title = title_text
                                break

                if not title or len(title) < 2:
                    if link_elem:
                        title = link_elem.get('title', '') or link_elem.get('aria-label', '')

                # 清理標題
                title = self.clean_summary(title)

                # 查找書籍連結
                book_url = None
                if link_elem:
                    href = link_elem.get('href', '')
                    if href:
                        book_url = urljoin('https://www.kobo.com', href)

                # 建立 BookItem
                if title and book_url and len(title.strip()) > 0:
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
