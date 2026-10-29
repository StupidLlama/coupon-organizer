"""抓網頁並轉成純文字。會先檢查 robots.txt，網站不允許就跳過。"""
import re
import urllib.robotparser
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

USER_AGENT = "CouponOrganizerBot/0.3 (+https://github.com/StupidLlama/coupon-organizer)"
_robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def allowed(url: str) -> bool:
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=15)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            _robots_cache[base] = rp
        except requests.RequestException:
            _robots_cache[base] = None  # 讀不到 robots.txt：照一般慣例視為允許
    rp = _robots_cache[base]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def fetch_text(url: str, max_chars: int = 15000) -> tuple[str | None, str]:
    """回傳 (文字, 狀態說明)。失敗時文字是 None。"""
    if not allowed(url):
        return None, "robots.txt 不允許抓取"
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-TW,zh;q=0.9"}, timeout=25)
    except requests.RequestException as e:
        return None, f"連線失敗：{e.__class__.__name__}"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    r.encoding = r.apparent_encoding or r.encoding
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "header", "footer", "nav"]):
        tag.decompose()
    text = re.sub(r"\n\s*\n+", "\n", soup.get_text("\n"))
    text = re.sub(r"[ \t　]+", " ", text).strip()
    if len(text) < 80:
        return None, "沒有文字（可能是 JavaScript 動態載入的網頁）"
    return text[:max_chars], "ok"
