"""把網頁文字交給 Gemini，整理成固定格式的優惠清單。"""
import json
import time

import requests

from common import AUD, COND, TYPE

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "title": {"type": "STRING", "description": "優惠標題，30 字以內，繁體中文"},
            "desc": {"type": "STRING", "description": "使用方式或限制，60 字以內，用自己的話改寫，不要整段照抄"},
            "type": {"type": "STRING", "enum": list(TYPE)},
            "start": {"type": "STRING", "description": "開始日期 YYYY-MM-DD，網頁沒寫就留空字串"},
            "end": {"type": "STRING", "description": "到期日期 YYYY-MM-DD，網頁沒寫就留空字串"},
            "aud": {"type": "ARRAY", "items": {"type": "STRING", "enum": list(AUD)}},
            "cond": {"type": "ARRAY", "items": {"type": "STRING", "enum": list(COND)}},
            "code": {"type": "STRING", "description": "優惠碼，沒有就留空字串"},
        },
        "required": ["title", "desc", "type", "start", "end", "aud", "cond", "code"],
    },
}

PROMPT = """你是優惠資料整理員。以下是「{store}」網頁（{url}）的文字內容，今天是 {today}（台灣時間）。

請找出網頁上明確寫出、目前或即將有效的優惠：優惠券、特價、活動、免費試用、點數回饋、方案折扣。
規則：
- 只收網頁上真的有寫的優惠，不要猜測或補充。
- 已經過期的不要收。
- aud（適合對象）只在網頁明確限定對象時才填，例如寫了「學生限定」才填 student；不限對象就給空陣列。
  student=學生 worker=上班族 startup=新創或企業 family=家庭或多人 senior=長者 newbie=新用戶或首購
- cond（使用條件）同樣只填網頁明確寫的：member=會員 app=App 限定 line=LINE 限定 pay=指定支付或信用卡 bundle=綁約 store=門市限定
- 標題和說明用繁體中文、用自己的話改寫，不要整段照抄網頁。
- 沒有任何優惠就回傳空陣列。

網頁內容：
---
{text}
---"""


def extract(store: str, url: str, text: str, model: str, api_key: str, today: str) -> list[dict]:
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(store=store, url=url, today=today, text=text)}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA, "temperature": 0.1},
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    for attempt in range(3):
        r = requests.post(API.format(model=model), headers=headers, json=body, timeout=90)
        if r.status_code == 429 or r.status_code >= 500:  # 超過免費額度或伺服器忙：等一下再試
            time.sleep(30 * (attempt + 1))
            continue
        r.raise_for_status()
        try:
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            items = json.loads(raw)
        except (KeyError, IndexError, json.JSONDecodeError):
            return []
        return items if isinstance(items, list) else []
    raise RuntimeError("Gemini 連續失敗，可能超過今日免費額度")
