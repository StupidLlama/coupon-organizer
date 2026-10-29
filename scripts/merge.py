"""合併：把新抓到的優惠、使用者回報併進資料檔，並清掉過期或太久沒出現的優惠。"""
import re
from datetime import date

from common import AUD, COND, TYPE, coupon_id, now_iso, today, valid_date

LABEL_TO_AUD = {v: k for k, v in AUD.items()}
LABEL_TO_COND = {v: k for k, v in COND.items()}
LABEL_TO_TYPE = {v: k for k, v in TYPE.items()}


def clean_item(store: str, raw: dict, origin: str, source: str = "") -> dict | None:
    title = str(raw.get("title", "")).strip()[:60]
    if not title or raw.get("type") not in TYPE:
        return None
    end = valid_date(raw.get("end"))
    if end and end < today():
        return None
    return {
        "id": coupon_id(store, title),
        "store": store,
        "type": raw["type"],
        "title": title,
        "desc": str(raw.get("desc", "")).strip()[:120],
        "start": valid_date(raw.get("start")),
        "end": end,
        "aud": [a for a in dict.fromkeys(raw.get("aud") or []) if a in AUD],
        "cond": [c for c in dict.fromkeys(raw.get("cond") or []) if c in COND],
        "code": str(raw.get("code", "")).strip()[:30],
        "source": source,
        "redeem_url": str(raw.get("redeem_url") or "").strip() if str(raw.get("redeem_url") or "").startswith("http") else "",
        "checked_at": now_iso(),
        "origin": origin,
    }


def store_public(s: dict) -> dict:
    """網頁需要的店家欄位：url 是官網（第一個抓取網址），app_ios / app_android 是 App 下載頁（選填）。"""
    out = {f: s[f] for f in ("name", "domain", "sub", "color")}
    out["url"] = (s.get("urls") or [f"https://{s['domain']}/"])[0]
    for f in ("app_ios", "app_android"):
        if s.get(f):
            out[f] = s[f]
    return out


def parse_issue_form(body: str) -> dict[str, str]:
    """GitHub Issue 表單送出後會變成「### 欄位名稱」加內容的格式。"""
    fields, key = {}, None
    for line in (body or "").splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            key = m.group(1)
            fields[key] = ""
        elif key is not None:
            fields[key] += line + "\n"
    return {k: ("" if v.strip() == "_No response_" else v.strip()) for k, v in fields.items()}


def checked(text: str, mapping: dict[str, str]) -> list[str]:
    return [mapping[m] for m in re.findall(r"- \[[xX]\]\s*(.+)", text) if m.strip() in mapping]


def report_to_item(fields: dict, stores: dict) -> tuple[dict | None, str]:
    name = fields.get("店家", "").strip()
    store = next((sid for sid, s in stores.items() if s["name"].lower() == name.lower()), None)
    if not store:
        return None, f"找不到店家「{name}」，請先把它加進 sources.yaml"
    raw = {
        "title": fields.get("優惠標題", ""),
        "desc": fields.get("優惠內容", ""),
        "type": LABEL_TO_TYPE.get(fields.get("優惠類型", "").strip()),
        "end": fields.get("到期日", ""),
        "aud": checked(fields.get("適合誰", ""), LABEL_TO_AUD),
        "cond": checked(fields.get("使用條件", ""), LABEL_TO_COND),
        "code": fields.get("優惠碼", ""),
        "redeem_url": fields.get("兌換網址", ""),
    }
    item = clean_item(store, raw, "report", fields.get("來源網址", "").strip())
    return (item, "") if item else (None, "標題、類型或到期日有誤（或已經過期）")


def merge(data: dict, cfg: dict, found: dict[str, list[dict]], fetched_ok: set[str], issues: list[dict]):
    """found: 店家 → 這次抓到的優惠；fetched_ok: 這次成功抓到網頁的店家。
    回傳 (新資料, 已處理的 issue 編號, 被退回的 issue [(編號, 原因)], 紀錄文字)。"""
    settings = cfg.get("settings", {})
    stores = cfg["stores"]
    t = today()
    log, processed, rejected = [], [], []
    by_id = {c["id"]: c for c in data.get("coupons", [])}

    # 1. 新抓到的：同 ID 就更新內容與確認時間，否則新增
    for store, items in found.items():
        for raw in items:
            item = clean_item(store, raw, "auto", raw.get("_source", ""))
            if not item:
                continue
            old = by_id.get(item["id"])
            if old and old.get("origin") == "report":
                old["checked_at"] = item["checked_at"]  # 使用者回報的內容優先保留
            else:
                by_id[item["id"]] = item
                log.append(f"{'更新' if old else '新增'}：{stores[store]['name']}｜{item['title']}")

    # 2. 使用者回報（已加上 approved 標籤的 issue）
    for iss in issues:
        labels = {l["name"] for l in iss.get("labels", [])}
        fields = parse_issue_form(iss.get("body", ""))
        if "expired" in labels:
            cid = fields.get("優惠編號", "").strip()
            if cid in by_id:
                log.append(f"回報失效，移除：{by_id.pop(cid)['title']}")
                processed.append(iss["number"])
            else:
                rejected.append((iss["number"], f"找不到編號 {cid} 的優惠，可能已經被移除"))
        elif "new-coupon" in labels:
            item, why = report_to_item(fields, stores)
            if item:
                by_id[item["id"]] = item
                processed.append(iss["number"])
                log.append(f"回報新增：{stores[item['store']]['name']}｜{item['title']}")
            else:
                rejected.append((iss["number"], why))

    # 3. 清理：過期、自動抓的太久沒再出現、關掉示範資料
    stale_days = int(settings.get("stale_days", 14))
    keep_demo = bool(settings.get("keep_demo", True))
    kept = []
    for c in by_id.values():
        if c.get("end") and c["end"] < t:
            log.append(f"過期移除：{c['title']}")
            continue
        if c.get("origin") == "demo" and not keep_demo:
            continue
        if c.get("origin") == "auto" and c["store"] in fetched_ok:
            if (date.fromisoformat(t) - date.fromisoformat(c["checked_at"][:10])).days > stale_days:
                log.append(f"太久沒出現，移除：{c['title']}")
                continue
        if c["store"] not in stores:
            continue
        kept.append(c)

    kept.sort(key=lambda c: (c["store"], c.get("end") or "9999"))
    data["coupons"] = kept
    data["stores"] = {k: store_public(v) for k, v in stores.items()}
    data["categories"] = cfg["categories"]
    data["updated_at"] = now_iso()
    return data, processed, rejected, log
