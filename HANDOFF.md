# 優惠夾 交接文件（v0.4.2）

最後更新：2026-10-29 12:30（台灣時間）
下一個對話請先讀完這份文件，再繼續開發。

---

## 0. 給下一個對話的 Claude：先看這裡

**使用者**：Evan（GitHub：`StupidLlama`），NCKU 資工系學生，用繁體中文溝通。

**工作環境**
- Windows 筆電，主要在 **VS Code（繁體中文版）** 工作，git 和測試都在 VS Code 的終端機（PowerShell）執行
- 專案唯一位置：`C:\Users\user\Desktop\coupon-organizer`（「下載」裡的舊複本已刪除，不要再解壓到別處）
- Python 3.14（本機）；GitHub Actions 用 Python 3.12
- 已安裝並登入 GitHub CLI（`gh`）
- 新的對話會用「專案」直接連到使用者電腦的這個資料夾，**不再用 zip 傳檔**

**使用者的偏好（照做）**
- 一律用繁體中文回覆
- 較大的任務：先列計畫（大分類＋細項），等使用者同意再開工；小修正直接做
- 要使用者選擇時，給可以填的答案卷格式
- 給指令時，要能直接複製貼上，並且是在 VS Code 終端機執行的版本
- 使用任何圖片前先問
- 完成一個小版本（例如 v0.4 → v0.5）或大改動後，更新這份交接文件，請使用者開新對話
- 檔名不要加版本號

**改檔案時的注意事項**
- 透過連線改使用者電腦裡的檔案時，**預設不能刪除檔案**，git 也會因此出問題。所以 **git 操作（add / commit / push / pull）請交給使用者在 VS Code 執行**，Claude 只負責改檔案
- 改完請告訴使用者：在 VS Code 的「原始檔控制」檢查變更，再貼上 commit / push 指令

---

## 1. 專案目標
做一個「最全面」的優惠整理網站：讓所有類型的使用者（學生、上班族、新創、家庭、長者、新用戶）都能依分類找到各店家的優惠券、特價、活動、免費試用、點數回饋、訂閱方案折扣，並且資料能自動、頻繁地從多個來源更新。

- 介面語言：繁體中文
- 網站：https://stupidllama.github.io/coupon-organizer/ （GitHub Pages，`main` 分支根目錄）
- Repo：https://github.com/StupidLlama/coupon-organizer （公開）
- 自動更新：GitHub Actions 每天台灣時間 06:00 ＋ Gemini 免費額度
- 預算：$0
- 預覽版（Claude Artifact）：https://claude.ai/artifact/Vw8ZcCrhtLGr5Vpeh5GQFi

## 2. 目前狀態（2026-10-29 12:30）

| 項目 | 狀態 |
|---|---|
| 網站（GitHub Pages） | ✅ 已上線 |
| `GEMINI_API_KEY`（repo secret） | ✅ 已設定（Google AI Studio，Default Gemini Project） |
| Issue 標籤 `approved` / `new-coupon` / `expired` | ✅ 已建立 |
| Gemini 自動選模型（v0.4.1） | ✅ 已推上 GitHub，會選到 `gemini-3.8-flash` |
| 備用模型＋15 秒間隔（v0.4.2） | ✅ 已推上 GitHub |
| 真實優惠資料 | ⚠️ 已能抓到（約 75 筆），但第一次因 push 衝突沒存到，網站上仍是示範資料 |

### 最新進度（2026-10-29 13:00）
- v0.4.2 已推上 GitHub。第三次執行（run 40818764836）**Gemini 成功抓到約 75 筆真實優惠**（全家、家樂福、康是美、Apple 等），但 push 被拒（執行中使用者剛好 push），結果沒存到。
- 已修正：`update.yml` push 前先 `git pull --rebase`（commit 93b31c9）；`.gitignore` 加 `run.log`。
- 今日 `gemini-3.8-flash`、`3.7-flash` 回 429「超過額度」（被前幾次執行用光），`3.6`、`3.5` 回 503。額度台灣 15:00 重置。
- **下一步**：15:00 後 `gh workflow run update.yml`，確認 `data/coupons.json` 有真實優惠；之後做第 10 節第 2 項「換更好的來源網址」。
- 看完整紀錄的方法：`gh run view <ID> --log | Out-File -Encoding utf8 run.log`，Claude 直接讀檔（終端機中文會亂碼）。

