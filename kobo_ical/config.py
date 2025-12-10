from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    base_url: str = Field(
        "https://www.kobo.com/zh/blog",
        description="起始頁面，預設為 Kobo 中文部落格首頁",
    )
    keyword: str = Field(
        "一週99書單",
        description="用於篩選文章/區塊的關鍵字（不分大小寫）",
    )
    cron: str = Field(
        "0 6 * * *",
        description="預設的每日排程時間（說明用途，不強制啟動排程）",
    )
    user_agent: str = Field(
        "kobo-99-ical/0.1 (+https://github.com/oshukezu/kobo-99-ical)",
        description="HTTP User-Agent",
    )
    timeout_seconds: float = Field(15.0, description="單次請求逾時秒數")
    retries: int = Field(3, description="短暫錯誤的重試次數")
    rate_limit_seconds: float = Field(
        1.0,
        description="連續請求間隔秒數，避免過度頻繁",
    )
    request_delay_seconds: float = Field(
        0.2,
        description="頁面內多連結的解析延遲，避免太快",
    )
    data_store: str = Field(
        "data/events.json",
        description="事件持久化檔案，用於去重與狀態維護",
    )
    ics_path: str = Field(
        "data/kobo-99.ics",
        description="ICS 匯出檔案路徑（可作為靜態快取）",
    )
    retention_past_days: int = Field(
        180,
        description="保留過去事件天數",
    )
    retention_future_days: int = Field(
        365,
        description="保留未來事件天數",
    )
    refresh_interval_hours: int = Field(
        12,
        description="快取更新間隔，HTTP 端點請求時若超過此時間會自動刷新",
    )

    model_config = {
        "env_prefix": "KOBO99_",
        "env_file": ".env",
    }

