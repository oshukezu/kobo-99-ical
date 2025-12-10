"""Kobo 99 iCal 服務"""
import logging
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
        """合併新舊書籍資料，去重並保留最新資訊"""
        # 使用字典來去重，以 (book_url, date) 為 key
        books_dict = {}

        # 先加入現有書籍
        for book in existing_books:
            key = (book.book_url, book.date)
            books_dict[key] = book

        # 加入新書籍（會覆蓋舊的）
        for book in new_books:
            key = (book.book_url, book.date)
            books_dict[key] = book

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

        # 儲存合併後的資料
        self.storage.save(all_books)
        logger.info(f"Saved {len(all_books)} books to storage")

        # 生成 ICS
        ical_content = self.ics_generator.generate_ics(all_books)
        return ical_content
