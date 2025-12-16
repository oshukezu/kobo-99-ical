"""Kobo 99 iCal 服務"""
import logging
import re
from datetime import date, timedelta
from typing import List, Optional

from .config import Settings
from .crawler import KoboCrawler
from .ics import ICSGenerator
from .models import BookItem
from .storage import Storage

logger = logging.getLogger(__name__)


class Kobo99ICalService:
    """Kobo 99 iCal 服務主類別"""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.storage = Storage(self.settings.data_store)
        self.crawler = None
        self.ics_generator = ICSGenerator(self.settings)

    def crawl_books(self, start_year: Optional[int] = None, start_week: Optional[int] = None,
                    end_year: Optional[int] = None, end_week: Optional[int] = None,
                    use_random_delay: bool = False) -> List[BookItem]:
        """爬取書籍資料"""
        with KoboCrawler(self.settings) as crawler:
            books = crawler.crawl_weekly_books(start_year, start_week, end_year, end_week, use_random_delay=use_random_delay)
        return books

    def merge_books(self, new_books: List[BookItem], existing_books: List[BookItem]) -> List[BookItem]:
        """合併新舊書籍資料，依 book_url 去重並偏好較新的日期"""
        books_dict = {}
        # 先加入現有書籍
        for book in existing_books:
            books_dict[book.book_url] = book
        # 再加入新書籍（若同一 book_url 重複，保留較新的日期）
        for book in new_books:
            prev = books_dict.get(book.book_url)
            if not prev or (book.date and prev.date and book.date >= prev.date):
                books_dict[book.book_url] = book
        return list(books_dict.values())

    def generate_ical(self, start_year: Optional[int] = None, start_week: Optional[int] = None,
                      end_year: Optional[int] = None, end_week: Optional[int] = None,
                      use_random_delay: bool = False) -> str:
        """生成 ICS 檔案內容"""
        # 載入現有資料
        existing_books = self.storage.load()
        logger.info(f"Loaded {len(existing_books)} existing books from storage")

        # 爬取新資料
        logger.info("Starting to crawl books...")
        new_books = self.crawl_books(start_year, start_week, end_year, end_week, use_random_delay=use_random_delay)

        # 合併資料
        all_books = self.merge_books(new_books, existing_books)
        logger.info(f"Merged to {len(all_books)} total books")

        # 內嵌清理：移除錯誤標題、正規化商品頁 URL
        import re as _re
        cleaned_inline: List[BookItem] = []
        for b in all_books:
            title = (b.title or '').strip()
            if not title or _re.fullmatch(r'(查看電子書（HK）|查看電子書|閱讀電子書|電子書)', title):
                continue
            content = (getattr(b, 'content', '') or '').strip()
            content = _re.sub(r'https?://\S+', '', content)
            content = _re.sub(r'99元|NT\$?\s*99|HK\$?\s*99|購買|查看電子書（HK）|查看電子書', '', content)
            book_url = _re.sub(r'https://www\.kobo\.com/hk/zh/ebook/', 'https://www.kobo.com/tw/zh/ebook/', b.book_url)
            book_url = _re.sub(r'https://www\.kobo\.com/zh/ebook/', 'https://www.kobo.com/tw/zh/ebook/', book_url)
            try:
                from urllib.parse import urlsplit
                path = urlsplit(book_url).path
                mprod = _re.search(r'/ebook/([^/]+)', path)
                if mprod:
                    book_url = f"https://www.kobo.com/tw/zh/ebook/{mprod.group(1)}"
            except Exception:
                pass
            cleaned_inline.append(BookItem(
                title=title,
                book_url=book_url,
                article_url=b.article_url,
                article_title=getattr(b, 'article_title', ''),
                content=content,
                date=b.date,
                week=b.week,
                year=b.year,
            ))
        # 以 book_url 去重，偏好較新日期
        unique_inline = {}
        for b in cleaned_inline:
            prev = unique_inline.get(b.book_url)
            if not prev or (b.date and prev.date and b.date >= prev.date):
                unique_inline[b.book_url] = b
        all_books = list(unique_inline.values())
        logger.info(f"Cleaned inline to {len(all_books)} books")

        # 儲存合併後的資料
        self.storage.save(all_books)
        logger.info(f"Saved {len(all_books)} books to storage")

        # 生成 ICS
        ical_content = self.ics_generator.generate_ics(all_books)
        return ical_content

    def clean_existing_data(self) -> List[BookItem]:
        """清理既有資料：移除多餘描述、價格與購買資訊，校正日期與週次"""
        items = self.storage.load()
        cleaned: List[BookItem] = []
        base_w49 = "https://www.kobo.com/zh/blog/weekly-dd99-2025-w49"
        for idx, b in enumerate(items):
            title = b.title.strip()
            # 移除不必要的標題
            if not title or re.fullmatch(r'(查看電子書（HK）|查看電子書|閱讀電子書|電子書)', title):
                continue
            # 清理 content（若已有），移除 URL 與價格字樣
            content = (getattr(b, 'content', '') or '').strip()
            content = re.sub(r'https?://\S+', '', content)
            content = re.sub(r'99元|NT\$?\s*99|HK\$?\s*99|購買|查看電子書（HK）|查看電子書', '', content)
            # 校正日期：w49 統一到 12/4..12/10
            if b.article_url == base_w49:
                offset = hash(b.book_url) % 7
                b.date = date(2025,12,4) + timedelta(days=offset)
                b.week = 49
                b.year = 2025
            cleaned.append(BookItem(
                title=title,
                book_url=b.book_url,
                article_url=b.article_url,
                article_title=getattr(b, 'article_title', ''),
                content=content,
                date=b.date,
                week=b.week,
                year=b.year,
            ))
        # 以 book_url 去重，偏好較新日期
        unique = {}
        for b in cleaned:
            prev = unique.get(b.book_url)
            if not prev or (b.date and prev.date and b.date >= prev.date):
                unique[b.book_url] = b
        cleaned = list(unique.values())
        # 輸出清理後資料
        out_path = self.settings.path_cleaned if hasattr(self.settings, 'path_cleaned') else 'data/cleaned_events.json'
        Storage(out_path).save(cleaned)
        return cleaned
