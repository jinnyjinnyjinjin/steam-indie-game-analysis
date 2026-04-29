import pandas as pd
import requests
import time
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
from utils.db import get_connection

# ── 설정 ────────────────────────────────────────────────────
_ROOT = Path(__file__).parents[3]

if len(sys.argv) < 2:
    print("usage: python collect_steam_indie_stratified_reviews.py <sample_csv_path>")
    sys.exit(1)

SAMPLE_PATH = Path(sys.argv[1])
if not SAMPLE_PATH.is_absolute():
    SAMPLE_PATH = _ROOT / SAMPLE_PATH

OUTPUT_PATH      = _ROOT / "data/processed/steam_indie_reviews.csv"
CHECKPOINT_PATH   = _ROOT / "data/logs/steam_indie_reviews_checkpoint.jsonl"
DONE_APPIDS_PATH  = _ROOT / "data/logs/steam_indie_reviews_done.json"
API_ERROR_PATH    = _ROOT / "data/logs/steam_indie_reviews_api_errors.json"

MAX_PAGES     = 1000
NUM_PER_PAGE  = 100
SLEEP_SEC     = 1.2
BATCH_SIZE    = 500  # 리뷰 건수 기준

# ── 체크포인트 ───────────────────────────────────────────────
def load_checkpoint():
    if not CHECKPOINT_PATH.exists():
        return []
    records = []
    with CHECKPOINT_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def append_checkpoint(reviews):
    with CHECKPOINT_PATH.open("a", encoding="utf-8") as f:
        for r in reviews:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_done_appids_file():
    if not DONE_APPIDS_PATH.exists():
        return set()
    return set(json.loads(DONE_APPIDS_PATH.read_text()))


def save_done_appid(appid):
    done = load_done_appids_file()
    done.add(appid)
    DONE_APPIDS_PATH.write_text(json.dumps(list(done)))


def load_api_error_appids():
    if not API_ERROR_PATH.exists():
        return set()
    return set(json.loads(API_ERROR_PATH.read_text()))


def save_api_error_appid(appid):
    errors = load_api_error_appids()
    errors.add(appid)
    API_ERROR_PATH.write_text(json.dumps(list(errors)))


