"""
입력 CSV의 전체 appid를 기준으로 Steam API에서 review_summary를 수집하여 DB에 저장한다.

재실행 시 steam_indie_review_summary 테이블에 이미 저장된 appid는 스킵하고,
아직 저장되지 않은 appid만 이어서 수집한다.

usage:
    uv run python src/collect/jin/collect_review_summary.py
    uv run python src/collect/jin/collect_review_summary.py <csv_path>
"""
import sys
import time
import requests
import pandas as pd
from pathlib import Path
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
from utils.db import get_connection

_ROOT = Path(__file__).parents[3]
DEFAULT_SOURCE_PATH = _ROOT / "data/raw/steam_indie_games_new.csv"
FAILED_PATH = _ROOT / "data/raw/steam_indie_review_summary_failed.csv"

SLEEP_SEC = 1.2
TIMEOUT_SEC = 15
BATCH_SIZE = 100
MAX_RETRIES = 2
RETRY_SLEEP_SEC = 5


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
    print("DB 테이블 확인 완료: steam_indie_review_summary")


def get_done_appids(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT appid FROM steam_indie_review_summary")
            return {row[0] for row in cur.fetchall()}
    except Exception:
        conn.rollback()
        return set()


def load_appids(csv_path):
    df = pd.read_csv(csv_path, usecols=["appid"])
    return (
        df["appid"]
        .dropna()
        .astype("int64")
        .drop_duplicates()
        .sort_values()
        .tolist()
    )


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
        resp = requests.get(url, params=params, timeout=TIMEOUT_SEC)
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


def flush_batch(conn, summaries):
    if not summaries:
        return 0

    values = [
        (
            item["appid"],
            item["review_score"],
            item["review_score_desc"],
            item["total_positive"],
            item["total_negative"],
            item["total_reviews"],
        )
        for item in summaries
    ]

    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO steam_indie_review_summary (
                appid, review_score, review_score_desc,
                total_positive, total_negative, total_reviews
            ) VALUES %s
            ON CONFLICT (appid) DO UPDATE SET
                review_score      = EXCLUDED.review_score,
                review_score_desc = EXCLUDED.review_score_desc,
                total_positive    = EXCLUDED.total_positive,
                total_negative    = EXCLUDED.total_negative,
                total_reviews     = EXCLUDED.total_reviews
        """, values)
    conn.commit()
    flushed_count = len(summaries)
    summaries.clear()
    return flushed_count


def save_failed_appids(appids):
    failed = sorted(set(appids))
    if not failed:
        if FAILED_PATH.exists():
            FAILED_PATH.unlink()
        return

    FAILED_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"appid": failed}).to_csv(FAILED_PATH, index=False, encoding="utf-8-sig")
    print(f"최종 실패 appid 저장: {FAILED_PATH} ({len(failed)}개)")


def collect_pass(conn, appids, pass_label):
    batch = []
    failed = []
    success = 0
    total = len(appids)

    try:
        for i, appid in enumerate(appids, start=1):
            summary = fetch_summary(appid)
            if summary:
                batch.append(summary)
                success += 1
                print(
                    f"[{pass_label} {i}/{total}] appid={appid} 완료 "
                    f"(score={summary['review_score_desc']}, total={summary['total_reviews']})"
                )
            else:
                failed.append(appid)
                print(f"[{pass_label} {i}/{total}] appid={appid} 실패")

            if len(batch) >= BATCH_SIZE:
                flushed = flush_batch(conn, batch)
                print(f"[{pass_label}] 배치 DB 적재 완료: {flushed}개")

            time.sleep(SLEEP_SEC)
    finally:
        flushed = flush_batch(conn, batch)
        if flushed:
            print(f"[{pass_label}] 마지막 배치 DB 적재 완료: {flushed}개")

    return success, failed


def main():
    if len(sys.argv) >= 2:
        source_path = Path(sys.argv[1])
        if not source_path.is_absolute():
            source_path = _ROOT / source_path
    else:
        source_path = DEFAULT_SOURCE_PATH

    appids = load_appids(source_path)
    print(f"입력 파일: {source_path}")
    print(f"전체 appid: {len(appids)}개")

    conn = get_connection()
    try:
        ensure_table(conn)

        done_appids = get_done_appids(conn)
        targets = [appid for appid in appids if appid not in done_appids]
        print(f"이미 수집됨: {len(done_appids & set(appids))}개 → 스킵")
        print(f"이번 실행 수집 대상: {len(targets)}개\n")

        if not targets:
            save_failed_appids([])
            print("수집할 appid가 없습니다.")
            return

        remaining = targets
        total_success = 0
        for attempt in range(MAX_RETRIES + 1):
            pass_label = "1차" if attempt == 0 else f"재시도 {attempt}"
            print(f"\n{pass_label} 수집 시작: {len(remaining)}개")

            success, failed = collect_pass(conn, remaining, pass_label)
            total_success += success
            print(f"{pass_label} 완료 — 성공: {success}개 / 실패: {len(failed)}개")

            if not failed:
                remaining = []
                break
            if attempt < MAX_RETRIES:
                remaining = sorted(set(failed))
                print(f"실패분 {len(remaining)}개를 {RETRY_SLEEP_SEC}초 후 재시도합니다.")
                time.sleep(RETRY_SLEEP_SEC)
            else:
                remaining = sorted(set(failed))

        save_failed_appids(remaining)
        print(f"\n완료 — 이번 실행 성공: {total_success}개 / 최종 실패: {len(remaining)}개")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
