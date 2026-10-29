"""共用設定：讀寫設定檔與資料檔、日期、優惠 ID。"""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "sources.yaml"
DATA_PATH = ROOT / "data" / "coupons.json"

TAIPEI = timezone(timedelta(hours=8))

AUD = {"student": "學生", "worker": "上班族", "startup": "新創・企業",
       "family": "家庭", "senior": "長者", "newbie": "新用戶"}
COND = {"member": "會員限定", "app": "App 限定", "line": "LINE 限定",
        "pay": "指定支付", "bundle": "綁約限定", "store": "門市限定"}
TYPE = {"coupon": "優惠券", "sale": "特價", "event": "活動",
        "trial": "免費試用", "cashback": "點數回饋", "plan": "方案折扣"}


def today() -> str:
    return datetime.now(TAIPEI).date().isoformat()


def now_iso() -> str:
    return datetime.now(TAIPEI).isoformat(timespec="seconds")


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def load_data() -> dict:
    if DATA_PATH.exists():
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {"updated_at": None, "categories": {}, "stores": {}, "coupons": []}


def save_data(data: dict) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def coupon_id(store: str, title: str) -> str:
    """同一家店、同一個標題（忽略空白和標點）會得到同一個 ID，用來去除重複。"""
    norm = re.sub(r"[\s\W_]+", "", title.lower())
    return hashlib.sha1(f"{store}|{norm}".encode("utf-8")).hexdigest()[:10]


def valid_date(s) -> str | None:
    if not s or not isinstance(s, str):
        return None
    try:
        return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None
