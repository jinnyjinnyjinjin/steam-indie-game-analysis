from pathlib import Path
import ast
import hashlib
import json
import os
import re
from typing import List, Literal

import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv
    from pydantic import BaseModel, Field
    from pydantic_ai import Agent
    from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
    from pydantic_ai.providers.google import GoogleProvider
    LLM_IMPORT_AVAILABLE = True
except Exception:
    load_dotenv = None
    BaseModel = object
    Field = None
    Agent = None
    GoogleModel = None
    GoogleModelSettings = None
    GoogleProvider = None
    LLM_IMPORT_AVAILABLE = False


# ============================================================
# 기본 설정
# ============================================================
DEFAULT_RUN_NAME = "master"

REQUIRED_FILES = {
    "game_base": "prelaunch_game_base.csv",
    "issue_repeat_summary": "prelaunch_issue_repeat_summary.csv",
    "condition_issue_summary": "prelaunch_condition_issue_summary.csv",
    "evidence_base": "prelaunch_checklist_evidence_base.csv",
}


# ============================================================
# 프로젝트 루트 탐색
# ============================================================
def find_project_root() -> Path:
    """
    streamlit_app/utils/prelaunch_engine.py 기준으로 프로젝트 루트를 찾는다.
    일반적으로:
    프로젝트 루트/
    └── streamlit_app/
        └── utils/
            └── prelaunch_engine.py
    """
    current = Path(__file__).resolve()

    for parent in current.parents:
        if (parent / "data").exists():
            return parent

    # data 폴더를 못 찾으면 기본적으로 streamlit_app의 상위 폴더를 프로젝트 루트로 본다.
    return current.parents[2]


def get_prelaunch_output_dir(run_name: str = DEFAULT_RUN_NAME) -> Path:
    """
    출시 전 분석 결과 폴더 경로를 반환한다.

    기준 구조:
    data/outputs/prelaunch/master/
    """
    root = find_project_root()
    return root / "data" / "outputs" / "prelaunch" / run_name


def get_checklist_data_dir(run_name: str = DEFAULT_RUN_NAME) -> Path:
    """
    근거 집계 단계에서 생성한 출시 전 체크리스트용 CSV 폴더 경로를 반환한다.

    기준 구조:
    data/outputs/prelaunch/master/prelaunch_checklist_data/
    """
    return get_prelaunch_output_dir(run_name) / "prelaunch_checklist_data"


def get_prelaunch_llm_cache_dir(run_name: str = DEFAULT_RUN_NAME) -> Path:
    """
    Streamlit에서 생성한 출시 전 LLM 체크리스트 캐시 저장 폴더를 반환한다.
    """
    cache_dir = get_prelaunch_output_dir(run_name) / "prelaunch_checklist_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_graded_game_path() -> Path:
    """
    Steam 태그 DNA 참고용 파일 경로를 반환한다.
    """
    root = find_project_root()
    return root / "data" / "preprocessed" / "steam_indie_games_graded.csv"


# ============================================================
# 데이터 로드
# ============================================================
@st.cache_data(show_spinner="출시 전 분석 데이터를 불러오는 중...")
def load_prelaunch_data(run_name: str = DEFAULT_RUN_NAME) -> dict:
    """
    근거 집계 단계에서 생성한 CSV 4개를 불러온다.
    """
    data_dir = get_checklist_data_dir(run_name)

    missing_files = []
    paths = {}

    for key, filename in REQUIRED_FILES.items():
        path = data_dir / filename
        paths[key] = path

        if not path.exists():
            missing_files.append(str(path))

    if missing_files:
        missing_text = "\n".join(missing_files)
        raise FileNotFoundError(
            "필수 CSV 파일을 찾을 수 없습니다.\n"
            f"실행 기준: {run_name}\n"
            f"{missing_text}"
        )

    game_base = pd.read_csv(paths["game_base"])
    issue_repeat_summary = pd.read_csv(paths["issue_repeat_summary"])
    condition_issue_summary = pd.read_csv(paths["condition_issue_summary"])
    evidence_base = pd.read_csv(paths["evidence_base"])

    graded_path = get_graded_game_path()
    if graded_path.exists():
        graded_games = pd.read_csv(graded_path)
    else:
        graded_games = pd.DataFrame()

    return {
        "run_name": run_name,
        "data_dir": str(data_dir),
        "game_base": game_base,
        "issue_repeat_summary": issue_repeat_summary,
        "condition_issue_summary": condition_issue_summary,
        "evidence_base": evidence_base,
        "graded_games": graded_games,
    }


# ============================================================
# 문자열 처리 함수
# ============================================================
def text_contains_any(text, values) -> bool:
    """
    text 안에 values 중 하나라도 포함되는지 확인한다.
    """
    text = str(text).lower()
    values = [str(v).lower() for v in values if str(v).strip()]
    return any(v in text for v in values)


def text_contains_all(text, values) -> bool:
    """
    text 안에 values가 모두 포함되는지 확인한다.
    """
    text = str(text).lower()
    values = [str(v).lower() for v in values if str(v).strip()]
    return all(v in text for v in values)




def get_condition_values(user_condition: dict, plural_key: str, single_key: str) -> list[str]:
    """
    Streamlit 입력 조건을 리스트로 통일한다.
    - 새 버전: price_groups, play_styles처럼 리스트 사용
    - 이전 버전: price_group, play_style처럼 단일 값 사용
    """
    values = user_condition.get(plural_key, None)

    if values is None:
        single_value = user_condition.get(single_key, None)
        values = [single_value] if single_value else []

    if isinstance(values, str):
        values = [values]

    return [str(v) for v in values if pd.notna(v) and str(v).strip()]


def normalize_tag_name(tag: str) -> str:
    """
    Rogue-like, Roguelike처럼 표기가 조금 달라도 비교할 수 있도록 정규화한다.
    """
    tag = str(tag).lower()
    tag = re.sub(r"[^a-z0-9가-힣]", "", tag)
    return tag


def parse_tag_names(value):
    """
    steam_indie_games_graded.csv의 tags 컬럼을 태그 리스트로 변환한다.
    """
    if pd.isna(value):
        return []

    text = str(value).strip()
    if text == "":
        return []

    try:
        parsed = json.loads(text.replace("'", '"'))
    except Exception:
        try:
            parsed = ast.literal_eval(text)
        except Exception:
            parsed = None

    if isinstance(parsed, dict):
        return list(parsed.keys())

    if isinstance(parsed, list):
        return [str(x) for x in parsed]

    return [x.strip() for x in text.split(",") if x.strip()]


