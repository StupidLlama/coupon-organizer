"""線索來源（部落格／媒體）：從 RSS 或列表頁找出「新的優惠文章」，抓內文準備交給 Gemini。

只挑標題有優惠字眼、之前沒處理過的文章；處理過的文章網址記在 data/tips_seen.json，避免每天重複花 Gemini 額度。
"""
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from common import ROOT, today
from fetch import fetch_raw, fetch_text

SEEN_PATH = ROOT / "data" / "tips_seen.json"
KEEP_DAYS = 60
# 標題要有這些字眼才算優惠文（不呼叫 Gemini，先用關鍵字省額度）
DEAL_WORDS = re.compile(
    r"優惠|買一送一|買\s*\d+\s*送\s*\d+|第二件|\d+\s*折|折扣|折價|特價|半價|免費|回饋|優惠碼|好康|限時|"
    r"生日|壽星|懶人包|\d+\s*元|銅板|加價購|1\+1")
ARTICLE_CHARS = 5000  # 每篇文章最多送多少字給 Gemini


def load_seen() -> dict[str, str]:
    try:
        return json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_seen(seen: dict[str, str]) -> None:
    cutoff = (date.fromisoformat(today()) - timedelta(days=KEEP_DAYS)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    SEEN_PATH.write_text(json.dumps(seen, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")


def due(tip: dict) -> bool:
    """every: daily 每天；weekly 只在週一（台灣時間）。"""
    if (tip.get("every") or "daily") == "weekly":
        return date.fromisoformat(today()).weekday() == 0
    return True


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _parse_feed(body: bytes) -> list[tuple[str, str]]:
    """RSS 或 Atom → [(標題, 連結)]。"""
    root = ET.fromstring(body)
    out = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        title = link = ""
        for ch in el:
            name = _local(ch.tag)
            if name == "title":
                title = (ch.text or "").strip()
            elif name == "link":
                link = (ch.text or ch.get("href") or "").strip() or link
        if title and link.startswith("http"):
            out.append((title, link))
    return out


def _parse_list_page(html: str, base: str) -> list[tuple[str, str]]:
    """一般列表頁 → 同網域、文字夠長的連結。"""
    host = urlsplit(base).netloc
    out, seen = [], set()
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        title = re.sub(r"\s+", " ", a.get_text(" ")).strip()
        link = urljoin(base, a["href"]).split("#")[0]
        if len(title) < 8 or urlsplit(link).netloc != host or link in seen or link.rstrip("/") == base.rstrip("/"):
            continue
        seen.add(link)
        out.append((title[:100], link))
    return out


def list_articles(url: str) -> tuple[list[tuple[str, str]], str]:
    r, status = fetch_raw(url)
    if r is None:
        return [], status
    head = r.content[:500].lstrip().lower()
    if head.startswith(b"<?xml") or b"<rss" in head or b"<feed" in head:
        try:
            return _parse_feed(r.content), "ok"
        except ET.ParseError as e:
            return [], f"RSS 格式錯誤：{e}"
    return _parse_list_page(r.text, url), "ok"


def new_articles(tip: dict, seen: dict[str, str]) -> tuple[list[dict], str]:
    """回傳最多 max_articles 篇「新的優惠文」：[{title, url, text}]。"""
    items, status = list_articles(tip["url"])
    if status != "ok":
        return [], status
    picked = []
    limit = int(tip.get("max_articles", 2))
    for title, link in items:
        if len(picked) >= limit:
            break
        if link in seen or not DEAL_WORDS.search(title):
            continue
        text, st = fetch_text(link, ARTICLE_CHARS)
        if not text:
            print(f"  略過文章 {title}：{st}")
            seen[link] = today()  # 抓不到內文的也記下來，明天不再試
            continue
        picked.append({"title": title, "url": link, "text": text})
    return picked, f"列表 {len(items)} 篇，新的優惠文 {len(picked)} 篇"


if __name__ == "__main__":
    # 測試用：python scripts/tips.py  → 列出每個線索來源這次會挑到哪些文章（不呼叫 Gemini、不記錄）
    from common import load_config
    for tid, tip in (load_config().get("tips") or {}).items():
        if not tip.get("url"):
            print(f"⏸ {tip['name']}：暫停（沒有網址）")
            continue
        arts, status = new_articles(tip, load_seen())
        print(f"{'✅' if arts else '⚠️'} {tip['name']}：{status}")
        for a in arts:
            print(f"   - {a['title']}（{len(a['text'])} 字）{a['url']}")