## 3. 版本紀錄
| 版本 | 內容 |
|---|---|
| v0.1 | 第一版示範頁：分類、篩選、到期倒數、收藏、複製優惠碼，假資料寫死在 HTML |
| v0.2 | 白色主題新介面；同一家店的優惠歸在一起；移除「所有人」篩選；篩選改為嚴格比對（AND），類型單選 |
| v0.3 | 資料和網頁分離（`data/coupons.json`）；GitHub Actions 每日自動更新；Gemini 整理網頁；GitHub Issue 回報表單；身分設定與「為你推薦」；「我的優惠夾」（已收藏、已使用）；已使用的券變灰、蓋紅章、移到最下面 |
| v0.4 | 優惠詳情頁：有效期間與進度條、優惠碼複製、「兌換網址 → App → 官網」主要按鈕（有優惠碼時先複製再前往）、同店家其他優惠＋「你可能也喜歡」、可分享的網址（#c-優惠編號） |
| v0.4.1 | 手機版：詳情頁改為全螢幕（頂部固定店家列和關閉鍵）；頁首不再固定在畫面上方；`requirements.txt` 改用 `>=`（修正 Python 3.14 無法安裝 PyYAML 6.0.2）；Gemini 模型改為自動選擇（`model: auto`） |
| v0.4.2 | Gemini 備用模型：一次挑出最多 4 個 flash 模型，遇到 503（忙線）或 429（太頻繁／沒額度）自動換下一個，同一家店重試；錯誤訊息顯示實際原因；呼叫間隔 7 秒 → 15 秒 |

## 4. 執行紀錄與發現的問題

**第一次執行（v0.4）**：每家都 404，因為 `gemini-2.5-flash` 已停用 → v0.4.1 改成自動選模型。

**第二次執行（v0.4.1）**：自動選到 `gemini-3.8-flash`，有送出約 1.5 萬個 token。但 Google AI Studio 的錯誤圖表顯示大量 **503 ServiceUnavailable** 和一些 **429 TooManyRequests**，第一家（肯德基）就失敗，舊程式誤判成「超過今日額度」而停止 → v0.4.2 加入備用模型。

**另外**：之前同時觸發了 #2、#3、#4 三次執行。workflow 設了 `concurrency`，同時只會跑一次，其他的排隊。#3 出現驚嘆號（可能被取消或逾時），原因還沒確認。

**抓不到網頁的店家**（39 家中 13 家）：
| 原因 | 店家 |
|---|---|
| HTTP 403（被擋） | 麥當勞、屈臣氏、KKBOX、Canva、威秀影城 |
| JavaScript 動態載入，抓不到文字 | 漢堡王、燦坤、蝦皮、momo、Agoda、國泰世華 |
| robots.txt 禁止（照規矩跳過） | Netflix、Disney+ |

其他 26 家抓得到網頁內容，只差 Gemini 成功回應。

## 5. 目前的設計決定
- **嚴格篩選**：選多個對象或條件時，優惠必須全部符合才顯示。不限對象的優惠 `aud` 是空陣列，不會出現在任何對象篩選裡。
- **推薦邏輯**：身分是「或」的關係，符合越多身分的排越前面，再依到期日排序；下面另列「不限身分的熱門優惠」前 8 張。已使用的不推薦。
- **使用者資料**（身分、收藏、已使用）存在瀏覽器 localStorage，**不會跨裝置同步**。
- **已使用**：探索頁裡留在原店家區塊但排到最後；優惠夾裡獨立成「已使用」區，可按「復原」。
- **Logo**：用 Google favicon 服務讀各品牌官網的小圖示，載入失敗時顯示品牌色＋首字。Claude 預覽頁會擋外部圖片，只有 GitHub Pages 上才看得到真 logo。
- **示範資料**：53 筆虛構資料，`origin` 為 `demo`，畫面標「示範」。`sources.yaml` 的 `keep_demo` 改成 `false` 後，下次更新就會清掉（建議等真實資料夠多再改）。
- **詳情頁按鈕順序**：有 `redeem_url` →「前往兌換」；否則若是「App 限定」且有 App 連結 →「開啟 App」；否則 →「前往官網」。Android 沒填 App 連結時改用 Google Play 搜尋；iPhone 沒填就只顯示提示文字。
- **相關優惠**：先列同店家其他優惠（最多 4 張），再補同子分類、同類型或對象重疊的，湊到約 6 張。
- **版面**：只做白色主題（使用者要求）。字體 Chiron GoRound TC（標題）＋ Noto Sans TC（內文）；黃色價格標籤 `#ffd43b` 是主要特色；已使用的紅章 `#e0352b`。手機版（≤ 640px）詳情頁全螢幕、頁首不固定。

