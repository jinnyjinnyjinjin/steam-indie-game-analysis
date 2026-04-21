import pandas as pd
import requests
import time
import json
from pathlib import Path

# ── 설정 ────────────────────────────────────────────────────
_ROOT         = Path(__file__).parents[3]
SAMPLE_PATH   = _ROOT / "data/processed/steam_stratified_sample.csv"
OUTPUT_PATH   = _ROOT / "data/processed/steam_indie_review_histogram.csv"
LOG_PATH      = _ROOT / "data/raw/steam_indie_collection_log_histogram.json"

TARGET_STRATA = ['large_high', 'mid_high', 'small_high']
SLEEP_SEC     = 1.2   # 호출 간격 (rate limit 대응)

# ── 데이터 로드 ──────────────────────────────────────────────
df = pd.read_csv(SAMPLE_PATH)
df['release_date'] = pd.to_datetime(df['release_date'], errors='coerce')
targets = df[df['stratum'].isin(TARGET_STRATA)].reset_index(drop=True)

print(f"수집 대상: {len(targets)}개 게임")
print(targets['stratum'].value_counts().sort_index())
print()

# ── appreviewhistogram API 호출 함수 ─────────────────────────
def fetch_histogram(appid):
    """
    https://store.steampowered.com/appreviewhistogram/{appid}
    반환 구조:
      results.rollups  : 월별 집계 (전체 기간)
      results.recent   : 일별 집계 (최근 30일)
    """
    url = f"https://store.steampowered.com/appreviewhistogram/{appid}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [오류] appid={appid} : {e}")
        return None

# ── 메인 수집 루프 ────────────────────────────────────────────
all_rows = []   # CSV 저장용 (행 단위)
log      = []   # JSON 로그용 (게임 단위)

for i, row in targets.iterrows():
    appid        = row['appid']
    name         = row['name_store']
    release_date = row['release_date']
    stratum      = row['stratum']

    print(f"[{i+1}/{len(targets)}] {name} (appid={appid}, 층={stratum}) 수집 중...")

    data = fetch_histogram(appid)
    time.sleep(SLEEP_SEC)

    if not data or data.get("success") != 1:
        print(f"  [실패] 데이터 없음")
        log.append({"appid": appid, "name": name, "status": "failed"})
        continue

    results  = data.get("results", {})
    rollups  = results.get("rollups", [])   # 월별
    recent   = results.get("recent",  [])   # 일별 (최근 30일)

    # rollups 행 저장
    for entry in rollups:
        all_rows.append({
            "appid":                appid,
            "name":                 name,
            "stratum":              stratum,
            "release_date":         release_date.date(),
            "date":                 entry.get("date"),
            "recommendations_up":   entry.get("recommendations_up", 0),
            "recommendations_down": entry.get("recommendations_down", 0),
            "rollup_type":          "month",
            "data_type":            "rollups",
        })

    # recent 행 저장
    for entry in recent:
        all_rows.append({
            "appid":                appid,
            "name":                 name,
            "stratum":              stratum,
            "release_date":         release_date.date(),
            "date":                 entry.get("date"),
            "recommendations_up":   entry.get("recommendations_up", 0),
            "recommendations_down": entry.get("recommendations_down", 0),
            "rollup_type":          "day",
            "data_type":            "recent",
        })

    rollup_months = len(rollups)
    recent_days   = len(recent)
    total_up      = sum(r.get("recommendations_up",   0) for r in rollups)
    total_down    = sum(r.get("recommendations_down", 0) for r in rollups)

    print(f"  → rollups: {rollup_months}개월  recent: {recent_days}일  "
          f"전체 긍정: {total_up:,}  전체 부정: {total_down:,}")

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

# ── 저장 ─────────────────────────────────────────────────────
df_result = pd.DataFrame(all_rows)
df_result.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
Path(LOG_PATH).write_text(json.dumps(log, ensure_ascii=False, indent=2))

print(f"\n수집 완료 → {OUTPUT_PATH}")
print(f"로그 저장 → {LOG_PATH}")
print(f"\n총 행 수: {len(df_result):,}개")
print(f"성공: {sum(1 for l in log if l['status']=='success')}개  "
      f"실패: {sum(1 for l in log if l['status']=='failed')}개")
print(f"\n=== data_type 분포 ===")
print(df_result['data_type'].value_counts())
print(f"\n=== 층별 수집 게임 수 ===")
print(df_result.groupby('stratum')['appid'].nunique())
