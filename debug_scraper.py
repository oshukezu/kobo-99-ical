from scraper import Scraper
from kobo_ical.calendar_manager import CalendarManager
import logging

# Configure logging to show parsing details
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scraper")
logger.setLevel(logging.INFO)

def debug():
    # Crawl Oct to Dec 2025 (approx Week 40 to 52)
    # Let's pick a few representative weeks
    weeks = [40, 44, 48, 50] 
    year = 2025
    
    with Scraper() as scraper:
        all_raw_books = []
        for w in weeks:
            url = f"https://www.kobo.com/zh/blog/weekly-dd99-{year}-w{w}"
            print(f"\n=== Debugging Week {w} ({url}) ===")
            content = scraper.fetch_page(url)
            if not content:
                print("Failed to fetch content")
                continue
                
            books = scraper.parse_weekly_article(content, url, year, w)
            all_raw_books.extend(books)
            print(f"Raw found: {len(books)}")
            
        print("\n=== Processing & Deduplicating ===")
        processed = CalendarManager.process_dates(all_raw_books)
        
        print(f"Final count: {len(processed)}")
        for b in processed:
             print(f"  [{b['date_obj']}] {b['title']}")
             print(f"    Raw: {b.get('raw_text', 'N/A')}")


if __name__ == "__main__":
    debug()
