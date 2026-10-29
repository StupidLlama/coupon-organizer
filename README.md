# 優惠夾 Coupon Organizer

一站查詢各店家的優惠券、特價、活動與訂閱方案，資料每天自動更新。

網站：https://stupidllama.github.io/coupon-organizer/

## 功能
- **探索**：分類瀏覽（大分類 → 子分類），同一家店的優惠歸在一起；搜尋；嚴格篩選（選多個條件時只顯示全部符合的優惠）
- **為你推薦**：使用者選擇身分（學生、上班族、新創・企業、家庭、長者、新用戶），優先列出符合的優惠
- **我的優惠夾**：已收藏、已使用兩區；已使用的券會變灰、蓋紅色「已使用」章並移到最下面
- **回報**：每張券都有「回報失效」，頁尾有「回報新優惠」，都會開 GitHub Issue 表單

## 資料怎麼更新
```
sources.yaml ──► scripts/fetch.py ──► scripts/extract.py (Gemini) ──► scripts/merge.py ──► data/coupons.json
                                     已核准的 Issue 回報 ─────────────────┘
```
GitHub Actions（`.github/workflows/update.yml`）每天台灣時間早上 6 點執行，有變動就自動 commit。

## 檔案
| 路徑 | 用途 |
|---|---|
| `index.html` | 整個網站（讀取 `data/coupons.json`） |
| `data/coupons.json` | 優惠資料（由腳本產生，不要手動大改） |
| `sources.yaml` | 店家清單、分類、抓取網址、設定 |
| `scripts/` | 抓取、AI 整理、合併 |
| `.github/ISSUE_TEMPLATE/` | 回報表單 |

## 本機測試
```powershell
pip install -r requirements.txt
python scripts/run.py --no-fetch
$env:GEMINI_API_KEY="你的金鑰"; python scripts/run.py --only mcd,sbux
python -m http.server 8000
```
然後打開 http://localhost:8000 。

品牌名稱與商標屬各品牌所有；優惠內容以官方公告為準。
