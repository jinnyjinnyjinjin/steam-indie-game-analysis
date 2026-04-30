import pandas as pd
import requests
import time
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
from utils.db import get_connection


def ts_to_date(ts):
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d') if ts else None

def normalize_db_date(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped.lower() == "nat":
            return None
        return stripped
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            return value
    return value


# ── 설정 ────────────────────────────────────────────────────
_ROOT = Path(__file__).parents[3]

if len(sys.argv) < 2:
    print("usage: python collect_steam_indie_stratified_histogram.py <sample_csv_path>")
    sys.exit(1)

SAMPLE_PATH = Path(sys.argv[1])
if not SAMPLE_PATH.is_absolute():
    SAMPLE_PATH = _ROOT / SAMPLE_PATH

OUTPUT_PATH = _ROOT / "data/raw/steam_origin_indie_review_histogram.csv"
LOG_PATH    = _ROOT / "data/logs/steam_indie_collection_log_histogram.json"

SLEEP_SEC        = 1.2
BATCH_SIZE       = 300  # 행 단위
DONE_APPIDS_PATH = _ROOT / "data/logs/steam_indie_histogram_done.json"


def load_done_appids():
    if not DONE_APPIDS_PATH.exists():
        return set()
    return set(json.loads(DONE_APPIDS_PATH.read_text()))


def save_done_appid(appid):
    done = load_done_appids()
    done.add(appid)
    DONE_APPIDS_PATH.write_text(json.dumps(list(done)))


# ── DB ───────────────────────────────────────────────────────
def get_db_done_appids(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT appid FROM steam_indie_review_histogram")
        return {row[0] for row in cur.fetchall()}


def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS steam_indie_review_histogram (
                appid                BIGINT,
                name                 TEXT,
                stratum              TEXT,
                release_date         DATE,
                hist_start_date      DATE,
                hist_end_date        DATE,
                date                 DATE,
                recommendations_up   INTEGER,
                recommendations_down INTEGER,
                data_type            TEXT,
                PRIMARY KEY (appid, date, data_type)
            )
        """)
    conn.commit()


def flush_to_db(conn, batch):
    if not batch:
        return
    normalized_batch = []
    for row in batch:
        normalized_row = dict(row)
        normalized_row["release_date"] = normalize_db_date(normalized_row.get("release_date"))
        normalized_row["hist_start_date"] = normalize_db_date(normalized_row.get("hist_start_date"))
        normalized_row["hist_end_date"] = normalize_db_date(normalized_row.get("hist_end_date"))
        normalized_row["date"] = normalize_db_date(normalized_row.get("date"))
        normalized_batch.append(normalized_row)
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO steam_indie_review_histogram (
                appid, name, stratum, release_date,
                hist_start_date, hist_end_date,
                date, recommendations_up, recommendations_down, data_type
            ) VALUES (
                %(appid)s, %(name)s, %(stratum)s, %(release_date)s,
                %(hist_start_date)s, %(hist_end_date)s,
                %(date)s, %(recommendations_up)s, %(recommendations_down)s, %(data_type)s
            )
            ON CONFLICT (appid, date, data_type) DO NOTHING
        """, normalized_batch)
    conn.commit()
    print(f"  [DB] {len(batch)}행 적재 완료")


# ── appreviewhistogram API 호출 함수 ─────────────────────────
def fetch_histogram(appid):
    url = f"https://store.steampowered.com/appreviewhistogram/{appid}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [오류] appid={appid} : {e}")
        return None


# ── 데이터 로드 ──────────────────────────────────────────────
df = pd.read_csv(SAMPLE_PATH)
df['release_date'] = pd.to_datetime(df['release_date'], errors='coerce')
targets = df.reset_index(drop=True)

print(f"수집 대상: {len(targets)}개 게임")
print(targets['stratum'].value_counts().sort_index())
print()

# ── 메인 수집 루프 ────────────────────────────────────────────
conn = get_connection()
ensure_table(conn)

