# 優惠夾 交接文件（v0.4）

日期：2026-10-28
下一個對話請先讀這份文件，再繼續開發。

## 1. 專案目標
做一個「最全面」的優惠整理網站：讓所有類型的使用者（學生、上班族、新創、家庭、長者、新用戶）都能依分類找到各店家的優惠券、特價、活動、免費試用、點數回饋、訂閱方案折扣，並且資料能自動、頻繁地從多個來源更新。

- 介面語言：繁體中文
- 部署：GitHub Pages（repo：`StupidLlama/coupon-organizer`）
- 自動更新：GitHub Actions + Gemini 免費額度
- 預算：$0

## 2. 版本紀錄
| 版本 | 內容 |
|---|---|
| v0.1 | 第一版示範頁：分類、篩選、到期倒數、收藏、複製優惠碼，假資料寫死在 HTML |
| v0.2 | 白色主題新介面；同一家店的優惠歸在一起；移除「所有人」篩選；篩選改為嚴格比對（AND），類型單選 |
| v0.4 | 優惠詳情頁：點任何優惠卡打開（電腦是右側面板、手機是底部彈出）；顯示開始到到期日期與進度條、剩餘天數；優惠碼大字顯示＋複製；主要按鈕依序選「兌換網址 → App → 官網」，有優惠碼時按下去會先複製再前往；同店家其他優惠＋「你可能也喜歡」；詳情有自己的網址（#c-優惠編號），可以分享 |
| v0.3 | 資料和網頁分離（`data/coupons.json`）；GitHub Actions 每日自動更新流程；Gemini 整理網頁；GitHub Issue 回報表單；使用者身分設定與「為你推薦」頁；「我的優惠夾」（已收藏、已使用）；已使用的券變灰、蓋紅章、移到最下面 |

## 3. 目前的設計決定
- **嚴格篩選**：選多個對象或條件時，優惠必須全部符合才顯示。不限對象的優惠 `aud` 是空陣列，不會出現在任何對象篩選裡。
- **推薦邏輯**：使用者身分是「或」的關係，符合越多身分的優惠排越前面，再依到期日排序；下面另列「不限身分的熱門優惠」前 8 張。已使用的不推薦。
- **使用者資料**（身分、收藏、已使用）存在瀏覽器 localStorage，**不會跨裝置同步**。
- **已使用**：探索頁裡留在原店家區塊但排到最後；優惠夾裡獨立成「已使用」區，可按「復原」。
- **Logo**：用 Google favicon 服務讀各品牌官網的小圖示，載入失敗時顯示品牌色＋首字。Claude 的預覽頁會擋外部圖片，所以預覽只會看到首字，GitHub Pages 上才有真 logo。
- **示範資料**：目前 53 筆都是虛構的，`origin` 為 `demo`，畫面標「示範」。`sources.yaml` 的 `keep_demo` 改成 `false` 後，下次更新就會清掉。
- **詳情頁按鈕順序**：優惠有 `redeem_url` →「前往兌換」；否則若是「App 限定」且有 App 連結 →「開啟 App」；否則 →「前往官網」（店家 `url`，即 `sources.yaml` 第一個網址）。Android 沒填 App 連結時會改用 Google Play 搜尋；iPhone 沒填就只顯示提示文字。
- **相關優惠**：先列同店家其他優惠（最多 4 張），再補同子分類、同類型或對象重疊的優惠，湊到約 6 張。
- **主題**：只做白色主題（使用者要求）。字體：Chiron GoRound TC（標題）＋ Noto Sans TC（內文）；黃色價格標籤 `#ffd43b` 是主要特色。

## 4. 資料格式（`data/coupons.json`）
```json
{
 "updated_at": "2026-10-28T20:44:00+08:00",
 "categories": { "food": { "name": "美食", "subs": { "fast": "速食" } } },
 "stores": { "mcd": { "name": "麥當勞", "domain": "mcdonalds.com.tw", "sub": "fast", "color": "#d62300",
                    "url": "官網", "app_ios": "App Store 網址（選填）", "app_android": "Google Play 網址（選填）" } },
 "coupons": [{
   "id": "10 碼 hash（店家＋標題）", "store": "mcd", "type": "coupon",
   "title": "...", "desc": "...", "start": null, "end": "2026-11-02",
   "aud": ["student"], "cond": ["app"], "code": "", "source": "https://...", "redeem_url": "https://...（選填）",
   "checked_at": "...", "origin": "demo | auto | report"
 }]
}
```
- `type`：coupon 優惠券、sale 特價、event 活動、trial 免費試用、cashback 點數回饋、plan 方案折扣
- `aud`：student、worker、startup、family、senior、newbie
- `cond`：member、app、line、pay、bundle、store
- `end` 為 null 代表長期有效

## 5. 自動更新流程
1. `scripts/fetch.py`：依 `sources.yaml` 抓網頁，先檢查 robots.txt，轉成純文字
2. `scripts/extract.py`：送給 Gemini（REST API、JSON schema 輸出），只收網頁明確寫的優惠，用自己的話改寫
3. `scripts/merge.py`：去除重複（同店家＋同標題 = 同 ID）、併入已核准的回報、刪掉過期、自動抓到但超過 `stale_days` 天沒再出現的也刪掉
4. Workflow 有變動就 commit；處理過的 Issue 自動關閉，有問題的會留言並移除 `approved` 標籤

回報流程：使用者開 Issue（標籤 `new-coupon` 或 `expired`）→ 你檢查後加上 `approved` 標籤 → 下次自動更新時併入。

## 6. 已測試／未測試
- ✅ 網頁：電腦與手機寬度、探索／推薦／優惠夾三個頁面、已使用狀態、優惠詳情（點卡片開啟、Esc 關閉），沒有 JavaScript 錯誤
- ✅ 合併腳本：回報新增、回報失效、未知店家退回都測過
- ❌ **還沒實際呼叫過 Gemini 和抓真實網頁**（開發環境沒有金鑰、也連不到外部網站）。第一次執行請先用手動觸發，看 Actions 紀錄。

## 7. 已知問題與下一步
0. **`sources.yaml` 還沒填 `app_ios` / `app_android`**：請用子代理查各品牌官方 App 的商店網址再填入（不要用猜的 ID）。之後也可以加 LINE 官方帳號連結，給「LINE 限定」的優惠用。
1. **`sources.yaml` 的網址多半是官網首頁**，要換成各店家的優惠／活動頁（可以用子代理分頭搜尋）。
2. 很多網站是 JavaScript 動態載入，純抓 HTML 拿不到內容 → 之後可改用 Playwright，或改抓官方 Facebook、新聞稿、PTT／Dcard 優惠板。
3. 很多速食券只在 App 裡，爬不到 → 靠使用者回報補。
4. Gemini 模型名稱寫在 `sources.yaml` 的 `settings.model`，Google 改版時要更新。
5. 跨裝置同步收藏需要登入功能（例如 Firebase 或 Supabase 免費方案）。
6. 可加：到期提醒、依地區（台南）篩選、PWA 讓手機能加到主畫面。
