# Kobo 99 書單 iCal 服務

自動爬取 Kobo 部落格「一週 99 元書單」文章、解析書單並輸出可訂閱的 `.ics` (iCalendar) 檔案，供 Google 日曆「從網址新增」訂閱。

## 功能特色

- 🔍 自動爬取 Kobo 每週 99 元書單頁面（格式：`weekly-dd99-{年份}-w{周數}`）
- 📅 生成 ICS 檔案，包含每天 99 元書籍的標題與「查看電子書」連結
- 🔄 GitHub Actions 自動化執行，每天更新
- 📱 可直接訂閱到 Google 日曆或其他支援 ICS 的日曆應用

## 快速開始

### 本地執行

```bash
# 安裝依賴
pip install -r requirements.txt

# 執行爬蟲並生成 ICS 檔案
python main.py

# 生成的檔案位於 docs/kobo99.ics
```

### GitHub Pages 訂閱

生成的 ICS 檔案會自動發布到 GitHub Pages，訂閱網址：
```
https://oshukezu.github.io/kobo-99-ical/docs/kobo99.ics
```

在 Google 日曆中：
1. 點擊「+」→「從網址新增」
2. 輸入上述網址
3. 即可自動同步每天的 99 元書單

## 專案結構

```
kobo-99-ical/
├── kobo_ical/
│   ├── __init__.py
│   ├── config.py          # 配置設定
│   ├── models.py          # 資料模型（BookItem）
│   ├── crawler.py         # 爬蟲邏輯
│   ├── ics.py            # ICS 檔案生成
│   ├── service.py        # 服務整合層
│   └── storage.py        # 資料持久化
├── main.py               # CLI 入口
├── .github/
│   └── workflows/
│       └── generate-ics.yml  # GitHub Actions 自動化
├── docs/
│   └── kobo99.ics        # 生成的 ICS 檔案（GitHub Pages）
└── data/
    └── events.json       # 書籍資料快取（用於去重）
```

## 工作原理

1. **爬蟲 (`crawler.py`)**：
   - 根據當前日期計算需要爬取的週次範圍
   - 訪問 `https://www.kobo.com/zh/blog/weekly-dd99-{年份}-w{周數}` 格式的頁面
   - 解析每篇文章，提取書籍標題和「查看電子書」連結
   - 根據文章日期分配每本書對應的日期（每週 7 本書，每天一本）

2. **資料處理 (`service.py`)**：
   - 載入現有資料（用於去重）
   - 合併新舊資料
   - 儲存到 `data/events.json`

3. **ICS 生成 (`ics.py`)**：
   - 為每本書創建日曆事件
   - 事件標題：`99元 - {書名}`
   - 事件描述：包含書名、查看電子書連結、來源文章連結
   - 保留過去 180 天與未來 365 天的事件

4. **自動化 (`generate-ics.yml`)**：
   - GitHub Actions 每天 UTC 00:00（台灣時間 08:00）自動執行
   - 爬取最新書單並更新 ICS 檔案
   - 自動提交並推送到 GitHub Pages

## 配置

可透過環境變數覆寫設定，前綴 `KOBO99_`：

| 變數 | 預設 | 說明 |
| --- | --- | --- |
| `KOBO99_BASE_URL` | `https://www.kobo.com/zh/blog` | 起始頁面 |
| `KOBO99_USER_AGENT` | `kobo-99-ical/0.1 ...` | HTTP User-Agent |
| `KOBO99_TIMEOUT_SECONDS` | `15` | 單次請求逾時 |
| `KOBO99_RETRIES` | `3` | 重試次數 |
| `KOBO99_RATE_LIMIT_SECONDS` | `1.0` | 連續請求間隔 |
| `KOBO99_REQUEST_DELAY_SECONDS` | `0.2` | 文章內多書籍抓取時的延遲 |
| `KOBO99_DATA_STORE` | `data/events.json` | 去重與狀態儲存檔 |
| `KOBO99_RETENTION_PAST_DAYS` | `180` | 保留過去事件天數 |
| `KOBO99_RETENTION_FUTURE_DAYS` | `365` | 保留未來事件天數 |

## 手動觸發 GitHub Actions

如果需要立即更新 ICS 檔案，可以：

1. 前往 GitHub 專案的 Actions 頁面
2. 選擇 "Generate Kobo 99 ICS" workflow
3. 點擊 "Run workflow" 按鈕手動觸發

## 注意事項

- 請遵守網站 robots.txt 與使用條款，程式已加入 User-Agent、逾時、重試與基本 rate limit
- 若解析不到「查看電子書」連結會跳過該書並寫入日誌
- 由於 Kobo 網站可能有 Cloudflare 保護，某些情況下可能需要調整爬蟲策略
- `data` 目錄用於持久化歷史事件與去重資訊，建議加入 `.gitignore`（但 GitHub Actions 會自動處理）

## 授權

MIT License
