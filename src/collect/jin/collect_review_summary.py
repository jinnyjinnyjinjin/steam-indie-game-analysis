"""
steam_indie_games.csv 기준으로
Steam API에서 review_summary를 수집하여 DB에 저장한다.

usage:
    python src/collect/jin/collect_review_summary.py
    python src/collect/jin/collect_review_summary.py <csv_path>  # 경로 지정 시 덮어쓰기
"""
import sys
import time
import requests
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
from utils.db import get_connection

_ROOT     = Path(__file__).parents[3]
SLEEP_SEC = 1.2


def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS steam_indie_review_summary (
                appid                BIGINT PRIMARY KEY,
                review_score         INTEGER,
                review_score_desc    TEXT,
                total_positive       INTEGER,
                total_negative       INTEGER,
                total_reviews        INTEGER
            )
        """)
    conn.commit()


def get_done_appids(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT appid FROM steam_indie_review_summary")
            return {row[0] for row in cur.fetchall()}
    except Exception:
        conn.rollback()
        return set()


def fetch_summary(appid):
    url = f"https://store.steampowered.com/appreviews/{appid}"
    params = {
        "json": 1,
        "filter": "recent",
        "language": "all",
        "num_per_page": 0,
        "purchase_type": "steam",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success") != 1:
            return None
        qs = data.get("query_summary", {})
        return {
            "appid":             appid,
            "review_score":      qs.get("review_score"),
            "review_score_desc": qs.get("review_score_desc"),
            "total_positive":    qs.get("total_positive"),
            "total_negative":    qs.get("total_negative"),
            "total_reviews":     qs.get("total_reviews"),
        }
    except Exception as e:
        print(f"  [오류] appid={appid}: {e}")
        return None


def flush_summary(conn, summary):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO steam_indie_review_summary (
                appid, review_score, review_score_desc,
                total_positive, total_negative, total_reviews
            ) VALUES (
                %(appid)s, %(review_score)s, %(review_score_desc)s,
                %(total_positive)s, %(total_negative)s, %(total_reviews)s
            )
            ON CONFLICT (appid) DO UPDATE SET
                review_score      = EXCLUDED.review_score,
                review_score_desc = EXCLUDED.review_score_desc,
                total_positive    = EXCLUDED.total_positive,
                total_negative    = EXCLUDED.total_negative,
                total_reviews     = EXCLUDED.total_reviews
        """, summary)
    conn.commit()


def main():
    if len(sys.argv) >= 2:
        sample_path = Path(sys.argv[1])
        if not sample_path.is_absolute():
            sample_path = _ROOT / sample_path
    else:
        sample_path = _ROOT / "data/preprocessed/steam_indie_games.csv"

    df = pd.read_csv(sample_path)
    sample_appids = df['appid'].unique().tolist()
    print(f"수집 대상: {len(sample_appids)}개 게임")

    conn = get_connection()
    ensure_table(conn)

    done_appids = get_done_appids(conn)
    targets = [appid for appid in sample_appids if appid not in done_appids]
    print(f"이미 수집됨: {len(done_appids & set(sample_appids))}개 → 스킵")
    print(f"신규 수집 대상: {len(targets)}개\n")

    success, fail = 0, 0
    for i, appid in enumerate(targets):
        summary = fetch_summary(appid)
        if summary:
            flush_summary(conn, summary)
            success += 1
            print(f"[{i+1}/{len(targets)}] appid={appid} 완료 "
                  f"(score={summary['review_score_desc']}, total={summary['total_reviews']})")
        else:
            fail += 1
            print(f"[{i+1}/{len(targets)}] appid={appid} 실패")
        time.sleep(SLEEP_SEC)

    conn.close()
    print(f"\n완료 — 성공: {success}개 / 실패: {fail}개")


if __name__ == "__main__":
    main()
