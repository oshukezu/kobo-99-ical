#!/usr/bin/env python3
"""
測試爬蟲功能
用於驗證爬蟲是否能正確抓取資料
"""

import logging
import re
from datetime import date

from kobo_ical.crawler import KoboCrawler
from kobo_ical.config import Settings

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_crawler():
    """測試爬蟲功能"""
    print("🧪 測試 Kobo 99 書單爬蟲...")
    print("=" * 60)
    
    settings = Settings()
    
    # 測試當前週次
    with KoboCrawler(settings) as crawler:
        year, week = crawler.get_current_week_info()
        print(f"📅 當前年份：{year}，週數：{week}")
        print(f"📅 當前日期：{date.today()}")
        
        # 測試多個週次（當前週往前推2週，往後推2週）
        start_week = max(1, week - 2)
        start_year = year
        if start_week <= 2:
            start_year -= 1
            start_week = 52 + start_week - 2
        
        end_week = min(52, week + 2)
        end_year = year
        if end_week >= 51:
            end_year += 1
            end_week = end_week - 52
        
        print(f"\n🔍 測試範圍：{start_year}年第{start_week}週 到 {end_year}年第{end_week}週")
        
        # 測試生成 URL
        urls = crawler.generate_weekly_urls(start_year, start_week, end_year, end_week)
        print(f"\n🔗 將測試以下 {len(urls)} 個 URL：")
        for i, url in enumerate(urls, 1):
            print(f"  {i}. {url}")
        
        # 嘗試抓取多個週次
        print(f"\n{'=' * 60}")
        print("開始抓取書單...")
        print("=" * 60)
        
        all_books = []
        for test_url in urls[:3]:  # 先測試前3個 URL
            match = re.search(r'weekly-dd99-(\d{4})-w(\d+)', test_url)
            if match:
                test_year = int(match.group(1))
                test_week = int(match.group(2))
                print(f"\n📖 測試 {test_year}年第{test_week}週...")
                try:
                    books = crawler.crawl_weekly_books(test_year, test_week, test_year, test_week)
                    if books:
                        print(f"  ✅ 找到 {len(books)} 本書籍")
                        all_books.extend(books)
                        for book in books[:3]:  # 只顯示前3本
                            print(f"    - {book.title} ({book.date})")
                        if len(books) > 3:
                            print(f"    ... 還有 {len(books) - 3} 本書")
                    else:
                        print(f"  ⚠️  未找到書籍資料")
                except Exception as e:
                    print(f"  ❌ 錯誤：{e}")
                    import traceback
                    traceback.print_exc()
        
        print(f"\n{'=' * 60}")
        print(f"📊 總計抓取結果：{len(all_books)} 本書籍")
        print("=" * 60)
        
        if all_books:
            print("\n✅ 成功抓取的書籍列表：")
            for i, book in enumerate(all_books, 1):
                print(f"\n{i}. {book.title}")
                print(f"   日期：{book.date}")
                print(f"   書籍連結：{book.book_url}")
                print(f"   來源文章：{book.article_url}")
        else:
            print("\n⚠️  未找到任何書籍資料")
            print("\n可能原因：")
            print("1. 該週次尚未發布書單")
            print("2. 網頁結構與預期不同")
            print("3. Cloudflare 保護導致無法訪問")
            print("4. 選擇器需要調整")
            print("\n建議：")
            print("- 檢查 URL 是否可正常訪問")
            print("- 查看日誌輸出以了解詳細錯誤")
            print("- 可能需要調整 crawler.py 中的 HTML 選擇器")

if __name__ == "__main__":
    test_crawler()

