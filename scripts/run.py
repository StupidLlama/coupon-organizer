"""每日更新主程式：抓網頁 → Gemini 整理 → 合併 → 寫回 data/coupons.json。

用法：
  python scripts/run.py                       # 完整更新（需要環境變數 GEMINI_API_KEY）
  python scripts/run.py --no-fetch            # 不抓網頁，只處理回報和清理過期
  python scripts/run.py --only mcd,sbux       # 只抓指定店家（測試用）
  python scripts/run.py --issues issues.json  # 一併處理已核准的 GitHub Issue 回報
  python scripts/run.py --windowed            # 只抓有設定 window（指定時段）的店家
  python scripts/run.py --only-tips           # 只跑線索來源（部落格），測試用
  python scripts/run.py --no-tips             # 不跑線索來源
"""
import argparse
import json
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, in_window, load_config, load_data, now_iso, save_data, today  # noqa: E402
from merge import merge  # noqa: E402


def save_usage(usage: dict, kind: str, keep: int = 60) -> None:
    """把這次的 Gemini 用量加到 data/usage.json（保留最近 60 次），方便之後查額度用到哪裡。"""
    path = ROOT / "data" / "usage.json"
    try:
        runs = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        runs = []
    runs.append({"time": now_iso(), "kind": kind, "models": usage})
    path.write_text(json.dumps(runs[-keep:], ensure_ascii=False, indent=1), encoding="utf-8")
    for m, u in usage.items():
        print(f"用量 {m}：{u['requests']} 次（成功 {u['ok']}、429 {u['http_429']}、5xx {u['http_5xx']}），"
              f"輸入 {u['input_tokens']} / 輸出 {u['output_tokens']} tokens {u['last_error']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--issues", default="")
    ap.add_argument("--windowed", action="store_true")
    ap.add_argument("--only-tips", action="store_true")
    ap.add_argument("--no-tips", action="store_true")
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
        from extract import USAGE, ModelBusy, extract, extract_tips, resolve_models
        from fetch import fetch_text

        models = resolve_models(settings.get("model", "auto"), api_key)
        print(f"候選模型：{'、'.join(models)}")
        print(f"使用模型：{models[0]}")
        only = {s for s in args.only.split(",") if s}
        gap = float(settings.get("request_gap_seconds", 7))
        deadline = time.monotonic() + float(settings.get("max_minutes", 22)) * 60

        def ask(call, label: str):
            """呼叫 Gemini；這個模型忙線或沒額度就換下一個候選模型再試。所有模型都不能用時回傳 None。"""
            while models:
                try:
                    return call(models[0])
                except ModelBusy as e:
                    print(f"{models[0]} 無法使用（{e}），改用下一個模型")
                    models.pop(0)
                    if models:
                        print(f"使用模型：{models[0]}")
                except PermissionError as e:
                    print(e)
                    models.clear()
                except Exception as e:  # 其他錯誤只影響這一次
                    print(f"Gemini 失敗 {label}：{e}")
                    return []
            print("所有候選模型都無法使用，停止這次更新，已抓到的資料仍會保存。")
            return None

        stop = False

        # 1. 線索來源（部落格／媒體）：一個網址涵蓋很多店家，所以排在前面
        if not (args.no_tips or args.windowed or only):
            from tips import due, load_seen, new_articles, save_seen
            seen = load_seen()
            for tid, tip in (cfg.get("tips") or {}).items():
                if stop or not tip.get("url") or not due(tip):
                    continue
                arts, status = new_articles(tip, seen)
                print(f"線索 {tip['name']}：{status}")
                if not arts:
                    continue
                items = ask(lambda m: extract_tips(tip["name"], arts, cfg["stores"], m, api_key, today()), tip["name"])
                if items is None:
                    stop = True
                    break
                for a in arts:
                    seen[a["url"]] = today()
                for it in items:
                    found.setdefault(it.pop("store"), []).append(it)
                print(f"線索 {tip['name']}：找到 {len(items)} 筆（{len({i['_source'] for i in items})} 篇文章）")
                time.sleep(gap)
            save_seen(seen)

        # 2. 各店家官網
        # 每天換一家店開頭：時間不夠時，排在後面的店家隔天就會輪到前面，不會一直抓不到
        stores = [] if args.only_tips else list(cfg["stores"].items())
        k = date.fromisoformat(today()).toordinal() % max(len(stores), 1)
        for sid, store in stores[k:] + stores[:k]:
            if stop:
                break
            if only and sid not in only:
                continue
            window = store.get("window")
            if args.windowed and not window:
                continue
            if window and not in_window(window):
                if store.get("urls"):
                    print(f"略過 {store['name']}：只允許台灣時間 {window} 抓取")
                continue
            for url in store.get("urls", []):
                if time.monotonic() > deadline:  # 超過時間上限：先停，已抓到的照樣存檔，避免整個工作被 Actions 強制取消、全部白跑
                    print(f"已執行超過 {settings.get('max_minutes', 22)} 分鐘，剩下的店家下次再抓")
                    stop = True
                    break
                text, status = fetch_text(url, int(settings.get("max_chars_per_page", 15000)))
                if not text:
                    print(f"略過 {store['name']} {url}：{status}")
                    continue
                items = ask(lambda m: extract(store["name"], url, text, m, api_key, today()), store["name"])
                if items is None:
                    stop = True
                    break
                for it in items:
                    it["_source"] = url
                found.setdefault(sid, []).extend(items)
                fetched_ok.add(sid)
                print(f"{store['name']}：找到 {len(items)} 筆")
                time.sleep(gap)

    if not args.no_fetch and api_key:
        save_usage(USAGE, "windowed" if args.windowed else "daily")

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
