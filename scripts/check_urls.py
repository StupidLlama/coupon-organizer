"""測試 sources.yaml 裡的網址抓不抓得到（不呼叫 Gemini，不改任何資料）。

用法：
  python scripts/check_urls.py                 # 測全部店家
  python scripts/check_urls.py --only mcd,bk   # 只測指定店家
  python scripts/check_urls.py --url https://...   # 測任意網址
結果會同時存到 check_urls.log（UTF-8），可以直接給 Claude 讀。
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, load_config  # noqa: E402
from fetch import fetch_text  # noqa: E402

# 粗略判斷頁面有沒有優惠內容：數一下常見的優惠字眼
KEYWORDS = re.compile(r"優惠|折扣|折價|特價|活動|免費|贈|買.送|限時|回饋|%\s*off|\d+\s*折", re.I)


def check(url: str) -> str:
    try:
        text, status = fetch_text(url)
    except Exception as e:  # noqa: BLE001
        text, status = None, f"錯誤：{e.__class__.__name__}"
    if text is None:
        return f"❌ {status}"
    hits = len(KEYWORDS.findall(text))
    mark = "✅" if hits >= 5 else "⚠️"
    return f"{mark} {len(text)} 字，優惠字眼 {hits} 個"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--url", action="append", default=[])
    args = ap.parse_args()

    lines = []
    log = ROOT / "check_urls.log"
    log.write_text("", encoding="utf-8")
    if args.url:
        for url in args.url:
            lines.append(f"{check(url)}  {url}")
    else:
        only = set(filter(None, args.only.split(",")))
        for key, store in load_config()["stores"].items():
            if only and key not in only:
                continue
            for url in store.get("urls", []):
                lines.append(f"{key:10} {check(url)}  {url}")
                print(lines[-1], flush=True)
                with log.open("a", encoding="utf-8") as f:  # 每測一個就存，中途中斷也看得到
                    f.write(lines[-1] + "\n")
    if args.url:
        print("\n".join(lines))
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n✅＝抓到而且有優惠內容　⚠️＝抓到但優惠字眼很少　❌＝抓不到")
    return 0


if __name__ == "__main__":
    sys.exit(main())
