from dataclasses import dataclass, field

from .data_loader import (
    LANGUAGE_SILENCE_RATE,
    get_genre_silence_rates,
    get_price_tier_silence_rates,
    get_tag_silence_rates,
)

WEIGHTS = {
    "genre": 0.30,
    "price": 0.25,
    "tag": 0.25,
    "language": 0.20,
}

SILENCE_BASELINE = 0.433
FAVORABLE_THRESHOLD = SILENCE_BASELINE - 0.05
RISKY_THRESHOLD = SILENCE_BASELINE + 0.05

# 언어 구간별 반응 도달률 (1 - silence_rate)
LANGUAGE_REACH_RATE = {k: round(1 - v, 3) for k, v in LANGUAGE_SILENCE_RATE.items()}


@dataclass
class ReachResult:
    # 컴포넌트별 무반응 비율 (내부 계산용)
    genre_silence: float
    price_silence: float
    tag_silence: float
    language_silence: float

    # 컴포넌트별 도달 기여도 (0~100, 높을수록 좋음)
    contributions: dict[str, float]

    # 종합 점수
    reach_score: float   # 0~100, 높을수록 좋음
    reach_level: str     # "낮음" | "보통" | "높음" | "매우 높음"

    # 태그 분류
    competitive_tags: list[str]   # 경쟁 밀도 높은 태그 (구 risky)
    favorable_tags: list[str]     # 도달에 유리한 태그

    # 강점 / 개선 기회 (언어 제외)
    strengths: list[dict]
    opportunities: list[dict]

    # 언어 어드바이저리 (별도 처리)
    language_advisory: dict  # {"current", "max_gain", "message"}


def _compute_genre_silence(genres: list[str]) -> float:
    rates = get_genre_silence_rates()
    matched = [rates[g] for g in genres if g in rates]
    return sum(matched) / len(matched) if matched else SILENCE_BASELINE


def _compute_price_silence(price: float) -> float:
    tier_rates = get_price_tier_silence_rates()
    if price <= 5:
        key = "~$5"
    elif price <= 10:
        key = "$5~10"
    elif price <= 15:
        key = "$10~15"
    elif price <= 20:
        key = "$15~20"
    elif price <= 30:
        key = "$20~30"
    else:
        key = "$30+"
    return tier_rates.get(key, SILENCE_BASELINE)


def _compute_tag_silence(tags: list[str]) -> tuple[float, list[str], list[str]]:
    tag_rates = get_tag_silence_rates()
    competitive, favorable = [], []
    matched_rates = []
    for tag in tags:
        rate = tag_rates.get(tag)
        if rate is None:
            continue
        matched_rates.append(rate)
        if rate >= RISKY_THRESHOLD:
            competitive.append(tag)
        elif rate <= FAVORABLE_THRESHOLD:
            favorable.append(tag)
    avg = sum(matched_rates) / len(matched_rates) if matched_rates else SILENCE_BASELINE
    return avg, competitive, favorable


def _build_insights(
    genres: list[str],
    tags: list[str],
    price: float,
    genre_silence: float,
    competitive_tags: list[str],
    favorable_tags: list[str],
) -> tuple[list[dict], list[dict]]:
    """강점과 개선 기회 분리. 언어는 포함하지 않음."""
    strengths, opportunities = [], []

    # 가격대
    if price > 5:
        strengths.append({
            "label": "가격 포지셔닝",
            "detail": f"${price:.2f} — 반응 도달률이 높은 가격대입니다.",
        })
    else:
        opportunities.append({
            "label": "가격 조정 검토",
            "detail": f"${price:.2f}는 경쟁이 가장 치열한 구간입니다. $5~$15 구간의 반응 도달률이 더 높습니다.",
            "gain_hint": "가격 $10~15 변경 시 도달률 약 +14%p 향상 가능",
        })

    # 태그 수
    if len(tags) >= 5:
        strengths.append({
            "label": "태그 충분히 입력",
            "detail": f"태그 {len(tags)}개 — Steam 노출 기회를 충분히 확보하고 있습니다.",
        })
    else:
        opportunities.append({
            "label": "태그 추가 권장",
            "detail": f"현재 태그 {len(tags)}개 — 5개 이상 입력 시 Steam 검색 노출이 넓어집니다.",
            "gain_hint": None,
        })

    # 태그 경쟁도
    if not competitive_tags:
        strengths.append({
            "label": "태그 차별화",
            "detail": "선택한 태그들은 반응군 비율이 상대적으로 높습니다.",
        })
    else:
        tag_str = ", ".join(competitive_tags)
        opportunities.append({
            "label": "태그 경쟁도 높음",
            "detail": (
                f"{tag_str} — 인디게임 전체에서 매우 많이 쓰이는 태그입니다. "
                "차별화 태그를 함께 사용하면 틈새 유저에게 더 잘 발견됩니다."
            ),
            "gain_hint": None,
        })

    # 장르 도달률
    genre_reach = 1 - genre_silence
    if genre_reach >= 0.55:
        strengths.append({
            "label": "장르 도달률 양호",
            "detail": f"선택 장르 반응 도달률 {genre_reach:.1%} — 시장 평균(56.7%) 이상입니다.",
        })
    elif genre_reach >= 0.50:
        strengths.append({
            "label": "장르 도달률 평균 수준",
            "detail": f"선택 장르 반응 도달률 {genre_reach:.1%} — 시장 평균 수준입니다.",
        })
    else:
        genre_str = ", ".join(genres)
        opportunities.append({
            "label": "장르 포지셔닝 전략 필요",
            "detail": (
                f"{genre_str} 장르 도달률 {genre_reach:.1%} — 경쟁이 치열한 장르입니다. "
                "게임만의 차별점을 스토어 설명과 태그에 명확히 드러내세요."
            ),
            "gain_hint": None,
        })

    return strengths, opportunities


