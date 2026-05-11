import ast
import json
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "preprocessed"

PRICE_BINS = [0, 5, 10, 15, 20, 30, 9999]
PRICE_LABELS = ["~$5", "$5~10", "$10~15", "$15~20", "$20~30", "$30+"]

# 언어 지원 구간별 무반응 비율 (분석 결과 통계치)
LANGUAGE_SILENCE_RATE = {
    "1개 (영어 단독)": 0.567,
    "2~4개": 0.431,
    "5개 이상": 0.366,
}


def _parse_genres(value: str) -> list[str]:
    try:
        genres = ast.literal_eval(value)
        return [g for g in genres if g != "Indie"]
    except Exception:
        return []


def _parse_tags(value: str) -> list[str]:
    try:
        return list(json.loads(value).keys())
    except Exception:
        return []


def _assign_price_tier(series: pd.Series) -> pd.Series:
    return pd.cut(series, bins=PRICE_BINS, labels=PRICE_LABELS, right=True)


@st.cache_data
def load_combined() -> pd.DataFrame:
    """반응군 + 무반응군 합산 데이터프레임 반환."""
    reaction = pd.read_csv(DATA_DIR / "steam_indie_games.csv")
    silence = pd.read_csv(DATA_DIR / "steam_indie_games_silence.csv")

    reaction["group"] = "reaction"
    silence["group"] = "silence"

    df = pd.concat([reaction, silence], ignore_index=True)
    df["positive_rate"] = df["positive"] / df["total_reviews"].replace(0, 1)
    df["price_tier"] = _assign_price_tier(df["price"])
    return df


@st.cache_data
def load_reaction() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "steam_indie_games.csv")
    df["positive_rate"] = df["positive"] / df["total_reviews"].replace(0, 1)
    df["price_tier"] = _assign_price_tier(df["price"])
    return df


@st.cache_data
def get_genre_silence_rates() -> dict[str, float]:
    """장르별 실제 무반응 비율."""
    df = load_combined()
    rates = {}
    for row in df.itertuples():
        for genre in _parse_genres(row.genres):
            if genre not in rates:
                rates[genre] = {"silence": 0, "total": 0}
            rates[genre]["total"] += 1
            if row.group == "silence":
                rates[genre]["silence"] += 1
    return {
        g: v["silence"] / v["total"]
        for g, v in rates.items()
        if v["total"] >= 30
    }


@st.cache_data
def get_price_tier_silence_rates() -> dict[str, float]:
    """가격대별 실제 무반응 비율."""
    df = load_combined()
    stats = df.groupby("price_tier", observed=True).apply(
        lambda x: (x["group"] == "silence").sum() / len(x)
    )
    return stats.to_dict()


@st.cache_data
def get_tag_silence_rates() -> dict[str, float]:
    """태그별 무반응 비율 (등장 횟수 30회 이상)."""
    df = load_combined()
    tag_stats: dict[str, dict] = {}
    for row in df.itertuples():
        for tag in _parse_tags(row.tags):
            if tag not in tag_stats:
                tag_stats[tag] = {"silence": 0, "total": 0}
            tag_stats[tag]["total"] += 1
            if row.group == "silence":
                tag_stats[tag]["silence"] += 1
    return {
        t: v["silence"] / v["total"]
        for t, v in tag_stats.items()
        if v["total"] >= 30
    }


@st.cache_data
def get_all_genres() -> list[str]:
    df = load_combined()
    genres: set[str] = set()
    for val in df["genres"].dropna():
        genres.update(_parse_genres(val))
    return sorted(genres)


@st.cache_data
def get_top_tags(top_n: int = 80) -> list[str]:
    df = load_combined()
    counter: Counter = Counter()
    for val in df["tags"].dropna():
        counter.update(_parse_tags(val))
    # Indie 태그 제외
    return [t for t, _ in counter.most_common(top_n + 1) if t != "Indie"][:top_n]


def _genre_overlap_score(game_genres_str: str, selected_genres: list[str]) -> float:
    """선택 장르 중 몇 개가 겹치는지 비율 반환 (0~1)."""
    if not selected_genres:
        return 0.0
    game_genres = set(_parse_genres(game_genres_str))
    matched = len(game_genres & set(selected_genres))
    return matched / len(selected_genres)


def _tag_overlap_score(game_tags_str: str, selected_tags: list[str]) -> float:
    """선택 태그 중 몇 개가 겹치는지 비율 반환 (0~1)."""
    if not selected_tags:
        return 0.0
    game_tags = set(_parse_tags(game_tags_str))
    matched = len(game_tags & set(selected_tags))
    return matched / len(selected_tags)


def _price_proximity_score(game_price: float, input_price: float) -> float:
    """가격 근접도 점수 (0~1). $3 이내 1.0, $15 초과 0.0으로 선형 감소."""
    diff = abs(game_price - input_price)
    return max(0.0, 1.0 - diff / 15.0)


@st.cache_data
def get_similar_games(
    genres: list[str],
    tags: list[str],
    price: float,
    top_n: int = 5,
) -> pd.DataFrame:
    """장르 일치 + 태그 유사도(40%) + 가격 근접도(30%) + 장르 겹침(30%) 복합 점수로 유사 게임 선별."""
    df = load_reaction()
    if not genres:
        return pd.DataFrame()

    # 1단계: 장르 최소 1개 일치 필터 (필수)
    genre_mask = df["genres"].apply(
        lambda v: any(g in _parse_genres(v) for g in genres)
    )
    candidates = df[genre_mask].copy()

    if candidates.empty:
        return pd.DataFrame()

    # 2단계: 복합 유사도 점수 계산
    candidates["_genre_score"] = candidates["genres"].apply(
        lambda v: _genre_overlap_score(v, genres)
    )
    candidates["_tag_score"] = candidates["tags"].apply(
        lambda v: _tag_overlap_score(v, tags)
    )
    candidates["_price_score"] = candidates["price"].apply(
        lambda v: _price_proximity_score(v, price)
    )
    candidates["_similarity"] = (
        candidates["_tag_score"]   * 0.40
        + candidates["_price_score"] * 0.30
        + candidates["_genre_score"] * 0.30
    )

    result = candidates.nlargest(top_n, "_similarity")
    cols = ["name", "genres", "price", "total_reviews", "positive_rate", "tags", "_similarity"]
    return result[cols].reset_index(drop=True)
