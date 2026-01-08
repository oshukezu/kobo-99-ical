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
    # Crawl daily: +/- 2 weeks from today
    today = date.today()
    
    # Calculate start and end dates
    start_date = today - timedelta(weeks=2)
    end_date = today + timedelta(weeks=2)
    
    start_iso = start_date.isocalendar()
    end_iso = end_date.isocalendar()
    
    # Extract year and week
    start_year, start_week = start_iso[0], start_iso[1]
    end_year, end_week = end_iso[0], end_iso[1]

    logger.info(f"Target date range: {start_date} to {end_date}")
    
    # We only need one range call because Scraper.crawl_weekly_books handles year crossing
    # But Scraper.crawl_weekly_books takes (sy, sw, ey, ew)
    
    raw_books = []
    
    with Scraper() as scraper:
        logger.info(f"Crawling range: {start_year}-W{start_week} to {end_year}-W{end_week}")
        # Note: scraper.crawl_weekly_books logic handles the wrap around years automatically
        raw_books = scraper.crawl_weekly_books(start_year, start_week, end_year, end_week)
            
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
