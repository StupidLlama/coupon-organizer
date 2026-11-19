"""把網頁文字交給 Gemini，整理成固定格式的優惠清單。"""
import json
import time

import requests

from common import AUD, COND, MEAL, TYPE

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
LIST_API = "https://generativelanguage.googleapis.com/v1beta/models"
SKIP_WORDS = ("lite", "image", "tts", "live", "audio", "embedding", "thinking", "exp", "preview", "omni")


def _version(name: str) -> tuple:
    import re
    m = re.search(r"gemini-(\d+)(?:\.(\d+))?", name)
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)


def resolve_models(preferred: str, api_key: str, limit: int = 4) -> list[str]:
    """向 Gemini 查詢這把金鑰能用的模型，回傳候選清單（第一個優先用，忙線或沒額度時換下一個）。
    preferred 是 auto 時，依版本由新到舊排列穩定的 flash 模型；有指定名稱且可用時，排在第一個。"""
    r = requests.get(LIST_API, headers={"x-goog-api-key": api_key}, params={"pageSize": 200}, timeout=30)
    r.raise_for_status()
    names = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    flash = [n for n in names if "flash" in n and not any(w in n for w in SKIP_WORDS)]
    if not flash:  # 沒有穩定版就退一步，接受 preview
        flash = [n for n in names if "flash" in n and not any(w in n for w in SKIP_WORDS if w != "preview")]
    if not flash and not (preferred in names):
        raise RuntimeError("找不到可用的 Gemini flash 模型，可用模型：" + ", ".join(names[:20]))
    # 版本新的優先；同版本時，名稱短的（例如 gemini-x-flash，而不是帶日期的版本）優先
    ordered = sorted(flash, key=lambda n: (_version(n), -len(n)), reverse=True)
    if preferred and preferred != "auto" and preferred in names:
        ordered = [preferred] + [n for n in ordered if n != preferred]
    # 最後一個備用放 Flash-Lite：比較不擠、免費額度大很多，flash 都 503／429 時還能整理（品質可能稍差）
    lite = sorted((n for n in names if "flash-lite" in n and not any(w in n for w in SKIP_WORDS if w != "lite")),
                  key=lambda n: (_version(n), -len(n)), reverse=True)
    if lite:
        return ordered[:limit - 1] + lite[:1]
    return ordered[:limit]


# 這次執行的 Gemini 用量：模型 → 次數與 token，run.py 最後存到 data/usage.json
USAGE: dict[str, dict] = {}


def _record(model: str, r: requests.Response) -> None:
    u = USAGE.setdefault(model, {"requests": 0, "ok": 0, "http_429": 0, "http_5xx": 0,
                                 "input_tokens": 0, "output_tokens": 0, "last_error": ""})
    u["requests"] += 1
    if r.status_code == 200:
        u["ok"] += 1
        meta = r.json().get("usageMetadata", {})
        u["input_tokens"] += meta.get("promptTokenCount", 0)
        u["output_tokens"] += meta.get("candidatesTokenCount", 0) + meta.get("thoughtsTokenCount", 0)
    else:
        if r.status_code == 429:
            u["http_429"] += 1
        elif r.status_code >= 500:
            u["http_5xx"] += 1
        u["last_error"] = f"HTTP {r.status_code}：{_api_message(r)}"  # 429 的訊息會寫是每分鐘還是每日額度


class ModelBusy(Exception):
    """這個模型目前忙線（503）或沒有額度（429），可以換下一個模型再試。"""


def _api_message(r: requests.Response) -> str:
    try:
        return r.json().get("error", {}).get("message", "")[:160]
    except ValueError:
        return r.text[:160]


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
            "meal": {"type": "ARRAY", "items": {"type": "STRING", "enum": list(MEAL)},
                     "description": "吃的喝的才填：適合哪些時段；不是餐飲就給空陣列"},
            "price": {"type": "INTEGER", "description": "優惠後的最低售價（新台幣整數），網頁沒寫明售價就填 0；折扣金額或滿額門檻不算售價"},
            "item": {"type": "STRING", "description": "實際買到或吃到什麼，15 字以內，例如「大比薩＋烤雞」；看不出來就留空字串"},
        },
        "required": ["title", "desc", "type", "start", "end", "aud", "cond", "code", "meal", "price", "item"],
    },
}

MEAL_RULES = """meal：只有吃的喝的才填，依品項判斷適合的時段，可以多選：
  breakfast=早餐 lunch=午餐 snack=下午茶或點心 dinner=晚餐 late=宵夜 drink=飲料；不是餐飲就給空陣列。
price：優惠後的最低售價（整數，新台幣），例如「個人比薩 3 個 $259」填 259；只寫「現折 10 元」「滿 400 送 400」「8 折」這種沒有售價的填 0。
item：實際買到或吃到什麼，15 字以內；看不出來就留空字串。"""

