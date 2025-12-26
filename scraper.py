"""
Kobo 99 元書單爬蟲
"""
import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import List, Optional

import cloudscraper
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class Scraper:
    """Kobo 99 元書單爬蟲 (Cloudscraper version)"""

    def __init__(self):
        # Create a cloudscraper instance to bypass Cloudflare
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'darwin',
                'desktop': True
            }
        )
        self.max_retries = 3

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def fetch_page(self, url: str) -> Optional[str]:
        """抓取頁面內容"""
        logger.info(f"Fetching URL: {url}")
        for attempt in range(self.max_retries):
            try:
                response = self.scraper.get(url)
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 404:
                    logger.warning(f"Page not found: {url}")
                    return None
                else:
                    logger.warning(f"Status {response.status_code} for {url}, retrying...")
                    time.sleep(2)
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                time.sleep(2)
        
        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
        return None

    def parse_weekly_article(self, html: str, article_url: str, year: int, week: int) -> List[dict]:
        """解析週次文章"""
        soup = BeautifulSoup(html, "html.parser")
        books = []
        
        # Strict Regex Pattern
        # Pattern: {Date}{星期}Kobo99選書：{書名}
        # Matches: "12/20週六Kobo99選書：《破咒師...》" or "12/20週六Kobo99選書：破咒師..."
        pattern = re.compile(r'(\d{1,2}/\d{1,2}).*?Kobo99選書[：:]\s*(?:《(.*?)》|(.+))')
        
        # Find all text nodes containing "Kobo99選書"
        text_nodes = soup.find_all(string=re.compile(r"Kobo99選書"))
        processed_parents = set()

        for node in text_nodes:
            # Find closest block parent
            parent = node.parent
            while parent and parent.name not in ['div', 'p', 'li', 'article', 'section']:
                parent = parent.parent
            
            if not parent or parent in processed_parents:
                continue
            
            processed_parents.add(parent)
            full_text = parent.get_text(strip=True)
            
            match = pattern.search(full_text)
            if not match:
                continue

            date_str = match.group(1)
            title1 = match.group(2)
            title2 = match.group(3)
            title = (title1 or title2 or "").strip()
            
            if title.endswith('》'):
                title = title[:-1]
            if not title or title == "《":
                continue

            # Parse Date (Month/Day)
            try:
                month, day = map(int, date_str.split('/'))
            except ValueError:
                continue
            
            # Find Link
            book_url = None
            # 1. Parent is link
            if parent.name == 'a':
                book_url = parent.get('href')
            # 2. Link inside parent
            if not book_url:
                link = parent.find('a', href=re.compile(r'/ebook/'))
                if link:
                    book_url = link.get('href')

            if book_url:
                if '?' in book_url:
                    book_url = book_url.split('?')[0]
                if book_url.startswith('/'):
                    book_url = f"https://www.kobo.com{book_url}"
                
                if "查看電子書" in title:
                     title = title.replace("查看電子書", "").strip()

                books.append({
                    "title": title,
                    "book_url": book_url,
                    "article_url": article_url,
                    "month": month,
                    "day": day,
                    "week": week,
                    "year_context": year  # Base year from URL
                })
                logger.debug(f"Parsed: {title} ({month}/{day})")

        return books

    def crawl_weekly_books(self, start_year: int, start_week: int, end_year: int, end_week: int) -> List[dict]:
        """爬取範圍內的週次"""
        all_books = []
        curr_y, curr_w = start_year, start_week
        target_y, target_w = end_year, end_week
        
        while (curr_y < target_y) or (curr_y == target_y and curr_w <= target_w):
            url = f"https://www.kobo.com/zh/blog/weekly-dd99-{curr_y}-w{curr_w}"
            content = self.fetch_page(url)
            
            if content:
                items = self.parse_weekly_article(content, url, curr_y, curr_w)
                all_books.extend(items)
            
            curr_w += 1
            if curr_w > 54:
                curr_w = 1
                curr_y += 1
                
        return all_books
