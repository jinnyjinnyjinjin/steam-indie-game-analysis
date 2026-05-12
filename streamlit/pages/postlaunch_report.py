import html
import re
from string import Template

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from utils.postlaunch_engine import (
    DEFAULT_RUN_NAME,
    load_postlaunch_data,
    get_game_options,
    filter_by_appid,
    make_analysis_overview,
    select_patch_ops_evidence,
    make_postlaunch_cache_key,
    load_cached_postlaunch_result,
    save_cached_postlaunch_result,
    extract_cached_result,
    build_patch_ops_prompt,
    generate_postlaunch_patch_ops_with_llm,
    validate_patch_ops_result,
    make_validation_result_df,
    make_patch_ops_strategy_table,
    make_evidence_display_df,
    make_review_display_df,
    make_postlaunch_llm_report_markdown_v2,
    make_patch_ops_proposal_markdown_v2,
    make_postlaunch_validation_report_markdown,
)

# ============================================================
# 대시보드 스타일 보조 함수
# ============================================================
def inject_dashboard_style() -> None:
    """출시 전/출시 후 화면의 카드형 결과 스타일을 통일합니다."""
    st.markdown(
        """
        <style>
        .stApp { background: radial-gradient(circle at top left, rgba(30,64,175,0.14), transparent 34%), linear-gradient(180deg, #0b1018 0%, #070b12 100%); color: #f8fafc; }
        [data-testid="stHeader"] { background: rgba(11,16,24,0.72); }
        [data-testid="stHeader"] {
            background-color: rgba(11, 16, 24, 0.86) !important;
        }
        [data-testid="stSidebar"], section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #0b1018 100%) !important;
            color: #f8fafc !important;
        }
        .stMarkdown, .stText, p, label, span, div {
            color: inherit;
        }
        .stButton > button {
            color: #f8fafc !important;
            border-color: rgba(148, 163, 184, 0.38) !important;
        }
        .stButton > button[kind="secondary"],
        .stButton > button[data-testid="baseButton-secondary"] {
            background-color: #111827 !important;
        }
        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {
            background-color: #0b0f17 !important;
            color: #f8fafc !important;
        }
        .dash-card {
            background: rgba(255,255,255,0.045);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 16px;
            padding: 18px 20px;
            min-height: 112px;
            box-shadow: 0 8px 20px rgba(0,0,0,0.12);
        }
        .dash-card.tone-high {
            background: linear-gradient(135deg, rgba(239,68,68,0.16), rgba(255,255,255,0.035));
            border-color: rgba(239,68,68,0.46);
        }
        .dash-card.tone-mid {
            background: linear-gradient(135deg, rgba(245,158,11,0.16), rgba(255,255,255,0.035));
            border-color: rgba(245,158,11,0.44);
        }
        .dash-card.tone-low {
            background: linear-gradient(135deg, rgba(59,130,246,0.15), rgba(255,255,255,0.035));
            border-color: rgba(59,130,246,0.38);
        }
        .dash-card.tone-good {
            background: linear-gradient(135deg, rgba(34,197,94,0.15), rgba(255,255,255,0.035));
            border-color: rgba(34,197,94,0.38);
        }
        .dash-card.tone-info {
            background: linear-gradient(135deg, rgba(59,130,246,0.15), rgba(255,255,255,0.035));
            border-color: rgba(59,130,246,0.38);
        }
        .dash-card.tone-warn {
            background: linear-gradient(135deg, rgba(245,158,11,0.16), rgba(255,255,255,0.035));
            border-color: rgba(245,158,11,0.44);
        }
        .dash-card.tone-danger {
            background: linear-gradient(135deg, rgba(239,68,68,0.16), rgba(255,255,255,0.035));
            border-color: rgba(239,68,68,0.46);
        }
        .dash-card.tone-high .dash-kpi-value,
        .dash-card.tone-danger .dash-kpi-value { color: #fca5a5; }
        .dash-card.tone-mid .dash-kpi-value,
        .dash-card.tone-warn .dash-kpi-value { color: #fcd34d; }
        .dash-card.tone-low .dash-kpi-value { color: #93c5fd; }
        .dash-card.tone-good .dash-kpi-value { color: #86efac; }
        .dash-card.tone-info .dash-kpi-value { color: #93c5fd; }
        .dash-kpi-value { font-size: 1.95rem; font-weight: 800; line-height: 1.05; margin-bottom: 6px; }
        .dash-kpi-label { font-size: 0.92rem; font-weight: 700; color: rgba(250,250,250,0.92); }
        .dash-kpi-caption { font-size: 0.78rem; color: rgba(250,250,250,0.62); margin-top: 4px; line-height: 1.45; }
        .dash-section-lead {
            background: linear-gradient(135deg, rgba(42,117,255,0.15), rgba(40,190,140,0.08));
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 18px;
            padding: 18px 22px;
            margin: 10px 0 18px 0;
        }
        .dash-section-title { font-size: 1.08rem; font-weight: 800; margin-bottom: 4px; }
        .dash-section-text { font-size: 0.9rem; color: rgba(250,250,250,0.72); line-height: 1.55; white-space: pre-line; }
        .badge { display: inline-block; border-radius: 999px; padding: 4px 10px; font-size: 0.78rem; font-weight: 800; margin-right: 6px; margin-bottom: 8px; }
        .badge-high { background: rgba(239,68,68,0.16); color: #fca5a5; border: 1px solid rgba(239,68,68,0.30); }
        .badge-mid { background: rgba(245,158,11,0.16); color: #fcd34d; border: 1px solid rgba(245,158,11,0.30); }
        .badge-low { background: rgba(59,130,246,0.16); color: #93c5fd; border: 1px solid rgba(59,130,246,0.30); }
        .badge-neutral { background: rgba(148,163,184,0.14); color: #cbd5e1; border: 1px solid rgba(148,163,184,0.24); }
        .ops-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.13);
            border-left: 5px solid #60a5fa;
            border-radius: 16px;
            padding: 16px 18px;
            margin-bottom: 14px;
        }
        .ops-card.high {
            border-color: rgba(239,68,68,0.36);
            border-left-color: #ef4444;
            background: linear-gradient(135deg, rgba(239,68,68,0.10), rgba(255,255,255,0.035));
        }
        .ops-card.mid {
            border-color: rgba(245,158,11,0.34);
            border-left-color: #f59e0b;
            background: linear-gradient(135deg, rgba(245,158,11,0.10), rgba(255,255,255,0.035));
        }
        .ops-card.low {
            border-color: rgba(59,130,246,0.34);
            border-left-color: #3b82f6;
            background: linear-gradient(135deg, rgba(59,130,246,0.10), rgba(255,255,255,0.035));
        }
        .ops-title { font-size: 1.08rem; font-weight: 800; margin-bottom: 8px; }
        .mini-label { font-size: 0.78rem; font-weight: 800; color: rgba(250,250,250,0.58); margin: 12px 0 4px 0; }
        .mini-text { font-size: 0.9rem; line-height: 1.58; color: rgba(250,250,250,0.84); white-space: pre-line; }


        /* ============================================================
           출시 후 패치·운영 카드 리디자인
           - 좌측: 이슈 요약 / 중앙: 확인 이유·권장 대응 / 우측: 근거 요약
           ============================================================ */
        .ops-card {
            position: relative;
            display: grid;
            grid-template-columns: minmax(220px, 0.7fr) minmax(360px, 1.15fr) 330px;
            gap: 24px;
            align-items: center;
            overflow: hidden;
            margin: 0 0 8px 0;
            padding: 18px 20px 18px 22px;
            border-radius: 18px;
            border: 1px solid rgba(96,165,250,0.32);
            border-left: 4px solid #60a5fa;
            background:
                radial-gradient(circle at 8% 16%, rgba(56,189,248,0.10), transparent 28%),
                linear-gradient(135deg, rgba(15,23,42,0.88), rgba(2,8,23,0.94));
            box-shadow: 0 18px 42px rgba(2,8,23,0.28), inset 0 0 0 1px rgba(255,255,255,0.025);
        }
        .ops-card::before {
            content: "";
            position: absolute;
            inset: 0;
            background-image:
                linear-gradient(rgba(148,163,184,0.026) 1px, transparent 1px),
                linear-gradient(90deg, rgba(148,163,184,0.026) 1px, transparent 1px);
            background-size: 30px 30px;
            pointer-events: none;
            opacity: 0.74;
        }
        .ops-card > * {
            position: relative;
            z-index: 1;
        }
        .ops-card.high {
            border-color: rgba(248,113,113,0.50);
            border-left-color: #ff4d5a;
            background:
                radial-gradient(circle at 5% 10%, rgba(248,113,113,0.16), transparent 30%),
                linear-gradient(135deg, rgba(52,12,24,0.78), rgba(2,8,23,0.94));
            box-shadow: 0 20px 54px rgba(127,29,29,0.20), 0 0 28px rgba(239,68,68,0.10), inset 0 0 0 1px rgba(255,255,255,0.025);
        }
        .ops-card.mid {
            border-color: rgba(245,158,11,0.46);
            border-left-color: #f59e0b;
            background:
                radial-gradient(circle at 5% 10%, rgba(245,158,11,0.14), transparent 30%),
                linear-gradient(135deg, rgba(42,28,9,0.78), rgba(2,8,23,0.94));
        }
        .ops-card.low {
            border-color: rgba(96,165,250,0.46);
            border-left-color: #3b82f6;
            background:
                radial-gradient(circle at 5% 10%, rgba(59,130,246,0.16), transparent 30%),
                linear-gradient(135deg, rgba(15,23,42,0.88), rgba(2,8,23,0.94));
        }
        .ops-left, .ops-center {
            min-width: 0;
        }
        .ops-title {
            font-size: 1.35rem;
            font-weight: 920;
            color: #f8fafc;
            margin: 6px 0 0 0;
            letter-spacing: -0.045em;
        }
        .ops-mini-label {
            font-size: 0.76rem;
            font-weight: 900;
            color: rgba(226,232,240,0.72);
            margin: 0 0 5px 0;
        }
        .ops-mini-text {
            font-size: 0.92rem;
            line-height: 1.55;
            color: #e5e7eb;
            margin: 0;
            white-space: pre-line;
        }
        .ops-center {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding-left: 2px;
        }
        .ops-center-block {
            min-width: 0;
        }
        .ops-evidence-box {
            align-self: stretch;
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 108px;
            padding: 15px 18px;
            border-radius: 14px;
            border: 1px solid rgba(96,165,250,0.30);
            background: linear-gradient(135deg, rgba(15,23,42,0.78), rgba(8,47,73,0.16));
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.022), 0 0 26px rgba(59,130,246,0.08);
        }
        .ops-evidence-title {
            color: #93c5fd;
            font-size: 0.98rem;
            font-weight: 920;
            margin-bottom: 8px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(96,165,250,0.24);
        }
        .ops-evidence-line {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 10px;
            color: #e2e8f0;
            font-size: 0.86rem;
            line-height: 1.45;
            margin: 4px 0;
        }
        .ops-evidence-name {
            color: #cbd5e1;
        }
        .ops-evidence-value {
            color: #f8fafc;
            font-weight: 800;
            white-space: nowrap;
        }
        .ops-detail-box {
            grid-column: 1 / -1;
            display: grid;
            grid-template-columns: 1.15fr 0.85fr 0.9fr;
            gap: 18px;
            margin-top: 2px;
            padding-top: 16px;
            border-top: 1px solid rgba(148,163,184,0.18);
        }
        .ops-detail-block {
            min-width: 0;
            padding: 13px 15px;
            border-radius: 13px;
            border: 1px solid rgba(148,163,184,0.16);
            background: rgba(15,23,42,0.42);
        }
        .ops-detail-label {
            font-size: 0.78rem;
            font-weight: 900;
            color: #93c5fd;
            margin: 0 0 8px 0;
        }
        .ops-detail-text {
            font-size: 0.88rem;
            line-height: 1.58;
            color: #e5e7eb;
            white-space: pre-line;
        }
        .ops-detail-caution {
            border-color: rgba(56,189,248,0.26);
            background: rgba(14,116,144,0.16);
        }
        @media (max-width: 1250px) {
            .ops-card {
                grid-template-columns: 1fr;
                gap: 16px;
            }
            .ops-center {
                grid-template-columns: 1fr;
                gap: 14px;
            }
            .ops-detail-box { grid-template-columns: 1fr; }
        }

        </style>
        """,
        unsafe_allow_html=True,
    )