PROMPT = """你是優惠資料整理員。以下是「{store}」網頁（{url}）的文字內容，今天是 {today}（台灣時間）。

請找出網頁上明確寫出、目前或即將有效的優惠：優惠券、特價、活動、免費試用、點數回饋、方案折扣。
規則：
- 只收網頁上真的有寫的優惠，不要猜測或補充。
- 已經過期的不要收。
- aud（適合對象）只在網頁明確限定對象時才填，例如寫了「學生限定」才填 student；不限對象就給空陣列。
  student=學生 worker=上班族 startup=新創或企業 family=家庭或多人 senior=長者 newbie=新用戶或首購
- cond（使用條件）同樣只填網頁明確寫的：member=會員 app=App 限定 line=LINE 限定 pay=指定支付或信用卡 bundle=綁約 store=門市限定
- 標題和說明用繁體中文、用自己的話改寫，不要整段照抄網頁。
- meal、price、item 是給「今天吃什麼」推薦用的（規則見下方）。
- 沒有任何優惠就回傳空陣列。

{meal_rules}

網頁內容：
---
{text}
---"""


def _generate(prompt: str, schema: dict, model: str, api_key: str) -> list[dict]:
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "temperature": 0.1},
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    last = ""
    for attempt in range(2):
        r = requests.post(API.format(model=model), headers=headers, json=body, timeout=120)
        _record(model, r)
        if r.status_code == 429 or r.status_code >= 500:  # 沒額度或伺服器忙：等一下再試一次
            last = f"HTTP {r.status_code}：{_api_message(r)}"
            time.sleep(20 * (attempt + 1))
            continue
        if r.status_code in (401, 403):
            raise PermissionError(f"金鑰無效或沒有權限（HTTP {r.status_code}）：{_api_message(r)}")
        r.raise_for_status()
        try:
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            items = json.loads(raw)
        except (KeyError, IndexError, json.JSONDecodeError):
            return []
        return items if isinstance(items, list) else []
    raise ModelBusy(last)


def extract(store: str, url: str, text: str, model: str, api_key: str, today: str) -> list[dict]:
    return _generate(PROMPT.format(store=store, url=url, today=today, text=text, meal_rules=MEAL_RULES), SCHEMA, model, api_key)


TIP_PROMPT = """你是優惠資料整理員。以下是優惠整理網站「{via}」的 {n} 篇文章，今天是 {today}（台灣時間）。
這些是第三方整理，不是店家官方公告。

請找出文章裡寫到、目前或即將有效的優惠，並對到下面的店家代號：
{stores}

規則：
- store 填上面清單裡的代號；清單裡沒有的店家就填 other。
- article 填這筆優惠出自第幾篇文章（從 1 開始）。
- 只收文章裡真的有寫的優惠，不要猜測或補充；沒有寫到期日就留空字串。
- 已經過期的不要收；只是新品上市、沒有任何折扣的不要收。
- aud、cond 只在文章明確寫出限定時才填（規則同下）：
  aud：student=學生 worker=上班族 startup=新創或企業 family=家庭或多人 senior=長者 newbie=新用戶或首購
  cond：member=會員 app=App 限定 line=LINE 限定 pay=指定支付或信用卡 bundle=綁約 store=門市限定
- 標題和說明用繁體中文、用自己的話重新寫，只保留事實（品項、價格、折扣、日期、條件），不要照抄文章的句子、評語或推薦語。
- 沒有任何優惠就回傳空陣列。
{meal_rules}

{articles}"""


def tip_schema(store_ids: list[str]) -> dict:
    item = json.loads(json.dumps(SCHEMA["items"]))  # 複製一份再加欄位
    item["properties"]["store"] = {"type": "STRING", "enum": store_ids + ["other"]}
    item["properties"]["article"] = {"type": "INTEGER", "description": "出自第幾篇文章，從 1 開始"}
    item["required"] = item["required"] + ["store", "article"]
    return {"type": "ARRAY", "items": item}


def extract_tips(via: str, articles: list[dict], stores: dict, model: str, api_key: str, today: str) -> list[dict]:
    """一次把多篇文章交給 Gemini。回傳的每筆優惠帶 store（店家代號）和 _source（原文網址）。"""
    store_list = "、".join(f"{sid}={s['name']}" for sid, s in stores.items())
    body = "\n\n".join(f"【第 {i} 篇】{a['title']}\n---\n{a['text']}\n---" for i, a in enumerate(articles, 1))
    prompt = TIP_PROMPT.format(via=via, n=len(articles), today=today, stores=store_list, articles=body, meal_rules=MEAL_RULES)
    out = []
    for it in _generate(prompt, tip_schema(list(stores)), model, api_key):
        n = it.get("article")
        if it.get("store") in stores and isinstance(n, int) and 1 <= n <= len(articles):
            it["_source"] = articles[n - 1]["url"]
            it["_via"] = via
            out.append(it)
    return out
