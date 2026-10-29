"""每日更新主程式：抓網頁 → Gemini 整理 → 合併 → 寫回 data/coupons.json。

用法：
  python scripts/run.py                       # 完整更新（需要環境變數 GEMINI_API_KEY）
  python scripts/run.py --no-fetch            # 不抓網頁，只處理回報和清理過期
  python scripts/run.py --only mcd,sbux       # 只抓指定店家（測試用）
  python scripts/run.py --issues issues.json  # 一併處理已核准的 GitHub Issue 回報
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, load_config, load_data, save_data, today  # noqa: E402
from merge import merge  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--issues", default="")
    args = ap.parse_args()

    cfg = load_config()
    settings = cfg.get("settings", {})
    data = load_data()
    found: dict[str, list[dict]] = {}
    fetched_ok: set[str] = set()

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not args.no_fetch and not api_key:
        print("⚠️ 沒有設定 GEMINI_API_KEY，這次只處理回報和清理過期。")
    if not args.no_fetch and api_key:
        from extract import extract, resolve_model
        from fetch import fetch_text

        model = resolve_model(settings.get("model", "auto"), api_key)
        print(f"使用模型：{model}")
        only = {s for s in args.only.split(",") if s}
        gap = float(settings.get("request_gap_seconds", 7))
        stop = False
        for sid, store in cfg["stores"].items():
            if stop:
                break
            if only and sid not in only:
                continue
            for url in store.get("urls", []):
                text, status = fetch_text(url, int(settings.get("max_chars_per_page", 15000)))
                if not text:
                    print(f"略過 {store['name']} {url}：{status}")
                    continue
                try:
                    items = extract(store["name"], url, text, model, api_key, today())
                except Exception as e:  # 單一網頁失敗不影響其他店家
                    print(f"Gemini 失敗 {store['name']}：{e}")
                    if "額度" in str(e) or "401" in str(e) or "403" in str(e):
                        print("金鑰無效或超過今日額度，停止這次更新。")
                        stop = True
                        break
                    continue
                for it in items:
                    it["_source"] = url
                found.setdefault(sid, []).extend(items)
                fetched_ok.add(sid)
                print(f"{store['name']}：找到 {len(items)} 筆")
                time.sleep(gap)

    issues = []
    if args.issues and os.path.exists(args.issues):
        issues = json.load(open(args.issues, encoding="utf-8"))

    data, processed, rejected, log = merge(data, cfg, found, fetched_ok, issues)
    save_data(data)

    (ROOT / "processed.txt").write_text("\n".join(map(str, processed)), encoding="utf-8")
    (ROOT / "rejected.tsv").write_text("\n".join(f"{n}\t{why}" for n, why in rejected), encoding="utf-8")
    print("\n".join(log) or "沒有變動")
    print(f"目前共 {len(data['coupons'])} 筆優惠")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