# ============================================================
# 정렬 / 표시 보조 함수
# ============================================================
def add_priority_order(df: pd.DataFrame, priority_col: str = "priority_level") -> pd.DataFrame:
    """
    상/중/하 우선순위를 정렬용 숫자로 변환한다.
    """
    order_map = {"상": 1, "중": 2, "하": 3}

    out = df.copy()

    if priority_col in out.columns:
        out["priority_order"] = out[priority_col].map(order_map).fillna(9)
    else:
        out["priority_order"] = 9

    return out


def sort_price_options(options):
    """
    가격대 옵션을 보기 좋은 순서로 정렬한다.
    예: 0-5, 5-10, 10-20, 20-40, 40+
    """
    def key_func(value):
        text = str(value)

        if text.lower() in ["free", "무료"]:
            return -1

        numbers = re.findall(r"\d+", text)
        if numbers:
            return int(numbers[0])

        return 9999

    return sorted(options, key=key_func)


def condition_type_to_kor(condition_type: str) -> str:
    mapping = {
        "genre": "장르",
        "price_group": "가격대",
        "steam_tag": "Steam 태그",
        "play_style": "플레이 방식",
    }
    return mapping.get(str(condition_type), str(condition_type))


def get_check_category(issue_name, checklist_text=""):
    """
    이슈명과 체크 질문을 바탕으로 점검 구분을 간단히 분류한다.
    """
    text = f"{issue_name} {checklist_text}".lower()

    if any(word in text for word in ["버그", "크래시", "안정", "저장", "진행 불가", "오류"]):
        return "기술 안정성"

    if any(word in text for word in ["조작", "input", "반응", "컨트롤"]):
        return "조작감"

    if any(word in text for word in ["게임플레이", "루프", "핵심 재미", "전투", "플레이"]):
        return "핵심 루프"

    if "난이도" in text:
        return "난이도"

    if "밸런스" in text:
        return "밸런스"

    if any(word in text for word in ["ui", "ux", "튜토리얼", "목표 안내", "메뉴", "인터페이스"]):
        return "UI/UX"

    if any(word in text for word in ["콘텐츠", "분량", "볼륨", "반복"]):
        return "콘텐츠 분량"

    if any(word in text for word in ["그래픽", "사운드", "음악", "비주얼", "연출"]):
        return "그래픽/사운드"

    if any(word in text for word in ["가격", "가치", "price", "value"]):
        return "가격 대비 가치"

    return "기타"