done_appids = get_db_done_appids(conn) | load_done_appids()
if done_appids:
    print(f"[재개] 이미 수집된 게임 {len(done_appids)}개 스킵\n")

all_rows = []
batch    = []
log      = []

for i, row in targets.iterrows():
    appid        = row['appid']
    name         = row['name']
    release_date = row['release_date']
    stratum      = row['stratum']

    if appid in done_appids:
        print(f"[{i+1}/{len(targets)}] {name} — 이미 수집됨, 스킵")
        continue

    print(f"[{i+1}/{len(targets)}] {name} (appid={appid}, 층={stratum}) 수집 중...")

    data = fetch_histogram(appid)
    time.sleep(SLEEP_SEC)

    if not data or data.get("success") != 1:
        print(f"  [실패] 데이터 없음")
        log.append({"appid": appid, "name": name, "status": "failed"})
        continue

    save_done_appid(appid)

    results    = data.get("results", {})
    rollups    = results.get("rollups", [])
    recent     = results.get("recent",  [])
    start_date = ts_to_date(results.get("start_date"))
    end_date   = ts_to_date(results.get("end_date"))

    rows = []
    for entry in rollups:
        rows.append({
            "appid":                appid,
            "name":                 name,
            "stratum":              stratum,
            "release_date":         release_date.date(),
            "hist_start_date":      start_date,
            "hist_end_date":        end_date,
            "date":                 ts_to_date(entry.get("date")),
            "recommendations_up":   entry.get("recommendations_up", 0),
            "recommendations_down": entry.get("recommendations_down", 0),
            "data_type":            "rollups",
        })

    for entry in recent:
        rows.append({
            "appid":                appid,
            "name":                 name,
            "stratum":              stratum,
            "release_date":         release_date.date(),
            "hist_start_date":      start_date,
            "hist_end_date":        end_date,
            "date":                 ts_to_date(entry.get("date")),
            "recommendations_up":   entry.get("recommendations_up", 0),
            "recommendations_down": entry.get("recommendations_down", 0),
            "data_type":            "recent",
        })

    all_rows.extend(rows)
    batch.extend(rows)

    rollup_months = len(rollups)
    recent_days   = len(recent)
    total_up      = sum(r.get("recommendations_up",   0) for r in rollups)
    total_down    = sum(r.get("recommendations_down", 0) for r in rollups)

    print(f"  → rollups: {rollup_months}개월  recent: {recent_days}일  "
          f"긍정: {total_up:,}  부정: {total_down:,}")

    log.append({
        "appid":         appid,
        "name":          name,
        "stratum":       stratum,
        "status":        "success",
        "rollup_months": rollup_months,
        "recent_days":   recent_days,
        "total_up":      total_up,
        "total_down":    total_down,
    })

    if len(batch) >= BATCH_SIZE:
        flush_to_db(conn, batch)
        batch.clear()

# 남은 배치 처리
if batch:
    flush_to_db(conn, batch)

conn.close()

# ── CSV / 로그 저장 ──────────────────────────────────────────
df_result = pd.DataFrame(all_rows)
df_result.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
Path(LOG_PATH).write_text(json.dumps(log, ensure_ascii=False, indent=2))

print(f"\n수집 완료 → {OUTPUT_PATH}")
print(f"로그 저장 → {LOG_PATH}")
print(f"\n총 행 수: {len(df_result):,}개")
print(f"성공: {sum(1 for l in log if l['status'] == 'success')}개  "
      f"실패: {sum(1 for l in log if l['status'] == 'failed')}개")
if df_result.empty:
    print("\\n수집된 신규 데이터가 없어 분포를 출력하지 않습니다.")
else:
    print(f"\\n=== data_type 분포 ===")
    print(df_result['data_type'].value_counts())
    print(f"\\n=== 층별 수집 게임 수 ===")
    print(df_result.groupby('stratum')['appid'].nunique())
