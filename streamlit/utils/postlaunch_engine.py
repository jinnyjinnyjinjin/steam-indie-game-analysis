from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
from datetime import datetime, date
from typing import Any, List, Literal

import pandas as pd
import streamlit as st

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

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

REQUIRED_PREPROCESS_FILES = {
    "review_base": "postlaunch_review_base.csv",
    "issue_summary": "postlaunch_issue_summary.csv",
    "evidence_base": "postlaunch_patch_ops_evidence_base.csv",
    "tableau_source": "tableau_postlaunch_patch_ops_source.csv",
}

ACTION_GROUP_ORDER = {
    "즉시 확인": 1,
    "단기 개선": 2,
    "운영 커뮤니케이션 개선": 3,
    "장기 검토": 4,
    "검토 필요": 5,
    "강점 유지": 6,
}

PRIORITY_ORDER = {"상": 1, "중": 2, "하": 3}

DEFAULT_GROUP_LIMITS = {
    "즉시 확인": 5,
    "단기 개선": 6,
    "운영 커뮤니케이션 개선": 3,
    "장기 검토": 4,
    "검토 필요": 2,
    "강점 유지": 3,
}


# ============================================================
# 경로 관련 함수
# ============================================================
def find_project_root() -> Path:
    """
    현재 파일 위치 기준으로 프로젝트 루트를 찾는다.
    프로젝트 루트에는 data 폴더가 있다고 가정한다.
    """
    current = Path(__file__).resolve()

    for parent in current.parents:
        if (parent / "data").exists():
            return parent

    return current.parents[2]


def get_postlaunch_output_dir(run_name: str = DEFAULT_RUN_NAME) -> Path:
    """
    기준 구조:
    data/outputs/postlaunch/master/
    """
    root = find_project_root()
    return root / "data" / "outputs" / "postlaunch" / run_name


def get_postlaunch_preprocess_dir(run_name: str = DEFAULT_RUN_NAME) -> Path:
    """
    출시 후 분석용 전처리 결과 폴더를 반환한다.

    1순위:
    data/outputs/postlaunch/master/postlaunch_preprocess_data/

    2순위:
    data/outputs/postlaunch/master/
    """
    output_dir = get_postlaunch_output_dir(run_name)
    preprocess_dir = output_dir / "postlaunch_preprocess_data"

    if preprocess_dir.exists():
        return preprocess_dir

    return output_dir


def get_postlaunch_llm_cache_dir(run_name: str = DEFAULT_RUN_NAME) -> Path:
    """
    Streamlit에서 생성한 출시 후 LLM 리포트 캐시 폴더를 반환한다.
    """
    cache_dir = get_postlaunch_output_dir(run_name) / "postlaunch_report_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