def apply_dark_chart_theme(chart: alt.Chart) -> alt.Chart:
    """Streamlit 라이트 모드에서도 그래프가 다크 배경으로 보이도록 고정합니다."""
    return (
        chart
        .properties(background="#0b0f17")
        .configure_view(fill="#0b0f17", strokeOpacity=0)
        .configure_axis(
            labelColor="#cbd5e1",
            titleColor="#f8fafc",
            gridColor="#273142",
            domainColor="#3a4252",
            tickColor="#3a4252",
        )
        .configure_title(color="#f8fafc")
    )

def _html_text(value) -> str:
    return html.escape(clean_pipeline_terms("" if value is None or pd.isna(value) else str(value)))

def render_metric_card(label: str, value: str, caption: str = "", tone: str = "neutral") -> None:
    """요약 KPI 카드를 출력합니다. tone 값으로 중요도에 따른 색상만 최소 적용합니다."""
    safe_tone = str(tone) if str(tone) in {"neutral", "high", "mid", "low", "good", "info", "warn", "danger"} else "neutral"
    st.markdown(
        f"""
        <div class="dash-card tone-{safe_tone}">
            <div class="dash-kpi-value">{_html_text(value)}</div>
            <div class="dash-kpi-label">{_html_text(label)}</div>
            <div class="dash-kpi-caption">{_html_text(caption)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_section_lead(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="dash-section-lead">
            <div class="dash-section-title">{_html_text(title)}</div>
            <div class="dash-section-text">{_html_text(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def _priority_class(priority: str) -> str:
    return {"상": "high", "중": "mid", "하": "low"}.get(str(priority), "neutral")

def _priority_display(priority: str) -> str:
    return {"상": "우선 점검", "중": "추가 검토", "하": "참고"}.get(str(priority), str(priority))

def _priority_raw(display_value: str) -> str:
    return {"우선 점검": "상", "추가 검토": "중", "참고": "하"}.get(str(display_value), str(display_value))

def render_badge(label: str, tone: str = "neutral") -> str:
    return f'<span class="badge badge-{tone}">{html.escape(str(label))}</span>'

def notify_detail_toggle_change(enabled: bool, page_key: str, detail_label: str) -> None:
    """상세 근거·검증 보기 상태가 바뀔 때 토스트 알림을 띄웁니다."""
    prev_key = f"{page_key}_detail_toggle_prev"
    if prev_key in st.session_state and st.session_state[prev_key] != enabled:
        if enabled:
            message = f"{detail_label}가 켜졌습니다. 결과 영역에 상세 탭이 추가됩니다."
            icon = "🔎"
        else:
            message = f"{detail_label}가 꺼졌습니다. 핵심 결과만 표시합니다."
            icon = "✅"
        try:
            st.toast(message, icon=icon)
        except Exception:
            st.caption(message)
    st.session_state[prev_key] = enabled

def _split_tag_values(value) -> list[str]:
    """쉼표/줄바꿈/리스트 형태의 태그 값을 화면 필터용 목록으로 정리합니다."""
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        raw_values = []
        for item in value:
            raw_values.extend(_split_tag_values(item))
        return raw_values

    try:
        if pd.isna(value):
            return []
    except TypeError:
        pass

    text_value = str(value).strip()
    if not text_value or text_value in {"-", "nan", "None"}:
        return []

    parts = re.split(r"[,|;\n]+", text_value)
    tags = []
    for part in parts:
        tag = part.strip()
        if tag and tag not in {"-", "nan", "None"}:
            tags.append(tag)
    return tags

def _strategy_issue_tag_values(row: pd.Series) -> list[str]:
    """패치·운영 카드에 표시하고 필터에 사용할 이슈 태그를 정합니다.

    관련 태그 컬럼이 없거나 비어 있어도 이슈명 자체를 태그처럼 사용해,
    카드와 태그 필터에서 항상 어떤 이슈인지 확인할 수 있게 합니다.
    """
    for col in ["관련 태그", "이슈 태그", "세부 이슈 태그", "issue_tags", "tags"]:
        if col in row.index:
            tags = _split_tag_values(row.get(col, ""))
            if tags:
                return tags

    issue = row.get("이슈", "")
    tags = _split_tag_values(issue)
    if tags:
        return tags

    return ["이슈 태그"]

def _available_strategy_issue_tag_options(df: pd.DataFrame) -> list[str]:
    """패치·운영 카드 필터에 표시할 이슈 태그 목록을 만듭니다."""
    if df is None or df.empty:
        return []

    options = []
    for _, row in df.iterrows():
        options.extend(_strategy_issue_tag_values(row))

    return sorted(pd.Series(options).dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist())

def _row_has_selected_strategy_issue_tag(row: pd.Series, selected_tags: list[str]) -> bool:
    if not selected_tags:
        return True
    row_tags = set(_strategy_issue_tag_values(row))
    return bool(row_tags.intersection(set(selected_tags)))

# ============================================================
# 화면 표시 보조 함수
# ============================================================
def clean_pipeline_terms(text: str) -> str:
    """사용자 화면에서 코드 번호 중심 표현을 업무 단계 표현으로 바꿉니다."""
    if not text:
        return ""

    replacements = {
        "04-1에서 계산한": "근거 집계 단계에서 계산한",
        "04-1에서 집계한": "근거 집계 단계에서 집계한",
        "04-1에서는": "근거 집계 단계에서는",
        "04-1 단계에서": "근거 집계 단계에서",
        "04-1 근거표": "근거 데이터 표",
        "04-1": "근거 집계 단계",
        "04번 리뷰 분류 단계": "리뷰 분류 단계",
        "04번": "리뷰 분류 단계",
        "04-2 report-version": "문단형 리포트",
    }

    out = str(text)
    for old, new in replacements.items():
        out = out.replace(old, new)

    user_facing_replacements = {
        "출시 후 LLM 패치·운영 방향 생성 리포트": "출시 후 패치·운영 방향 생성 리포트",
        "출시 후 LLM 패치·운영 제안 리포트": "출시 후 패치·운영 제안 리포트",
        "출시 후 LLM 분석 리포트": "출시 후 리뷰 분석 리포트",
        "LLM 패치·운영 제안": "패치·운영 제안",
        "LLM 패치·운영 방향": "패치·운영 방향",
        "LLM 출력": "생성 결과",
        "LLM 결과": "생성 결과",
        "LLM 기준": "분류 기준",
        "LLM 부정·혼합": "부정·혼합",
        "LLM 감정": "감정",
        "LLM 주요 이슈": "주요 이슈",
        "LLM urgency 후보": "긴급 확인 후보",
        "LLM 리뷰 요약": "리뷰 요약",
        "LLM 개선 제안 후보": "개선 제안 후보",
        "LLM 입력용 근거 문장": "근거 문장",
        "리뷰 단위 LLM 분류 결과": "리뷰 단위 분류 결과",
        "LLM 리뷰 분류 결과": "리뷰 분류 결과",
        "이전 LLM 리뷰 분류 결과": "이전 리뷰 분류 결과",
        "LLM이 임의로": "생성 과정에서 임의로",
        "LLM이 리뷰 문맥상": "리뷰 문맥상",
        "LLM이 리뷰별로 분류한": "리뷰별로 분류된",
        "LLM이 분류한": "분류된",
        "LLM이 문장화한": "생성 과정에서 문장화한",
        "LLM이": "생성 과정이",
        "LLM은": "생성 과정은",
        "LLM": "리뷰 분석 모델",
        "rule_priority_hint": "사전 계산된 점검 우선도",
        "action_group_hint": "사전 계산된 대응 구분",
    }
    for old, new in user_facing_replacements.items():
        out = out.replace(old, new)
    return out

def _count_chart_df(df: pd.DataFrame, column: str, order: list[str] | None = None, label: str = "항목") -> pd.DataFrame:
    if df is None or df.empty or column not in df.columns:
        return pd.DataFrame(columns=[label, "건수"])

    counts = df[column].fillna("미분류").astype(str).value_counts()

    if order:
        counts = counts.reindex(order).fillna(0).astype(int)

    out = counts.reset_index()
    out.columns = [label, "건수"]
    return out

def render_bar_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    x_title: str | None = None,
    y_title: str | None = None,
    height: int = 350,
) -> None:
    """축 라벨이 잘리지 않도록 여백을 확보해 Altair 막대그래프를 출력합니다."""
    if df is None or df.empty or x_col not in df.columns or y_col not in df.columns:
        st.info("표시할 그래프 데이터가 없습니다.")
        return

    chart_df = df.copy()
    chart_df[x_col] = chart_df[x_col].fillna("미분류").astype(str)
    chart_df[y_col] = pd.to_numeric(chart_df[y_col], errors="coerce").fillna(0)

    max_value = chart_df[y_col].max()
    y_max = max_value * 1.15 if max_value > 0 else 1

    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X(
                f"{x_col}:N",
                title=x_title or x_col,
                axis=alt.Axis(
                    labelAngle=0,
                    labelLimit=180,
                    titleAngle=0,
                    titlePadding=12,
                ),
            ),
            y=alt.Y(
                f"{y_col}:Q",
                title=y_title or y_col,
                scale=alt.Scale(domain=[0, y_max], nice=True),
                axis=alt.Axis(
                    titleAngle=0,
                    titleAlign="left",
                    titleAnchor="start",
                    titleX=0,
                    titleY=-8,
                    titlePadding=8,
                    labelPadding=6,
                ),
            ),
            color=alt.condition(
                alt.FieldOneOfPredicate(field=x_col, oneOf=["우선 점검", "추가 검토", "참고"]),
                alt.Color(
                    f"{x_col}:N",
                    scale=alt.Scale(
                        domain=["우선 점검", "추가 검토", "참고"],
                        range=["#ef4444", "#f59e0b", "#3b82f6"],
                    ),
                    legend=None,
                ),
                alt.value("#60a5fa"),
            ),
            tooltip=[
                alt.Tooltip(f"{x_col}:N", title=x_title or x_col),
                alt.Tooltip(f"{y_col}:Q", title=y_title or y_col),
            ],
        )
        .properties(
            height=height,
            padding={"top": 18, "left": 8, "right": 8, "bottom": 8},
        )
    )

    st.altair_chart(apply_dark_chart_theme(chart), use_container_width=True)

def render_horizontal_bar_chart(
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    label_title: str | None = None,
    value_title: str | None = None,
    height: int = 340,
) -> None:
    """항목명이 긴 그래프는 가로 막대로 보여주어 가독성을 높입니다."""
    if df is None or df.empty or label_col not in df.columns or value_col not in df.columns:
        st.info("표시할 그래프 데이터가 없습니다.")
        return

    chart_df = df.copy()
    chart_df[label_col] = chart_df[label_col].fillna("미분류").astype(str)
    chart_df[value_col] = pd.to_numeric(chart_df[value_col], errors="coerce").fillna(0)

    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X(
                f"{value_col}:Q",
                title=value_title or value_col,
                axis=alt.Axis(labelAngle=0, titleAngle=0, titlePadding=12),
            ),
            y=alt.Y(
                f"{label_col}:N",
                title=label_title or label_col,
                sort="-x",
                axis=alt.Axis(labelAngle=0, labelLimit=260, titleAngle=0, titleAlign="left", titleAnchor="start"),
            ),
            tooltip=[
                alt.Tooltip(f"{label_col}:N", title=label_title or label_col),
                alt.Tooltip(f"{value_col}:Q", title=value_title or value_col),
            ],
        )
        .properties(height=height)
    )

    st.altair_chart(apply_dark_chart_theme(chart), use_container_width=True)

def _cell_class_name(column_name: str) -> str:
    class_map = {
        "패치·운영 방향": "col-long-text",
        "세부 실행안": "col-long-text",
        "근거 요약": "col-long-text",
        "기대 효과": "col-long-text",
        "주의사항": "col-long-text",
        "판단 근거": "col-long-text",
        "패치·운영 참고": "col-long-text",
        "LLM 입력용 근거 문장": "col-long-text",
        "근거 문장": "col-long-text",
        "LLM 리뷰 요약": "col-long-text",
        "리뷰 요약": "col-long-text",
        "LLM 개선 제안 후보": "col-long-text",
        "개선 제안 후보": "col-long-text",
        "내용": "col-long-text",
        "기준": "col-long-text",
        "의미": "col-long-text",
    }
    return class_map.get(str(column_name), "")

def _format_table_cell_text(column_name: str, value) -> str:
    if isinstance(value, list):
        text = "\n".join([str(x) for x in value])
    else:
        text = "" if pd.isna(value) else str(value)

    text = text.replace("\r", "\n").strip()
    text = re.sub(r"[ \t]+", " ", text)
    text = clean_pipeline_terms(text)

    if not text:
        return ""

    if column_name in [
        "근거 요약",
        "패치·운영 방향",
        "기대 효과",
        "주의사항",
        "판단 근거",
        "패치·운영 참고",
        "내용",
        "기준",
        "의미",
    ]:
        text = re.sub(r"(다\.)\s+", r"\1\n", text)
        text = re.sub(r"(습니다\.)\s+", r"\1\n", text)
        text = re.sub(r"(확인되었다\.)\s+", r"\1\n", text)
        text = re.sub(r"(필요하다\.)\s+", r"\1\n", text)

    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("-"):
            lines.append(line)
        else:
            lines.append(line)

    return "<br>".join(html.escape(line) for line in lines)

def _column_width_px(column_name: str) -> int:
    width_map = {
        "대응 구분": 180,
        "우선 검토 수준": 130,
        "이슈": 180,
        "패치·운영 방향": 380,
        "세부 실행안": 430,
        "근거 요약": 430,
        "기대 효과": 360,
        "주의사항": 360,
        "관련 리뷰 수": 110,
        "긍정 리뷰 수": 110,
        "부정 리뷰 수": 110,
        "혼합 리뷰 수": 110,
        "부정·혼합 리뷰 수": 150,
        "Steam 비추천 리뷰 수": 160,
        "최근 30일 부정·혼합": 160,
        "짧은 플레이타임 부정·혼합": 180,
        "High urgency 리뷰 수": 150,
        "우선순위 산정 규칙": 260,
        "판단 근거": 420,
        "패치·운영 참고": 420,
        "LLM 입력용 근거 문장": 520,
        "근거 문장": 520,
        "검증 항목": 220,
        "결과": 140,
        "내용": 520,
        "분류": 150,
        "기준": 560,
        "의미": 560,
        "리뷰 ID": 150,
        "리뷰 작성일": 160,
        "Steam 라벨": 130,
        "LLM 감정": 120,
        "LLM 주요 이슈": 170,
        "주요 이슈": 170,
        "LLM urgency 후보": 150,
        "urgency": 120,
        "리뷰 시점 플레이타임": 170,
        "플레이타임 구간": 150,
        "최근성 구간": 130,
        "LLM 리뷰 요약": 420,
        "리뷰 요약": 420,
        "LLM 개선 제안 후보": 420,
        "개선 제안 후보": 420,
    }
    return width_map.get(str(column_name), 160)

def render_wrapped_table(df: pd.DataFrame, height_px: int = 520) -> None:
    """긴 문장이 있는 표를 줄바꿈 가능한 HTML 표로 출력합니다."""
    if df is None or df.empty:
        st.info("표시할 데이터가 없습니다.")
        return

    display_df = df.copy().fillna("")
    display_df = display_df.rename(columns={
        "LLM 입력용 근거 문장": "근거 문장",
        "LLM 감정": "감정",
        "LLM 주요 이슈": "주요 이슈",
        "LLM urgency 후보": "긴급 확인 후보",
        "LLM 리뷰 요약": "리뷰 요약",
        "LLM 개선 제안 후보": "개선 제안 후보",
    })
    columns = list(display_df.columns)
    col_widths = [_column_width_px(col) for col in columns]
    min_table_width = max(sum(col_widths), 1100)

    colgroup_html = "\n".join(f'<col style="width: {width}px;">' for width in col_widths)
    thead_html = "".join(
        f'<th class="{_cell_class_name(col)}">{html.escape(str(col))}</th>'
        for col in columns
    )

    row_html_list = []
    for _, row in display_df.iterrows():
        cells = []
        for col in columns:
            cell_class = _cell_class_name(col)
            cell_text = _format_table_cell_text(col, row[col])
            cells.append(f'<td class="{cell_class}">{cell_text}</td>')
        row_html_list.append("<tr>" + "".join(cells) + "</tr>")

    tbody_html = "\n".join(row_html_list)

    template = Template(
        """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
html, body {
    margin: 0;
    padding: 0;
    background: transparent;
    color: rgb(250, 250, 250);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 14px;
}
.wrapped-table-wrapper {
    height: ${height_px}px;
    overflow: auto;
    border: 1px solid rgba(250, 250, 250, 0.18);
    border-radius: 10px;
    background: rgb(14, 17, 23);
}
.wrapped-table {
    width: ${min_table_width}px;
    min-width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}
.wrapped-table thead th {
    position: sticky;
    top: 0;
    z-index: 2;
    background: rgb(38, 39, 48);
    color: rgb(250, 250, 250);
    font-weight: 700;
    text-align: left;
}
.wrapped-table th,
.wrapped-table td {
    padding: 10px 12px;
    border-bottom: 1px solid rgba(250, 250, 250, 0.12);
    border-right: 1px solid rgba(250, 250, 250, 0.08);
    vertical-align: top;
    white-space: normal;
    word-break: keep-all;
    overflow-wrap: break-word;
    line-height: 1.55;
}
.wrapped-table .col-long-text {
    white-space: normal;
    word-break: keep-all;
    overflow-wrap: break-word;
}
.wrapped-table tbody tr:nth-child(even) td {
    background: rgba(250, 250, 250, 0.025);
}
.wrapped-table tbody tr:hover td {
    background: rgba(250, 250, 250, 0.06);
}
</style>
</head>
<body>
<div class="wrapped-table-wrapper">
<table class="wrapped-table">
<colgroup>
${colgroup_html}
</colgroup>
<thead><tr>${thead_html}</tr></thead>
<tbody>
${tbody_html}
</tbody>
</table>
</div>
</body>
</html>"""
    )

    table_html = template.substitute(
        height_px=height_px,
        min_table_width=min_table_width,
        colgroup_html=colgroup_html,
        thead_html=thead_html,
        tbody_html=tbody_html,
    )
    components.html(table_html, height=height_px + 24, scrolling=False)

def make_postlaunch_classification_guide_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    priority_guide = pd.DataFrame(
        [
            {
                "분류": "우선 점검",
                "기준": "부정·혼합 리뷰, Steam 비추천 맥락, 최근 반복 여부, 짧은 플레이타임 부정 반응 등을 함께 봤을 때 패치·운영 전에 우선적으로 점검할 이슈",
            },
            {
                "분류": "추가 검토",
                "기준": "반복성은 있으나 우선 점검 항목보다 영향 범위나 부정 맥락이 상대적으로 약해 단기 개선 또는 추가 확인이 필요한 이슈",
            },
            {
                "분류": "참고",
                "기준": "현재 근거만으로는 우선도는 낮지만, 운영 과정에서 참고하거나 누적 여부를 모니터링할 이슈",
            },
        ]
    )

    action_guide = pd.DataFrame(
        [
            {"분류": "즉시 확인", "의미": "재현 테스트, 로그 확인, 진행 차단 여부처럼 다음 패치 전 바로 확인해야 하는 항목"},
            {"분류": "단기 개선", "의미": "경험 품질을 낮추는 반복 문제로, 다음 업데이트나 가까운 패치에서 보완을 검토할 항목"},
            {"분류": "운영 커뮤니케이션 개선", "의미": "패치 노트, 공지, 알려진 이슈 안내, 커뮤니티 응답으로 오해나 불만을 줄일 수 있는 항목"},
            {"분류": "장기 검토", "의미": "콘텐츠, 구조, 밸런스처럼 개발 범위가 커서 로드맵 관점으로 검토할 항목"},
            {"분류": "강점 유지", "의미": "긍정 반응에서 확인된 강점으로, 업데이트와 마케팅 메시지에서 계속 살릴 항목"},
        ]
    )

    return priority_guide, action_guide

# ============================================================
# 출시 후 패치·운영 필터 도움말
# ============================================================

POSTLAUNCH_FILTER_HELP = {
    "priority": (
        "패치·운영에서 어떤 항목을 먼저 확인할지 선택합니다.\n\n"
        "- 우선 점검: 반복성과 부정 맥락이 커서 패치·운영에서 먼저 확인할 필요가 큰 항목입니다.\n"
        "- 추가 검토: 반복 근거는 있지만 패치 범위나 운영 상황에 따라 검토할 항목입니다.\n"
        "- 참고: 우선도는 낮지만 이후 업데이트나 회의에서 참고할 수 있는 항목입니다."
    ),
    "response_type": (
        "리뷰에서 발견된 이슈를 패치·운영 관점의 대응 방식으로 나눠 봅니다.\n\n"
        "- 즉시 확인: 버그, 진행 불가, 크래시처럼 QA 재현이나 원인 확인이 먼저 필요한 항목입니다.\n"
        "- 단기 개선: 다음 패치나 업데이트에서 비교적 빠르게 개선을 검토할 수 있는 항목입니다.\n"
        "- 운영 커뮤니케이션 개선: 공지, 패치 노트, 알려진 이슈 안내, 커뮤니티 응답으로 오해나 불만을 줄일 수 있는 항목입니다.\n"
        "- 장기 검토: 콘텐츠 구조, 밸런스, 반복 플레이 피로도처럼 중장기적으로 검토할 항목입니다.\n"
        "- 강점 유지: 유저가 긍정적으로 평가한 요소로, 이후 업데이트에서도 유지하거나 강화할 항목입니다."
    ),
    "issue_tag": (
        "리뷰에서 추출된 세부 이슈를 기준으로 패치·운영 제안 카드를 좁혀 봅니다.\n\n"
        "예: 버그, 최적화, UI/UX, 밸런스, 콘텐츠, 조작감, 가격·가치, 그래픽·사운드"
    ),
}

def render_postlaunch_filter_guide() -> None:
    """출시 후 필터 기준을 사용자에게 설명합니다."""
    st.markdown("### 필터 기준 안내")

    guide_col1, guide_col2 = st.columns(2)

    with guide_col1:
        render_section_lead(
            "대응 방식 설명",
            "즉시 확인: 버그, 진행 불가, 크래시처럼 QA 재현이나 원인 확인이 먼저 필요한 항목입니다.\n"
            "단기 개선: 패치나 업데이트에서 비교적 빠르게 개선을 검토할 수 있는 항목입니다.\n"
            "운영 커뮤니케이션 개선: 공지, 패치 노트, 알려진 이슈 안내, 커뮤니티 응답으로 불만을 줄일 수 있는 항목입니다.\n"
            "장기 검토: 콘텐츠 구조, 밸런스, 반복 플레이 피로도처럼 중장기적으로 검토할 항목입니다.\n"
            "강점 유지: 유저가 긍정적으로 평가한 요소로, 이후 업데이트에서도 유지하거나 강화할 항목입니다.",
        )

    with guide_col2:
        render_section_lead(
            "점검 우선도 설명",
            "우선 점검: 반복성과 부정 맥락이 커서 패치·운영에서 먼저 확인할 필요가 큰 항목입니다.\n"
            "추가 검토: 반복 근거는 있지만, 패치 범위나 운영 상황에 따라 검토할 항목입니다.\n"
            "참고: 우선도는 낮지만, 이후 업데이트나 회의에서 참고할 수 있는 항목입니다.",
        )

def render_postlaunch_validation_guide(validation_df: pd.DataFrame) -> None:
    """출시 후 패치·운영 생성 결과가 어떤 기준으로 점검되는지 설명합니다."""
    if validation_df is None or validation_df.empty:
        validation_count = 0
        passed_count = 0
        warning_count = 0
        result_message = "검증 결과 표가 아직 만들어지지 않았습니다."
    else:
        validation_count = len(validation_df)
        result_series = validation_df.get("결과", pd.Series(dtype=str)).fillna("").astype(str)
        passed_count = int(result_series.str.contains("통과", na=False).sum())
        warning_count = int(validation_count - passed_count)
        if warning_count == 0:
            result_message = "생성 결과가 근거 데이터의 대응 방식과 점검 우선도 기준을 그대로 사용했습니다."
        else:
            result_message = "일부 항목은 근거 데이터 기준으로 다시 확인하거나 보정할 필요가 있습니다."

    st.info(
        "생성 결과가 사전 계산된 대응 방식과 점검 우선도 기준을 유지했는지 확인합니다.      \n"
        "확인 필요 항목이 있으면 최종 표에서는 근거 데이터 기준으로 보정합니다."
    )

    metric_cols = st.columns(3)
    with metric_cols[0]:
        render_metric_card("검증 항목", f"{validation_count:,}개", "생성 결과와 근거 기준을 비교한 항목", tone="info")
    with metric_cols[1]:
        render_metric_card("통과", f"{passed_count:,}개", "근거 데이터 기준과 일치한 항목", tone="good")
    with metric_cols[2]:
        render_metric_card("확인 필요", f"{warning_count:,}개", "근거 기준과 차이가 있어 확인할 항목", tone="high")

    st.markdown(
        f"""
        #### 생성 결과 검증 기준

        검증 기준은 출시 후 패치·운영 분석에서 사용한 근거 데이터 원칙을 따릅니다.

        - 생성 과정은 **점검 우선도**와 **대응 방식**을 새로 판단하지 않습니다.
        - 점검 우선도는 근거 데이터에서 계산한 **우선 점검 / 추가 검토 / 참고** 기준을 그대로 사용합니다.
        - 대응 방식은 근거 데이터에서 계산한 **즉시 확인 / 단기 개선 / 운영 커뮤니케이션 개선 / 장기 검토 / 강점 유지** 기준을 그대로 사용합니다.
        - 반복 리뷰 수, 부정·혼합 맥락, Steam 비추천 맥락, 최근 반복 여부, 짧은 플레이타임 부정 반응을 주요 근거로 확인합니다.
        - `High urgency`는 빠르게 확인할 가능성이 있는 보조 신호로만 참고하고, 단독 기준으로 사용하지 않습니다.
        - 생성 과정은 계산된 근거를 바탕으로 개발자가 이해하기 쉬운 **권장 대응과 세부 실행안**을 문장화하는 역할을 합니다.

        **검증 결과 요약:** {result_message}
        """
    )

def build_postlaunch_top_issue_chart_df(
    strategy_df: pd.DataFrame,
    evidence_df: pd.DataFrame | None = None,
    top_n: int = 10,
) -> pd.DataFrame:
    """패치·운영 제안과 근거 데이터를 연결해 우선 이슈 TOP N 그래프용 데이터를 만듭니다.

    카드 결과에는 리뷰 수가 없을 수 있으므로, 가능하면 근거 데이터의
    affected_review_count와 rule_priority_hint를 사용합니다. 이 방식은 출시 전
    체크리스트의 우선 점검 이슈 TOP 10 그래프와 같은 구조입니다.
    """
    columns = ["이슈", "관련 리뷰 수", "점검 우선도", "_priority_order"]

    target_issues: list[str] = []
    if strategy_df is not None and not strategy_df.empty and "이슈" in strategy_df.columns:
        target_issues = (
            strategy_df["이슈"]
            .dropna()
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .unique()
            .tolist()
        )

    # 1순위: 근거 데이터의 실제 반복 리뷰 수를 사용합니다.
    if evidence_df is not None and not evidence_df.empty and "issue_name_kor" in evidence_df.columns:
        work = evidence_df.copy()

        if target_issues:
            work = work[work["issue_name_kor"].astype(str).isin(target_issues)].copy()

        if not work.empty:
            count_col = next(
                (c for c in ["affected_review_count", "관련 리뷰 수", "review_count", "negative_mixed_review_count"] if c in work.columns),
                None,
            )
            if count_col is None:
                work["관련 리뷰 수"] = 1
            else:
                work["관련 리뷰 수"] = pd.to_numeric(work[count_col], errors="coerce").fillna(0)

            priority_col = "rule_priority_hint" if "rule_priority_hint" in work.columns else None
            if priority_col is None:
                work["_priority_raw"] = "하"
            else:
                work["_priority_raw"] = work[priority_col].fillna("하").astype(str)

            work["_priority_order"] = work["_priority_raw"].map({"상": 1, "중": 2, "하": 3}).fillna(9).astype(int)

            chart_df = (
                work.groupby("issue_name_kor", as_index=False)
                .agg({"관련 리뷰 수": "max", "_priority_order": "min"})
                .rename(columns={"issue_name_kor": "이슈"})
            )
            chart_df["점검 우선도"] = chart_df["_priority_order"].map(
                {1: "우선 점검", 2: "추가 검토", 3: "참고"}
            ).fillna("참고")
            chart_df = chart_df.sort_values(
                ["_priority_order", "관련 리뷰 수"],
                ascending=[True, False],
            ).head(top_n)
            return chart_df[columns]

    # 2순위: 근거 데이터가 없을 때는 카드 결과 자체의 이슈 등장 횟수를 사용합니다.
    if strategy_df is None or strategy_df.empty or "이슈" not in strategy_df.columns:
        return pd.DataFrame(columns=columns)

    work = strategy_df.copy()
    if "우선 검토 수준" not in work.columns:
        work["우선 검토 수준"] = "하"

    work["관련 리뷰 수"] = 1
    work["_priority_order"] = work["우선 검토 수준"].map({"상": 1, "중": 2, "하": 3}).fillna(9).astype(int)

    chart_df = (
        work.groupby("이슈", as_index=False)
        .agg({"관련 리뷰 수": "sum", "_priority_order": "min"})
    )
    chart_df["점검 우선도"] = chart_df["_priority_order"].map(
        {1: "우선 점검", 2: "추가 검토", 3: "참고"}
    ).fillna("참고")
    chart_df = chart_df.sort_values(
        ["_priority_order", "관련 리뷰 수"],
        ascending=[True, False],
    ).head(top_n)
    return chart_df[columns]

def render_postlaunch_top_issue_chart(chart_df: pd.DataFrame) -> None:
    """출시 전 우선 점검 이슈 TOP 10과 같은 형태로 패치·운영 우선 이슈를 출력합니다."""
    if chart_df is None or chart_df.empty:
        st.info("표시할 패치·운영 우선 이슈 데이터가 없습니다.")
        return

    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X(
                "관련 리뷰 수:Q",
                title="관련 리뷰 수",
                axis=alt.Axis(labelAngle=0, titleAngle=0, titlePadding=12),
            ),
            y=alt.Y(
                "이슈:N",
                title="이슈",
                sort="-x",
                axis=alt.Axis(
                    labelAngle=0,
                    labelLimit=260,
                    titleAngle=0,
                    titleAlign="left",
                    titleAnchor="start",
                    titleX=-2,
                    titleY=-10,
                    titlePadding=10,
                ),
            ),
            color=alt.Color(
                "점검 우선도:N",
                scale=alt.Scale(
                    domain=["우선 점검", "추가 검토", "참고"],
                    range=["#ef4444", "#f59e0b", "#3b82f6"],
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("이슈:N", title="이슈"),
                alt.Tooltip("점검 우선도:N", title="점검 우선도"),
                alt.Tooltip("관련 리뷰 수:Q", title="관련 리뷰 수"),
            ],
        )
        .properties(height=340, padding={"top": 8, "left": 8, "right": 8, "bottom": 8})
    )
    st.altair_chart(apply_dark_chart_theme(chart), use_container_width=True)

def render_postlaunch_overview(
    analysis_overview: dict,
    selected_evidence: pd.DataFrame,
    show_header: bool = True,
    show_lead: bool = True,
) -> None:
    if show_header:
        st.header("2. 현재 리뷰 상태 요약")

    if show_lead:
        render_section_lead(
            "현재 리뷰 상태를 먼저 확인합니다",
            "상단 지표는 분석에 사용한 리뷰 규모, 부정·혼합 반응, Steam 비추천, 긴급 확인 후보를 빠르게 보여줍니다. 아래 반복 이슈 요약은 어떤 문제를 먼저 확인할지 판단하기 위한 보조 근거입니다.",
        )
    else:
        st.caption(
            "분석에 사용한 리뷰 규모, 부정·혼합 반응, Steam 비추천, 긴급 확인 후보와 반복 이슈를 함께 요약합니다."
        )

    metric1, metric2, metric3, metric4, metric5 = st.columns(5)

    with metric1:
        render_metric_card("분석 리뷰", f"{analysis_overview['review_count']:,}개", "분석에 사용한 리뷰", tone="info")

    with metric2:
        render_metric_card("발견된 이슈 태그", f"{analysis_overview['issue_tag_count']:,}개", "리뷰에서 추출된 이슈", tone="info")

    with metric3:
        render_metric_card(
            "부정·혼합 반응",
            f"{analysis_overview['llm_negative_mixed_review_count']:,}개",
            f"전체 대비 {analysis_overview['llm_negative_mixed_rate'] * 100:.1f}%",
            tone="warn",
        )

    with metric4:
        render_metric_card(
            "Steam 비추천",
            f"{analysis_overview['steam_negative_review_count']:,}개",
            f"전체 대비 {analysis_overview['steam_negative_rate'] * 100:.1f}%",
            tone="high",
        )

    with metric5:
        render_metric_card(
            "긴급 확인 후보",
            f"{analysis_overview['high_urgency_review_count']:,}개",
            f"전체 대비 {analysis_overview['high_urgency_rate'] * 100:.1f}%",
            tone="high",
        )

    st.caption(
        "긴급 확인 후보는 리뷰 문맥상 빠른 확인이 필요해 보이는 사례를 표시한 보조 지표입니다. "
        "우선 점검 항목은 반복성, 부정 맥락, 시급도 근거를 함께 사용해 정리합니다."
    )

    st.subheader("반복 이슈 요약")
    chart_col1, chart_col2 = st.columns(2)

    evidence_for_chart = selected_evidence.copy()
    if "rule_priority_hint" in evidence_for_chart.columns:
        evidence_for_chart["점검 우선도"] = evidence_for_chart["rule_priority_hint"].apply(_priority_display)

    with chart_col1:
        priority_df = _count_chart_df(
            evidence_for_chart,
            column="점검 우선도",
            order=["우선 점검", "추가 검토", "참고"],
            label="점검 우선도",
        )
        render_bar_chart(priority_df, "점검 우선도", "건수", "점검 우선도", "건수", height=280)

    with chart_col2:
        action_order = ["즉시 확인", "단기 개선", "운영 커뮤니케이션 개선", "장기 검토", "검토 필요", "강점 유지"]
        action_df = _count_chart_df(
            selected_evidence,
            column="action_group_hint",
            order=[g for g in action_order if g in selected_evidence.get("action_group_hint", pd.Series(dtype=str)).astype(str).unique().tolist()],
            label="대응 방식",
        )
        render_horizontal_bar_chart(action_df, "대응 방식", "건수", "대응 방식", "건수", height=280)

    if "affected_review_count" in selected_evidence.columns and "issue_name_kor" in selected_evidence.columns:
        top_issue_df = (
            selected_evidence[["issue_name_kor", "affected_review_count"]]
            .copy()
            .rename(columns={"issue_name_kor": "이슈", "affected_review_count": "관련 리뷰 수"})
        )
        top_issue_df["관련 리뷰 수"] = pd.to_numeric(top_issue_df["관련 리뷰 수"], errors="coerce").fillna(0)
        top_issue_df = top_issue_df.sort_values("관련 리뷰 수", ascending=False).head(10)

        st.subheader("상위 반복 이슈 TOP 10")
        render_horizontal_bar_chart(top_issue_df, "이슈", "관련 리뷰 수", "이슈", "관련 리뷰 수", height=360)



def _extract_count_from_text(text: str, patterns: list[str]) -> str:
    """근거 요약 문장에서 특정 수치를 추출합니다."""
    clean = clean_pipeline_terms(str(text or ""))
    for pattern in patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if match:
            return match.group(1).replace(",", "")
    return "-"

def _postlaunch_evidence_counts_for_card(evidence_summary: str) -> dict[str, str]:
    """패치·운영 카드 우측 근거 박스에 표시할 핵심 수치를 정리합니다."""
    text = clean_pipeline_terms(str(evidence_summary or ""))
    affected = _extract_count_from_text(
        text,
        [
            r"(?:영향|관련)\s*리뷰\s*(?:수)?\s*([0-9,]+)\s*개",
            r"리뷰\s*(?:수)?\s*([0-9,]+)\s*개",
        ],
    )
    steam_negative = _extract_count_from_text(
        text,
        [
            r"Steam\s*비추천\s*(?:맥락|리뷰)?\s*([0-9,]+)\s*개",
            r"비추천\s*(?:맥락|리뷰)?\s*([0-9,]+)\s*개",
        ],
    )
    early_negative = _extract_count_from_text(
        text,
        [
            r"(?:초반|초기|짧은\s*플레이타임|짧은\s*플레이\s*타임).*?(?:부정|혼합|반응).*?([0-9,]+)\s*개",
            r"(?:부정\s*반응|부정·혼합).*?([0-9,]+)\s*개",
        ],
    )
    return {
        "영향 리뷰 수": affected,
        "Steam 비추천 맥락": steam_negative,
        "초기 플레이타임 부정 반응": early_negative,
    }

def render_strategy_cards(
    strategy_df: pd.DataFrame,
    evidence_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """패치·운영 제안 탭을 KPI → 그래프 → 필터 → 카드 순서로 출력합니다."""
    render_section_lead(
        "우선 점검할 이슈와 대응 방향을 카드로 확인합니다.",
        "아래 요약과 그래프는 전체 패치·운영 제안 항목을 기준으로 먼저 보여줍니다.      \n"
        "이후 점검 우선도, 대응 방식, 이슈 태그로 필요한 카드만 좁혀 확인할 수 있습니다.",
    )

    # --------------------------------------------------------
    # 1) 전체 기준 KPI
    # --------------------------------------------------------
    total_count = len(strategy_df)
    high_count = int((strategy_df["우선 검토 수준"].astype(str) == "상").sum()) if "우선 검토 수준" in strategy_df.columns else 0
    mid_count = int((strategy_df["우선 검토 수준"].astype(str) == "중").sum()) if "우선 검토 수준" in strategy_df.columns else 0
    low_count = int((strategy_df["우선 검토 수준"].astype(str) == "하").sum()) if "우선 검토 수준" in strategy_df.columns else 0

    summary_cols = st.columns(4)
    with summary_cols[0]:
        render_metric_card("전체 제안 항목", f"{total_count:,}개", "생성된 패치·운영 제안 항목", tone="neutral")
    with summary_cols[1]:
        render_metric_card("우선 점검", f"{high_count:,}개", "패치·운영에서 먼저 확인할 항목", tone="high")
    with summary_cols[2]:
        render_metric_card("추가 검토", f"{mid_count:,}개", "조건에 따라 추가로 확인할 항목", tone="mid")
    with summary_cols[3]:
        render_metric_card("참고", f"{low_count:,}개", "후순위로 참고할 항목", tone="low")

    st.caption(
        "아래 그래프는 전체 패치·운영 제안 항목의 점검 우선도와 주요 이슈 분포를 보여줍니다. "
    )

    # --------------------------------------------------------
    # 2) 전체 기준 그래프
    # --------------------------------------------------------
    priority_chart_source = strategy_df.copy()
    if "우선 검토 수준" in priority_chart_source.columns:
        priority_chart_source["점검 우선도"] = priority_chart_source["우선 검토 수준"].apply(_priority_display)

    priority_chart_df = _count_chart_df(
        priority_chart_source,
        column="점검 우선도",
        order=["우선 점검", "추가 검토", "참고"],
        label="점검 우선도",
    )
    top_issue_chart_df = build_postlaunch_top_issue_chart_df(strategy_df, evidence_df=evidence_df, top_n=10)

    graph_col1, graph_col2 = st.columns(2)
    with graph_col1:
        st.caption("점검 우선도 분포")
        st.caption("전체 제안 항목이 우선 점검, 추가 검토, 참고 중 어디에 많이 분포하는지 보여줍니다.")
        render_bar_chart(
            priority_chart_df,
            x_col="점검 우선도",
            y_col="건수",
            x_title="점검 우선도",
            y_title="건수",
            height=320,
        )
    with graph_col2:
        st.caption("패치·운영 우선 이슈 TOP 10")
        st.caption("리뷰에서 반복적으로 언급된 이슈 중 패치·운영에서 먼저 확인할 항목입니다.")
        render_postlaunch_top_issue_chart(top_issue_chart_df)

    st.divider()

    # --------------------------------------------------------
    # 3) 카드 필터
    # --------------------------------------------------------
    st.markdown("#### 패치·운영 카드 필터")
    filter_col1, filter_col2, filter_col3 = st.columns(3)

    with filter_col1:
        raw_priority_values = strategy_df["우선 검토 수준"].astype(str).unique().tolist()
        priority_options = ["전체"] + [_priority_display(p) for p in ["상", "중", "하"] if p in raw_priority_values]
        selected_priority_display = st.selectbox(
            "점검 우선도",
            priority_options,
            key="postlaunch_strategy_priority_filter",
            help=POSTLAUNCH_FILTER_HELP["priority"],
        )
        selected_priority = _priority_raw(selected_priority_display)

    with filter_col2:
        action_options = ["전체"] + sorted(strategy_df["대응 구분"].dropna().astype(str).unique().tolist())
        selected_action = st.selectbox(
            "대응 방식",
            action_options,
            key="postlaunch_strategy_action_filter",
            help=POSTLAUNCH_FILTER_HELP["response_type"],
        )

    with filter_col3:
        issue_tag_options = _available_strategy_issue_tag_options(strategy_df)
        selected_issue_tags = st.multiselect(
            "이슈 태그",
            options=issue_tag_options,
            default=[],
            key="postlaunch_strategy_issue_tag_filter",
            help=POSTLAUNCH_FILTER_HELP["issue_tag"],
            placeholder="이슈 태그를 선택해주세요",
        )

    card_df = strategy_df.copy()

    if selected_action != "전체":
        card_df = card_df[card_df["대응 구분"].astype(str) == selected_action]

    if selected_priority_display != "전체":
        card_df = card_df[card_df["우선 검토 수준"].astype(str) == selected_priority]

    if selected_issue_tags:
        card_df = card_df[
            card_df.apply(lambda row: _row_has_selected_strategy_issue_tag(row, selected_issue_tags), axis=1)
        ]

    st.caption(
        f"현재 선택한 필터에 해당하는 패치·운영 제안 항목: {len(card_df):,}개 / 전체 {len(strategy_df):,}개"
    )

    # --------------------------------------------------------
    # 5) 카드 목록
    # --------------------------------------------------------
    if card_df.empty:
        st.info("현재 필터 조건에 맞는 패치·운영 제안이 없습니다.")
        return card_df

    for idx, row in card_df.reset_index(drop=True).iterrows():
        priority = row.get("우선 검토 수준", "-")
        p_class = _priority_class(priority)
        issue_badges = [render_badge(tag, "neutral") for tag in _strategy_issue_tag_values(row)[:2]]
        badges = "".join(
            [
                render_badge(_priority_display(priority), p_class),
                render_badge(row.get("대응 구분", "-"), "neutral"),
                *issue_badges,
            ]
        )

        evidence_summary = clean_pipeline_terms(str(row.get("근거 요약", "-") or "-"))
        evidence_counts = _postlaunch_evidence_counts_for_card(evidence_summary)
        issue_name = row.get("이슈", "")
        patch_direction = row.get("패치·운영 방향", "-")
        detail_actions = clean_pipeline_terms(str(row.get("세부 실행안", "") or "").strip())
        expected_effect = clean_pipeline_terms(str(row.get("기대 효과", "") or "").strip())
        caution = clean_pipeline_terms(str(row.get("주의사항", "") or "").strip())

        detail_sections = []
        if detail_actions:
            detail_sections.append(
                '<div class="ops-detail-block">'
                '<div class="ops-detail-label">권장 실행 방법</div>'
                f'<div class="ops-detail-text">{_html_text(detail_actions)}</div>'
                '</div>'
            )
        if expected_effect:
            detail_sections.append(
                '<div class="ops-detail-block">'
                '<div class="ops-detail-label">기대 효과</div>'
                f'<div class="ops-detail-text">{_html_text(expected_effect)}</div>'
                '</div>'
            )
        if caution:
            detail_sections.append(
                '<div class="ops-detail-block ops-detail-caution">'
                '<div class="ops-detail-label">확인 전 주의사항</div>'
                f'<div class="ops-detail-text">{_html_text(caution)}</div>'
                '</div>'
            )

        detail_html = ""
        if detail_sections:
            detail_html = '<div class="ops-detail-box">' + "".join(detail_sections) + '</div>'

        card_html = (
            f'<div class="ops-card {p_class}">'
            '<div class="ops-left">'
            f'<div class="ops-badges">{badges}</div>'
            f'<div class="ops-title">{idx + 1}. {_html_text(issue_name)}</div>'
            '</div>'
            '<div class="ops-center">'
            '<div class="ops-center-block">'
            '<div class="ops-mini-label">왜 확인해야 하나요?</div>'
            f'<div class="ops-mini-text">{_html_text(evidence_summary)}</div>'
            '</div>'
            '<div class="ops-center-block">'
            '<div class="ops-mini-label">권장 대응</div>'
            f'<div class="ops-mini-text">{_html_text(patch_direction)}</div>'
            '</div>'
            '</div>'
            '<div class="ops-evidence-box">'
            '<div class="ops-evidence-title">근거 요약</div>'
            f'<div class="ops-evidence-line"><span class="ops-evidence-name">영향 리뷰 수</span><span class="ops-evidence-value">{_html_text(evidence_counts["영향 리뷰 수"])}개</span></div>'
            f'<div class="ops-evidence-line"><span class="ops-evidence-name">Steam 비추천 맥락</span><span class="ops-evidence-value">{_html_text(evidence_counts["Steam 비추천 맥락"])}개</span></div>'
            f'<div class="ops-evidence-line"><span class="ops-evidence-name">초기 플레이타임 부정 반응</span><span class="ops-evidence-value">{_html_text(evidence_counts["초기 플레이타임 부정 반응"])}개</span></div>'
            '</div>'
            f'{detail_html}'
            '</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)
    return card_df

# ============================================================
# 페이지 제목
# ============================================================
inject_dashboard_style()

st.title("🛠️ 출시 후 패치·운영 전략")
st.caption("출시 후 Steam 리뷰를 바탕으로, 먼저 확인할 패치·운영 이슈를 제안합니다.")

with st.expander("이 페이지 설명 자세히 보기", expanded=False):
    st.markdown(
        """
#### 이 페이지는 무엇을 하나요?
이미 출시된 게임의 Steam 리뷰를 바탕으로 반복되는 문제와 강점을 정리하고, 패치·운영에서 먼저 확인할 항목을 제안 카드로 보여줍니다.

#### 사용 순서
1. **분석할 게임을 선택합니다.**  
   출시 후 리뷰가 수집된 게임 중 확인할 대상을 선택합니다.
2. **[패치·운영 방향 생성] 버튼을 누릅니다.**  
   선택한 게임의 리뷰 기반 제안 카드가 생성됩니다.
3. **제안 카드를 확인합니다.**  
   우선 점검, 추가 검토, 참고 항목을 보고 어떤 이슈를 먼저 확인할지 정리합니다.
4. **필요하면 필터로 좁혀 봅니다.**  
   점검 우선도, 대응 방식, 이슈 태그를 선택해 필요한 카드만 확인합니다.
5. **근거가 필요하면 상세 근거·검증 보기를 켭니다.**  
   반복 이슈 근거, 리뷰 샘플, 생성 결과 검증 내용을 추가로 확인할 수 있습니다.

#### 해석할 때 주의할 점
- 이 결과는 패치 방향을 확정하는 도구가 아니라 우선 검토 항목을 정리하는 참고 자료입니다.
- 최종 판단에는 개발 일정, 팀 리소스, 실제 버그 재현 여부, 커뮤니티 상황을 함께 반영해야 합니다.
        """
    )

st.divider()

# ============================================================
# 사이드바 설정
# ============================================================
run_name = DEFAULT_RUN_NAME

# 사용자 화면에서는 내부 근거 행 수/LLM 세부 설정을 숨깁니다.
# 발표·시연 안정성을 위해 기본값은 코드에서 고정합니다.
max_issues = 18
max_evidence_rows = 12
max_review_rows = 100
use_cache = True
force_regenerate = False
temperature = 0.0
max_retries = 3

show_debug_info = False

with st.sidebar:
    st.header("🛠️ 화면 안내")
    st.caption(
        "분석할 게임을 선택하면 Steam 리뷰에서 반복된 이슈를 바탕으로 "
        "패치·운영 우선순위와 대응 방향을 확인할 수 있습니다."
    )
    show_detail_sections = st.checkbox(
        "상세 근거·검증 보기",
        value=False,
        help="기본 화면은 패치·운영 제안만 보여줍니다. 켜면 근거 보기와 리뷰·검증 탭을 추가로 확인할 수 있습니다.",
    )

notify_detail_toggle_change(
    enabled=show_detail_sections,
    page_key="postlaunch",
    detail_label="상세 근거·검증 보기",
)

# ============================================================
# 데이터 로드
# ============================================================
try:
    data = load_postlaunch_data(run_name=run_name)
except FileNotFoundError as e:
    st.error("출시 후 패치·운영 전략에 필요한 분석 데이터 파일을 찾을 수 없습니다.")
    st.info("먼저 출시 후 분석/전처리 과정을 실행해 필요한 CSV 파일을 생성한 뒤 다시 실행해주세요.")
    if show_debug_info:
        with st.expander("상세 오류 확인", expanded=False):
            st.code(str(e))
    st.stop()

review_base = data["review_base"]
issue_summary = data["issue_summary"]
evidence_base = data["evidence_base"]
tableau_source = data["tableau_source"]

# ============================================================
# 데이터 로드 정보: 개발자 정보 보기에서만 노출
# ============================================================
if show_debug_info:
    with st.expander("📁 불러온 데이터 확인", expanded=False):
        st.write(f"**실행 기준:** `{data['run_name']}`")
        st.write(f"**데이터 폴더:** `{data['data_dir']}`")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("리뷰 전처리", f"{len(review_base):,}행")

        with col2:
            st.metric("이슈 요약", f"{len(issue_summary):,}행")

        with col3:
            st.metric("패치·운영 근거", f"{len(evidence_base):,}행")

        with col4:
            st.metric("원천 데이터", f"{len(tableau_source):,}행")

# ============================================================
# 게임 선택 및 제안 생성
# ============================================================
game_options = get_game_options(review_base, evidence_base)

if game_options.empty:
    st.error("선택 가능한 게임 목록을 만들 수 없습니다. appid, game_name 컬럼을 확인해야 합니다.")
    st.stop()

NO_GAME_OPTION = "게임을 선택해주세요"
game_label_options = [NO_GAME_OPTION] + game_options["game_label"].tolist()

if st.session_state.get("postlaunch_game_select") not in game_label_options:
    st.session_state["postlaunch_game_select"] = NO_GAME_OPTION

def reset_postlaunch_input_state() -> None:
    """게임 선택과 생성 결과를 함께 초기화합니다."""
    for key in list(st.session_state.keys()):
        if str(key).startswith("postlaunch_llm_result_"):
            del st.session_state[key]
    st.session_state["postlaunch_game_select"] = NO_GAME_OPTION

st.header("1. 분석 대상 게임 선택 및 제안 생성")
st.caption("분석할 게임을 선택하고 **패치·운영 방향 생성** 버튼을 누르면 제안 카드가 생성됩니다.")

postlaunch_input_box = st.container(border=True)

with postlaunch_input_box:
    selected_label = st.selectbox(
        "게임 선택",
        options=game_label_options,
        key="postlaunch_game_select",
        help="분석 데이터가 준비된 게임만 선택할 수 있습니다.",
    )

    col_generate, col_clear = st.columns([1, 1])

    with col_generate:
        generate_clicked = st.button(
            "패치·운영 방향 생성",
            type="primary",
            use_container_width=True,
            disabled=(selected_label == NO_GAME_OPTION),
        )

    with col_clear:
        clear_clicked = st.button(
            "현재 결과 초기화",
            use_container_width=True,
            on_click=reset_postlaunch_input_state,
        )

if selected_label == NO_GAME_OPTION:
    st.info("분석할 게임을 먼저 선택해주세요. 게임을 선택하면 패치·운영 방향 생성 버튼을 사용할 수 있습니다.")
    st.stop()

selected_row = game_options[game_options["game_label"] == selected_label].iloc[0]
selected_appid = int(selected_row["appid"])
selected_game_name = str(selected_row["game_name"])

# ============================================================
# 선택 게임 데이터 생성
# ============================================================
review_game = filter_by_appid(review_base, selected_appid)

if review_game.empty:
    st.warning("선택한 게임의 리뷰 분석 데이터가 없습니다.")
    st.stop()

analysis_overview = make_analysis_overview(
    review_base=review_base,
    tableau_source=tableau_source,
    selected_appid=selected_appid,
    selected_game_name=selected_game_name,
)

selected_evidence = select_patch_ops_evidence(
    evidence_base=evidence_base,
    selected_appid=selected_appid,
    max_issues=max_issues,
)

if selected_evidence.empty:
    st.warning("선택한 게임의 패치·운영 근거 데이터가 없습니다.")
    st.stop()

patch_ops_prompt = build_patch_ops_prompt(
    analysis_overview=analysis_overview,
    selected_evidence_df=selected_evidence,
    max_issues_for_prompt=max_issues,
)

cache_key = make_postlaunch_cache_key(selected_appid, selected_evidence)
cached_payload = load_cached_postlaunch_result(run_name, selected_appid, cache_key) if use_cache else None
cached_result = extract_cached_result(cached_payload)

state_key = f"postlaunch_llm_result_{selected_appid}_{cache_key}"

if force_regenerate:
    st.session_state[state_key] = None
elif state_key not in st.session_state:
    st.session_state[state_key] = cached_result

result_dict = st.session_state[state_key]

if result_dict:
    st.success("이 게임과 현재 근거표 기준의 기존 패치·운영 제안 결과를 불러왔습니다.")
else:
    st.info("아직 이 게임과 현재 근거표 기준의 패치·운영 제안 결과가 없습니다. 버튼을 누르면 제안 카드를 생성합니다.")

if generate_clicked:
    if cached_result is not None and not force_regenerate:
        st.session_state[state_key] = cached_result
        st.success("동일 조건의 기존 패치·운영 제안 결과를 불러왔습니다.")
        st.rerun()
    else:
        with st.spinner("패치·운영 방향 제안 리포트를 생성하는 중입니다..."):
            try:
                generated_result = generate_postlaunch_patch_ops_with_llm(
                    patch_ops_prompt=patch_ops_prompt,
                    temperature=temperature,
                    max_retries=max_retries,
                )
                save_cached_postlaunch_result(
                    run_name=run_name,
                    selected_appid=selected_appid,
                    cache_key=cache_key,
                    result_dict=generated_result,
                    analysis_overview=analysis_overview,
                )
                st.session_state[state_key] = generated_result
                st.success("패치·운영 제안 리포트를 생성했습니다.")
                st.rerun()
            except Exception as e:
                st.error("패치·운영 제안 생성 중 오류가 발생했습니다.")
                st.info("API 키, 모델명, 네트워크 상태를 확인한 뒤 다시 시도해주세요.")
                if show_debug_info:
                    with st.expander("상세 오류 확인", expanded=False):
                        st.exception(e)

result_dict = st.session_state.get(state_key)
validation_warnings = validate_patch_ops_result(result_dict, selected_evidence) if result_dict else ["생성 결과가 아직 없습니다."]
validation_df = make_validation_result_df(validation_warnings)
strategy_df = make_patch_ops_strategy_table(result_dict) if result_dict else None

# ============================================================
# 탭 출력
# ============================================================
st.divider()

if show_detail_sections:
    tab_strategy, tab_evidence, tab_review_validation = st.tabs(
        [
            "🛠️ 패치·운영 제안",
            "📊 근거 보기",
            "🧾 리뷰·검증",
        ]
    )
else:
    (tab_strategy,) = st.tabs(["🛠️ 패치·운영 제안"])

# ------------------------------------------------------------
# Tab 1. 패치·운영 제안
# ------------------------------------------------------------
with tab_strategy:
    if not result_dict or strategy_df is None or strategy_df.empty:
        st.warning("아직 패치·운영 제안이 생성되지 않았습니다. 상단의 생성 버튼을 먼저 눌러주세요.")
    else:
        filtered_strategy_df = render_strategy_cards(strategy_df, evidence_df=selected_evidence)

        with st.expander("표 형태로 보기", expanded=False):
            render_wrapped_table(filtered_strategy_df, height_px=560)

        strategy_csv = strategy_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="패치 및 운영 제안 CSV 다운로드",
            data=strategy_csv,
            file_name=f"postlaunch_patch_ops_strategy_{selected_appid}.csv",
            mime="text/csv",
        )

# ------------------------------------------------------------
# Tab 2. 근거 보기
# ------------------------------------------------------------
if show_detail_sections:
    with tab_evidence:
        render_section_lead(
            "패치·운영 제안에 사용한 근거를 확인합니다.",
            "이 탭은 선택한 게임의 리뷰에서 어떤 이슈가 반복되었고, 어떤 대응 방식으로 묶였는지 보여줍니다.     \n"
            "반복 리뷰 수, 부정·혼합 맥락, Steam 비추천 맥락, High urgency 신호를 함께 확인할 수 있습니다.",
        )

        with st.expander("현재 리뷰 상태 요약 보기", expanded=False):
            st.info(
                "선택한 게임의 리뷰 규모, 부정·혼합 반응, Steam 비추천, 긴급 확인 후보를 요약합니다.    \n"
                "패치·운영 제안 카드가 어떤 리뷰 상태를 바탕으로 만들어졌는지 빠르게 확인하는 용도입니다."
            )
            render_postlaunch_overview(
                analysis_overview=analysis_overview,
                selected_evidence=selected_evidence,
                show_header=False,
                show_lead=False,
            )

        with st.expander("반복 이슈 근거 데이터 보기", expanded=False):
            st.info(
                "패치·운영 제안에 사용된 이슈별 근거 데이터를 표로 확인합니다.  \n"
                "반복 리뷰 수, 부정·혼합 맥락, Steam 비추천, 짧은 플레이타임 부정 반응 등을 함께 보며 제안의 근거를 검토할 수 있습니다."
            )
            filter_col1, filter_col2, filter_col3 = st.columns(3)

            with filter_col1:
                raw_priority_values = selected_evidence.get("rule_priority_hint", pd.Series(dtype=str)).astype(str).unique().tolist()
                priority_options = ["전체"] + [_priority_display(p) for p in ["상", "중", "하"] if p in raw_priority_values]
                selected_priority_display = st.selectbox(
                    "점검 우선도",
                    priority_options,
                    key="postlaunch_priority_filter",
                    help=POSTLAUNCH_FILTER_HELP["priority"],
                )
                selected_priority_filter = _priority_raw(selected_priority_display)

            with filter_col2:
                action_options = ["전체"] + sorted(
                    selected_evidence["action_group_hint"].dropna().astype(str).unique().tolist()
                ) if "action_group_hint" in selected_evidence.columns else ["전체"]
                selected_action_filter = st.selectbox(
                    "대응 방식",
                    action_options,
                    key="postlaunch_action_filter",
                    help=POSTLAUNCH_FILTER_HELP["response_type"],
                )

            with filter_col3:
                issue_tag_options = (
                    sorted(selected_evidence["issue_name_kor"].dropna().astype(str).unique().tolist())
                    if "issue_name_kor" in selected_evidence.columns
                    else []
                )
                selected_issue_tags = st.multiselect(
                    "이슈 태그",
                    options=issue_tag_options,
                    default=[],
                    key="postlaunch_issue_tag_filter",
                    help=POSTLAUNCH_FILTER_HELP["issue_tag"],
                    placeholder="이슈 태그를 선택해주세요",
                )

            evidence_view = selected_evidence.copy()

            if selected_action_filter != "전체" and "action_group_hint" in evidence_view.columns:
                evidence_view = evidence_view[evidence_view["action_group_hint"] == selected_action_filter]

            if selected_priority_filter != "전체" and "rule_priority_hint" in evidence_view.columns:
                evidence_view = evidence_view[evidence_view["rule_priority_hint"] == selected_priority_filter]

            if selected_issue_tags and "issue_name_kor" in evidence_view.columns:
                evidence_view = evidence_view[
                    evidence_view["issue_name_kor"].astype(str).isin(selected_issue_tags)
                ]

            st.caption(f"표시 중인 근거 데이터: {len(evidence_view):,}행 / 전체 {len(selected_evidence):,}행")

            evidence_display_df = make_evidence_display_df(evidence_view, max_rows=max_evidence_rows)
            render_wrapped_table(evidence_display_df, height_px=560)

            evidence_csv = evidence_display_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="근거 데이터 CSV 다운로드",
                data=evidence_csv,
                file_name=f"postlaunch_evidence_{selected_appid}.csv",
                mime="text/csv",
            )

# ------------------------------------------------------------
# Tab 3. 리뷰·검증
# ------------------------------------------------------------
if show_detail_sections:
    with tab_review_validation:
        render_section_lead(
            "패치·운영 제안의 검증 결과와 리뷰 샘플을 확인합니다.",
            "이 탭에서는 생성된 패치·운영 제안이 근거 데이터의 대응 방식과 점검 우선도를 유지했는지 확인합니다.     \n필요할 때 실제 리뷰 샘플과 패치·운영 분류 기준도 함께 참고할 수 있습니다.",
        )

        with st.expander("생성 결과 점검 보기", expanded=False):
            render_postlaunch_validation_guide(validation_df)

            st.markdown("#### 검증 결과표")
            st.caption(
                "생성된 패치·운영 제안이 근거 데이터의 대응 방식과 점검 우선도를 그대로 사용했는지 확인한 결과입니다. "
                "확인 필요 항목이 있을 경우, 최종 표에서는 근거 데이터 기준으로 보정합니다."
            )
            render_wrapped_table(validation_df, height_px=360)

            validation_csv = validation_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="검증 결과 CSV 다운로드",
                data=validation_csv,
                file_name=f"postlaunch_validation_result_{selected_appid}.csv",
                mime="text/csv",
            )

        with st.expander("리뷰 샘플 보기", expanded=False):
            st.info(
                "선택한 게임의 실제 리뷰 단위 분석 결과를 확인합니다.   \n"
                "제안 카드가 어떤 리뷰 내용에서 출발했는지 볼 때 사용하는 참고 자료입니다."
            )

            review_display_df = make_review_display_df(
                review_base=review_base,
                selected_appid=selected_appid,
                max_rows=max_review_rows,
            )
            render_wrapped_table(review_display_df, height_px=620)

            review_csv = review_display_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="리뷰 샘플 CSV 다운로드",
                data=review_csv,
                file_name=f"postlaunch_review_sample_{selected_appid}.csv",
                mime="text/csv",
            )

        with st.expander("패치·운영 분류 기준 보기", expanded=False):
            st.info(
                "패치·운영 제안 카드의 점검 우선도와 대응 방식을 어떻게 해석해야 하는지 정리한 기준표입니다.    \n"
                "내부 기준값은 화면에서 우선 점검, 추가 검토, 참고로 바꾸어 표시합니다."
            )
            priority_guide_df, action_guide_df = make_postlaunch_classification_guide_tables()
            guide_col1, guide_col2 = st.columns(2)
            with guide_col1:
                st.markdown("#### 점검 우선도 기준")
                render_wrapped_table(priority_guide_df, height_px=260)
            with guide_col2:
                st.markdown("#### 대응 방식 기준")
                render_wrapped_table(action_guide_df, height_px=320)
