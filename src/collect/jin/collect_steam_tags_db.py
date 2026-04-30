import sys
import os

# src 디렉토리를 path에 추가하여 src.utils.db 임포트 가능하게 함
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.db import get_connection
import requests
import time
import json
import pandas as pd
from datetime import datetime
import argparse

# --- 설정 ---
# 기본 입력 파일: 층화 추출된 샘플 파일
DEFAULT_INPUT = os.path.join(PROJECT_ROOT, "data/preprocessed/steam_indie_genre_stratified_sample.csv")
# 수집 완료된 appid를 기록할 JSON 로그 파일
CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, "data/logs/collect_tags_checkpoint.json")
BATCH_SIZE = 20
SLEEP_SEC = 1.2  # SteamSpy API 속도 제한

def init_db():
    """데이터베이스 및 테이블 초기화 (PostgreSQL)"""
    conn = get_connection()
    cursor = conn.cursor()
    # PostgreSQL에서는 JSONB 타입을 사용하여 태그를 효율적으로 저장 가능
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS steam_indie_tags (
            appid INTEGER PRIMARY KEY,
            name TEXT,
            developer TEXT,
            publisher TEXT,
            owners TEXT,
            positive INTEGER,
            negative INTEGER,
            price INTEGER,
            tags JSONB
        )
    """)
    conn.commit()
    cursor.close()
    return conn


def load_checkpoint():
    """JSON 로그 파일에서 이미 수집된 appid 목록 로드"""
    if os.path.exists(CHECKPOINT_PATH):
        try:
            with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_checkpoint(collected_set):
    """수집 완료된 목록을 JSON 로그 파일에 업데이트"""
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(list(collected_set), f, indent=4)


def fetch_steamspy_data(appid):
    """SteamSpy API 호출"""
    url = f"https://steamspy.com/api.php?request=appdetails&appid={appid}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"\n[Error] {appid} 호출 실패: {e}")
    return None


def main():
    # 1. 실행 인자 처리
    parser = argparse.ArgumentParser(description="SteamSpy Tags Collector (PostgreSQL)")
    parser.add_argument(
        "--input", type=str, default=DEFAULT_INPUT, help="입력 CSV 경로"
    )
    parser.add_argument(
        "--strata",
        nargs="+",
        default=["large_high", "mid_high", "small_high"],
        help="수집할 계층 지정 (예: large_high mid_high). 전체 수집 시 'all' 입력",
    )
    args = parser.parse_args()

    # 2. 수집 대상 로드
    if not os.path.exists(args.input):
        print(f"Error: 입력 파일이 없습니다. ({args.input})")
        return

    df_raw = pd.read_csv(args.input)
    if "appid" not in df_raw.columns:
        print("Error: 입력 CSV에 'appid' 컬럼이 없습니다.")
        return

    # 계층 필터링 로직
    if "all" not in args.strata:
        if "stratum" not in df_raw.columns:
            print("Error: 필터링을 위한 'stratum' 컬럼이 CSV에 없습니다. 전체 수집을 위해 --strata all 을 사용하세요.")
            return
        df_filtered = df_raw[df_raw["stratum"].isin(args.strata)]
        all_appids = df_filtered["appid"].unique().tolist()
        strata_info = ", ".join(args.strata)
    else:
        all_appids = df_raw["appid"].unique().tolist()
        strata_info = "전체 (All)"

    # 3. 체크포인트 로드 (JSON 로그 확인)
    collected = load_checkpoint()
    to_collect = [aid for aid in all_appids if int(aid) not in collected]

    # 4. DB 연결
    try:
        conn = init_db()
    except Exception as e:
        print(f"Database 연결 실패: {e}")
        return

    print(f"=== SteamSpy 태그 수집 시작 (PostgreSQL) ===")
    print(f"입력 파일: {args.input}")
    print(f"전체 대상: {len(all_appids):,}개")
    print(f"기존 수집(로그 기준): {len(collected):,}개")
    print(f"신규 수집 대상: {len(to_collect):,}개")
    print(f"==============================")

    batch_data = []
    success_batch_ids = []

    # PostgreSQL 용 쿼리 (ON CONFLICT 구문 사용)
    query = """
        INSERT INTO steam_indie_tags 
        (appid, name, developer, publisher, owners, positive, negative, price, tags, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (appid) DO UPDATE SET
        name = EXCLUDED.name,
        developer = EXCLUDED.developer,
        publisher = EXCLUDED.publisher,
        owners = EXCLUDED.owners,
        positive = EXCLUDED.positive,
        negative = EXCLUDED.negative,
        price = EXCLUDED.price,
        tags = EXCLUDED.tags
    """

    try:
        for i, appid in enumerate(to_collect):
            data = fetch_steamspy_data(appid)

            if data and data.get("name"):
                row = (
                    data.get("appid"),
                    data.get("name"),
                    data.get("developer"),
                    data.get("publisher"),
                    data.get("owners"),
                    data.get("positive"),
                    data.get("negative"),
                    data.get("price"),
                    json.dumps(data.get("tags", {}), ensure_ascii=False),
                    datetime.now(),
                )
                batch_data.append(row)
                success_batch_ids.append(int(appid))
                print(
                    f"[{i + 1}/{len(to_collect)}] {str(data.get('name'))[:25]:<25} | Tags: {len(data.get('tags', {}))}",
                    end="\r",
                )
            else:
                print(f"\n[{i + 1}/{len(to_collect)}] AppID {appid} 데이터 수집 실패")

            # 배치 완료 시 DB 저장 및 JSON 체크포인트 업데이트
            if len(batch_data) >= BATCH_SIZE:
                cursor = conn.cursor()
                cursor.executemany(query, batch_data)
                conn.commit()
                cursor.close()

                # 체크포인트 파일 업데이트
                collected.update(success_batch_ids)
                save_checkpoint(collected)

                print(
                    f"\n>>> {len(batch_data)}개 배치 저장 및 로그 업데이트 완료 (누적: {len(collected)})"
                )
                batch_data = []
                success_batch_ids = []

            time.sleep(SLEEP_SEC)

    except KeyboardInterrupt:
        print("\n\n[Interrupt] 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n\n[Fatal Error] {e}")
    finally:
        # 마지막 남은 데이터 최종 저장
        if batch_data:
            cursor = conn.cursor()
            cursor.executemany(query, batch_data)
            conn.commit()
            cursor.close()
            collected.update(success_batch_ids)
            save_checkpoint(collected)
            print(f"\n마지막 {len(batch_data)}개 데이터 저장 및 로그 업데이트 완료.")

        conn.close()
        print(f"=== 수집 종료 (총 기록된 appid: {len(collected)}개) ===")


if __name__ == "__main__":
    main()
