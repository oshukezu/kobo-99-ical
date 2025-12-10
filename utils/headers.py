"""隨機 User-Agent 和 Headers 生成工具"""
import random
from typing import Dict, List


# 5 組 Chrome User-Agent（定期更新以保持真實性）
CHROME_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


def get_random_user_agent() -> str:
    """隨機選擇一個 Chrome User-Agent"""
    return random.choice(CHROME_USER_AGENTS)


def get_random_headers(referer: str = "https://www.kobo.com/zh/blog") -> Dict[str, str]:
    """生成隨機的瀏覽器 headers"""
    user_agent = get_random_user_agent()
    
    # 基礎 headers
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9",
        "Referer": referer,
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    
    return headers


def shuffle_headers_order(headers: Dict[str, str]) -> Dict[str, str]:
    """隨機排序 headers（模仿真實瀏覽器）"""
    # 將 headers 轉換為列表，隨機排序後轉回字典
    items = list(headers.items())
    random.shuffle(items)
    return dict(items)

