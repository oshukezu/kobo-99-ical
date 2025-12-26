"""
CLI version of Kobo-99 iCal generator (Advanced Refactor).
Generates kobo99.ics into docs/ folder for GitHub Pages publishing.
"""

import logging
import os
import sys
from datetime import date, timedelta

from scraper import Scraper
from kobo_ical.calendar_manager import CalendarManager

OUTPUT_DIR = "docs"
OUTPUT_FILE = "kobo99.ics"

# Log config
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def main():
    logger.info("Starting Kobo 99 Crawler (Advanced)...")
    ensure_output_dir()
    
    # 1. Determine Range
    # Crawl current year + next year (to be safe for Dec/Jan transition)
    today = date.today()
    this_year = today.year
    
    # Range: this_year Jan 1 to next_year Jan (covers sufficient ground)
    # Actually, user wants "Daily at 10 AM", implies rolling window.
    # But crawler logic is cheap with cloudscraper. let's crawl broad range.
    # Start: this_year, week 1. End: this_year, week 53.
    # Also check next year week 1-5 just in case.
    
    ranges = [
        (this_year, 1, this_year, 54),
        (this_year + 1, 1, this_year + 1, 8)
    ]
    
    raw_books = []
    
    with Scraper() as scraper:
        for (sy, sw, ey, ew) in ranges:
            logger.info(f"Crawling range: {sy}-W{sw} to {ey}-W{ew}")
            batch = scraper.crawl_weekly_books(sy, sw, ey, ew)
            raw_books.extend(batch)
            
    logger.info(f"Total raw books found (incl duplicates): {len(raw_books)}")
    
    # 2. Process Data (Dates & Logic)
    processed_books = CalendarManager.process_dates(raw_books)
    
    # 3. Generate ICS
    ical_data = CalendarManager.create_ical(processed_books)
    
    # 4. Write File
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    try:
        with open(output_path, "wb") as f: # ICS binary write
            f.write(ical_data)
        logger.info(f"✅ ICS file written: {output_path} ({len(ical_data)} bytes)")
    except Exception as e:
        logger.error(f"Failed to write ICS: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
