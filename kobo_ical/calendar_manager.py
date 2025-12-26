"""
Calendar Manager for Kobo99
"""
import logging
from datetime import date
from typing import List

from icalendar import Calendar, Event, vText, vCalAddress
from cloudscraper import create_scraper

logger = logging.getLogger(__name__)

class CalendarManager:
    """Manages date logic and ICS generation"""
    
    @staticmethod
    def process_dates(books_data: List[dict]) -> List[dict]:
        """
        Process raw book data to resolve year context.
        Logic: Try to detect year transition (e.g. Dec -> Jan) within a batch.
        But since we process week by week, strict global logic is hard.
        
        Local logic:
        Each book is associated with a 'year_context' (the year in URL).
        If book month is 1 and year_context month is 12 (approx), assume next year.
        If book month is 12 and year_context month is 1 (approx), assume prev year.
        
        Actually, simpler rule provided by user:
        "如果 URL 年份為 $Y$，內文月份為 12 月，且下一本書月份為 1 月，則該書年份自動記為 $Y+1$。"
        This implies sequential processing.
        """
        processed = []
        
        # Sort by week first to ensure order? 
        # The list usually comes in order from crawler.
        
        for i, book in enumerate(books_data):
            base_year = book['year_context']
            month = book['month']
            day = book['day']
            
            final_year = base_year
            
            # Cross-year logic:
            # If current book is Jan, and previous book (in same batch/week) was Dec -> Year++
            # Since we process flat list, look at neighbors.
            
            # Problem: If the list is mixed weeks, we need to be careful.
            # Assuming 'books_data' is a chronological list.
            
            # Simple heuristic per user requirement:
            # If book is Jan/Feb and we seem to be in a "late year" context (e.g. week > 48), it's next year.
            # Or if book is Dec and we are in "early year" context (week < 5), it's previous year.
            
            if book['week'] >= 48 and month <= 2:
                final_year += 1
            elif book['week'] <= 5 and month >= 11:
                final_year -= 1
                
            book['date_obj'] = date(final_year, month, day)
            processed.append(book)
            
        return processed

    @staticmethod
    def create_ical(books: List[dict]) -> bytes:
        """Generate ICS binary content using icalendar"""
        cal = Calendar()
        cal.add('prodid', '-//Kobo99 Crawler//zh-TW//')
        cal.add('version', '2.0')
        cal.add('X-WR-CALNAME', 'Kobo 99 選書')
        
        # Deduplicate by (Date, Title)
        seen = set()
        
        for book in books:
            b_date = book.get('date_obj')
            title = book.get('title')
            
            if not b_date or not title:
                continue
                
            unique_key = (b_date, title)
            if unique_key in seen:
                continue
            seen.add(unique_key)
            
            event = Event()
            
            # SUMMARY: {書名}
            event.add('summary', title)
            
            # DTSTART;VALUE=DATE
            event.add('dtstart', b_date)
            
            # DESCRIPTION
            # Plaintext書名：{書名}
            # 查看電子書：{URL}
            # 來源文章：{Blog_URL}
            desc = f"書名：{title}\n查看電子書：{book['book_url']}\n來源文章：{book['article_url']}"
            event.add('description', desc)
            
            # URL
            event.add('url', book['book_url'])
            
            # UID: Stable hash
            uid = f"kobo99-{hash(desc)}"
            event.add('uid', uid)
            
            cal.add_component(event)
            
        return cal.to_ical()