def _build_language_advisory(language_option: str) -> dict:
    current_silence = LANGUAGE_SILENCE_RATE[language_option]
    best_silence = min(LANGUAGE_SILENCE_RATE.values())   # 5개 이상
    # 언어 가중치 기준 도달 점수 향상 가능 폭
    max_gain = round((current_silence - best_silence) * WEIGHTS["language"] * 100, 1)

    if language_option == "5개 이상":
        message = "다국어 지원으로 Steam 노출 기회를 최대화하고 있습니다."
        tip = None
    elif language_option == "2~4개":
        message = "부분적으로 다국어를 지원하고 있습니다."
        tip = f"5개 이상으로 확대하면 도달 가능성 약 +{max_gain}점 향상 가능합니다."
    else:
        message = "영어 단독 지원 중입니다."
        tip = (
            f"Steam은 언어 지원을 핵심 노출 요소로 명시합니다. "
            f"한국어·일본어·중국어 추가 시 도달 가능성 약 +{max_gain}점 향상 가능합니다."
        )

    return {
        "current": language_option,
        "current_reach": round((1 - current_silence) * 100, 1),
        "best_reach": round((1 - best_silence) * 100, 1),
        "max_gain": max_gain,
        "message": message,
        "tip": tip,
    }


def _reach_level(score: float) -> str:
    if score >= 65:
        return "매우 높음"
    elif score >= 50:
        return "높음"
    elif score >= 35:
        return "보통"
    return "낮음"


def compute_reach(
    genres: list[str],
    tags: list[str],
    price: float,
    language_option: str,
) -> ReachResult:
    genre_silence = _compute_genre_silence(genres)
    price_silence = _compute_price_silence(price)
    tag_silence, competitive_tags, favorable_tags = _compute_tag_silence(tags)
    language_silence = LANGUAGE_SILENCE_RATE.get(language_option, SILENCE_BASELINE)

    weighted_silence = (
        genre_silence * WEIGHTS["genre"]
        + price_silence * WEIGHTS["price"]
        + tag_silence * WEIGHTS["tag"]
        + language_silence * WEIGHTS["language"]
    )
    reach_score = round((1 - weighted_silence) * 100, 1)

    contributions = {
        "장르": round((1 - genre_silence) * 100, 1),
        "가격": round((1 - price_silence) * 100, 1),
        "태그": round((1 - tag_silence) * 100, 1),
        "언어 지원": round((1 - language_silence) * 100, 1),
    }

    strengths, opportunities = _build_insights(
        genres, tags, price, genre_silence, competitive_tags, favorable_tags
    )

    language_advisory = _build_language_advisory(language_option)

    return ReachResult(
        genre_silence=genre_silence,
        price_silence=price_silence,
        tag_silence=tag_silence,
        language_silence=language_silence,
        contributions=contributions,
        reach_score=reach_score,
        reach_level=_reach_level(reach_score),
        competitive_tags=competitive_tags,
        favorable_tags=favorable_tags,
        strengths=strengths,
        opportunities=opportunities,
        language_advisory=language_advisory,
    )
