#!/usr/bin/env python3
"""Fetch public RSS feeds and rebuild data/news-live.json.

Stdlib only (urllib, xml.etree, html, email.utils) - no pip install step,
per AGENTS.md ("外部ライブラリを増やさない" / "ビルド工程を作らない").

On any per-feed failure, the previous data for that section is kept as-is
instead of being overwritten with empty/broken content.
"""

import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "news-live.json"
REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; BriefingAppNewsBot/1.0)"

GENERAL_FEED = {
    "url": "https://www.nhk.or.jp/rss/news/cat0.xml",
    "source": "NHKニュース",
    "id_prefix": "g",
    "count": 5,
}

# "あなた向け" タグ。実装順2番：タグ選択でニュースの種類を切り替えられるようにする。
PERSONAL_CATEGORIES = [
    {
        "id": "tech",
        "label": "テクノロジー",
        "url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",
        "source": "ITmedia NEWS",
        "id_prefix": "tech",
        "count": 5,
    },
    {
        "id": "economy",
        "label": "経済",
        "url": "https://www.nhk.or.jp/rss/news/cat5.xml",
        "source": "NHKニュース",
        "id_prefix": "economy",
        "count": 5,
    },
    {
        "id": "world",
        "label": "国際",
        "url": "https://www.nhk.or.jp/rss/news/cat6.xml",
        "source": "NHKニュース",
        "id_prefix": "world",
        "count": 5,
    },
    {
        "id": "sports",
        "label": "スポーツ",
        "url": "https://www.nhk.or.jp/rss/news/cat7.xml",
        "source": "NHKニュース",
        "id_prefix": "sports",
        "count": 5,
    },
    {
        "id": "entertainment",
        "label": "エンタメ",
        "url": "https://www.nhk.or.jp/rss/news/cat2.xml",
        "source": "NHKニュース",
        "id_prefix": "ent",
        "count": 5,
    },
]

TAG_RE = re.compile(r"<[^>]+>")
SUMMARY_MAX_CHARS = 110


def is_safe_url(url):
    try:
        return urlparse(url).scheme in ("http", "https")
    except ValueError:
        return False


def clean_summary(raw):
    if not raw:
        return ""
    text = html.unescape(TAG_RE.sub("", raw)).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > SUMMARY_MAX_CHARS:
        text = text[:SUMMARY_MAX_CHARS].rstrip() + "…"
    return text


def parse_pub_date(raw):
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc).isoformat()


def fetch_feed(url, source, id_prefix, count):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as res:
        raw = res.read()

    root = ElementTree.fromstring(raw)
    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not is_safe_url(link):
            continue
        items.append(
            {
                "id": "{}{}".format(id_prefix, len(items) + 1),
                "headline": title,
                "summary": clean_summary(item.findtext("description")),
                "source": source,
                "url": link,
                "updatedAt": parse_pub_date(item.findtext("pubDate")),
            }
        )
        if len(items) >= count:
            break

    if len(items) < count:
        raise ValueError(
            "only got {} of {} required items from {}".format(len(items), count, url)
        )
    return items


def load_existing():
    if DATA_PATH.exists():
        try:
            return json.loads(DATA_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"generatedAt": None, "general": [], "personalCategories": []}


def main():
    data = load_existing()
    existing_categories = {c["id"]: c for c in data.get("personalCategories", [])}
    had_error = False

    try:
        data["general"] = fetch_feed(
            GENERAL_FEED["url"], GENERAL_FEED["source"], GENERAL_FEED["id_prefix"], GENERAL_FEED["count"]
        )
        print("[ok] general: {} items from {}".format(len(data["general"]), GENERAL_FEED["url"]))
    except Exception as exc:  # noqa: BLE001 - keep the batch alive on any single feed failure
        had_error = True
        print("[warn] general: fetch failed ({}), keeping previous data".format(exc), file=sys.stderr)
        data.setdefault("general", [])

    new_categories = []
    for cfg in PERSONAL_CATEGORIES:
        try:
            items = fetch_feed(cfg["url"], cfg["source"], cfg["id_prefix"], cfg["count"])
            new_categories.append({"id": cfg["id"], "label": cfg["label"], "items": items})
            print("[ok] {}: {} items from {}".format(cfg["id"], len(items), cfg["url"]))
        except Exception as exc:  # noqa: BLE001 - keep the batch alive on any single feed failure
            had_error = True
            print(
                "[warn] {}: fetch failed ({}), keeping previous data".format(cfg["id"], exc),
                file=sys.stderr,
            )
            fallback = existing_categories.get(cfg["id"])
            new_categories.append(
                fallback if fallback else {"id": cfg["id"], "label": cfg["label"], "items": []}
            )
    data["personalCategories"] = new_categories

    data["generatedAt"] = datetime.now(timezone.utc).isoformat()

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("wrote {}".format(DATA_PATH))

    if had_error and not data["general"] and not any(c["items"] for c in data["personalCategories"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