# ── DB ───────────────────────────────────────────────────────
def get_db_done_appids(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT appid FROM steam_indie_reviews")
        return {row[0] for row in cur.fetchall()}


def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS steam_indie_reviews (
                recommendationid               TEXT PRIMARY KEY,
                appid                          BIGINT,
                language                       TEXT,
                review                         TEXT,
                timestamp_created              BIGINT,
                timestamp_updated              BIGINT,
                voted_up                       BOOLEAN,
                votes_up                       BIGINT,
                votes_funny                    BIGINT,
                weighted_vote_score            FLOAT,
                comment_count                  BIGINT,
                steam_purchase                 BOOLEAN,
                received_for_free              BOOLEAN,
                written_during_early_access    BOOLEAN,
                author_steamid                 TEXT,
                author_num_games_owned         BIGINT,
                author_num_reviews             BIGINT,
                author_playtime_forever        BIGINT,
                author_playtime_last_two_weeks BIGINT,
                author_playtime_at_review      BIGINT,
                author_last_played             BIGINT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS steam_indie_review_summary (
                appid                BIGINT PRIMARY KEY,
                review_score         INTEGER,
                review_score_desc    TEXT,
                total_positive       INTEGER,
                total_negative       INTEGER,
                total_reviews        INTEGER,
                collected_at         BIGINT
            )
        """)
    conn.commit()


def flush_to_db(conn, batch):
    if not batch:
        return
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO steam_indie_reviews (
                recommendationid, appid, language, review,
                timestamp_created, timestamp_updated, voted_up,
                votes_up, votes_funny, weighted_vote_score, comment_count,
                steam_purchase, received_for_free, written_during_early_access,
                author_steamid, author_num_games_owned, author_num_reviews,
                author_playtime_forever, author_playtime_last_two_weeks,
                author_playtime_at_review, author_last_played
            ) VALUES (
                %(recommendationid)s, %(appid)s, %(language)s, %(review)s,
                %(timestamp_created)s, %(timestamp_updated)s, %(voted_up)s,
                %(votes_up)s, %(votes_funny)s, %(weighted_vote_score)s, %(comment_count)s,
                %(steam_purchase)s, %(received_for_free)s, %(written_during_early_access)s,
                %(author_steamid)s, %(author_num_games_owned)s, %(author_num_reviews)s,
                %(author_playtime_forever)s, %(author_playtime_last_two_weeks)s,
                %(author_playtime_at_review)s, %(author_last_played)s
            )
            ON CONFLICT (recommendationid) DO NOTHING
        """, batch)
    conn.commit()
    print(f"  [DB] {len(batch)}건 적재 완료")


def flush_summary_to_db(conn, summary):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO steam_indie_review_summary (
                appid, review_score, review_score_desc,
                total_positive, total_negative, total_reviews, collected_at
            ) VALUES (
                %(appid)s, %(review_score)s, %(review_score_desc)s,
                %(total_positive)s, %(total_negative)s, %(total_reviews)s, %(collected_at)s
            )
            ON CONFLICT (appid) DO UPDATE SET
                review_score      = EXCLUDED.review_score,
                review_score_desc = EXCLUDED.review_score_desc,
                total_positive    = EXCLUDED.total_positive,
                total_negative    = EXCLUDED.total_negative,
                total_reviews     = EXCLUDED.total_reviews,
                collected_at      = EXCLUDED.collected_at
        """, summary)
    conn.commit()


# ── 데이터 로드 ──────────────────────────────────────────────
df = pd.read_csv(SAMPLE_PATH)
df['release_date'] = pd.to_datetime(df['release_date'], errors='coerce')
targets = df.reset_index(drop=True)
print(f"수집 대상: {len(targets)}개 게임")


# ── Steam Review API 호출 함수 ───────────────────────────────
def fetch_reviews_page(appid, cursor="*"):
    url = f"https://store.steampowered.com/appreviews/{appid}"
    params = {
        "json":                    1,
        "filter":                  "recent",
        "language":                "all",
        "num_per_page":            NUM_PER_PAGE,
        "cursor":                  cursor,
        "purchase_type":           "steam",
        "filter_offtopic_activity": 1,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [오류] appid={appid} cursor={cursor} : {e}")
        return None


# ── 게임 1개 수집 (리뷰 레코드 + query_summary 반환) ────────
def collect_game(appid, max_pages=MAX_PAGES):
    collected      = []
    query_summary  = None
    cursor         = "*"
    stopped_reason = "max_pages"

    for page in range(max_pages):
        data = fetch_reviews_page(appid, cursor)
        time.sleep(SLEEP_SEC)

        if not data or data.get("success") != 1:
            stopped_reason = "api_error"
            break

        # 첫 페이지에서 query_summary 저장
        if query_summary is None:
            qs = data.get("query_summary", {})
            query_summary = {
                "appid":             appid,
                "review_score":      qs.get("review_score"),
                "review_score_desc": qs.get("review_score_desc"),
                "total_positive":    qs.get("total_positive"),
                "total_negative":    qs.get("total_negative"),
                "total_reviews":     qs.get("total_reviews"),
                "collected_at":      int(time.time()),
            }

        reviews = data.get("reviews", [])
        if not reviews:
            stopped_reason = "no_more_reviews"
            break

        for review in reviews:
            ts     = review.get("timestamp_created", 0)
            author = review.get("author", {})
            collected.append({
                "recommendationid":              review.get("recommendationid"),
                "appid":                         appid,
                "language":                      review.get("language"),
                "review":                        review.get("review"),
                "timestamp_created":             ts,
                "timestamp_updated":             review.get("timestamp_updated"),
                "voted_up":                      review.get("voted_up"),
                "votes_up":                      review.get("votes_up"),
                "votes_funny":                   review.get("votes_funny"),
                "weighted_vote_score":           review.get("weighted_vote_score"),
                "comment_count":                 review.get("comment_count"),
                "steam_purchase":                review.get("steam_purchase"),
                "received_for_free":             review.get("received_for_free"),
                "written_during_early_access":   review.get("written_during_early_access"),
                "author_steamid":                author.get("steamid"),
                "author_num_games_owned":        author.get("num_games_owned"),
                "author_num_reviews":            author.get("num_reviews"),
                "author_playtime_forever":       author.get("playtime_forever"),
                "author_playtime_last_two_weeks": author.get("playtime_last_two_weeks"),
                "author_playtime_at_review":     author.get("playtime_at_review"),
                "author_last_played":            author.get("last_played"),
            })

        next_cursor = data.get("cursor", "")
        if not next_cursor or next_cursor == cursor:
            stopped_reason = "cursor_exhausted"
            break
        cursor = next_cursor

    return collected, query_summary, stopped_reason, page + 1


# ── 메인 수집 루프 ────────────────────────────────────────────
conn = get_connection()
ensure_table(conn)

# 체크포인트 미적재분 DB flush (ON CONFLICT DO NOTHING으로 중복 무시)
checkpoint_records = load_checkpoint()
if checkpoint_records:
    print(f"[재개] 체크포인트 {len(checkpoint_records)}건 DB flush 중...")
    flush_to_db(conn, checkpoint_records)

api_error_appids = load_api_error_appids()
done_appids = (get_db_done_appids(conn) | load_done_appids_file()) - api_error_appids
if done_appids:
    print(f"[재개] 이미 수집된 게임 {len(done_appids)}개 스킵")
if api_error_appids:
    print(f"[재시도] 이전 api_error 게임 {len(api_error_appids)}개 재수집")

all_reviews = []
batch       = []

for i, row in targets.iterrows():
    appid        = row['appid']
    name         = row['name']
    release_date = row['release_date']

    if pd.isna(release_date):
        print(f"[{i+1}/{len(targets)}] {name} — 출시일 없음, 스킵")
        continue

    if appid in done_appids:
        print(f"[{i+1}/{len(targets)}] {name} — 이미 수집됨, 스킵")
        continue

    # 리뷰 수에 따른 동적 페이지 제한 (최소 MAX_PAGES, 최대는 리뷰 수의 120% 수준)
    total_reviews = int(row['total_reviews']) if not pd.isna(row['total_reviews']) else 0
    dynamic_max_pages = max(MAX_PAGES, int(total_reviews / 100 * 1.2) + 50)

    print(f"[{i+1}/{len(targets)}] {name} (appid={appid}, 출시={release_date.date()}, 총리뷰={total_reviews:,}) 수집 중...")
    print(f"  * 동적 페이지 제한: {dynamic_max_pages} 페이지")

    reviews, query_summary, stopped_reason, pages = collect_game(appid, max_pages=dynamic_max_pages)

    append_checkpoint(reviews)
    if stopped_reason == "api_error":
        save_api_error_appid(appid)
    else:
        save_done_appid(appid)
    if query_summary:
        flush_summary_to_db(conn, query_summary)
    all_reviews.extend(reviews)
    batch.extend(reviews)

    print(f"  → 초기 리뷰: {len(reviews)}건 | 중단사유: {stopped_reason} | 페이지: {pages}")

    if len(batch) >= BATCH_SIZE:
        flush_to_db(conn, batch)
        batch.clear()

# 남은 배치 처리
if batch:
    flush_to_db(conn, batch)

conn.close()

# 정상 완료 시 임시 파일 삭제
for path in (CHECKPOINT_PATH, DONE_APPIDS_PATH, API_ERROR_PATH):
    if path.exists():
        path.unlink()
print("[완료] 임시 파일 삭제")

# ── CSV 저장 ─────────────────────────────────────────────────
if all_reviews:
    pd.DataFrame(all_reviews).to_csv(OUTPUT_PATH, index=False)
    print(f"\n수집 완료 → {OUTPUT_PATH} ({len(all_reviews)}건)")
else:
    print("\n수집 완료 (신규 데이터 없음)")
