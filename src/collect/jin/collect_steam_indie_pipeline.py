import sys
import os
import re
import json
import time
import random
import argparse
import tempfile

import requests
from bs4 import BeautifulSoup
from psycopg2.extras import Json, execute_values
from requests import RequestException

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.db import get_connection


# ========================
# 설정
# ========================
INDIE_TAG_ID = 492
STEAM_SEARCH_URL = "https://store.steampowered.com/search/results/"
STEAMSPY_URL = "https://steamspy.com/api.php"

CHECKPOINT_PATH = os.path.join(
    PROJECT_ROOT, "data/logs/steam_indie_pipeline_checkpoint.json"
)
FAILED_APPIDS_PATH = os.path.join(
    PROJECT_ROOT, "data/logs/steam_indie_pipeline_failed_appids.jsonl"
)

PAGE_SIZE = 100
BATCH_SIZE = 50
STEAM_SEARCH_SLEEP_SEC = 1.0
STEAMSPY_SLEEP_SEC = 1.2
MAX_RETRIES = 5
REQUEST_TIMEOUT = 20

APPID_PATTERN = re.compile(r"/app/(\d+)")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ========================
# DB
# ========================
def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS steam_indie_tags (
            appid INTEGER PRIMARY KEY,
            title TEXT,
            release_date TEXT,
            owners TEXT,
            positive INTEGER,
            negative INTEGER,
            price INTEGER,
            developer TEXT,
            publisher TEXT,
            tags JSONB,
            fetched_at TIMESTAMP DEFAULT NOW()
        )
    """)

    conn.commit()
    cursor.close()
    return conn


# ========================
# 체크포인트
# ========================
def load_checkpoint():
    if not os.path.exists(CHECKPOINT_PATH):
        return {"start": 0, "done": []}

    try:
        with open(CHECKPOINT_PATH, "r") as f:
            checkpoint = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[WARN] checkpoint load failed: {e}. starting from 0")
        return {"start": 0, "done": []}

    return {
        "start": checkpoint.get("start", 0),
        "done": checkpoint.get("done", []),
    }


def save_checkpoint(start, done):
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    payload = {"start": start, "done": sorted(done)}

    fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(CHECKPOINT_PATH),
        prefix=".steam_indie_pipeline_checkpoint_",
        suffix=".json",
        text=True,
    )

    with os.fdopen(fd, "w") as f:
        json.dump(
            payload,
            f,
            indent=2
        )
    os.replace(tmp_path, CHECKPOINT_PATH)


def append_failed_appid(appid, reason):
    os.makedirs(os.path.dirname(FAILED_APPIDS_PATH), exist_ok=True)
    payload = {
        "appid": appid,
        "reason": reason,
        "failed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(FAILED_APPIDS_PATH, "a") as f:
        f.write(json.dumps(payload) + "\n")


# ========================
# 공통 요청
# ========================
def request_with_retry(session, url, params=None):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r

        except RequestException as e:
            if attempt == MAX_RETRIES:
                print(f"[FAIL] {e}")
                return None

            status_code = getattr(e.response, "status_code", None)
            wait = 1.5 * attempt + random.random()
            if status_code == 429:
                wait = max(wait, STEAMSPY_SLEEP_SEC * attempt * 2)
            print(f"[RETRY] {e} -> {wait:.1f}s")
            time.sleep(wait)


# ========================
# Steam Search
# ========================
def fetch_search(session, start):
    params = {
        "query": "",
        "start": start,
        "count": PAGE_SIZE,
        "tags": INDIE_TAG_ID,
        "category1": 998,
        "infinite": 1
    }

    r = request_with_retry(session, STEAM_SEARCH_URL, params)
    if not r:
        return None

    try:
        return r.json()
    except ValueError as e:
        print(f"[WARN] search JSON parse failed start={start}: {e}")
        return None


def parse_search(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for el in soup.select("a.search_result_row"):
        href = el.get("href", "")
        m = APPID_PATTERN.search(href)
        if not m:
            continue

        rows.append({
            "appid": int(m.group(1)),
            "title": el.select_one("span.title").text.strip() if el.select_one("span.title") else None,
            "release_date": el.select_one("div.search_released").text.strip() if el.select_one("div.search_released") else None,
        })

    return rows


# ========================
# SteamSpy
# ========================
def fetch_steamspy(session, appid):
    r = request_with_retry(session, STEAMSPY_URL, {
        "request": "appdetails",
        "appid": appid
    })

    if not r:
        return None

    try:
        data = r.json()
    except ValueError as e:
        print(f"[WARN] steamspy JSON parse failed appid={appid}: {e}")
        return None

    if not data or not data.get("name"):
        return None

    return data


# ========================
# DB 저장
# ========================
def save_batch(conn, batch):
    if not batch:
        return []

    query = """
        INSERT INTO steam_indie_tags
        (appid, title, release_date, owners, positive, negative,
         price, developer, publisher, tags)
        VALUES %s
        ON CONFLICT (appid) DO UPDATE SET
            title = EXCLUDED.title,
            release_date = EXCLUDED.release_date,
            owners = EXCLUDED.owners,
            positive = EXCLUDED.positive,
            negative = EXCLUDED.negative,
            price = EXCLUDED.price,
            developer = EXCLUDED.developer,
            publisher = EXCLUDED.publisher,
            tags = EXCLUDED.tags,
            fetched_at = NOW()
    """

    values = [
        (
            r["appid"],
            r["title"],
            r["release_date"],
            r["owners"],
            r["positive"],
            r["negative"],
            r["price"],
            r["developer"],
            r["publisher"],
            Json(r["tags"])
        )
        for r in batch
    ]

    try:
        with conn.cursor() as cur:
            execute_values(cur, query, values)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return [r["appid"] for r in batch]


def checkpoint_saved_batch(conn, batch, done, start):
    saved_appids = save_batch(conn, batch)
    if not saved_appids:
        return 0

    done.update(saved_appids)
    save_checkpoint(start, done)
    batch.clear()
    return len(saved_appids)


# ========================
# MAIN
# ========================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    conn = init_db()

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    cp = load_checkpoint()

    done = set() if args.reset else set(cp["done"])
    start = 0 if args.reset else cp["start"]

    batch = []
    fetched_count = 0
    db_saved_count = 0
    failed_count = 0
    page = 0

    print("=== START PIPELINE ===")

    try:
        while True:

            if args.max_pages and page >= args.max_pages:
                break

            data = fetch_search(session, start)
            if not data:
                break
            time.sleep(STEAM_SEARCH_SLEEP_SEC)

            total_count = data.get("total_count")
            rows = parse_search(data.get("results_html", ""))

            if not rows:
                break

            total_label = f"{total_count:,}" if isinstance(total_count, int) else "unknown"
            print(
                f"\n[SEARCH PAGE] start={start:,} rows={len(rows):,} total={total_label}"
            )

            for idx, row in enumerate(rows, start=1):
                appid = row["appid"]
                search_position = start + idx

                if appid in done:
                    continue

                if args.limit and fetched_count >= args.limit:
                    raise KeyboardInterrupt

                spy = fetch_steamspy(session, appid)
                if spy is None:
                    failed_count += 1
                    append_failed_appid(appid, "steamspy_appdetails_failed")
                    continue

                batch.append({
                    "appid": appid,
                    "title": row["title"] or spy.get("name"),
                    "release_date": row["release_date"],
                    "owners": spy.get("owners"),
                    "positive": spy.get("positive"),
                    "negative": spy.get("negative"),
                    "price": spy.get("price"),
                    "developer": spy.get("developer"),
                    "publisher": spy.get("publisher"),
                    "tags": spy.get("tags", {})
                })

                fetched_count += 1

                print(
                    f"[FETCHED {fetched_count}] search={search_position:,}/{total_label} | "
                    f"{row['title']} | "
                    f"tags={len(spy.get('tags', {}))}",
                    end="\r"
                )

                if len(batch) >= BATCH_SIZE:
                    saved_now = checkpoint_saved_batch(conn, batch, done, start)
                    db_saved_count += saved_now
                    print(f"\n[BATCH SAVED] batch={saved_now} total_db_saved={db_saved_count}")

                time.sleep(STEAMSPY_SLEEP_SEC)

            if batch:
                saved_now = checkpoint_saved_batch(conn, batch, done, start)
                db_saved_count += saved_now
                print(f"\n[PAGE BATCH SAVED] batch={saved_now} total_db_saved={db_saved_count}")

            start += len(rows)
            page += 1
            save_checkpoint(start, done)

            print(f"\n[PAGE] {page} next_start={start}")

    except KeyboardInterrupt:
        print("\n[STOPPED] checkpoint saved")

    finally:
        saved_now = checkpoint_saved_batch(conn, batch, done, start)
        db_saved_count += saved_now
        save_checkpoint(start, done)
        session.close()
        conn.close()

        print(
            "\n=== DONE: "
            f"fetched={fetched_count}, db_saved={db_saved_count}, failed={failed_count} ==="
        )


if __name__ == "__main__":
    main()