# ============================================================
# 선택 옵션 생성
# ============================================================
def get_filter_options(game_base: pd.DataFrame, evidence_base: pd.DataFrame) -> dict:
    """
    Streamlit 입력 위젯에 사용할 선택 옵션을 만든다.
    """
    genre_options = (
        evidence_base.loc[evidence_base["condition_type"] == "genre", "condition_value"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
        if {"condition_type", "condition_value"}.issubset(evidence_base.columns)
        else []
    )

    price_options = (
        evidence_base.loc[evidence_base["condition_type"] == "price_group", "condition_value"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
        if {"condition_type", "condition_value"}.issubset(evidence_base.columns)
        else []
    )

    tag_options = (
        evidence_base.loc[evidence_base["condition_type"] == "steam_tag", "condition_value"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
        if {"condition_type", "condition_value"}.issubset(evidence_base.columns)
        else []
    )

    play_style_options = (
        evidence_base.loc[evidence_base["condition_type"] == "play_style", "condition_value"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
        if {"condition_type", "condition_value"}.issubset(evidence_base.columns)
        else []
    )

    return {
        "genres": sorted(genre_options),
        "price_groups": sort_price_options(price_options),
        "steam_tags": sorted(tag_options),
        "play_styles": sorted(play_style_options),
    }


# ============================================================
# 사용자 조건 기반 게임 필터링
# ============================================================
def filter_matched_games(game_base: pd.DataFrame, user_condition: dict) -> pd.DataFrame:
    """
    사용자가 입력한 장르/가격대/Steam 태그/플레이 방식 조건에 맞는 게임을 찾는다.

    다중 선택 조건은 같은 항목 안에서는 OR로 처리한다.
    예: 가격대가 [10-20, 20-40]이면 둘 중 하나에 해당하는 게임을 통과시킨다.
    Steam 태그만 any/all 옵션을 따로 적용한다.
    """
    matched = game_base.copy()

    genres = user_condition.get("genres", [])
    price_groups = get_condition_values(user_condition, "price_groups", "price_group")
    steam_tags = user_condition.get("steam_tags", [])
    steam_tag_match = user_condition.get("steam_tag_match", "any")
    play_styles = get_condition_values(user_condition, "play_styles", "play_style")

    if genres and "genres_text" in matched.columns:
        matched = matched[
            matched["genres_text"].apply(lambda x: text_contains_any(x, genres))
        ]

    if price_groups and "price_group" in matched.columns:
        matched = matched[
            matched["price_group"].astype(str).isin([str(x) for x in price_groups])
        ]

    if steam_tags and "top_steam_tags_text" in matched.columns:
        if steam_tag_match == "all":
            matched = matched[
                matched["top_steam_tags_text"].apply(lambda x: text_contains_all(x, steam_tags))
            ]
        else:
            matched = matched[
                matched["top_steam_tags_text"].apply(lambda x: text_contains_any(x, steam_tags))
            ]

    if play_styles and "play_style" in matched.columns:
        matched = matched[
            matched["play_style"].astype(str).isin([str(x) for x in play_styles])
        ]

    return matched.reset_index(drop=True)


# ============================================================
# 사용자 조건 기반 근거 데이터 선택
# ============================================================
def select_condition_evidence(
    evidence_base: pd.DataFrame,
    user_condition: dict,
    top_n_per_condition: int = 8,
    max_total_rows: int = 40,
) -> pd.DataFrame:
    """
    사용자 조건에 해당하는 조건별 반복 이슈 근거 데이터를 선택한다.

    가격대와 플레이 방식은 다중 선택을 지원한다.
    선택된 값 중 하나라도 맞으면 해당 조건의 근거 데이터를 포함한다.
    """
    selected_parts = []

    genres = user_condition.get("genres", [])
    price_groups = get_condition_values(user_condition, "price_groups", "price_group")
    steam_tags = user_condition.get("steam_tags", [])
    play_styles = get_condition_values(user_condition, "play_styles", "play_style")

    if genres:
        temp = evidence_base[
            (evidence_base["condition_type"] == "genre")
            & (evidence_base["condition_value"].isin(genres))
        ].copy()
        selected_parts.append(temp)

    if price_groups:
        temp = evidence_base[
            (evidence_base["condition_type"] == "price_group")
            & (evidence_base["condition_value"].astype(str).isin([str(x) for x in price_groups]))
        ].copy()
        selected_parts.append(temp)

    if steam_tags:
        temp = evidence_base[
            (evidence_base["condition_type"] == "steam_tag")
            & (evidence_base["condition_value"].isin(steam_tags))
        ].copy()
        selected_parts.append(temp)

    if play_styles:
        temp = evidence_base[
            (evidence_base["condition_type"] == "play_style")
            & (evidence_base["condition_value"].astype(str).isin([str(x) for x in play_styles]))
        ].copy()
        selected_parts.append(temp)

    if not selected_parts:
        return pd.DataFrame()

    selected = pd.concat(selected_parts, ignore_index=True)

    selected = selected.drop_duplicates(
        subset=[
            col for col in [
                "condition_type",
                "condition_value",
                "issue_name_kor",
            ]
            if col in selected.columns
        ]
    )

    selected = add_priority_order(selected, priority_col="priority_level")

    sort_cols = [
        "priority_order",
        "issue_game_ratio",
        "issue_game_count",
        "negative_game_count",
        "total_issue_review_count",
    ]
    sort_cols = [col for col in sort_cols if col in selected.columns]

    selected = selected.sort_values(
        sort_cols,
        ascending=[True] + [False] * (len(sort_cols) - 1),
    )

    # 조건별로 너무 많은 이슈가 들어가지 않도록 제한한다.
    if {"condition_type", "condition_value"}.issubset(selected.columns):
        selected = (
            selected
            .groupby(["condition_type", "condition_value"], group_keys=False)
            .head(top_n_per_condition)
            .reset_index(drop=True)
        )

    selected = selected.head(max_total_rows).copy()

    if "priority_level" in selected.columns:
        selected["fixed_priority"] = selected["priority_level"]

    if {"condition_type", "condition_value"}.issubset(selected.columns):
        selected["source_condition"] = (
            selected["condition_type"].astype(str)
            + "="
            + selected["condition_value"].astype(str)
        )

    return selected.reset_index(drop=True)


# ============================================================
# 전체 기준 반복 이슈
# ============================================================
def get_overall_issues(issue_repeat_summary: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    """
    전체 게임 기준으로 반복된 이슈를 가져온다.
    """
    if issue_repeat_summary.empty:
        return pd.DataFrame()

    df = add_priority_order(issue_repeat_summary, priority_col="priority_level")

    sort_cols = [
        "priority_order",
        "issue_game_ratio",
        "issue_game_count",
        "negative_game_count",
        "total_issue_review_count",
    ]
    sort_cols = [col for col in sort_cols if col in df.columns]

    df = df.sort_values(
        sort_cols,
        ascending=[True] + [False] * (len(sort_cols) - 1),
    )

    return df.head(top_n).drop(columns=["priority_order"], errors="ignore").reset_index(drop=True)


# ============================================================
# Steam 태그 DNA 참고 정보
# ============================================================
def make_tag_dna_summary(graded_games: pd.DataFrame, input_tags: list[str]) -> pd.DataFrame:
    """
    사용자가 입력한 Steam 태그가 성과 상위권 게임에서 얼마나 나타나는지 참고용으로 계산한다.
    """
    if graded_games.empty or not input_tags:
        return pd.DataFrame()

    required_cols = {"appid", "performance_grade", "tags"}
    if not required_cols.issubset(graded_games.columns):
        return pd.DataFrame()

    work = graded_games[["appid", "performance_grade", "tags"]].copy()
    work["tag_list"] = work["tags"].apply(parse_tag_names)

    tag_long = work.explode("tag_list").dropna(subset=["tag_list"]).copy()
    tag_long["steam_tag"] = tag_long["tag_list"].astype(str).str.strip()
    tag_long = tag_long[tag_long["steam_tag"] != ""]
    tag_long["tag_norm"] = tag_long["steam_tag"].apply(normalize_tag_name)

    top_tier_grades = ["high_high", "high_mid", "mid_high"]

    rows = []

    for input_tag in input_tags:
        input_norm = normalize_tag_name(input_tag)
        matched_rows = tag_long[tag_long["tag_norm"] == input_norm].copy()

        total_game_count = matched_rows["appid"].nunique()

        high_high_game_count = matched_rows.loc[
            matched_rows["performance_grade"] == "high_high",
            "appid",
        ].nunique()

        high_mid_game_count = matched_rows.loc[
            matched_rows["performance_grade"] == "high_mid",
            "appid",
        ].nunique()

        mid_high_game_count = matched_rows.loc[
            matched_rows["performance_grade"] == "mid_high",
            "appid",
        ].nunique()

        top_tier_game_count = matched_rows.loc[
            matched_rows["performance_grade"].isin(top_tier_grades),
            "appid",
        ].nunique()

        top_tier_ratio = 0.0
        if total_game_count > 0:
            top_tier_ratio = round(top_tier_game_count / total_game_count * 100, 1)

        matched_tag_name = ""
        if len(matched_rows) > 0:
            matched_tag_name = matched_rows["steam_tag"].mode().iloc[0]

        if total_game_count == 0:
            note = f"'{input_tag}' 태그는 성과 등급 데이터에서 확인되지 않았다."
        else:
            note = (
                f"'{input_tag}' 태그는 성과 등급 데이터에서 {total_game_count:,}개 게임에 나타났고, "
                f"그중 성과 상위권 게임은 {top_tier_game_count:,}개({top_tier_ratio}%)다. "
                f"이는 성공 보장이 아니라 태그 조건 해석용 참고 정보다."
            )

        rows.append(
            {
                "입력 태그": input_tag,
                "매칭 태그": matched_tag_name,
                "전체 게임 수": total_game_count,
                "high_high 게임 수": high_high_game_count,
                "high_mid 게임 수": high_mid_game_count,
                "mid_high 게임 수": mid_high_game_count,
                "성과 상위권 게임 수": top_tier_game_count,
                "성과 상위권 비율": top_tier_ratio,
                "참고 설명": note,
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# 규칙 기반 체크리스트 생성
# ============================================================
def make_check_question(issue_direction: str, issue_name: str, category: str) -> str:
    """
    이슈 방향과 이슈명을 바탕으로 질문형 체크리스트 문장을 만든다.
    """
    if issue_direction == "강화 요소":
        return f"{issue_name} 요소가 출시 초반 유저에게 강점으로 충분히 전달되는가?"

    if issue_direction == "리스크 요소":
        return f"{issue_name} 문제가 출시 초반 부정 리뷰로 이어지지 않도록 사전에 점검했는가?"

    if category == "기술 안정성":
        return f"{issue_name} 관련 오류, 크래시, 진행 불가 문제가 없는가?"

    if category == "UI/UX":
        return f"{issue_name} 관련 안내, 메뉴, 튜토리얼 흐름이 초반 유저에게 충분히 명확한가?"

    if category == "조작감":
        return f"{issue_name} 관련 조작 반응과 입력 흐름이 불편하지 않은가?"

    if category == "핵심 루프":
        return f"{issue_name} 요소가 초반 30분 안에 충분히 드러나는가?"

    return f"{issue_name} 요소를 출시 전에 점검했는가?"


def make_how_to_check(issue_name: str, category: str) -> str:
    """
    개발자가 실제로 확인할 수 있는 점검 방법을 만든다.
    """
    if category == "기술 안정성":
        return "초반 구간 반복 플레이 테스트, 저장/불러오기 테스트, 크래시 로그 확인"

    if category == "UI/UX":
        return "신규 유저 기준 튜토리얼 테스트, 목표 안내 문구 확인, 메뉴 이동 동선 점검"

    if category == "조작감":
        return "키보드/마우스/패드 입력 테스트, 전투·이동·상호작용 반응 속도 확인"

    if category == "핵심 루프":
        return "초반 30분 플레이 흐름 점검, 핵심 재미가 드러나는 시점 확인"

    if category == "난이도":
        return "초반 난이도 곡선, 실패 구간, 재도전 피로도 확인"

    if category == "밸런스":
        return "초반 성장 속도, 적 체력, 보상량, 반복 플레이 피로도 확인"

    if category == "콘텐츠 분량":
        return "초반 콘텐츠 밀도, 반복 구간, 플레이 목표의 다양성 확인"

    if category == "그래픽/사운드":
        return "비주얼 가독성, 사운드 피드백, 분위기 전달력 확인"

    if category == "가격 대비 가치":
        return "예상 플레이타임, 콘텐츠 분량, 가격대 유사 게임과 비교"

    return "내부 플레이 테스트와 유사 게임 리뷰 비교를 통해 확인"


def make_evidence_summary(row: pd.Series) -> str:
    """
    근거표 한 행을 사람이 읽기 쉬운 요약 문장으로 바꾼다.
    """
    condition_type = condition_type_to_kor(row.get("condition_type", ""))
    condition_value = row.get("condition_value", "")

    condition_game_count = int(row.get("condition_game_count", 0))
    issue_game_count = int(row.get("issue_game_count", 0))
    issue_game_ratio = float(row.get("issue_game_ratio", 0))
    negative_game_count = int(row.get("negative_game_count", 0))
    high_urgency_game_count = int(row.get("high_urgency_game_count", 0))

    return (
        f"{condition_type} '{condition_value}' 조건에서 "
        f"{condition_game_count:,}개 게임 중 {issue_game_count:,}개 게임({issue_game_ratio:.1f}%)에서 반복 언급되었다. "
        f"Steam 비추천 맥락은 {negative_game_count:,}개 게임에서 확인되었다. "
        f"High urgency는 {high_urgency_game_count:,}개 게임에서 확인되었지만 보조 참고 지표로만 해석한다."
    )


def make_rule_based_checklist(selected_evidence: pd.DataFrame) -> pd.DataFrame:
    """
    LLM 호출 없이 선택된 근거표를 바탕으로 체크리스트 표를 만든다.
    """
    if selected_evidence.empty:
        return pd.DataFrame()

    rows = []

    for _, row in selected_evidence.iterrows():
        priority = row.get("priority_level", "")
        issue_direction = row.get("issue_direction", "참고 요소")
        issue_name = row.get("issue_name_kor", "")

        category = get_check_category(issue_name)
        check_question = make_check_question(issue_direction, issue_name, category)
        evidence_summary = make_evidence_summary(row)
        how_to_check = make_how_to_check(issue_name, category)

        source_condition = row.get(
            "source_condition",
            f"{row.get('condition_type', '')}={row.get('condition_value', '')}",
        )

        rows.append(
            {
                "해석 방향": issue_direction,
                "구분": category,
                "체크 질문": check_question,
                "우선순위": priority,
                "근거 이슈": issue_name,
                "근거": evidence_summary,
                "확인 방법": how_to_check,
                "근거 조건": source_condition,
                "조건 내 반복 비율": row.get("issue_game_ratio", 0),
                "반복 게임 수": row.get("issue_game_count", 0),
                "Steam 비추천 게임 수": row.get("negative_game_count", 0),
                "High urgency 게임 수": row.get("high_urgency_game_count", 0),
                "우선순위 산정 규칙": row.get("priority_rule_detail", ""),
            }
        )

    checklist_df = pd.DataFrame(rows)

    if checklist_df.empty:
        return checklist_df

    priority_order_map = {"상": 1, "중": 2, "하": 3}
    checklist_df["priority_order"] = checklist_df["우선순위"].map(priority_order_map).fillna(9)

    checklist_df = checklist_df.sort_values(
        [
            "priority_order",
            "조건 내 반복 비율",
            "반복 게임 수",
            "Steam 비추천 게임 수",
        ],
        ascending=[True, False, False, False],
    ).drop(columns="priority_order")

    return checklist_df.reset_index(drop=True)


# ============================================================
# 표시용 데이터프레임 생성
# ============================================================
def make_condition_summary_df(user_condition: dict) -> pd.DataFrame:
    """
    사용자가 입력한 조건을 표로 만든다.
    """
    price_groups = get_condition_values(user_condition, "price_groups", "price_group")
    play_styles = get_condition_values(user_condition, "play_styles", "play_style")

    rows = [
        {
            "항목": "장르",
            "값": ", ".join(user_condition.get("genres", [])) or "-",
            "매칭 방식": "선택 장르 중 하나라도 포함",
        },
        {
            "항목": "가격대",
            "값": ", ".join(price_groups) or "-",
            "매칭 방식": "선택 가격대 중 하나라도 해당",
        },
        {
            "항목": "Steam 태그",
            "값": ", ".join(user_condition.get("steam_tags", [])) or "-",
            "매칭 방식": user_condition.get("steam_tag_match", "-"),
        },
        {
            "항목": "플레이 방식",
            "값": ", ".join(play_styles) or "-",
            "매칭 방식": "선택 플레이 방식 중 하나라도 해당",
        },
    ]

    return pd.DataFrame(rows)


def make_evidence_display_df(selected_evidence: pd.DataFrame) -> pd.DataFrame:
    """
    Streamlit 화면에 보여줄 근거표 컬럼만 정리한다.
    """
    if selected_evidence.empty:
        return pd.DataFrame()

    display_cols = [
        "priority_level",
        "issue_direction",
        "condition_type",
        "condition_value",
        "issue_name_kor",
        "condition_game_count",
        "issue_game_count",
        "issue_game_ratio",
        "positive_game_count",
        "negative_game_count",
        "tag_positive_game_count",
        "tag_negative_game_count",
        "tag_mixed_game_count",
        "high_urgency_game_count",
        "priority_rule_detail",
        "priority_reason",
        "llm_evidence_text",
    ]

    display_cols = [col for col in display_cols if col in selected_evidence.columns]

    out = selected_evidence[display_cols].copy()

    rename_map = {
        "priority_level": "우선순위",
        "issue_direction": "해석 방향",
        "condition_type": "조건 종류",
        "condition_value": "조건 값",
        "issue_name_kor": "이슈",
        "condition_game_count": "조건 게임 수",
        "issue_game_count": "반복 게임 수",
        "issue_game_ratio": "조건 내 반복 비율",
        "positive_game_count": "Steam 추천 맥락 게임 수",
        "negative_game_count": "Steam 비추천 맥락 게임 수",
        "tag_positive_game_count": "LLM 긍정 태그 게임 수",
        "tag_negative_game_count": "LLM 부정 태그 게임 수",
        "tag_mixed_game_count": "LLM 혼합 태그 게임 수",
        "high_urgency_game_count": "High urgency 게임 수",
        "priority_rule_detail": "우선순위 산정 규칙",
        "priority_reason": "우선순위 근거 설명",
        "llm_evidence_text": "LLM 입력용 근거 문장",
    }

    out = out.rename(columns=rename_map)

    if "조건 종류" in out.columns:
        out["조건 종류"] = out["조건 종류"].apply(condition_type_to_kor)

    return out

# ============================================================
# LLM 체크리스트 생성 스키마
# ============================================================
if LLM_IMPORT_AVAILABLE:
    class ChecklistItem(BaseModel):
        priority: Literal["상", "중", "하"] = Field(description="근거표의 fixed_priority를 그대로 복사한 고정 점검 중요도")
        issue_direction: Literal["강화 요소", "리스크 요소", "참고 요소"] = Field(description="근거표의 issue_direction 값을 그대로 복사한 이슈 해석 방향")
        category: str = Field(description="점검 구분. 예: 기술 안정성, 조작감, 핵심 루프, 난이도, UI/UX, 콘텐츠 분량, 그래픽/사운드, 가격 대비 가치")
        check_question: str = Field(description="출시 전 확인해야 할 질문형 체크 항목. 반드시 질문형으로 작성")
        evidence_issue: str = Field(description="근거가 된 이슈명. 반드시 근거표의 issue_name_kor 값 중 하나를 그대로 사용")
        evidence_summary: str = Field(description="제공된 근거표의 수치와 조건을 바탕으로 한 요약")
        how_to_check: str = Field(description="개발자가 출시 전에 확인할 수 있는 방법")
        source_conditions: List[str] = Field(description="이 근거가 나온 조건 목록")


    class PrelaunchChecklistResult(BaseModel):
        title: str = Field(description="체크리스트 제목")
        condition_summary: str = Field(description="사용자 입력 조건 요약")
        data_summary: str = Field(description="근거 데이터 규모 요약")
        tag_dna_summary: str = Field(description="Steam 태그 DNA 참고 정보 요약")
        high_priority: List[ChecklistItem] = Field(description="fixed_priority가 상인 체크리스트")
        mid_priority: List[ChecklistItem] = Field(description="fixed_priority가 중인 체크리스트")
        low_priority: List[ChecklistItem] = Field(description="fixed_priority가 하인 체크리스트")
        cautions: List[str] = Field(description="해석 시 주의사항")
        final_summary: str = Field(description="전체 요약")
else:
    ChecklistItem = None
    PrelaunchChecklistResult = None


# ============================================================
# LLM용 공통 유틸
# ============================================================
def to_serializable(obj):
    """
    Pydantic 모델, dict, list 등을 JSON 저장 가능한 객체로 변환한다.
    """
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_serializable(v) for v in obj]
    return obj


def df_to_text_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
    """
    LLM 프롬프트에 넣기 좋은 텍스트 표를 만든다.
    pandas.to_markdown()을 쓰지 않아 tabulate 의존성이 없다.
    """
    if df is None or df.empty:
        return "데이터 없음"

    work = df.copy()

    if columns is not None:
        columns = [col for col in columns if col in work.columns]
        work = work[columns].copy()

    work = work.head(max_rows).copy()

    rows = []
    for idx, row in work.iterrows():
        parts = []
        for col in work.columns:
            value = row[col]
            if pd.isna(value):
                value = ""
            value = str(value).replace("\n", " ").strip()
            parts.append(f"{col}: {value}")
        rows.append(f"- " + " | ".join(parts))

    return "\n".join(rows)


def _normalize_for_cache(value):
    if isinstance(value, dict):
        return {k: _normalize_for_cache(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        return sorted([str(v) for v in value])
    return value


def make_prelaunch_cache_key(user_condition: dict, selected_evidence_df: pd.DataFrame) -> str:
    """
    사용자 조건과 선택 근거 이슈를 기준으로 LLM 결과 캐시 키를 만든다.
    """
    issue_cols = [
        "condition_type",
        "condition_value",
        "issue_name_kor",
        "fixed_priority",
        "priority_level",
        "issue_direction",
    ]
    issue_cols = [col for col in issue_cols if col in selected_evidence_df.columns]

    payload = {
        "user_condition": _normalize_for_cache(user_condition),
        "evidence": selected_evidence_df[issue_cols].fillna("").astype(str).to_dict("records"),
    }

    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def get_prelaunch_cache_path(run_name: str, cache_key: str) -> Path:
    return get_prelaunch_llm_cache_dir(run_name) / f"prelaunch_checklist_{cache_key}.json"


def load_cached_prelaunch_result(run_name: str, cache_key: str) -> dict | None:
    path = get_prelaunch_cache_path(run_name, cache_key)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cached_prelaunch_result(run_name: str, cache_key: str, result_dict: dict) -> Path:
    path = get_prelaunch_cache_path(run_name, cache_key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)
    return path


# ============================================================
# 프롬프트 생성
# ============================================================
def build_checklist_prompt(
    user_condition: dict,
    matched_game_count: int,
    matched_review_count: int,
    selected_evidence_df: pd.DataFrame,
    overall_issues_df: pd.DataFrame,
    tag_dna_df: pd.DataFrame,
    max_evidence_rows_for_prompt: int = 40,
    top_n_overall_issues: int = 8,
) -> str:
    selected_evidence_df = selected_evidence_df.copy()

    if "fixed_priority" not in selected_evidence_df.columns and "priority_level" in selected_evidence_df.columns:
        selected_evidence_df["fixed_priority"] = selected_evidence_df["priority_level"]

    if "source_condition" not in selected_evidence_df.columns:
        selected_evidence_df["source_condition"] = (
            selected_evidence_df.get("condition_type", "").astype(str)
            + "="
            + selected_evidence_df.get("condition_value", "").astype(str)
        )

    evidence_cols = [
        "fixed_priority",
        "source_condition",
        "condition_type",
        "condition_value",
        "issue_name_kor",
        "issue_direction",
        "condition_game_count",
        "issue_game_count",
        "issue_game_ratio",
        "positive_game_count",
        "negative_game_count",
        "tag_negative_game_count",
        "high_urgency_game_count",
        "llm_evidence_text",
    ]
    evidence_cols = [col for col in evidence_cols if col in selected_evidence_df.columns]

    overall_cols = [
        "issue_name_kor",
        "issue_game_count",
        "issue_game_ratio",
        "negative_game_count",
        "tag_negative_game_count",
        "high_urgency_game_count",
        "priority_level",
    ]
    overall_cols = [col for col in overall_cols if col in overall_issues_df.columns]

    tag_dna_cols = [
        "input_steam_tag",
        "matched_steam_tag",
        "total_game_count",
        "top_tier_game_count",
        "top_tier_ratio",
        "tag_dna_note",
        "입력 태그",
        "매칭 태그",
        "전체 게임 수",
        "성과 상위권 게임 수",
        "성과 상위권 비율",
        "참고 설명",
    ]
    tag_dna_cols = [col for col in tag_dna_cols if col in tag_dna_df.columns]

    evidence_text = df_to_text_table(
        selected_evidence_df,
        columns=evidence_cols,
        max_rows=max_evidence_rows_for_prompt,
    )

    overall_text = df_to_text_table(
        overall_issues_df,
        columns=overall_cols,
        max_rows=top_n_overall_issues,
    )

    tag_dna_text = df_to_text_table(
        tag_dna_df,
        columns=tag_dna_cols,
        max_rows=20,
    )

    prompt = f"""
당신은 Steam 인디게임 출시 전 점검 체크리스트를 작성하는 데이터 분석 보조자입니다.

목표:
개발자가 입력한 장르·가격대·Steam 태그·플레이 방식 조건을 바탕으로,
기존 Steam 인디게임의 D0-D30 초기 리뷰 분석 결과에서 반복된 이슈를 참고하여
출시 전 체크리스트를 작성하세요.

가장 중요한 제한:
- 당신은 우선순위를 새로 계산하거나 판단하지 않습니다.
- 조건별 반복 이슈 근거표의 fixed_priority는 이미 데이터 기준으로 계산된 고정 우선순위입니다.
- 각 체크리스트 항목의 priority는 반드시 근거표의 fixed_priority를 그대로 사용하세요.
- fixed_priority가 "상"인 항목은 high_priority에, "중"인 항목은 mid_priority에, "하"인 항목은 low_priority에 넣으세요.
- fixed_priority를 올리거나 내리거나, 다른 우선순위로 재배치하지 마세요.
- 근거표에 없는 issue_name_kor를 새로 만들지 마세요.
- evidence_issue에는 반드시 조건별 반복 이슈 근거표에 있는 issue_name_kor 값을 그대로 작성하세요.
- issue_direction에는 반드시 근거표의 issue_direction 값을 그대로 작성하세요.

이슈 해석 방향:
- issue_direction이 "리스크 요소"인 경우, 출시 전 문제가 발생하지 않도록 점검하는 질문으로 작성하세요.
- issue_direction이 "강화 요소"인 경우, 이미 유저가 긍정적으로 평가한 요소를 유지하거나 강화하는 질문으로 작성하세요.
- issue_direction이 "참고 요소"인 경우, 단정하지 말고 참고 점검 항목으로 작성하세요.
- 모든 항목을 문제처럼 표현하지 마세요.

근거 사용 기준:
- issue_game_count와 issue_game_ratio는 여러 게임에서 반복되었는지 확인하는 핵심 근거입니다.
- negative_game_count는 Steam 비추천 맥락에서 반복되었는지 확인하는 핵심 근거입니다.
- tag_negative_game_count는 LLM이 이슈 단위로 부정 맥락을 분류한 보조 지표입니다.
- high_urgency_game_count는 이전 LLM 리뷰 분류 결과를 집계한 보조 지표입니다.
- high_urgency_game_count만으로 우선순위를 바꾸거나 새로 판단하지 마세요.
- 태그 수나 리뷰 수만으로 과도하게 단정하지 마세요.
- 근거가 약하면 "참고 수준" 또는 "주의해서 해석"이라고 표현하세요.
- 체크 질문은 반드시 실제 출시 전에 확인 가능한 질문형 문장으로 작성하세요.

Steam 태그 DNA 참고 기준:
- Steam 태그 DNA는 조원 EDA에서 가져온 보조 관점입니다.
- 성과 상위권 게임에서 특정 Steam 태그가 얼마나 자주 나타나는지 보여줍니다.
- 이것은 "해당 태그를 넣으면 성공한다"는 뜻이 아닙니다.
- 체크리스트의 직접 근거는 조건별 반복 이슈 근거표입니다.
- Steam 태그 DNA는 Steam 태그 조건을 해석하는 보조 정보로만 사용하세요.

사용자 입력 조건:
{json.dumps(user_condition, ensure_ascii=False, indent=2)}

조건에 맞는 게임 수:
- 게임 수: {matched_game_count}
- 분석 리뷰 수: {matched_review_count}

조건별 반복 이슈 근거표:
{evidence_text}

전체 게임 기준 반복 이슈:
{overall_text}

Steam 태그 DNA 참고 정보:
{tag_dna_text}

출력 요구:
1. 사용자의 조건을 간단히 요약하세요.
2. 데이터 규모를 간단히 설명하세요.
3. Steam 태그 DNA 참고 정보를 1~2문장으로 요약하세요.
4. high_priority에는 fixed_priority가 "상"인 근거 이슈만 작성하세요.
5. mid_priority에는 fixed_priority가 "중"인 근거 이슈만 작성하세요.
6. low_priority에는 fixed_priority가 "하"인 근거 이슈만 작성하세요.
7. 각 항목은 issue_direction, category, check_question, evidence_issue, evidence_summary, how_to_check가 표로 출력되기 좋은 내용이어야 합니다.
8. evidence_summary에는 가능한 한 issue_game_count, issue_game_ratio, negative_game_count 중 2개 이상을 포함하고, high_urgency_game_count는 보조 정보로만 언급하세요.
9. 마지막에는 해석 시 주의사항을 작성하세요.
"""

    return prompt.strip()


# ============================================================
# PydanticAI / Gemini Agent
# ============================================================
def _read_secret_or_env(name: str, default: str | None = None) -> str | None:
    """
    st.secrets 또는 환경변수에서 설정값을 읽는다.
    """
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass

    return os.getenv(name, default)


@st.cache_resource(show_spinner=False)
def create_prelaunch_checklist_agent(
    temperature: float = 0.0,
    max_retries: int = 3,
):
    """
    Streamlit에서 사용할 체크리스트 생성 Agent를 만든다.

    우선 Vertex AI 설정을 사용한다.
    .env 또는 st.secrets에 다음 값이 필요하다.
    - GOOGLE_CLOUD_PROJECT
    - GOOGLE_CLOUD_LOCATION, 기본 us-central1
    - GEMINI_MODEL, 기본 gemini-3.1-flash-lite

    Google AI Studio API Key를 사용할 경우 GEMINI_API_KEY도 지원한다.
    """
    if not LLM_IMPORT_AVAILABLE:
        raise RuntimeError(
            "pydantic-ai 관련 패키지를 불러오지 못했습니다. "
            "pip install pydantic-ai python-dotenv 명령으로 설치를 확인하세요."
        )

    if load_dotenv is not None:
        load_dotenv()

    google_cloud_project = _read_secret_or_env("GOOGLE_CLOUD_PROJECT")
    google_cloud_location = _read_secret_or_env("GOOGLE_CLOUD_LOCATION", "us-central1")
    gemini_model = _read_secret_or_env("GEMINI_MODEL", "gemini-3.1-flash-lite")
    gemini_api_key = _read_secret_or_env("GEMINI_API_KEY")

    provider = None

    if google_cloud_project:
        provider = GoogleProvider(
            vertexai=True,
            project=google_cloud_project,
            location=google_cloud_location,
        )
    elif gemini_api_key:
        provider = GoogleProvider(api_key=gemini_api_key)
    else:
        raise RuntimeError(
            "LLM 설정을 찾지 못했습니다. .env 또는 .streamlit/secrets.toml에 "
            "GOOGLE_CLOUD_PROJECT 또는 GEMINI_API_KEY를 설정해야 합니다."
        )

    model = GoogleModel(gemini_model, provider=provider)

    system_prompt = """
당신은 Steam 인디게임 출시 전 체크리스트를 작성하는 데이터 분석 보조자입니다.

당신의 역할은 우선순위 판단이 아니라 문장화입니다.
제공된 근거표의 fixed_priority를 반드시 그대로 사용하세요.
fixed_priority를 새로 계산하거나, 올리거나, 내리거나, 다른 우선순위 목록으로 옮기지 마세요.
근거표에 없는 issue_name_kor를 새로 만들지 마세요.
evidence_issue에는 근거표의 issue_name_kor 값을 그대로 작성하세요.
negative_game_count는 Steam 비추천 맥락 기준의 핵심 근거로 사용하세요.
High urgency 관련 값은 이전 LLM 리뷰 분류 결과를 집계한 보조 지표이므로, 단독 우선순위 기준으로 사용하지 마세요.
Steam 태그 DNA는 보조 근거로만 사용하고, 성공을 보장하는 표현을 쓰지 마세요.
체크리스트는 개발자가 출시 전에 실제로 확인할 수 있는 질문형 문장으로 작성하세요.
"""

    agent = Agent(
        model,
        output_type=PrelaunchChecklistResult,
        system_prompt=system_prompt,
        retries=max_retries,
        output_retries=3,
    )

    settings = GoogleModelSettings(temperature=temperature)

    return agent, settings


def generate_prelaunch_checklist_with_llm(
    checklist_prompt: str,
    temperature: float = 0.0,
    max_retries: int = 3,
) -> dict:
    """
    LLM을 호출해서 출시 전 체크리스트를 생성한다.
    """
    agent, settings = create_prelaunch_checklist_agent(
        temperature=temperature,
        max_retries=max_retries,
    )

    result = agent.run_sync(
        checklist_prompt,
        model_settings=settings,
    )

    return to_serializable(result.output)


# ============================================================
# LLM 결과 검증 / 표 변환
# ============================================================
def build_fixed_priority_maps(evidence_df: pd.DataFrame):
    priority_order_map = {"상": 1, "중": 2, "하": 3}
    work = evidence_df.copy()

    if "fixed_priority" not in work.columns and "priority_level" in work.columns:
        work["fixed_priority"] = work["priority_level"]

    if "source_condition" not in work.columns:
        work["source_condition"] = (
            work.get("condition_type", "").astype(str)
            + "="
            + work.get("condition_value", "").astype(str)
        )

    work["priority_order"] = work["fixed_priority"].map(priority_order_map).fillna(9)

    sort_cols = [
        "issue_name_kor",
        "priority_order",
        "issue_game_ratio",
        "issue_game_count",
        "negative_game_count",
        "total_issue_review_count",
    ]
    sort_cols = [col for col in sort_cols if col in work.columns]

    ascending_map = {
        "issue_name_kor": True,
        "priority_order": True,
        "issue_game_ratio": False,
        "issue_game_count": False,
        "negative_game_count": False,
        "total_issue_review_count": False,
    }
    ascending = [ascending_map[col] for col in sort_cols]

    fixed_priority_map = (
        work
        .sort_values(sort_cols, ascending=ascending)
        .drop_duplicates("issue_name_kor")
        .set_index("issue_name_kor")["fixed_priority"]
        .to_dict()
    ) if "issue_name_kor" in work.columns and "fixed_priority" in work.columns else {}

    source_condition_map = (
        work
        .groupby("issue_name_kor")["source_condition"]
        .apply(lambda x: sorted(set([str(v) for v in x if str(v).strip()])))
        .to_dict()
    ) if "issue_name_kor" in work.columns and "source_condition" in work.columns else {}

    return fixed_priority_map, source_condition_map


def validate_checklist_priority(result_dict: dict, evidence_df: pd.DataFrame) -> list[str]:
    fixed_priority_map, _ = build_fixed_priority_maps(evidence_df)

    priority_info = [
        ("상", "high_priority"),
        ("중", "mid_priority"),
        ("하", "low_priority"),
    ]

    warnings = []

    for bucket_priority, key in priority_info:
        items = result_dict.get(key, [])

        for item in items:
            issue_name = item.get("evidence_issue", item.get("issue_name", ""))
            item_priority = item.get("priority", "")
            fixed_priority = fixed_priority_map.get(issue_name)

            if fixed_priority is None:
                warnings.append(f"근거표에 없는 이슈가 LLM 결과에 포함됨: {issue_name}")
                continue

            if item_priority and item_priority != fixed_priority:
                warnings.append(
                    f"이슈 '{issue_name}'의 LLM priority={item_priority}, 근거표 fixed_priority={fixed_priority}"
                )

            if bucket_priority != fixed_priority:
                warnings.append(
                    f"이슈 '{issue_name}'가 {bucket_priority} 목록에 들어갔지만, 근거표 fixed_priority는 {fixed_priority}"
                )

    return warnings


def make_checklist_table(result_dict: dict, evidence_df: pd.DataFrame | None = None, drop_unknown_issues: bool = True) -> pd.DataFrame:
    rows = []

    priority_info = [
        ("상", "high_priority"),
        ("중", "mid_priority"),
        ("하", "low_priority"),
    ]

    fixed_priority_map = {}
    source_condition_map = {}

    if evidence_df is not None:
        fixed_priority_map, source_condition_map = build_fixed_priority_maps(evidence_df)

    for bucket_priority, key in priority_info:
        items = result_dict.get(key, [])

        for item in items:
            issue_name = item.get("evidence_issue", item.get("issue_name", ""))
            check_question = item.get("check_question", item.get("checklist_item", ""))
            category = item.get("category", "")

            if category == "":
                category = get_check_category(issue_name, check_question)

            fixed_priority = fixed_priority_map.get(issue_name, bucket_priority)

            if evidence_df is not None and drop_unknown_issues and issue_name not in fixed_priority_map:
                continue

            source_conditions = item.get("source_conditions", [])
            if not source_conditions:
                source_conditions = source_condition_map.get(issue_name, [])

            rows.append(
                {
                    "우선순위": fixed_priority,
                    "해석 방향": item.get("issue_direction", ""),
                    "구분": category,
                    "체크 질문": check_question,
                    "근거 이슈": issue_name,
                    "근거 요약": item.get("evidence_summary", ""),
                    "확인 방법": item.get("how_to_check", ""),
                    "근거 조건": ", ".join([str(x) for x in source_conditions]),
                }
            )

    out = pd.DataFrame(rows)

    if out.empty:
        return out

    order_map = {"상": 1, "중": 2, "하": 3}
    out["priority_order"] = out["우선순위"].map(order_map).fillna(9)
    out = out.sort_values(["priority_order", "구분", "근거 이슈"]).drop(columns="priority_order")

    return out.reset_index(drop=True)


def make_prelaunch_validation_result_df(result_dict: dict, evidence_df: pd.DataFrame) -> pd.DataFrame:
    warnings = validate_checklist_priority(result_dict, evidence_df)

    if not warnings:
        return pd.DataFrame([
            {
                "검증 항목": "LLM 체크리스트 우선순위 검증",
                "결과": "통과",
                "내용": "LLM 출력이 근거표의 fixed_priority 기준과 일치한다.",
            }
        ])

    return pd.DataFrame([
        {
            "검증 항목": "LLM 체크리스트 우선순위 검증",
            "결과": "보정 필요",
            "내용": warning,
        }
        for warning in warnings
    ])


def make_prelaunch_report_markdown(result_dict: dict, user_condition: dict, matched_game_count: int, matched_review_count: int) -> str:
    genres = ", ".join(user_condition.get("genres", [])) or "-"
    price_groups = ", ".join(get_condition_values(user_condition, "price_groups", "price_group")) or "-"
    steam_tags = ", ".join(user_condition.get("steam_tags", [])) or "-"
    play_styles = ", ".join(get_condition_values(user_condition, "play_styles", "play_style")) or "-"

    lines = []
    lines.append("## 1. 출시 전 LLM 체크리스트 생성")
    lines.append("")
    lines.append("개발자가 입력한 조건과 유사한 Steam 인디게임의 출시 초기 D0-D30 리뷰를 바탕으로, 출시 전 개발 단계에서 점검해야 할 항목을 LLM이 체크리스트로 정리한다.")
    lines.append("")
    lines.append("| 항목 | 값 |")
    lines.append("|---|---|")
    lines.append(f"| 입력 장르 | {genres} |")
    lines.append(f"| 입력 가격대 | {price_groups} |")
    lines.append(f"| 입력 Steam 태그 | {steam_tags} |")
    lines.append(f"| 입력 플레이 방식 | {play_styles} |")
    lines.append(f"| 입력 조건 직접 매칭 게임 수 | {matched_game_count:,}개 |")
    lines.append(f"| 입력 조건 직접 매칭 리뷰 수 | {matched_review_count:,}개 |")
    lines.append("")
    lines.append("체크리스트 생성에는 직접 매칭 결과뿐 아니라, 장르·가격대·Steam 태그·플레이 방식별 반복 이슈 근거도 함께 사용하였다.")
    lines.append("")
    lines.append("## 2. 체크리스트 판단 기준")
    lines.append("")
    lines.append("- **LLM은 우선순위를 직접 정하지 않는다.**")
    lines.append("- 체크리스트 우선순위는 사전에 계산한 `priority_level`을 `fixed_priority`로 전달해 그대로 사용한다.")
    lines.append("- 우선순위는 이슈 발생 게임 수, 조건 내 발생 비율, Steam 비추천 맥락 발생 게임 수를 기준으로 계산한 값이다.")
    lines.append("- `High urgency`는 이전 LLM 리뷰 분류 결과에서 나온 보조 지표이며, 우선순위 산정 기준으로 직접 사용하지 않는다.")
    lines.append("- LLM은 계산된 근거를 바탕으로 체크 질문과 확인 방법을 문장화하는 역할만 한다.")
    lines.append("")

    if result_dict.get("condition_summary"):
        lines.append("## 3. 입력 조건 요약")
        lines.append("")
        lines.append(result_dict.get("condition_summary", ""))
        lines.append("")

    if result_dict.get("data_summary"):
        lines.append("## 4. 데이터 요약")
        lines.append("")
        lines.append(result_dict.get("data_summary", ""))
        lines.append("")

    if result_dict.get("tag_dna_summary"):
        lines.append("## 5. Steam 태그 DNA 참고")
        lines.append("")
        lines.append(result_dict.get("tag_dna_summary", ""))
        lines.append("")

    if result_dict.get("final_summary"):
        lines.append("## 6. 최종 요약")
        lines.append("")
        lines.append(result_dict.get("final_summary", ""))
        lines.append("")

    cautions = result_dict.get("cautions", [])
    if cautions:
        lines.append("## 7. 해석 시 주의사항")
        lines.append("")
        for caution in cautions:
            lines.append(f"- {caution}")
        lines.append("")

    return "\n".join(lines)