## 6. 檔案結構
| 路徑 | 用途 |
|---|---|
| `index.html` | 整個網站（HTML＋CSS＋JS 一個檔），讀取 `data/coupons.json`。頁面路由：`#explore`、`#for-you`、`#wallet`、`#c-優惠編號` |
| `data/coupons.json` | 優惠資料（由腳本產生，GitHub Actions 會自動 commit） |
| `sources.yaml` | 設定（`model: auto`、`request_gap_seconds: 15`、`stale_days`、`keep_demo`）、分類、39 家店的抓取網址 |
| `scripts/common.py` | 共用常數與讀寫 |
| `scripts/fetch.py` | 抓網頁，檢查 robots.txt，轉純文字 |
| `scripts/extract.py` | Gemini 呼叫。v0.4.2：`resolve_models()` 回傳候選模型清單；`extract()` 遇到 429/503 重試 2 次後丟出 `ModelBusy`，遇到 401/403 丟出 `PermissionError` |
| `scripts/merge.py` | 去重、併入回報、清理過期 |
| `scripts/run.py` | 主程式。v0.4.2：遇到 `ModelBusy` 就換下一個候選模型、同一網頁重試；全部模型都不行才停止 |
| `.github/workflows/update.yml` | 每日 22:00 UTC 執行，也可手動 `gh workflow run update.yml` |
| `.github/ISSUE_TEMPLATE/` | 回報新優惠、回報失效 |
| `requirements.txt` | `requests>=2.32.3`、`beautifulsoup4>=4.12.3`、`PyYAML>=6.0.3` |

## 7. 資料格式（`data/coupons.json`）
```json
{
 "updated_at": "2026-10-29T...+08:00",
 "categories": { "food": { "name": "美食", "subs": { "fast": "速食" } } },
 "stores": { "mcd": { "name": "麥當勞", "domain": "mcdonalds.com.tw", "sub": "fast", "color": "#d62300",
                    "url": "官網", "app_ios": "（選填）", "app_android": "（選填）" } },
 "coupons": [{
   "id": "10 碼 hash（店家＋標題）", "store": "mcd", "type": "coupon",
   "title": "...", "desc": "...", "start": "2026-10-25", "end": "2026-11-02",
   "aud": ["student"], "cond": ["app"], "code": "", "source": "https://...", "redeem_url": "（選填）",
   "checked_at": "...", "origin": "demo | auto | report"
 }]
}
```
- `type`：coupon 優惠券、sale 特價、event 活動、trial 免費試用、cashback 點數回饋、plan 方案折扣
- `aud`：student、worker、startup、family、senior、newbie
- `cond`：member、app、line、pay、bundle、store
- `end` 為 null 代表長期有效

## 8. 自動更新流程
1. `fetch.py`：依 `sources.yaml` 抓網頁（先看 robots.txt）
2. `extract.py`：查詢可用模型 → 送給 Gemini（JSON schema 輸出），只收網頁明確寫的優惠，用自己的話改寫
3. `merge.py`：同店家＋同標題 = 同 ID；併入已核准的回報；刪掉過期，以及自動抓到但超過 `stale_days` 天沒再出現的
4. Workflow 有變動就 commit；處理過的 Issue 自動關閉，有問題的會留言並移除 `approved`

回報流程：使用者開 Issue → Evan 檢查後加上 `approved` → 下次更新時併入。

## 9. 常用指令（VS Code 終端機）
```powershell
cd "$HOME\Desktop\coupon-organizer"
git pull                                   # 先同步機器人每天 commit 的資料
python scripts/run.py --no-fetch           # 本機只處理回報、清理過期
$env:GEMINI_API_KEY="金鑰"; python scripts/run.py --only kfc,sbux   # 本機只抓兩家測試（不要 commit 金鑰）
python -m http.server 8000                 # 本機預覽 http://localhost:8000
git add .; git commit -m "說明"; git push
gh workflow run update.yml                 # 手動觸發自動更新
gh run list --limit 5                      # 看最近的執行
gh run view --log | Select-String "使用模型|找到|略過|無法使用|失敗"   # 看最新一次的重點紀錄
```
注意：Windows PowerShell 讀中文檔案時要加 `-Encoding utf8`，不然會變亂碼。

## 10. 下一步（依優先順序）
1. **讓 v0.4.2 上線並確認真的抓到資料**（見第 2 節）。如果所有 flash 模型都 503／429，考慮：間隔再拉長、分兩批跑（例如早上和晚上各跑一半店家），或把 `model` 指定成較舊、較不擠的穩定版。
2. **換更好的來源網址**（可用子代理分頭搜尋）：
   - 26 家抓得到的：首頁 → 各店的「優惠／活動／最新消息」頁
   - 13 家抓不到的：改抓官方新聞稿、活動頁、FB 粉專公開貼文，或 PTT／Dcard 優惠板（要遵守 robots.txt 和網站條款）
3. **填 `app_ios` / `app_android`**：用子代理查各品牌官方 App 的商店網址（不要用猜的 ID）；之後可加 LINE 官方帳號連結給「LINE 限定」用。
4. JavaScript 動態網頁可改用 Playwright 抓（GitHub Actions 可以裝）。
5. 很多速食券只在 App 裡 → 靠使用者回報。
6. 真實資料夠多後，`keep_demo: false` 清掉示範資料。
7. 之後可加：跨裝置同步收藏（Firebase／Supabase 免費方案）、到期提醒、依地區（台南）篩選、PWA。
