"""
첫 반응군 층화 샘플(steam_indie_first_response_sample.csv) 게임의
리뷰를 Steam Review API로 수집하여 CSV로 저장한다.

usage:
    python src/collect/jin/collect_first_response_reviews.py
"""
import json
import time
from pathlib import Path

import pandas as pd
import requests

_ROOT       = Path(__file__).parents[3]
SAMPLE_PATH = _ROOT / "data/preprocessed/steam_indie_first_response_sample.csv"
OUTPUT_PATH = _ROOT / "data/preprocessed/steam_indie_first_response_reviews.csv"
DONE_PATH   = _ROOT / "data/logs/first_response_reviews_done.json"

NUM_PER_PAGE = 100
SLEEP_SEC    = 1.2


def load_done() -> set:
    if not DONE_PATH.exists():
        return set()
    return set(json.loads(DONE_PATH.read_text()))


def save_done(done: set):
    DONE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DONE_PATH.write_text(json.dumps(list(done)))


def fetch_page(appid: int, cursor: str = "*") -> dict | None:
    url = f"https://store.steampowered.com/appreviews/{appid}"
    params = {
        "json": 1,
        "filter": "recent",
        "language": "all",
        "num_per_page": NUM_PER_PAGE,
        "cursor": cursor,
        "purchase_type": "steam",
        "filter_offtopic_activity": 1,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [오류] appid={appid}: {e}")
        return None


def collect_game(appid: int) -> list[dict]:
    collected = []
    cursor = "*"

    for _ in range(50):  # 첫 반응군은 최대 49개이므로 페이지 1~2로 충분
        data = fetch_page(appid, cursor)
        time.sleep(SLEEP_SEC)

        if not data or data.get("success") != 1:
            break

        reviews = data.get("reviews", [])
        if not reviews:
            break

        for r in reviews:
            author = r.get("author", {})
            collected.append({
                "recommendationid":            r.get("recommendationid"),
                "appid":                       appid,
                "language":                    r.get("language"),
                "review":                      r.get("review"),
                "timestamp_created":           r.get("timestamp_created"),
                "timestamp_updated":           r.get("timestamp_updated"),
                "voted_up":                    r.get("voted_up"),
                "votes_up":                    r.get("votes_up"),
                "votes_funny":                 r.get("votes_funny"),
                "weighted_vote_score":         r.get("weighted_vote_score"),
                "comment_count":               r.get("comment_count"),
                "steam_purchase":              r.get("steam_purchase"),
                "received_for_free":           r.get("received_for_free"),
                "written_during_early_access": r.get("written_during_early_access"),
                "author_steamid":              author.get("steamid"),
                "author_num_games_owned":      author.get("num_games_owned"),
                "author_num_reviews":          author.get("num_reviews"),
                "author_last_played":          author.get("last_played"),
                "playtime_forever_hours":      round(author.get("playtime_forever", 0) / 60, 4),
                "playtime_at_review_hours":    round(author.get("playtime_at_review", 0) / 60, 4),
            })

        next_cursor = data.get("cursor", "")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor

    return collected


def main():
    sample = pd.read_csv(SAMPLE_PATH)
    done   = load_done()
    all_reviews: list[dict] = []

    # 이미 수집된 것은 기존 파일에서 로드
    if OUTPUT_PATH.exists() and done:
        existing = pd.read_csv(OUTPUT_PATH)
        all_reviews = existing.to_dict("records")
        print(f"[재개] 기존 수집 {len(all_reviews)}건 로드, {len(done)}개 게임 스킵")

    targets = sample[~sample["appid"].isin(done)]
    print(f"수집 대상: {len(targets)}개 게임 (전체 {len(sample)}개 중)\n")

    for i, (_, row) in enumerate(targets.iterrows(), 1):
        appid = int(row["appid"])
        name  = row["name"]
        total = int(row["total_reviews"])

        print(f"[{i}/{len(targets)}] {name} (appid={appid}, 총리뷰={total}) 수집 중...")
        reviews = collect_game(appid)
        all_reviews.extend(reviews)
        done.add(appid)
        save_done(done)

        print(f"  → {len(reviews)}건 수집")

        # 50게임마다 중간 저장
        if i % 50 == 0:
            pd.DataFrame(all_reviews).to_csv(OUTPUT_PATH, index=False)
            print(f"  [중간저장] {len(all_reviews)}건")

    pd.DataFrame(all_reviews).to_csv(OUTPUT_PATH, index=False)
    print(f"\n수집 완료 → {OUTPUT_PATH}")
    print(f"총 {len(all_reviews)}건 ({sample['appid'].nunique()}개 게임)")


if __name__ == "__main__":
    main()
