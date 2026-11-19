"""每週整理「回報錯誤」：讀 Google 表單回覆（發布成 CSV 的網址），把上次之後的新回報依優惠合併成一份清單。

用法：
  python scripts/reports.py            # 印出清單，並寫到 reports.md（Actions 會用它開一個 Issue）
  python scripts/reports.py --dry-run  # 只印出，不記錄「已整理到第幾筆」

表單網址填在 sources.yaml 的 settings.report_csv；沒填就什麼都不做。
"""
import argparse
import csv
import io
import json
import sys
import os
from collections import defaultdict

import requests

sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, load_config, load_data, today  # noqa: E402

STATE_PATH = ROOT / "data" / "reports_state.json"
OUT_PATH = ROOT / "reports.md"


def col(row: dict, *names: str) -> str:
    """依欄位名稱找值（表單題目名稱可能有小差異，用「包含」比對）。"""
    for k, v in row.items():
        if k and any(n in k for n in names):
            return (v or "").strip()
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    url = (load_config().get("settings", {}).get("report_csv") or "").strip()
    if not url:
        print("settings.report_csv 沒有填，略過")
        return 0
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))

    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {"rows": 0}
    new = rows[state.get("rows", 0):]
    print(f"表單共 {len(rows)} 筆回報，新的 {len(new)} 筆")

    coupons = {c["id"]: c for c in load_data().get("coupons", [])}
    stores = load_config()["stores"]
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in new:
        groups[col(row, "優惠代號", "代號") or "（沒有代號）"].append(row)

    lines = [f"# 回報錯誤整理（{today()}）", "",
             f"上次整理之後共 {len(new)} 筆回報，涉及 {len(groups)} 筆優惠。回報多的排前面。", ""]
    for cid, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        c = coupons.get(cid)
        if c:
            name = stores.get(c["store"], {}).get("name", c["store"])
            src = f"（{c.get('via')}）" if c.get("via") else ""
            head = f"## {len(items)} 筆｜{name}｜{c['title']}{src}"
            info = [f"- 代號 `{cid}`，來源：{c.get('source') or '—'}，到期：{c.get('end') or '沒寫'}"]
        else:
            head = f"## {len(items)} 筆｜{col(items[0], '店家') or '?'}｜代號 `{cid}`（資料裡已經沒有這筆，可能已移除）"
            info = []
        kinds = defaultdict(int)
        for it in items:
            kinds[col(it, "哪裡有問題", "問題") or "沒選"] += 1
        lines += [head, *info, "- 問題：" + "、".join(f"{k} ×{n}" for k, n in kinds.items())]
        for it in items:
            note = col(it, "補充", "說明")
            if note:
                lines.append(f"  - {col(it, '時間戳記', 'Timestamp')}：{note[:200]}")
        lines.append("")

    text = "\n".join(lines)
    print(text)
    if new and not args.dry_run:
        OUT_PATH.write_text(text, encoding="utf-8")
        STATE_PATH.write_text(json.dumps({"rows": len(rows), "updated": today()}) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
