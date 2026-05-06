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
import random
import json
import pandas as pd
from datetime import datetime
import argparse

# --- 설정 ---
# 기본 입력 파일: 전처리 완료된 전체 모집단
DEFAULT_INPUT = os.path.join(PROJECT_ROOT, "data/preprocessed/steam_indie_games.csv")
# 수집 완료된 appid를 기록할 JSON 로그 파일
CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, "data/logs/collect_tags_checkpoint.json")
BATCH_SIZE = 20
SLEEP_SEC = 1.2  # SteamSpy API 속도 제한
MAX_RETRIES = 5
BACKOFF_BASE_SEC = 1.5
BACKOFF_JITTER_SEC = 0.7

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
    # 기존에 PK 없이 생성된 테이블에서도 ON CONFLICT (appid)가 동작하도록 보정한다.
    # CREATE TABLE IF NOT EXISTS는 이미 존재하는 테이블의 제약조건을 변경하지 않는다.
    try:
        cursor.execute("""
            ALTER TABLE steam_indie_tags
            ALTER COLUMN appid SET NOT NULL
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS steam_indie_tags_appid_uidx
            ON steam_indie_tags (appid)
        """)
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise RuntimeError(
            "steam_indie_tags.appid에 unique index를 만들 수 없습니다. "
            "기존 테이블에 appid 중복 또는 NULL 값이 있는지 확인하세요."
        ) from e

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


def fetch_steamspy_data(appid, max_retries=MAX_RETRIES):
    """SteamSpy API 호출 (비JSON 응답/일시 오류 재시도 포함)"""
    url = f"https://steamspy.com/api.php?request=appdetails&appid={appid}"

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, timeout=15)
            content_type = resp.headers.get("Content-Type", "").lower()
            body_text = (resp.text or "").strip()

            if resp.status_code != 200:
                raise requests.HTTPError(f"HTTP {resp.status_code}")

            if "application/json" in content_type:
                try:
                    return resp.json()
                except ValueError:
                    # Content-Type이 JSON이어도 깨진 응답이 올 수 있어 아래 재시도 로직으로 처리
                    pass

            preview = body_text.replace("\n", " ")[:120] if body_text else "<empty>"
            is_too_many_connections = "too many connections" in body_text.lower()

            if attempt < max_retries:
                wait_sec = BACKOFF_BASE_SEC * attempt + random.uniform(
                    0, BACKOFF_JITTER_SEC
                )
                reason = (
                    "SteamSpy 과부하 응답"
                    if is_too_many_connections
                    else "비JSON/비정상 응답"
                )
                print(
                    f"\n[Warn] {appid} {reason} (시도 {attempt}/{max_retries}, "
                    f"Content-Type: {content_type or 'N/A'}, Body: {preview}) "
                    f"-> {wait_sec:.1f}초 후 재시도"
                )
                time.sleep(wait_sec)
                continue

            print(
                f"\n[Error] {appid} 호출 실패: 비정상 응답 지속 "
                f"(Content-Type: {content_type or 'N/A'}, Body: {preview})"
            )
            return None

        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                wait_sec = BACKOFF_BASE_SEC * attempt + random.uniform(
                    0, BACKOFF_JITTER_SEC
                )
                print(
                    f"\n[Warn] {appid} 요청 실패 (시도 {attempt}/{max_retries}): {e} "
                    f"-> {wait_sec:.1f}초 후 재시도"
                )
                time.sleep(wait_sec)
                continue
            print(f"\n[Error] {appid} 호출 실패: {e}")
            return None

    return None


def main():
    # 1. 실행 인자 처리
    parser = argparse.ArgumentParser(description="SteamSpy Tags Collector (PostgreSQL)")
    parser.add_argument(
        "--input", type=str, default=DEFAULT_INPUT, help="입력 CSV 경로"
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

    all_appids = df_raw["appid"].unique().tolist()

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
    print(f"입력 파일 : {args.input}")
    print(f"전체 대상 : {len(all_appids):,}개")
    print(f"기존 수집  : {len(collected):,}개")
    print(f"신규 수집  : {len(to_collect):,}개")
    print(f"==============================")

    batch_data = []
    success_batch_ids = []

    # PostgreSQL 용 쿼리 (ON CONFLICT 구문 사용)
    query = """
        INSERT INTO steam_indie_tags 
        (appid, name, developer, publisher, owners, positive, negative, price, tags)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    json.dumps(data.get("tags", {}), ensure_ascii=False)
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