# ============================================================
# 데이터 로드
# ============================================================
@st.cache_data(show_spinner="출시 후 분석 데이터를 불러오는 중...")
def load_postlaunch_data(run_name: str = DEFAULT_RUN_NAME) -> dict:
    """
    출시 후 분석용 CSV를 불러온다.
    """
    data_dir = get_postlaunch_preprocess_dir(run_name)

    missing_files = []
    paths = {}

    for key, filename in REQUIRED_PREPROCESS_FILES.items():
        path = data_dir / filename
        paths[key] = path

        if not path.exists():
            missing_files.append(str(path))

    if missing_files:
        missing_text = "\n".join(missing_files)
        raise FileNotFoundError(
            "필수 CSV 파일을 찾을 수 없습니다.\n"
            f"실행 기준: {run_name}\n"
            f"기준 폴더: {data_dir}\n\n"
            f"{missing_text}"
        )

    review_base = pd.read_csv(paths["review_base"])
    issue_summary = pd.read_csv(paths["issue_summary"])
    evidence_base = pd.read_csv(paths["evidence_base"])
    tableau_source = pd.read_csv(paths["tableau_source"])

    for df in [review_base, issue_summary, evidence_base, tableau_source]:
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    for df in [review_base, tableau_source]:
        for col in ["review_datetime", "release_date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

    return {
        "run_name": run_name,
        "output_dir": str(get_postlaunch_output_dir(run_name)),
        "data_dir": str(data_dir),
        "review_base": review_base,
        "issue_summary": issue_summary,
        "evidence_base": evidence_base,
        "tableau_source": tableau_source,
    }


# ============================================================
# 안전 변환 / 공통 보조 함수
# ============================================================
def make_json_safe(obj: Any) -> Any:
    """
    json.dumps()에서 오류가 나는 numpy/pandas 타입을 Python 기본 타입으로 변환한다.
    """
    if isinstance(obj, dict):
        return {str(key): make_json_safe(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [make_json_safe(value) for value in obj]

    if isinstance(obj, tuple):
        return [make_json_safe(value) for value in obj]

    if np is not None:
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)

    if isinstance(obj, pd.Timestamp):
        if pd.isna(obj):
            return None
        return obj.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if hasattr(obj, "model_dump"):
        return make_json_safe(obj.model_dump())

    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass

    return obj


def safe_rate(numerator, denominator) -> float:
    if denominator is None or pd.isna(denominator) or denominator == 0:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def safe_int(value, default=0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(value)
    except Exception:
        return default


def shorten_text(value, max_chars=180) -> str:
    text = "" if pd.isna(value) else str(value)
    text = text.replace("\n", " ").strip()

    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "..."

    return text


def value_count_text(series: pd.Series) -> str:
    if series is None or series.empty:
        return ""

    counts = series.value_counts(dropna=False)
    return ", ".join([f"{idx}: {cnt}" for idx, cnt in counts.items()])


def is_negative_or_mixed(value: str) -> bool:
    text = str(value).lower()
    return any(word in text for word in ["negative", "mixed", "부정", "혼합", "bad", "neutral"])


def is_high_urgency(value: str) -> bool:
    text = str(value).lower()
    return any(word in text for word in ["high", "상", "높음", "urgent", "critical"])


def filter_by_appid(df: pd.DataFrame, appid) -> pd.DataFrame:
    if df is None or df.empty or "appid" not in df.columns:
        return pd.DataFrame()

    return df[df["appid"].astype(str) == str(appid)].copy().reset_index(drop=True)


def add_order_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "action_group_hint" in out.columns:
        out["action_order"] = out["action_group_hint"].map(ACTION_GROUP_ORDER).fillna(9)
    else:
        out["action_order"] = 9

    if "rule_priority_hint" in out.columns:
        out["priority_order"] = out["rule_priority_hint"].map(PRIORITY_ORDER).fillna(9)
    else:
        out["priority_order"] = 9

    return out


def dataframe_to_markdown_table(df: pd.DataFrame) -> str:
    """
    pandas.to_markdown() 없이 Markdown 표를 직접 만든다.
    tabulate 패키지 의존성을 없앤다.
    """
    if df is None or df.empty:
        return ""

    work = df.copy()

    for col in work.columns:
        work[col] = (
            work[col]
            .fillna("")
            .astype(str)
            .str.replace("|", " / ", regex=False)
            .str.replace("\n", "<br>", regex=False)
        )

    headers = [str(col) for col in work.columns]
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"

    body_lines = []
    for _, row in work.iterrows():
        body_lines.append("| " + " | ".join([str(row[col]) for col in work.columns]) + " |")

    return "\n".join([header_line, separator_line] + body_lines)


def df_to_text_table(df: pd.DataFrame, columns: list[str], max_rows=20, max_cell_chars=180) -> str:
    """
    LLM 프롬프트에 넣을 간단한 텍스트 표를 만든다.
    """
    if df is None or df.empty:
        return "해당 조건에 맞는 근거 데이터가 없습니다."

    cols = [col for col in columns if col in df.columns]
    if len(cols) == 0:
        return "표시할 수 있는 근거 컬럼이 없습니다."

    small = df[cols].head(max_rows).copy()

    lines = []
    header = " | ".join(cols)
    lines.append(header)
    lines.append("-" * len(header))

    for _, row in small.iterrows():
        values = [shorten_text(row.get(col, ""), max_cell_chars) for col in cols]
        lines.append(" | ".join(values))

    return "\n".join(lines)


# ============================================================
# 게임 선택 / 분석 개요
# ============================================================
def get_game_options(review_base: pd.DataFrame, evidence_base: pd.DataFrame) -> pd.DataFrame:
    """
    Streamlit selectbox용 게임 목록을 만든다.
    """
    source = review_base.copy()

    if source.empty or not {"appid", "game_name"}.issubset(source.columns):
        source = evidence_base.copy()

    if source.empty or not {"appid", "game_name"}.issubset(source.columns):
        return pd.DataFrame(columns=["appid", "game_name", "game_label"])

    game_options = (
        source[["appid", "game_name"]]
        .dropna(subset=["appid", "game_name"])
        .drop_duplicates()
        .copy()
    )

    game_options["game_label"] = (
        game_options["game_name"].astype(str)
        + " (appid: "
        + game_options["appid"].astype(str)
        + ")"
    )

    return game_options.sort_values("game_name").reset_index(drop=True)


def make_analysis_overview(
    review_base: pd.DataFrame,
    tableau_source: pd.DataFrame,
    selected_appid,
    selected_game_name: str,
) -> dict:
    review_game = filter_by_appid(review_base, selected_appid)
    tableau_game = filter_by_appid(tableau_source, selected_appid)

    review_count = len(review_game)
    issue_tag_count = len(tableau_game)

    steam_negative_count = 0
    if "steam_negative_flag" in review_game.columns:
        steam_negative_count = int(review_game["steam_negative_flag"].sum())
    elif "steam_label_text" in review_game.columns:
        steam_negative_count = int(
            review_game["steam_label_text"].astype(str).str.lower().str.contains("negative|비추천").sum()
        )
    elif "voted_up" in review_game.columns:
        steam_negative_count = int((review_game["voted_up"] == False).sum())

    llm_negative_mixed_count = 0
    if "llm_negative_or_mixed_flag" in review_game.columns:
        llm_negative_mixed_count = int(review_game["llm_negative_or_mixed_flag"].sum())
    elif "llm_sentiment" in review_game.columns:
        llm_negative_mixed_count = int(review_game["llm_sentiment"].apply(is_negative_or_mixed).sum())

    high_urgency_count = 0
    if "high_urgency_flag" in review_game.columns:
        high_urgency_count = int(review_game["high_urgency_flag"].sum())
    elif "llm_urgency_candidate" in review_game.columns:
        high_urgency_count = int(review_game["llm_urgency_candidate"].apply(is_high_urgency).sum())
    elif "urgency" in review_game.columns:
        high_urgency_count = int(review_game["urgency"].apply(is_high_urgency).sum())

    recent_30d_count = 0
    if "recent_30d_flag" in review_game.columns:
        recent_30d_count = int(review_game["recent_30d_flag"].sum())

    avg_playtime = None
    median_playtime = None
    if "playtime_at_review_hours" in review_game.columns and not review_game.empty:
        avg_playtime = round(review_game["playtime_at_review_hours"].mean(), 1)
        median_playtime = round(review_game["playtime_at_review_hours"].median(), 1)

    review_date_min = ""
    review_date_max = ""
    if "review_datetime" in review_game.columns and not review_game["review_datetime"].isna().all():
        review_date_min = review_game["review_datetime"].min().strftime("%Y-%m-%d")
        review_date_max = review_game["review_datetime"].max().strftime("%Y-%m-%d")

    steam_label_distribution = ""
    if "steam_label_text" in review_game.columns:
        steam_label_distribution = value_count_text(review_game["steam_label_text"])

    llm_sentiment_distribution = ""
    if "llm_sentiment" in review_game.columns:
        llm_sentiment_distribution = value_count_text(review_game["llm_sentiment"])

    return make_json_safe(
        {
            "game_name": selected_game_name,
            "appid": selected_appid,
            "review_count": int(review_count),
            "issue_tag_count": int(issue_tag_count),
            "review_date_min": review_date_min,
            "review_date_max": review_date_max,
            "steam_negative_review_count": steam_negative_count,
            "llm_negative_mixed_review_count": llm_negative_mixed_count,
            "high_urgency_review_count": high_urgency_count,
            "recent_30d_review_count": recent_30d_count,
            "steam_negative_rate": safe_rate(steam_negative_count, review_count),
            "llm_negative_mixed_rate": safe_rate(llm_negative_mixed_count, review_count),
            "high_urgency_rate": safe_rate(high_urgency_count, review_count),
            "avg_playtime_at_review_hours": avg_playtime,
            "median_playtime_at_review_hours": median_playtime,
            "steam_label_distribution": steam_label_distribution,
            "llm_sentiment_distribution": llm_sentiment_distribution,
        }
    )


# ============================================================
# LLM 입력용 근거 데이터 선택
# ============================================================
def select_patch_ops_evidence(
    evidence_base: pd.DataFrame,
    selected_appid,
    max_issues: int = 18,
    group_limits: dict | None = None,
) -> pd.DataFrame:
    """
    LLM 프롬프트에 넣을 대표 이슈 근거를 선택한다.
    대응 구분별 대표 이슈를 고르고, 우선순위는 근거 데이터의 rule_priority_hint를 그대로 사용한다.
    """
    group_limits = group_limits or DEFAULT_GROUP_LIMITS
    work = filter_by_appid(evidence_base, selected_appid)

    if work.empty:
        return pd.DataFrame()

    work = add_order_columns(work)

    sort_cols = [
        "action_order",
        "priority_order",
        "negative_mixed_review_count",
        "steam_negative_review_count",
        "recent_30d_negative_mixed_review_count",
        "affected_review_count",
    ]
    sort_cols = [col for col in sort_cols if col in work.columns]
    ascending = [True, True] + [False] * max(0, len(sort_cols) - 2)

    work = work.sort_values(sort_cols, ascending=ascending)

    selected_parts = []
    for group_name, limit in group_limits.items():
        if "action_group_hint" in work.columns:
            part = work[work["action_group_hint"] == group_name].head(limit)
            if not part.empty:
                selected_parts.append(part)

    if selected_parts:
        selected = pd.concat(selected_parts, ignore_index=True)
    else:
        selected = work.copy()

    if "issue_name_kor" in selected.columns:
        selected = selected.drop_duplicates("issue_name_kor")

    selected = selected.head(max_issues).copy()
    selected = add_order_columns(selected)
    selected = selected.sort_values(sort_cols, ascending=ascending)

    return selected.drop(columns=["action_order", "priority_order"], errors="ignore").reset_index(drop=True)


# ============================================================
# LLM 출력 스키마
# ============================================================
if LLM_IMPORT_AVAILABLE:
    class PatchOpsItem(BaseModel):
        action_group: Literal[
            "즉시 확인",
            "단기 개선",
            "운영 커뮤니케이션 개선",
            "장기 검토",
            "강점 유지",
            "검토 필요",
        ] = Field(description="근거표의 action_group_hint를 그대로 복사한 대응 구분")
        priority: Literal["상", "중", "하"] = Field(description="근거표의 rule_priority_hint를 그대로 복사한 고정 우선 검토 수준")
        issue_name: str = Field(description="근거가 된 이슈명. 반드시 근거표의 issue_name_kor 값 중 하나를 그대로 사용")
        patch_ops_direction: str = Field(description="해당 이슈에 대한 패치·운영 방향 요약")
        detailed_actions: List[str] = Field(description="실제로 검토할 세부 실행안 2~4개")
        evidence_summary: str = Field(description="제공된 근거표의 수치와 대표 리뷰 근거를 바탕으로 한 요약")
        expected_effect: str = Field(description="이 대응이 기대하는 유저 경험 개선 효과")
        caution: str = Field(description="해석이나 실행 시 주의해야 할 점")

    class PostLaunchPatchOpsResult(BaseModel):
        game_summary: str = Field(description="게임과 분석 데이터 규모 요약")
        current_status_summary: str = Field(description="현재 리뷰 상태 요약")
        immediate_actions: List[PatchOpsItem] = Field(default_factory=list, description="즉시 확인 항목")
        short_term_improvements: List[PatchOpsItem] = Field(default_factory=list, description="단기 개선 항목")
        operation_communication: List[PatchOpsItem] = Field(default_factory=list, description="운영 커뮤니케이션 개선 항목")
        long_term_reviews: List[PatchOpsItem] = Field(default_factory=list, description="장기 검토 또는 검토 필요 항목")
        strengths_to_keep: List[PatchOpsItem] = Field(default_factory=list, description="강점 유지 항목")
        operation_notes: List[str] = Field(default_factory=list, description="패치 노트, 커뮤니티 공지, 모니터링 관점 제안")
        cautions: List[str] = Field(default_factory=list, description="해석 시 주의사항")
        final_summary: str = Field(description="최종 요약")
else:
    PatchOpsItem = None
    PostLaunchPatchOpsResult = None


# ============================================================
# LLM 캐시
# ============================================================
def make_postlaunch_cache_key(selected_appid, selected_evidence_df: pd.DataFrame) -> str:
    issue_cols = [
        "appid",
        "issue_name_kor",
        "action_group_hint",
        "rule_priority_hint",
        "affected_review_count",
        "negative_mixed_review_count",
        "steam_negative_review_count",
        "recent_30d_negative_mixed_review_count",
        "priority_rule_detail",
    ]
    issue_cols = [col for col in issue_cols if col in selected_evidence_df.columns]

    payload = {
        "appid": str(selected_appid),
        "evidence": selected_evidence_df[issue_cols].fillna("").astype(str).to_dict("records"),
    }

    raw = json.dumps(make_json_safe(payload), ensure_ascii=False, sort_keys=True)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def get_postlaunch_cache_path(run_name: str, selected_appid, cache_key: str) -> Path:
    return get_postlaunch_llm_cache_dir(run_name) / f"postlaunch_patch_ops_{selected_appid}_{cache_key}.json"


def load_cached_postlaunch_result(run_name: str, selected_appid, cache_key: str) -> dict | None:
    path = get_postlaunch_cache_path(run_name, selected_appid, cache_key)
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cached_postlaunch_result(run_name: str, selected_appid, cache_key: str, result_dict: dict, analysis_overview: dict) -> Path:
    path = get_postlaunch_cache_path(run_name, selected_appid, cache_key)
    payload = {
        "meta": {
            "appid": str(selected_appid),
            "game_name": analysis_overview.get("game_name", ""),
            "cache_key": cache_key,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
        "result": make_json_safe(result_dict),
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return path


def extract_cached_result(cached_payload: dict | None) -> dict | None:
    if not cached_payload:
        return None

    if "result" in cached_payload:
        return cached_payload["result"]

    return cached_payload


# ============================================================
# 프롬프트 생성
# ============================================================
def build_patch_ops_prompt(
    analysis_overview: dict,
    selected_evidence_df: pd.DataFrame,
    max_issues_for_prompt: int = 18,
    max_evidence_text_issues: int = 12,
) -> str:
    selected_evidence_df = selected_evidence_df.copy()
    target_game_name = analysis_overview.get("game_name", "선택 게임")

    evidence_cols = [
        "issue_name_kor",
        "action_group_hint",
        "rule_priority_hint",
        "priority_rule_detail",
        "affected_review_count",
        "negative_mixed_review_count",
        "steam_negative_review_count",
        "recent_30d_negative_mixed_review_count",
        "early_playtime_negative_mixed_review_count",
        "high_urgency_review_count",
        "high_urgency_rate",
        "negative_mixed_rate",
        "steam_negative_rate",
        "priority_reason",
        "patch_ops_note",
    ]
    evidence_cols = [col for col in evidence_cols if col in selected_evidence_df.columns]

    evidence_text = df_to_text_table(
        selected_evidence_df,
        columns=evidence_cols,
        max_rows=max_issues_for_prompt,
        max_cell_chars=180,
    )

    if "llm_evidence_text" in selected_evidence_df.columns:
        review_evidence_text = "\n\n".join(
            selected_evidence_df["llm_evidence_text"].head(max_evidence_text_issues).fillna("").astype(str).tolist()
        )
    else:
        review_evidence_text = "대표 리뷰 근거 컬럼이 없습니다."

    overview_json = json.dumps(make_json_safe(analysis_overview), ensure_ascii=False, indent=2)

    prompt = f"""
당신은 Steam 인디게임의 출시 후 패치·운영 전략을 정리하는 데이터 분석 보조자입니다.

목표:
{target_game_name}의 Steam 리뷰를 LLM으로 분류한 결과와 근거 집계 단계에서 집계한 이슈별 근거표를 바탕으로
개발자가 바로 읽을 수 있는 패치·운영 방향 제안 리포트를 작성하세요.

가장 중요한 제한:
- 당신은 상·중·하 우선 검토 수준을 새로 계산하거나 판단하지 않습니다.
- 근거표의 action_group_hint는 이미 근거 집계 단계에서 데이터 기준으로 계산된 대응 구분입니다.
- 근거표의 rule_priority_hint는 이미 근거 집계 단계에서 데이터 기준으로 계산된 고정 우선 검토 수준입니다.
- 각 항목의 action_group은 반드시 근거표의 action_group_hint를 그대로 사용하세요.
- 각 항목의 priority는 반드시 근거표의 rule_priority_hint를 그대로 사용하세요.
- action_group_hint를 바꾸거나, rule_priority_hint를 올리거나 내리지 마세요.
- 근거표에 없는 issue_name_kor를 새로 만들지 마세요.
- issue_name에는 반드시 근거표에 있는 issue_name_kor 값을 그대로 작성하세요.
- High urgency는 04번 리뷰 분류 단계에서 LLM이 분류한 보조 지표입니다.
- High urgency를 근거로 우선 검토 수준을 새로 판단하거나, 우선 검토 수준을 올리지 마세요.

우선 검토 수준 해석 기준:
- rule_priority_hint는 근거 집계 단계에서 부정·혼합 리뷰 수, Steam 비추천 리뷰 수, 최근 30일 반복 여부, 짧은 플레이타임 부정 반응을 기준으로 계산되었습니다.
- priority_rule_detail은 rule_priority_hint가 부여된 규칙 설명입니다.
- priority_reason은 수치 근거를 사람이 읽기 쉽게 정리한 문장입니다.
- LLM은 이 값을 해석해 문장으로 풀어쓰되, 순위 자체를 바꾸지 않습니다.

작성 기준:
- 패치·운영 제안은 개발자가 실제로 실행할 수 있는 문장으로 작성하세요.
- 즉시 확인 항목은 재현, 로그 확인, 진행 차단 여부, 크래시/성능/저장 문제 확인처럼 구체적으로 작성하세요.
- 단기 개선 항목은 경험 품질을 낮추는 반복 문제를 다음 패치에서 점검하는 방향으로 작성하세요.
- 운영 커뮤니케이션 개선 항목은 패치 노트, 공지, 커뮤니티 응답, 알려진 이슈 안내 관점으로 작성하세요.
- 장기 검토 항목은 개발 범위가 큰 콘텐츠, 스토리, 구조 개선을 로드맵 관점으로 작성하세요.
- 강점 유지 항목은 업데이트와 커뮤니티 메시지에서 계속 살릴 요소로 작성하세요.
- 리뷰 수나 LLM 분류만으로 실제 버그 원인을 확정하지 마세요.
- "반드시 개선된다", "성공한다" 같은 보장 표현은 쓰지 마세요.

분석 대상 요약:
{overview_json}

이슈별 집계 근거표:
{evidence_text}

대표 리뷰 근거와 LLM 개선 제안 후보:
{review_evidence_text}

출력 요구:
1. game_summary에는 게임과 데이터 규모를 간단히 요약하세요.
2. current_status_summary에는 현재 리뷰 상태를 2~3문장으로 요약하세요.
3. immediate_actions에는 action_group_hint가 "즉시 확인"인 항목만 작성하세요.
4. short_term_improvements에는 action_group_hint가 "단기 개선"인 항목만 작성하세요.
5. operation_communication에는 action_group_hint가 "운영 커뮤니케이션 개선"인 항목만 작성하세요.
6. long_term_reviews에는 action_group_hint가 "장기 검토" 또는 "검토 필요"인 항목만 작성하세요.
7. strengths_to_keep에는 action_group_hint가 "강점 유지"인 항목만 작성하세요.
8. 각 항목은 issue_name, priority, action_group, patch_ops_direction, detailed_actions, evidence_summary, expected_effect, caution을 포함해야 합니다.
9. evidence_summary에는 가능한 한 affected_review_count, negative_mixed_review_count, steam_negative_review_count, recent_30d_negative_mixed_review_count 중 2개 이상을 포함하세요.
10. operation_notes에는 패치 노트, 커뮤니티 공지, 모니터링 관점의 운영 제안을 작성하세요.
11. cautions에는 리뷰 기반 분석의 한계와 추가 확인 필요성을 작성하세요.
12. final_summary에는 전체 패치·운영 방향을 3~5문장으로 정리하세요.
"""

    return prompt.strip()


# ============================================================
# PydanticAI / Gemini Agent
# ============================================================
def _read_secret_or_env(name: str, default: str | None = None) -> str | None:
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass

    return os.getenv(name, default)


@st.cache_resource(show_spinner=False)
def create_postlaunch_patch_ops_agent(temperature: float = 0.0, max_retries: int = 3):
    """
    Streamlit에서 사용할 패치·운영 전략 생성 Agent를 만든다.

    .env 또는 st.secrets에 다음 값 중 하나가 필요하다.
    - Vertex AI: GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GEMINI_MODEL
    - API Key : GEMINI_API_KEY, GEMINI_MODEL
    """
    if not LLM_IMPORT_AVAILABLE:
        raise RuntimeError(
            "pydantic-ai 관련 패키지를 불러오지 못했습니다. "
            "pip install pydantic-ai python-dotenv 명령으로 설치를 확인하세요."
        )

    if load_dotenv is not None:
        root = find_project_root()
        load_dotenv()
        load_dotenv(root / ".env")
        load_dotenv(root / "streamlit" / ".env")

    google_cloud_project = _read_secret_or_env("GOOGLE_CLOUD_PROJECT")
    google_cloud_location = _read_secret_or_env("GOOGLE_CLOUD_LOCATION", "us-central1")
    gemini_model = _read_secret_or_env("GEMINI_MODEL", "gemini-3.1-flash-lite")
    gemini_api_key = _read_secret_or_env("GEMINI_API_KEY")

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
당신은 Steam 인디게임의 출시 후 패치·운영 전략을 정리하는 데이터 분석 보조자입니다.

당신의 역할은 우선 검토 수준 판단이 아니라 문장화와 전략 초안 작성입니다.
제공된 근거표의 action_group_hint와 rule_priority_hint를 반드시 그대로 사용하세요.
action_group_hint를 바꾸거나, rule_priority_hint를 새로 계산하거나, 올리거나, 내리지 마세요.
근거표에 없는 issue_name_kor를 새로 만들지 마세요.
issue_name에는 근거표의 issue_name_kor 값을 그대로 작성하세요.
priority_rule_detail과 priority_reason은 근거 집계 단계에서 계산된 규칙 기반 근거입니다.
High urgency는 이전 LLM 리뷰 분류 결과를 집계한 보조 지표이므로, 단독 우선 검토 수준 기준으로 사용하지 마세요.
리뷰 수, 부정·혼합 리뷰 수, Steam 비추천 리뷰 수, 최근 30일 반복 여부, 짧은 플레이타임 이슈를 함께 언급하세요.
실제 원인이 확정된 것처럼 단정하지 말고, 패치와 운영에서 확인해야 할 방향으로 표현하세요.
"""

    agent = Agent(
        model,
        output_type=PostLaunchPatchOpsResult,
        system_prompt=system_prompt,
        retries=max_retries,
        output_retries=3,
    )

    settings = GoogleModelSettings(temperature=temperature)
    return agent, settings


def generate_postlaunch_patch_ops_with_llm(patch_ops_prompt: str, temperature: float = 0.0, max_retries: int = 3) -> dict:
    """
    LLM을 호출해서 출시 후 패치·운영 방향 리포트를 생성한다.
    """
    agent, settings = create_postlaunch_patch_ops_agent(
        temperature=temperature,
        max_retries=max_retries,
    )

    result = agent.run_sync(patch_ops_prompt, model_settings=settings)

    output = getattr(result, "output", None)
    if output is None:
        output = getattr(result, "data", None)

    if output is None:
        raise RuntimeError("LLM 결과 객체에서 output/data를 찾지 못했습니다.")

    return make_json_safe(output)


# ============================================================
# LLM 결과 검증 / 변환
# ============================================================
def iter_all_items(result_dict: dict | None) -> list[dict]:
    if not result_dict:
        return []

    sections = [
        "immediate_actions",
        "short_term_improvements",
        "operation_communication",
        "long_term_reviews",
        "strengths_to_keep",
    ]

    items = []
    for section in sections:
        section_items = result_dict.get(section, []) or []
        for item in section_items:
            if isinstance(item, dict):
                item = item.copy()
                item["_section"] = section
                items.append(item)

    return items


def validate_patch_ops_result(result_dict: dict | None, evidence_df: pd.DataFrame) -> list[str]:
    """
    LLM 결과가 근거 데이터 표의 action_group_hint, rule_priority_hint를 바꾸지 않았는지 확인한다.
    """
    warnings = []

    if not result_dict:
        return ["LLM 결과가 아직 생성되지 않았습니다."]

    if evidence_df.empty:
        return ["비교할 근거표가 없습니다."]

    required_cols = {"issue_name_kor", "action_group_hint", "rule_priority_hint"}
    if not required_cols.issubset(evidence_df.columns):
        return ["근거표에 검증에 필요한 컬럼이 없습니다."]

    evidence_map = {}
    for _, row in evidence_df.iterrows():
        issue_name = str(row.get("issue_name_kor", ""))
        if issue_name:
            evidence_map[issue_name] = {
                "action_group": str(row.get("action_group_hint", "")),
                "priority": str(row.get("rule_priority_hint", "")),
            }

    for item in iter_all_items(result_dict):
        issue_name = str(item.get("issue_name", ""))
        action_group = str(item.get("action_group", ""))
        priority = str(item.get("priority", ""))

        if issue_name not in evidence_map:
            warnings.append(f"근거표에 없는 이슈가 LLM 결과에 포함됨: {issue_name}")
            continue

        expected_action = evidence_map[issue_name]["action_group"]
        expected_priority = evidence_map[issue_name]["priority"]

        if action_group != expected_action:
            warnings.append(
                f"대응 구분 불일치: {issue_name} / LLM={action_group} / 근거표={expected_action}"
            )

        if priority != expected_priority:
            warnings.append(
                f"우선 검토 수준 불일치: {issue_name} / LLM={priority} / 근거표={expected_priority}"
            )

    return warnings


def make_validation_result_df(warnings: list[str]) -> pd.DataFrame:
    if not warnings:
        return pd.DataFrame(
            [
                {
                    "검증 항목": "LLM 출력 검증",
                    "결과": "통과",
                    "내용": "LLM 결과가 근거 데이터 표의 대응 구분과 우선 검토 수준을 그대로 사용했다.",
                }
            ]
        )

    return pd.DataFrame(
        [
            {
                "검증 항목": "LLM 출력 검증",
                "결과": "확인 필요",
                "내용": warning,
            }
            for warning in warnings
        ]
    )


def make_patch_ops_strategy_table(result_dict: dict | None) -> pd.DataFrame:
    """
    LLM 결과를 패치 및 운영 제안 탭에서 사용할 카드/표 데이터로 변환한다.
    """
    items = iter_all_items(result_dict)

    rows = []
    for item in items:
        detailed_actions = item.get("detailed_actions", []) or []
        if isinstance(detailed_actions, list):
            detailed_actions_text = "\n".join([f"- {x}" for x in detailed_actions])
        else:
            detailed_actions_text = str(detailed_actions)

        rows.append(
            {
                "대응 구분": item.get("action_group", ""),
                "우선 검토 수준": item.get("priority", ""),
                "이슈": item.get("issue_name", ""),
                "패치·운영 방향": item.get("patch_ops_direction", ""),
                "세부 실행안": detailed_actions_text,
                "근거 요약": item.get("evidence_summary", ""),
                "기대 효과": item.get("expected_effect", ""),
                "주의사항": item.get("caution", ""),
                "section": item.get("_section", ""),
            }
        )

    strategy_df = pd.DataFrame(rows)

    if strategy_df.empty:
        return strategy_df

    strategy_df["action_order"] = strategy_df["대응 구분"].map(ACTION_GROUP_ORDER).fillna(9)
    strategy_df["priority_order"] = strategy_df["우선 검토 수준"].map(PRIORITY_ORDER).fillna(9)
    strategy_df = strategy_df.sort_values(["action_order", "priority_order", "이슈"])
    strategy_df = strategy_df.drop(columns=["action_order", "priority_order"])

    return strategy_df.reset_index(drop=True)


# ============================================================
# 리포트 Markdown 생성
# ============================================================
def make_analysis_overview_markdown(analysis_overview: dict) -> str:
    game_name = analysis_overview.get("game_name", "")
    appid = analysis_overview.get("appid", "")
    review_count = analysis_overview.get("review_count", 0)
    issue_tag_count = analysis_overview.get("issue_tag_count", 0)
    date_min = analysis_overview.get("review_date_min", "")
    date_max = analysis_overview.get("review_date_max", "")
    negative_mixed_count = analysis_overview.get("llm_negative_mixed_review_count", 0)
    negative_mixed_rate = analysis_overview.get("llm_negative_mixed_rate", 0) * 100
    steam_negative_count = analysis_overview.get("steam_negative_review_count", 0)
    steam_negative_rate = analysis_overview.get("steam_negative_rate", 0) * 100
    high_count = analysis_overview.get("high_urgency_review_count", 0)
    high_rate = analysis_overview.get("high_urgency_rate", 0) * 100
    avg_playtime = analysis_overview.get("avg_playtime_at_review_hours")
    median_playtime = analysis_overview.get("median_playtime_at_review_hours")

    lines = []
    lines.append("## 1. 분석 개요")
    lines.append("")
    lines.append(
        f"본 분석은 **{game_name}**(`appid: {appid}`)의 Steam 리뷰를 기반으로, "
        "출시 후 유저 반응에서 반복적으로 나타나는 이슈를 확인하고 패치 및 운영 방향을 정리하기 위한 분석이다."
    )
    lines.append("")

    if date_min and date_max:
        lines.append(
            f"분석에 포함된 리뷰 기간은 **{date_min}부터 {date_max}까지**이며, "
            f"총 **{review_count:,}개 리뷰**와 **{issue_tag_count:,}개 이슈 태그**를 기준으로 판단하였다."
        )
    else:
        lines.append(
            f"분석에는 총 **{review_count:,}개 리뷰**와 **{issue_tag_count:,}개 이슈 태그**가 사용되었다."
        )

    lines.append("")
    lines.append(
        f"LLM 기준 부정·혼합 리뷰는 **{negative_mixed_count:,}개({negative_mixed_rate:.1f}%)**로 집계되었고, "
        f"Steam 비추천 리뷰는 **{steam_negative_count:,}개({steam_negative_rate:.1f}%)**로 확인되었다. "
        f"또한 LLM이 리뷰 문맥상 빠른 확인이 필요하다고 분류한 High urgency 리뷰는 "
        f"**{high_count:,}개({high_rate:.1f}%)**다."
    )

    if avg_playtime is not None and median_playtime is not None:
        lines.append("")
        lines.append(
            f"리뷰 작성 시점의 평균 플레이타임은 **{avg_playtime}시간**, 중앙값은 **{median_playtime}시간**이다. "
            "따라서 일부 이슈는 초반 경험 문제인지, 장시간 플레이 후 누적된 불만인지 함께 구분해서 해석해야 한다."
        )

    return "\n".join(lines)


def make_priority_criteria_markdown() -> str:
    return """
## 2. 우선순위 판단 기준

본 분석에서 패치·운영 우선순위는 LLM이 임의로 새로 판단하지 않는다.  
우선 검토 수준은 근거 집계 단계에서 계산한 반복 이슈 근거 데이터를 기준으로 정리한다.

우선순위 판단에는 다음 요소를 함께 사용한다.

- 해당 이슈가 언급된 리뷰 수
- LLM 기준 부정·혼합 리뷰에서의 반복 여부
- Steam 비추천 리뷰와의 연결 여부
- 최근 30일 리뷰에서의 반복 여부
- 짧은 플레이타임 구간에서의 부정 반응 여부
- High urgency 리뷰 포함 여부

다만 **High urgency는 LLM이 리뷰별로 분류한 보조 지표**다.  
따라서 High urgency가 많다고 해서 그 자체만으로 우선순위를 올리지 않고,  
Steam 비추천 맥락과 부정·혼합 반복 여부를 함께 확인한다.
""".strip()


def make_llm_result_markdown(result_dict: dict | None) -> str:
    if not result_dict:
        return "LLM 결과가 아직 생성되지 않았다."

    lines = []

    game_summary = result_dict.get("game_summary", "")
    current_status_summary = result_dict.get("current_status_summary", "")
    final_summary = result_dict.get("final_summary", "")

    lines.append("## 3. 현재 상태 요약")
    lines.append("")
    if game_summary:
        lines.append(game_summary)
        lines.append("")
    if current_status_summary:
        lines.append(current_status_summary)
        lines.append("")

    sections = [
        ("## 4. 패치·운영 방향 제안", None),
        ("### 4-1. 지금 먼저 확인해야 할 문제", "immediate_actions"),
        ("### 4-2. 다음 업데이트에서 개선할 문제", "short_term_improvements"),
        ("### 4-3. 운영 커뮤니케이션으로 대응할 문제", "operation_communication"),
        ("### 4-4. 장기적으로 보강할 문제", "long_term_reviews"),
        ("### 4-5. 계속 살릴 강점", "strengths_to_keep"),
    ]

    for title, key in sections:
        lines.append(title)
        lines.append("")

        if key is None:
            lines.append(
                "다음 제안은 근거 데이터에서 계산한 대응 구분과 우선 검토 수준을 유지한 상태에서, "
                "각 이슈가 실제 운영과 패치 의사결정에서 어떻게 다뤄질 수 있는지 LLM이 문장화한 결과다."
            )
            lines.append("")
            continue

        items = result_dict.get(key, []) or []

        if not items:
            lines.append("해당 구분으로 분류된 항목은 없다.")
            lines.append("")
            continue

        for item in items:
            issue = item.get("issue_name", "이슈")
            priority = item.get("priority", "")
            action_group = item.get("action_group", "")
            direction = item.get("patch_ops_direction", "")
            evidence = item.get("evidence_summary", "")
            expected_effect = item.get("expected_effect", "")
            caution = item.get("caution", "")
            detailed_actions = item.get("detailed_actions", []) or []

            lines.append(f"#### {issue}")
            lines.append("")
            lines.append(f"- **대응 구분:** {action_group}")
            lines.append(f"- **우선 검토 수준:** {priority}")
            if evidence:
                lines.append(f"- **근거 요약:** {evidence}")
            if direction:
                lines.append(f"- **패치·운영 방향:** {direction}")

            if detailed_actions:
                lines.append("- **세부 실행안:**")
                for action in detailed_actions:
                    lines.append(f"  - {action}")

            if expected_effect:
                lines.append(f"- **기대 효과:** {expected_effect}")
            if caution:
                lines.append(f"- **주의사항:** {caution}")

            lines.append("")

    operation_notes = result_dict.get("operation_notes", []) or []
    if operation_notes:
        lines.append("## 5. 운영 커뮤니케이션 및 모니터링 제안")
        lines.append("")
        for note in operation_notes:
            lines.append(f"- {note}")
        lines.append("")

    cautions = result_dict.get("cautions", []) or []
    lines.append("## 6. 해석 시 주의사항")
    lines.append("")
    if cautions:
        for caution in cautions:
            lines.append(f"- {caution}")
    else:
        lines.append("- 본 결과는 Steam 리뷰 기반 분석이므로 전체 유저 의견을 완전히 대표하지 않을 수 있다.")
        lines.append("- 실제 원인 확정 전에는 내부 로그, 재현 테스트, 커뮤니티 반응 확인이 함께 필요하다.")
        lines.append("- High urgency는 보조 지표이며, 단독 우선순위 기준으로 사용하지 않는다.")
    lines.append("")

    if final_summary:
        lines.append("## 7. 최종 요약")
        lines.append("")
        lines.append(final_summary)

    return "\n".join(lines)


def build_full_report_markdown(
    analysis_overview: dict,
    result_dict: dict | None,
    evidence_df: pd.DataFrame,
    validation_warnings: list[str] | None = None,
    max_evidence_rows: int = 8,
) -> str:
    """
    문단형 리포트과 유사한 문단형 리포트를 생성한다.
    """
    game_name = analysis_overview.get("game_name", "")

    parts = []
    parts.append(f"# 출시 후 LLM 패치·운영 제안 리포트: {game_name}")
    parts.append("")
    parts.append(make_analysis_overview_markdown(analysis_overview))
    parts.append("")
    parts.append(make_priority_criteria_markdown())
    parts.append("")

    parts.append("## 3. 근거 데이터에서 계산한 이슈별 근거표")
    parts.append("")
    parts.append(
        "아래 표는 LLM 패치·운영 제안에 사용된 입력 근거다. "
        "우선 검토 수준과 대응 구분은 근거 집계 단계에서 계산된 값을 그대로 사용한다."
    )
    parts.append("")
    compact_evidence = make_compact_evidence_display_df(evidence_df, max_rows=max_evidence_rows)
    parts.append(dataframe_to_markdown_table(compact_evidence))
    parts.append("")

    parts.append("## 4. LLM 출력 검증 결과")
    parts.append("")
    if validation_warnings:
        parts.append("LLM 출력 중 아래 항목은 추가 확인이 필요하다.")
        parts.append("")
        for warning in validation_warnings:
            parts.append(f"- {warning}")
    else:
        parts.append(
            "LLM 출력은 근거 데이터에서 계산한 대응 구분과 우선 검토 수준을 그대로 사용했다. "
            "따라서 LLM이 임의로 우선순위를 새로 정한 것이 아니라, 제공된 근거를 바탕으로 패치·운영 방향을 문장화한 결과로 볼 수 있다."
        )
    parts.append("")

    parts.append(make_llm_result_markdown(result_dict))

    return "\n".join(parts)


# ============================================================
# 표시용 데이터프레임
# ============================================================
def make_compact_evidence_display_df(evidence_df: pd.DataFrame, max_rows: int | None = None) -> pd.DataFrame:
    if evidence_df is None or evidence_df.empty:
        return pd.DataFrame()

    display_cols = [
        "issue_name_kor",
        "action_group_hint",
        "rule_priority_hint",
        "affected_review_count",
        "negative_mixed_review_count",
        "steam_negative_review_count",
        "recent_30d_negative_mixed_review_count",
        "high_urgency_review_count",
        "priority_reason",
    ]
    display_cols = [col for col in display_cols if col in evidence_df.columns]

    out = evidence_df[display_cols].copy()

    if max_rows is not None:
        out = out.head(max_rows).copy()

    rename_map = {
        "issue_name_kor": "이슈",
        "action_group_hint": "대응 구분",
        "rule_priority_hint": "우선 검토 수준",
        "affected_review_count": "관련 리뷰 수",
        "negative_mixed_review_count": "부정·혼합 리뷰 수",
        "steam_negative_review_count": "Steam 비추천 리뷰 수",
        "recent_30d_negative_mixed_review_count": "최근 30일 부정·혼합",
        "high_urgency_review_count": "High urgency",
        "priority_reason": "판단 근거",
    }

    out = out.rename(columns=rename_map)

    if "판단 근거" in out.columns:
        out["판단 근거"] = out["판단 근거"].apply(lambda x: shorten_text(x, 160))

    return out


def make_evidence_display_df(evidence_df: pd.DataFrame, max_rows: int | None = None) -> pd.DataFrame:
    if evidence_df is None or evidence_df.empty:
        return pd.DataFrame()

    display_cols = [
        "issue_name_kor",
        "action_group_hint",
        "rule_priority_hint",
        "affected_review_count",
        "positive_review_count",
        "negative_review_count",
        "mixed_review_count",
        "negative_mixed_review_count",
        "steam_negative_review_count",
        "recent_30d_negative_mixed_review_count",
        "early_playtime_negative_mixed_review_count",
        "high_urgency_review_count",
        "priority_rule_detail",
        "priority_reason",
        "patch_ops_note",
        "llm_evidence_text",
    ]
    display_cols = [col for col in display_cols if col in evidence_df.columns]
    out = evidence_df[display_cols].copy()

    if max_rows is not None:
        out = out.head(max_rows).copy()

    rename_map = {
        "issue_name_kor": "이슈",
        "action_group_hint": "대응 구분",
        "rule_priority_hint": "우선 검토 수준",
        "affected_review_count": "관련 리뷰 수",
        "positive_review_count": "긍정 리뷰 수",
        "negative_review_count": "부정 리뷰 수",
        "mixed_review_count": "혼합 리뷰 수",
        "negative_mixed_review_count": "부정·혼합 리뷰 수",
        "steam_negative_review_count": "Steam 비추천 리뷰 수",
        "recent_30d_negative_mixed_review_count": "최근 30일 부정·혼합",
        "early_playtime_negative_mixed_review_count": "짧은 플레이타임 부정·혼합",
        "high_urgency_review_count": "High urgency 리뷰 수",
        "priority_rule_detail": "우선순위 산정 규칙",
        "priority_reason": "판단 근거",
        "patch_ops_note": "패치·운영 참고",
        "llm_evidence_text": "LLM 입력용 근거 문장",
    }

    out = out.rename(columns=rename_map)

    for col in ["판단 근거", "패치·운영 참고", "LLM 입력용 근거 문장"]:
        if col in out.columns:
            out[col] = out[col].apply(lambda x: shorten_text(x, 220))

    return out


def make_review_display_df(review_base: pd.DataFrame, selected_appid, max_rows: int = 100) -> pd.DataFrame:
    review_game = filter_by_appid(review_base, selected_appid)

    if review_game.empty:
        return pd.DataFrame()

    display_cols = [
        "recommendationid",
        "review_datetime",
        "steam_label_text",
        "llm_sentiment",
        "llm_primary_issue",
        "primary_issue",
        "llm_urgency_candidate",
        "urgency",
        "playtime_at_review_hours",
        "playtime_stage",
        "review_recency_group",
        "llm_review_summary",
        "summary",
        "llm_suggested_action",
        "suggested_action",
    ]

    display_cols = [col for col in display_cols if col in review_game.columns]
    out = review_game[display_cols].copy().head(max_rows)

    rename_map = {
        "recommendationid": "리뷰 ID",
        "review_datetime": "리뷰 작성일",
        "steam_label_text": "Steam 라벨",
        "llm_sentiment": "LLM 감정",
        "llm_primary_issue": "LLM 주요 이슈",
        "primary_issue": "주요 이슈",
        "llm_urgency_candidate": "LLM urgency 후보",
        "urgency": "urgency",
        "playtime_at_review_hours": "리뷰 시점 플레이타임",
        "playtime_stage": "플레이타임 구간",
        "review_recency_group": "최근성 구간",
        "llm_review_summary": "LLM 리뷰 요약",
        "summary": "리뷰 요약",
        "llm_suggested_action": "LLM 개선 제안 후보",
        "suggested_action": "개선 제안 후보",
    }

    out = out.rename(columns=rename_map)

    for col in ["LLM 리뷰 요약", "리뷰 요약", "LLM 개선 제안 후보", "개선 제안 후보"]:
        if col in out.columns:
            out[col] = out[col].apply(lambda x: shorten_text(x, 220))

    return out


# ============================================================
# Streamlit 출시 후 리포트 출력 보강 함수
# ============================================================
def make_postlaunch_overview_table_df(analysis_overview: dict) -> pd.DataFrame:
    """
    출시 전 LLM 리포트의 '항목/값' 표와 유사하게,
    출시 후 분석 대상의 핵심 정보를 표로 정리한다.
    """
    review_count = int(analysis_overview.get("review_count", 0) or 0)
    issue_tag_count = int(analysis_overview.get("issue_tag_count", 0) or 0)
    negative_mixed_count = int(analysis_overview.get("llm_negative_mixed_review_count", 0) or 0)
    steam_negative_count = int(analysis_overview.get("steam_negative_review_count", 0) or 0)
    high_urgency_count = int(analysis_overview.get("high_urgency_review_count", 0) or 0)
    recent_30d_count = int(analysis_overview.get("recent_30d_review_count", 0) or 0)

    def pct(count, total):
        if total == 0:
            return "0.0%"
        return f"{count / total * 100:.1f}%"

    rows = [
        {"항목": "게임명", "값": analysis_overview.get("game_name", "")},
        {"항목": "appid", "값": analysis_overview.get("appid", "")},
        {"항목": "분석 리뷰 수", "값": f"{review_count:,}개"},
        {"항목": "분석 이슈 태그 수", "값": f"{issue_tag_count:,}개"},
        {
            "항목": "분석 기간",
            "값": f"{analysis_overview.get('review_date_min', '')} ~ {analysis_overview.get('review_date_max', '')}",
        },
        {
            "항목": "LLM 부정·혼합 리뷰",
            "값": f"{negative_mixed_count:,}개 ({pct(negative_mixed_count, review_count)})",
        },
        {
            "항목": "Steam 비추천 리뷰",
            "값": f"{steam_negative_count:,}개 ({pct(steam_negative_count, review_count)})",
        },
        {
            "항목": "High urgency 리뷰",
            "값": f"{high_urgency_count:,}개 ({pct(high_urgency_count, review_count)})",
        },
        {"항목": "최근 30일 리뷰 수", "값": f"{recent_30d_count:,}개"},
    ]

    avg_playtime = analysis_overview.get("avg_playtime_at_review_hours")
    median_playtime = analysis_overview.get("median_playtime_at_review_hours")

    if avg_playtime is not None:
        rows.append({"항목": "평균 플레이타임(리뷰 시점)", "값": f"{avg_playtime}시간"})

    if median_playtime is not None:
        rows.append({"항목": "중앙값 플레이타임(리뷰 시점)", "값": f"{median_playtime}시간"})

    return pd.DataFrame(rows)


def _count_text_from_evidence(evidence_df: pd.DataFrame, col: str) -> str:
    if evidence_df is None or evidence_df.empty or col not in evidence_df.columns:
        return ""

    counts = evidence_df[col].fillna("-").astype(str).value_counts().to_dict()
    return ", ".join([f"{key} {value}개" for key, value in counts.items()])


def make_postlaunch_llm_report_markdown_v2(
    result_dict: dict | None,
    analysis_overview: dict,
    evidence_df: pd.DataFrame,
) -> str:
    """
    출시 전 LLM 리포트와 유사한 구성으로,
    출시 후 분석 대상에 대한 전반적인 LLM 리포트를 만든다.

    이 함수는 상세 패치 항목을 길게 나열하지 않는다.
    상세 제안은 make_patch_ops_proposal_markdown_v2에서 별도로 출력한다.
    """
    game_name = analysis_overview.get("game_name", "선택 게임")
    appid = analysis_overview.get("appid", "")

    overview_table = dataframe_to_markdown_table(
        make_postlaunch_overview_table_df(analysis_overview)
    )

    game_summary = ""
    current_status_summary = ""
    final_summary = ""
    cautions = []

    if result_dict:
        game_summary = result_dict.get("game_summary", "") or ""
        current_status_summary = result_dict.get("current_status_summary", "") or ""
        final_summary = result_dict.get("final_summary", "") or ""
        cautions = result_dict.get("cautions", []) or []

    if not game_summary:
        game_summary = (
            f"{game_name}(`appid: {appid}`)의 Steam 리뷰를 기반으로 출시 후 유저 반응을 분석하였다. "
            "분석 결과는 리뷰 단위 LLM 분류 결과와 근거 데이터에서 계산한 이슈별 반복 근거를 함께 사용한다."
        )

    if not current_status_summary:
        current_status_summary = (
            "현재 리뷰 상태는 LLM 부정·혼합 리뷰, Steam 비추천 리뷰, High urgency 리뷰의 분포를 함께 보며 해석한다. "
            "특히 부정·혼합 리뷰와 Steam 비추천 맥락이 동시에 나타나는 이슈는 패치 전 우선 확인할 필요가 있다."
        )

    if not final_summary:
        final_summary = (
            "선택한 게임의 출시 후 운영에서는 반복적으로 언급된 부정 이슈를 먼저 확인하고, "
            "동시에 긍정 리뷰에서 확인되는 강점이 약화되지 않도록 관리하는 것이 중요하다."
        )

    if not cautions:
        cautions = [
            "본 리포트는 Steam 리뷰 기반 분석이므로 전체 유저 의견을 완전히 대표하지 않을 수 있다.",
            "실제 원인 확정 전에는 내부 로그, 재현 테스트, 커뮤니티 반응, 추가 리뷰 확인이 함께 필요하다.",
            "High urgency는 04번 리뷰 분류 단계에서 LLM이 리뷰 문맥을 보고 분류한 보조 지표이며, 우선순위를 새로 올리는 기준으로 직접 사용하지 않는다.",
        ]

    action_count_text = _count_text_from_evidence(evidence_df, "action_group_hint")
    priority_count_text = _count_text_from_evidence(evidence_df, "rule_priority_hint")
    evidence_count = 0 if evidence_df is None else len(evidence_df)

    lines = []
    lines.append("# 출시 후 LLM 패치·운영 방향 생성 리포트")
    lines.append("")

    lines.append("## 1. 출시 후 LLM 패치·운영 방향 생성")
    lines.append("")
    lines.append(
        "선택한 게임의 Steam 리뷰를 기반으로, 출시 후 패치와 운영 단계에서 우선적으로 확인해야 할 항목을 LLM이 리포트로 정리한다."
    )
    lines.append(
        "리뷰 본문은 04번에서 LLM으로 감정, 주요 이슈, 세부 이슈 태그, urgency, 개선 제안 후보로 분류되었고, "
        "근거 집계 단계에서는 이 결과를 이슈별 패치·운영 근거표로 다시 집계하였다."
    )
    lines.append("")
    lines.append(overview_table)
    lines.append("")
    lines.append(
        "패치·운영 방향 생성에는 선택 게임의 리뷰 상태뿐 아니라, 근거 데이터에서 계산한 대응 구분과 우선 검토 수준 근거도 함께 사용하였다."
    )
    lines.append("")

    lines.append("## 2. 패치·운영 판단 기준")
    lines.append("")
    lines.append("- LLM은 우선 검토 수준을 직접 정하지 않는다.")
    lines.append("- 패치·운영 우선 검토 수준은 근거 데이터에서 계산한 `rule_priority_hint`를 그대로 사용한다.")
    lines.append("- 대응 구분은 근거 데이터에서 계산한 `action_group_hint`를 그대로 사용한다.")
    lines.append("- 우선 검토 수준은 부정·혼합 리뷰 수, Steam 비추천 맥락, 최근 30일 반복 여부, 짧은 플레이타임 부정 반응 등을 기준으로 계산한 값이다.")
    lines.append("- High urgency는 04번 LLM 리뷰 분류 결과에서 나온 보조 지표이며, 우선순위 산정 기준으로 직접 사용하지 않는다.")
    lines.append("- LLM은 계산된 근거를 바탕으로 패치·운영 방향, 세부 실행안, 기대 효과, 주의사항을 문장화하는 역할만 한다.")
    lines.append("")

    lines.append("## 3. 분석 대상 요약")
    lines.append("")
    lines.append(game_summary)
    lines.append("")

    lines.append("## 4. 데이터 요약")
    lines.append("")
    lines.append(
        f"선택한 게임에 대해 패치·운영 제안에 사용할 수 있는 이슈 근거는 총 **{evidence_count:,}개** 추출되었다."
    )
    if action_count_text:
        lines.append(f"대응 구분별로는 **{action_count_text}** 항목이 포함되어 있다.")
    if priority_count_text:
        lines.append(f"우선 검토 수준별로는 **{priority_count_text}** 항목이 포함되어 있다.")
    lines.append(
        "이 데이터는 직접 리뷰를 다시 읽는 대신, 리뷰 단위 LLM 분류 결과를 이슈 단위로 재집계한 패치·운영 판단 근거다."
    )
    lines.append("")

    lines.append("## 5. 현재 리뷰 상태 요약")
    lines.append("")
    lines.append(current_status_summary)
    lines.append("")

    lines.append("## 6. 최종 요약")
    lines.append("")
    lines.append(final_summary)
    lines.append("")

    lines.append("## 7. 해석 시 주의사항")
    lines.append("")
    for caution in cautions:
        lines.append(f"- {caution}")

    return "\n".join(lines)


def _section_items(result_dict: dict | None, key: str) -> list[dict]:
    if not result_dict:
        return []

    value = result_dict.get(key, []) or []
    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, dict)]


def _append_patch_ops_items(lines: list[str], items: list[dict], empty_message: str) -> None:
    if not items:
        lines.append(empty_message)
        lines.append("")
        return

    for item in items:
        issue = item.get("issue_name", "이슈")
        action_group = item.get("action_group", "-")
        priority = item.get("priority", "-")
        evidence = item.get("evidence_summary", "")
        direction = item.get("patch_ops_direction", "")
        detailed_actions = item.get("detailed_actions", []) or []
        expected_effect = item.get("expected_effect", "")
        caution = item.get("caution", "")

        lines.append(f"### {issue}")
        lines.append("")
        lines.append(f"- **대응 구분:** {action_group}")
        lines.append(f"- **우선 검토 수준:** {priority}")
        if evidence:
            lines.append(f"- **근거 요약:** {evidence}")
        if direction:
            lines.append(f"- **패치·운영 방향:** {direction}")
        if detailed_actions:
            lines.append("- **세부 실행안:**")
            for action in detailed_actions:
                lines.append(f"  - {action}")
        if expected_effect:
            lines.append(f"- **기대 효과:** {expected_effect}")
        if caution:
            lines.append(f"- **주의사항:** {caution}")
        lines.append("")


def make_patch_ops_proposal_markdown_v2(result_dict: dict | None) -> str:
    """
    패치 및 운영 제안 탭 전용 Markdown을 만든다.
    문단형 리포트의 '4. 패치·운영 방향 제안' 섹션에 해당한다.
    """
    if not result_dict:
        return "LLM 패치·운영 제안 결과가 아직 생성되지 않았다."

    lines = []
    lines.append("# 4. 패치·운영 방향 제안")
    lines.append("")
    lines.append(
        "다음 제안은 근거 데이터에서 계산한 대응 구분과 우선 검토 수준을 유지한 상태에서, "
        "각 이슈가 실제 운영과 패치 의사결정에서 어떻게 다뤄질 수 있는지 LLM이 문장화한 결과다."
    )
    lines.append("")

    sections = [
        (
            "## 4-1. 지금 먼저 확인해야 할 문제",
            "immediate_actions",
            "즉시 확인으로 분류된 항목은 없다. 다만 부정·혼합 리뷰와 Steam 비추천 맥락이 반복되는 이슈는 다음 패치 전 다시 확인하는 것이 좋다.",
        ),
        (
            "## 4-2. 다음 업데이트에서 개선할 문제",
            "short_term_improvements",
            "단기 개선으로 분류된 항목은 없다. 리뷰가 추가로 쌓이면 반복 이슈를 다시 확인해야 한다.",
        ),
        (
            "## 4-3. 운영 커뮤니케이션으로 대응할 문제",
            "operation_communication",
            "운영 커뮤니케이션 개선으로 분류된 항목은 없다.",
        ),
        (
            "## 4-4. 장기적으로 보강할 문제",
            "long_term_reviews",
            "장기 검토로 분류된 항목은 없다. 콘텐츠 확장이나 구조 개선 요구가 반복되는지 모니터링한다.",
        ),
        (
            "## 4-5. 계속 살릴 강점",
            "strengths_to_keep",
            "강점 유지로 분류된 항목은 없다. 긍정 리뷰에서 반복되는 만족 요인을 추가 확인하는 것이 좋다.",
        ),
    ]

    for title, key, empty_message in sections:
        lines.append(title)
        lines.append("")
        _append_patch_ops_items(lines, _section_items(result_dict, key), empty_message)

    operation_notes = result_dict.get("operation_notes", []) or []
    if operation_notes:
        lines.append("## 4-6. 운영 커뮤니케이션 및 모니터링 추가 제안")
        lines.append("")
        for note in operation_notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines)


def make_postlaunch_validation_report_markdown(validation_warnings: list[str]) -> str:
    """
    출시 전 검증 결과 탭과 비슷한 톤의 출시 후 검증 설명 Markdown을 만든다.
    """
    lines = []
    lines.append("## LLM 출력 검증 결과")
    lines.append("")
    lines.append("검증 기준은 출시 전 분석과 동일한 원칙을 따른다.")
    lines.append("")
    lines.append("- LLM은 우선 검토 수준을 직접 정하지 않는다.")
    lines.append("- 패치·운영 우선 검토 수준은 근거 데이터에서 계산한 `rule_priority_hint`를 그대로 사용해야 한다.")
    lines.append("- 대응 구분은 근거 데이터에서 계산한 `action_group_hint`를 그대로 사용해야 한다.")
    lines.append("- High urgency는 이전 LLM 리뷰 분류 결과에서 나온 보조 지표이며, 우선 검토 수준 산정 기준으로 직접 사용하지 않는다.")
    lines.append("- LLM은 계산된 근거를 바탕으로 패치·운영 방향과 세부 실행안을 문장화하는 역할만 한다.")
    lines.append("")

    if not validation_warnings:
        lines.append("검증 결과, LLM 출력은 근거 데이터 표의 대응 구분과 우선 검토 수준을 그대로 사용했다.")
    else:
        lines.append("검증 결과, 아래 항목은 추가 확인이 필요하다.")
        lines.append("")
        for warning in validation_warnings:
            lines.append(f"- {warning}")

    return "\n".join(lines)
