"""抓網頁並轉成純文字。會先檢查 robots.txt，網站不允許就跳過。"""
import re
import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

USER_AGENT = "CouponOrganizerBot/0.3 (+https://github.com/StupidLlama/coupon-organizer)"
TOTAL_SECONDS = 45
_robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def allowed(url: str) -> bool:
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=(10, 15))
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            _robots_cache[base] = rp
        except requests.RequestException:
            _robots_cache[base] = None  # 讀不到 robots.txt：照一般慣例視為允許
    rp = _robots_cache[base]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def fetch_raw(url: str) -> tuple[requests.Response | None, str]:
    """下載網頁原始內容（先檢查 robots.txt）。回傳 (回應, 狀態說明)；失敗時回應是 None。"""
    if not allowed(url):
        return None, "robots.txt 不允許抓取"
    try:
        # timeout 只管「多久沒收到資料」，網站一點一點慢慢傳會卡很久，所以另外限制整頁最多下載 TOTAL_SECONDS 秒
        r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-TW,zh;q=0.9"},
                         timeout=(10, 20), stream=True)
        if r.status_code != 200:
            r.close()
            return None, f"HTTP {r.status_code}"
        start, body = time.monotonic(), b""
        for chunk in r.iter_content(65536):
            body += chunk
            if time.monotonic() - start > TOTAL_SECONDS:
                r.close()
                return None, f"下載超過 {TOTAL_SECONDS} 秒，跳過"
            if len(body) > 5_000_000:  # 超過 5MB 的網頁不是一般優惠頁
                break
    except requests.RequestException as e:
        return None, f"連線失敗：{e.__class__.__name__}"
    r._content = body
    r.encoding = r.apparent_encoding or r.encoding
    return r, "ok"


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "header", "footer", "nav"]):
        tag.decompose()
    text = re.sub(r"\n\s*\n+", "\n", soup.get_text("\n"))
    return re.sub(r"[ \t　]+", " ", text).strip()


def fetch_text(url: str, max_chars: int = 15000) -> tuple[str | None, str]:
    """回傳 (文字, 狀態說明)。失敗時文字是 None。"""
    r, status = fetch_raw(url)
    if r is None:
        return None, status
    text = html_to_text(r.text)
    if len(text) < 80:
        return None, "沒有文字（可能是 JavaScript 動態載入的網頁）"
    return text[:max_chars], "ok"
