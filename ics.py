"""ICS 檔案生成"""
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

import pytz
from ics import Calendar, Event

from .config import Settings
from .models import BookItem

logger = logging.getLogger(__name__)

# 台灣時區
TAIPEI_TZ = pytz.timezone('Asia/Taipei')


class ICSGenerator:
    """ICS 檔案生成器"""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()

    def generate_ics(self, books: List[BookItem]) -> str:
        """生成 ICS 檔案內容"""
        cal = Calendar()
        cal.creator = "Kobo 99 iCal Generator"

        # 計算保留日期範圍
        today = date.today()
        past_cutoff = today - timedelta(days=self.settings.retention_past_days)
        future_cutoff = today + timedelta(days=self.settings.retention_future_days)

        # 過濾書籍，只保留在日期範圍內的
        filtered_books = [
            book for book in books
            if past_cutoff <= book.date <= future_cutoff
        ]

        logger.info(f"Generating ICS with {len(filtered_books)} books (filtered from {len(books)})")

        # 依日期限制每天最多 1 筆
        per_day_counts = {}
        event_count = 0
        for book in filtered_books:
            try:
                key = book.date
                cnt = per_day_counts.get(key, 0)
                if cnt >= 1:
                    continue
                event = Event()

                # 事件標題
                event.name = f"99元 - {book.title}"

                event.begin = book.date

                # 事件描述（包含商品頁連結與來源文章）
                description_parts = [
                    f"書名：{book.title}",
                    f"",
                    f"查看電子書：{book.book_url}",
                    f"",
                    f"來源文章：{book.article_url}",
                ]
                event.description = "\n".join(description_parts)

                # 事件 URL（商品頁連結）
                event.url = book.book_url

                # 事件 UID（用於去重）
                event.uid = f"kobo99-{hash(book.book_url + book.date.isoformat())}@kobo-99-ical"

                # 設定為全天事件
                event.make_all_day()

                cal.events.add(event)
                event_count += 1
                per_day_counts[key] = cnt + 1

            except Exception as e:
                logger.warning(f"Error creating event for book {book.title}: {e}", exc_info=True)
                continue

        ical_content = str(cal)
        logger.info(f"Generated ICS with {event_count} events, content length: {len(ical_content)} characters")
        
        if event_count == 0:
            logger.warning("No events in ICS file - this may indicate a problem with data crawling or filtering")
        
        return ical_content
