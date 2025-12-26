from scraper import KoboScraper
import logging

logging.basicConfig(level=logging.INFO)

def debug():
    url = "https://www.kobo.com/zh/blog/weekly-dd99-2025-w52"
    with KoboScraper(headless=True) as scraper:
        print(f"Fetching {url}...")
        html = scraper.fetch_page(url)
        if not html:
            print("Failed to fetch")
            return
            
        print("Parsing...")
        books = scraper.parse_weekly_article(html, url, 2025, 52)
        
        print(f"Found {len(books)} books:")
        for b in books:
            print(f"- {b['date']}: {b['title']} -> {b['book_url']}")

if __name__ == "__main__":
    debug()
