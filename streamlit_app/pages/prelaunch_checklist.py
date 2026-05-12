import html
import re

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from utils.prelaunch_engine import (
    DEFAULT_RUN_NAME,
    load_prelaunch_data,
    get_filter_options,
    filter_matched_games,
    select_condition_evidence,
    get_overall_issues,
    make_tag_dna_summary,
    make_evidence_display_df,
    build_checklist_prompt,
    make_prelaunch_cache_key,
    load_cached_prelaunch_result,
    save_cached_prelaunch_result,
    generate_prelaunch_checklist_with_llm,
    make_checklist_table,
    make_prelaunch_validation_result_df,
    make_prelaunch_report_markdown,
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
        .dash-kpi-value {
            font-size: 1.95rem;
            font-weight: 800;
            line-height: 1.05;
            margin-bottom: 6px;
        }
        .dash-kpi-label {
            font-size: 0.92rem;
            font-weight: 700;
            color: rgba(250,250,250,0.92);
        }
        .dash-kpi-caption {
            font-size: 0.78rem;
            color: rgba(250,250,250,0.62);
            margin-top: 4px;
            line-height: 1.45;
        }
        .dash-section-lead {
            background: linear-gradient(135deg, rgba(42,117,255,0.15), rgba(40,190,140,0.08));
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 18px;
            padding: 18px 22px;
            margin: 10px 0 18px 0;
        }
        .dash-section-title {
            font-size: 1.08rem;
            font-weight: 800;
            margin-bottom: 4px;
        }
        .dash-section-text {
            font-size: 0.9rem;
            color: rgba(250,250,250,0.72);
            line-height: 1.55;
            white-space: pre-line;
        }
        .badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 6px 13px;
            font-size: 0.82rem;
            font-weight: 850;
            margin-right: 8px;
            margin-bottom: 10px;
            letter-spacing: -0.02em;
        }
        .badge-high { background: rgba(239,68,68,0.17); color: #fecaca; border: 1px solid rgba(248,113,113,0.55); box-shadow: 0 0 18px rgba(239,68,68,0.12); }
        .badge-mid { background: rgba(245,158,11,0.15); color: #fde68a; border: 1px solid rgba(245,158,11,0.46); box-shadow: 0 0 18px rgba(245,158,11,0.10); }
        .badge-low { background: rgba(59,130,246,0.16); color: #bfdbfe; border: 1px solid rgba(96,165,250,0.48); box-shadow: 0 0 18px rgba(59,130,246,0.10); }
        .badge-neutral { background: rgba(148,163,184,0.14); color: #e2e8f0; border: 1px solid rgba(148,163,184,0.30); }

        .check-card {
            position: relative;
            display: grid;
            grid-template-columns: minmax(0, 1fr) 360px;
            gap: 28px;
            align-items: center;
            overflow: hidden;
            margin: 0 0 18px 0;
            padding: 24px 28px;
            border-radius: 22px;
            border: 1px solid rgba(96,165,250,0.30);
            border-left: 5px solid #60a5fa;
            background:
                radial-gradient(circle at 8% 18%, rgba(56,189,248,0.12), transparent 28%),
                linear-gradient(135deg, rgba(15,23,42,0.88), rgba(2,8,23,0.92));
            box-shadow: 0 18px 46px rgba(2, 8, 23, 0.30), inset 0 0 0 1px rgba(255,255,255,0.025);
        }
        .check-card::before {
            content: "";
            position: absolute;
            inset: 0;
            background-image:
                linear-gradient(rgba(148,163,184,0.035) 1px, transparent 1px),
                linear-gradient(90deg, rgba(148,163,184,0.035) 1px, transparent 1px);
            background-size: 32px 32px;
            pointer-events: none;
            opacity: 0.8;
        }
        .check-card > * {
            position: relative;
            z-index: 1;
        }
        .check-card.high {
            border-color: rgba(248,113,113,0.52);
            border-left-color: #ff4d5a;
            box-shadow: 0 20px 56px rgba(127,29,29,0.22), 0 0 32px rgba(239,68,68,0.11), inset 0 0 0 1px rgba(255,255,255,0.025);
            background:
                radial-gradient(circle at 5% 12%, rgba(248,113,113,0.18), transparent 28%),
                linear-gradient(135deg, rgba(52,12,24,0.80), rgba(2,8,23,0.93));
        }
        .check-card.mid {
            border-color: rgba(245,158,11,0.48);
            border-left-color: #f59e0b;
            background:
                radial-gradient(circle at 5% 12%, rgba(245,158,11,0.14), transparent 28%),
                linear-gradient(135deg, rgba(42,28,9,0.78), rgba(2,8,23,0.93));
        }
        .check-card.low {
            border-color: rgba(96,165,250,0.46);
            border-left-color: #3b82f6;
            background:
                radial-gradient(circle at 5% 12%, rgba(59,130,246,0.16), transparent 28%),
                linear-gradient(135deg, rgba(15,23,42,0.88), rgba(2,8,23,0.93));
        }
        .check-main {
            min-width: 0;
        }
        .check-title {
            font-size: clamp(1.45rem, 2.2vw, 1.95rem);
            font-weight: 920;
            color: #f8fafc;
            margin: 8px 0 8px 0;
            letter-spacing: -0.055em;
        }
        .check-question {
            font-size: 1.05rem;
            font-weight: 720;
            line-height: 1.65;
            color: #f8fafc;
            margin: 0 0 18px 0;
            padding-bottom: 16px;
            border-bottom: 1px solid rgba(148,163,184,0.16);
        }
        .method-block {
            margin-top: 4px;
        }
        .method-label {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #f87171;
            font-size: 0.96rem;
            font-weight: 900;
            letter-spacing: -0.02em;
            margin-bottom: 9px;
        }
        .method-text {
            color: #e5e7eb;
            font-size: 1.0rem;
            line-height: 1.72;
            padding-left: 34px;
        }
        .evidence-box {
            align-self: stretch;
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 152px;
            padding: 20px 22px;
            border-radius: 18px;
            border: 1px solid rgba(96,165,250,0.36);
            background: linear-gradient(135deg, rgba(15,23,42,0.76), rgba(8,47,73,0.18));
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.022), 0 0 28px rgba(59,130,246,0.08);
        }
        .evidence-title {
            color: #60a5fa;
            font-size: 1.2rem;
            font-weight: 920;
            letter-spacing: -0.04em;
            margin-bottom: 14px;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(96,165,250,0.30);
        }
        .evidence-line {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            color: #e2e8f0;
            font-size: 0.98rem;
            line-height: 1.55;
            margin: 8px 0;
        }
        .evidence-icon {
            width: 22px;
            min-width: 22px;
            color: #38bdf8;
            font-weight: 900;
            text-align: center;
        }
        .evidence-line.status-high .evidence-icon { color: #ff6b6b; }
        .evidence-line.status-mid .evidence-icon { color: #60a5fa; }
        .evidence-line.status-low .evidence-icon { color: #60a5fa; }
        @media (max-width: 1100px) {
            .check-card {
                grid-template-columns: 1fr;
                gap: 16px;
            }
        }
        .mini-label {
            font-size: 0.9rem;
            font-weight: 850;
            color: #e5e7eb;
            margin: 12px 0 6px 0;
        }
        .mini-text {
            font-size: 0.98rem;
            font-weight: 520;
            line-height: 1.68;
            color: #f1f5f9;
            margin-bottom: 6px;
        }
        .mini-text.evidence {
            color: #cbd5e1;
        }

        /* ============================================================
           출시 전 체크리스트 전용 레이아웃
           - 시안의 카드형 구조를 Streamlit 기본 컴포넌트에 입힘
           ============================================================ */
        .prelaunch-hero {
            position: relative;
            overflow: hidden;
            margin: 0 0 1.25rem 0;
            padding: 1.75rem 2rem 1.55rem 2rem;
            border-radius: 26px;
            border: 1px solid rgba(56, 189, 248, 0.32);
            background:
                radial-gradient(circle at 8% 30%, rgba(56, 189, 248, 0.20), transparent 18%),
                radial-gradient(circle at 92% 18%, rgba(37, 99, 235, 0.12), transparent 24%),
                linear-gradient(135deg, rgba(15, 23, 42, 0.88), rgba(2, 8, 23, 0.92));
            box-shadow: 0 24px 70px rgba(2, 8, 23, 0.40), inset 0 0 0 1px rgba(255,255,255,0.03);
        }
        .prelaunch-hero::before {
            content: "";
            position: absolute;
            inset: 0;
            background-image:
                linear-gradient(rgba(148, 163, 184, 0.045) 1px, transparent 1px),
                linear-gradient(90deg, rgba(148, 163, 184, 0.045) 1px, transparent 1px);
            background-size: 38px 38px;
            mask-image: linear-gradient(90deg, rgba(0,0,0,0.88), rgba(0,0,0,0.56), transparent);
            pointer-events: none;
        }
        .prelaunch-hero-content {
            position: relative;
            z-index: 1;
            display: flex;
            align-items: center;
            gap: 1.1rem;
        }
        .prelaunch-hero-icon {
            width: 78px;
            height: 78px;
            min-width: 78px;
            display: grid;
            place-items: center;
            border-radius: 24px;
            font-size: 2.55rem;
            background: radial-gradient(circle, rgba(59,130,246,0.26), rgba(15,23,42,0.18));
            border: 1px solid rgba(96, 165, 250, 0.42);
            box-shadow: 0 0 42px rgba(56, 189, 248, 0.24);
        }
        .prelaunch-hero-title {
            margin: 0;
            color: #ffffff;
            font-size: clamp(2.1rem, 3.6vw, 3.4rem);
            line-height: 1.08;
            letter-spacing: -0.07em;
            font-weight: 920;
        }
        .prelaunch-hero-subtitle {
            margin-top: 0.55rem;
            color: rgba(226, 232, 240, 0.78);
            font-size: 1.03rem;
            line-height: 1.65;
        }
        .prelaunch-section-caption {
            color: rgba(203, 213, 225, 0.72);
            font-size: 0.95rem;
            line-height: 1.7;
            margin: -0.35rem 0 1.05rem 0;
        }
        .prelaunch-panel-title {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            margin: 1.35rem 0 0.8rem 0;
            color: #ffffff;
            font-size: 1.58rem;
            font-weight: 900;
            letter-spacing: -0.055em;
        }
        .prelaunch-panel-title .small-icon {
            width: 32px;
            height: 32px;
            display: inline-grid;
            place-items: center;
            border-radius: 11px;
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.26);
            color: #7dd3fc;
            font-size: 1rem;
        }
        div[data-testid="stForm"] {
            padding: 1.05rem 1.05rem 1rem 1.05rem;
            border-radius: 22px;
            border: 1px solid rgba(56, 189, 248, 0.34);
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.72), rgba(2, 8, 23, 0.78));
            box-shadow: 0 22px 58px rgba(2, 8, 23, 0.28), inset 0 0 0 1px rgba(255,255,255,0.025);
        }
        div[data-testid="stForm"] label {
            font-weight: 760 !important;
            color: rgba(248, 250, 252, 0.94) !important;
        }
        div[data-testid="stForm"] .stButton > button {
            min-height: 2.95rem;
            border-radius: 13px !important;
            font-weight: 850 !important;
            letter-spacing: -0.02em;
        }
        .prelaunch-info-strip {
            margin: 0.65rem 0 0.75rem 0;
            padding: 0.78rem 1rem;
            border-radius: 16px;
            border: 1px solid rgba(56, 189, 248, 0.32);
            background: linear-gradient(135deg, rgba(14, 165, 233, 0.14), rgba(15, 23, 42, 0.70));
            color: rgba(191, 219, 254, 0.95);
            font-weight: 650;
            line-height: 1.55;
        }
        .prelaunch-chart-wrap {
            padding: 0.7rem 0.85rem 0.85rem 0.85rem;
            border-radius: 18px;
            border: 1px solid rgba(96, 165, 250, 0.23);
            background: rgba(15, 23, 42, 0.42);
        }
        div[data-testid="stTabs"] button[role="tab"] {
            color: rgba(226,232,240,0.72) !important;
            font-weight: 760 !important;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: #38bdf8 !important;
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
    return html.escape(clean_visible_terms("" if value is None or pd.isna(value) else str(value)))

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
    """내부 상/중/하 값을 사용자 친화적인 표현으로 바꿉니다."""
    return {"상": "우선 점검", "중": "추가 검토", "하": "참고"}.get(str(priority), str(priority))

def _priority_raw(display_value: str) -> str:
    """화면 표시값을 내부 우선순위 값으로 되돌립니다."""
    return {"우선 점검": "상", "추가 검토": "중", "참고": "하"}.get(str(display_value), str(display_value))

def _direction_display(direction: str) -> str:
    """분석자용 해석 방향 표현을 개발자용 점검 유형 표현으로 바꿉니다."""
    return {
        "리스크 요소": "확인 필요 요소",
        "강화 요소": "강화 요소",
        "확인 요소": "확인 요소",
        "참고 요소": "참고 요소",
    }.get(str(direction), str(direction))

def _direction_raw(display_value: str) -> str:
    return {
        "확인 필요 요소": "리스크 요소",
        "강화 요소": "강화 요소",
        "확인 요소": "확인 요소",
        "참고 요소": "참고 요소",
    }.get(str(display_value), str(display_value))

def clean_visible_terms(text: str) -> str:
    """사용자 화면에 보이는 내부 모델 표현을 자연스러운 표현으로 바꿉니다."""
    out = "" if text is None else str(text)
    replacements = {
        "출시 전 LLM 체크리스트 생성": "출시 전 체크리스트 생성",
        "LLM 체크리스트": "체크리스트",
        "LLM 출력": "생성 결과",
        "LLM 결과": "생성 결과",
        "LLM 입력용 근거 문장": "근거 문장",
        "LLM은 우선순위를 직접 정하지 않는다.": "생성 과정에서는 우선순위를 새로 정하지 않습니다.",
        "LLM은 계산된 근거를 바탕으로 체크 질문과 확인 방법을 문장화하는 역할만 한다.": "생성 과정은 계산된 근거를 바탕으로 체크 질문과 확인 방법을 문장화합니다.",
        "LLM이 이슈 단위로 부정 맥락을 분류한": "리뷰 분류 과정에서 이슈 단위로 부정 맥락을 정리한",
        "이전 LLM 리뷰 분류 결과": "이전 리뷰 분류 결과",
        "LLM 리뷰 분류 결과": "리뷰 분류 결과",
        "LLM이": "생성 과정이",
        "LLM은": "생성 과정은",
        "LLM": "리뷰 분석 모델",
        "fixed_priority": "사전 계산된 우선순위",
    }
    for old, new in replacements.items():
        out = out.replace(old, new)
    return out

def render_badge(label: str, tone: str = "neutral") -> str:
    return f'<span class="badge badge-{tone}">{html.escape(str(label))}</span>'

def strip_high_urgency_note(text: str) -> str:
    """카드 화면에서는 High urgency 보조 신호를 숨기고 반복 언급 근거만 보여줍니다."""
    out = "" if text is None or pd.isna(text) else str(text)
    out = clean_visible_terms(out)
    out = re.sub(r"\s*\((?:High urgency|high urgency)[^)]*\)", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s*High urgency\s*[:：]?\s*[^.,。)]*", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s+", " ", out).strip()
    return out or "-"

def compact_evidence_for_card(text: str) -> str:
    """카드 본문에는 반복 언급 규모만 짧게 보여줍니다."""
    out = strip_high_urgency_note(text)
    if not out or out == "-":
        return "유사 게임 리뷰에서 반복적으로 언급된 항목입니다."

    match = re.search(r"(\d+개\s*게임\s*중\s*\d+개)(?:\([^)]*\))?에서\s*언급", out)
    if match:
        return f"{match.group(1)}에서 언급된 항목입니다."

    # 정형 문장이 아닐 때는 첫 문장만 짧게 보여줍니다.
    first_sentence = re.split(r"(?<=[.!?。])\s+", out)[0].strip()
    if len(first_sentence) > 90:
        first_sentence = first_sentence[:87].rstrip() + "..."
    return first_sentence or "유사 게임 리뷰에서 반복적으로 언급된 항목입니다."

def compact_method_for_card(text: str) -> str:
    """카드 본문에는 점검 방법을 한 문장으로 짧게 보여줍니다."""
    out = clean_visible_terms(text)
    if not out or out == "-":
        return "출시 전 QA와 플레이 테스트에서 해당 항목을 먼저 확인합니다."

    first_sentence = re.split(r"(?<=[.!?。])\s+", out)[0].strip()
    if len(first_sentence) > 95:
        first_sentence = first_sentence[:92].rstrip() + "..."
    return first_sentence

def evidence_lines_for_card(text: str) -> tuple[str, str]:
    """카드 오른쪽 근거 박스에 들어갈 반복 언급/비추천 맥락 문장을 분리합니다."""
    out = strip_high_urgency_note(text)
    if not out or out == "-":
        return "유사 게임 리뷰에서 반복 언급", "비추천 맥락 확인 필요"

    repeat_match = re.search(
        r"(\d+개\s*게임\s*중\s*\d+개(?:\([^)]*\))?에서\s*언급(?:되었으며|되었습니다|된 항목입니다)?)",
        out,
    )
    negative_match = re.search(
        r"(비추천\s*맥락(?:이)?\s*\d+건\s*확인(?:되었습니다|됨|되었습니다\.)?)",
        out,
    )

    repeat_line = repeat_match.group(1).rstrip(".") if repeat_match else compact_evidence_for_card(out).rstrip(".")
    negative_line = negative_match.group(1).rstrip(".") if negative_match else "비추천 맥락 확인 필요"
    return repeat_line, negative_line


def priority_status_text(priority: str) -> str:
    """우선순위 값을 카드 오른쪽 근거 박스용 상태 문구로 변환합니다."""
    return {
        "상": "우선 점검 필요",
        "중": "추가 검토 가능",
        "하": "참고 항목",
        "우선 점검": "우선 점검 필요",
        "추가 검토": "추가 검토 가능",
        "참고": "참고 항목",
    }.get(str(priority), "점검 필요")


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

# ============================================================
# 화면 표시 보조 함수
# ============================================================
def _condition_values(user_condition: dict, plural_key: str, single_key: str) -> list[str]:
    """단일 선택/다중 선택 조건을 모두 리스트로 통일합니다."""
    values = user_condition.get(plural_key, None)

    if values is None:
        single_value = user_condition.get(single_key, None)
        values = [single_value] if single_value else []

    if isinstance(values, str):
        values = [values]

    return [str(v) for v in values if pd.notna(v) and str(v).strip()]

def _count_chart_df(df: pd.DataFrame, column: str, order: list[str] | None = None, label: str = "항목") -> pd.DataFrame:
    """value_counts 결과를 st.bar_chart에 넣기 쉬운 형태로 만듭니다."""
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=[label, "건수"])

    counts = df[column].fillna("미분류").astype(str).value_counts()

    if order:
        counts = counts.reindex(order).fillna(0).astype(int)

    out = counts.reset_index()
    out.columns = [label, "건수"]
    return out

def _safe_ratio_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([0] * len(df), index=df.index)
    return pd.to_numeric(df[column], errors="coerce").fillna(0)

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
    '''항목명이 긴 그래프는 가로 막대로 보여주어 라벨 가독성을 높입니다.'''
    if df.empty or label_col not in df.columns or value_col not in df.columns:
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
            tooltip=[
                alt.Tooltip(f"{label_col}:N", title=label_title or label_col),
                alt.Tooltip(f"{value_col}:Q", title=value_title or value_col),
            ],
        )
        .properties(height=height)
    )

    st.altair_chart(apply_dark_chart_theme(chart), use_container_width=True)

def _cell_class_name(column_name: str) -> str:
    """컬럼명에 따라 HTML table cell class를 부여합니다."""
    class_map = {
        "체크 질문": "col-check-question",
        "근거 요약": "col-evidence-summary",
        "확인 방법": "col-check-method",
        "LLM 입력용 근거 문장": "col-evidence-summary",
        "근거 문장": "col-evidence-summary",
        "우선순위 근거 설명": "col-evidence-summary",
    }
    return class_map.get(str(column_name), "")

def _format_table_cell_text(column_name: str, value) -> str:
    """표 안의 긴 문장을 읽기 좋은 줄 단위로 정리합니다."""
    if isinstance(value, list):
        text = ", ".join(map(str, value))
    else:
        text = "" if pd.isna(value) else str(value)

    text = re.sub(r"\s+", " ", text).strip()
    text = clean_visible_terms(text)

    if not text:
        return ""

    # 체크 질문은 표 너비에 맞춰 자연스럽게 줄바꿈되도록 둡니다.
    # 강제로 한 줄 고정하지 않습니다.
    if column_name == "체크 질문":
        text = re.sub(r"(입니까\?|습니까\?|있나요\?|없나요\?|않습니까\?)\s+", r"\1\n", text)

    # 근거 요약은 핵심 수치를 2~3줄로 나누어 읽기 쉽게 만듭니다.
    if column_name in ["근거 요약", "LLM 입력용 근거 문장", "근거 문장", "우선순위 근거 설명"]:
        text = re.sub(r"(반복되었으며,)\s*", r"\1\n", text)
        text = re.sub(r"(확인되었습니다\.)\s*", r"\1\n", text)
        text = re.sub(r"\s*(\(High urgency[^)]*\))", r"\n\1", text, flags=re.IGNORECASE)

    # 확인 방법은 첫 번째 쉼표를 기준으로 2줄 정도로 나누어 점검 행동을 분리합니다.
    if column_name == "확인 방법":
        if "，" in text:
            text = text.replace("，", ",")
        comma_pos = text.find(",")
        if comma_pos != -1:
            text = text[: comma_pos + 1] + "\n" + text[comma_pos + 1 :].strip()

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "<br>".join(html.escape(line) for line in lines)

def _column_width_px(column_name: str) -> int:
    """주요 컬럼의 가독성을 위해 표 컬럼 너비를 직접 지정합니다."""
    width_map = {
        "우선순위": 80,
        "해석 방향": 120,
        "구분": 120,
        "근거 이슈": 170,
        "체크 질문": 420,
        "근거 요약": 450,
        "확인 방법": 420,
        "근거 조건": 220,
        "조건 종류": 110,
        "조건 값": 180,
        "이슈": 180,
        "게임 수": 90,
        "반복 게임 수": 120,
        "조건 내 반복 비율": 140,
        "Steam 추천 맥락 게임 수": 170,
        "Steam 비추천 맥락 게임 수": 180,
        "High urgency 게임 수": 160,
        "우선순위 산정 규칙": 260,
        "우선순위 근거 설명": 420,
        "LLM 입력용 근거 문장": 520,
        "근거 문장": 520,
        "검증 결과": 160,
        "검증 메시지": 420,
        "내용": 520,
        "설명": 520,
        "기준": 560,
        "의미": 560,
        "앱 ID": 100,
        "게임명": 220,
        "장르": 220,
        "가격대": 110,
        "Steam 태그": 380,
        "플레이 방식": 180,
        "분석 리뷰 수": 120,
        "긍정 비율(%)": 130,
        "부정 비율(%)": 130,
        "High urgency 비율(%)": 160,
        "appid": 100,
        "game_name": 220,
        "genres_text": 220,
        "price_group": 110,
        "top_steam_tags_text": 360,
        "play_style": 180,
        "review_count": 110,
        "llm_positive_ratio": 130,
        "llm_negative_ratio": 130,
        "high_urgency_ratio": 150,
    }
    return width_map.get(str(column_name), 160)

def render_wrapped_table(df: pd.DataFrame, height_px: int = 520) -> None:
    """긴 문장이 있는 표를 줄바꿈 가능한 HTML 표로 출력합니다.

    체크 질문은 너무 길면 자연스럽게 줄바꿈하고,
    근거 요약은 2~3줄, 확인 방법은 2줄 정도로 보이도록
    컬럼 너비와 줄바꿈 위치를 직접 제어합니다.
    """
    if df.empty:
        st.info("표시할 데이터가 없습니다.")
        return

    display_df = df.copy().fillna("")
    display_df = display_df.rename(columns={
        "LLM 입력용 근거 문장": "근거 문장",
    })
    columns = list(display_df.columns)
    col_widths = [_column_width_px(col) for col in columns]
    min_table_width = max(sum(col_widths), 1100)

    colgroup_html = "\n".join(
        f'<col style="width: {width}px;">' for width in col_widths
    )

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

    table_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
html, body {{
    margin: 0;
    padding: 0;
    background: transparent;
    color: rgb(250, 250, 250);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 14px;
}}
.wrapped-table-wrapper {{
    height: {height_px}px;
    overflow: auto;
    border: 1px solid rgba(250, 250, 250, 0.18);
    border-radius: 10px;
    background: rgb(14, 17, 23);
}}
.wrapped-table {{
    width: {min_table_width}px;
    min-width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}}
.wrapped-table thead th {{
    position: sticky;
    top: 0;
    z-index: 2;
    background: rgb(38, 39, 48);
    color: rgb(250, 250, 250);
    font-weight: 700;
    text-align: left;
}}
.wrapped-table th,
.wrapped-table td {{
    padding: 10px 12px;
    border-bottom: 1px solid rgba(250, 250, 250, 0.12);
    border-right: 1px solid rgba(250, 250, 250, 0.08);
    vertical-align: top;
    white-space: normal;
    word-break: keep-all;
    overflow-wrap: break-word;
    line-height: 1.55;
}}
.wrapped-table .col-check-question {{
    white-space: normal;
    word-break: keep-all;
    overflow-wrap: break-word;
    line-height: 1.55;
}}
.wrapped-table .col-evidence-summary,
.wrapped-table .col-check-method {{
    white-space: normal;
    word-break: keep-all;
    overflow-wrap: break-word;
}}
.wrapped-table tbody tr:nth-child(even) td {{
    background: rgba(250, 250, 250, 0.025);
}}
.wrapped-table tbody tr:hover td {{
    background: rgba(250, 250, 250, 0.06);
}}
</style>
</head>
<body>
<div class="wrapped-table-wrapper">
<table class="wrapped-table">
<colgroup>
{colgroup_html}
</colgroup>
<thead><tr>{thead_html}</tr></thead>
<tbody>
{tbody_html}
</tbody>
</table>
</div>
</body>
</html>"""

    components.html(table_html, height=height_px + 24, scrolling=False)

def make_prelaunch_classification_guide_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """검증 결과 아래에 보여줄 체크리스트 분류 기준 안내표를 만듭니다."""
    priority_guide = pd.DataFrame(
        [
            {
                "분류": "우선 점검",
                "기준": "유사 게임 리뷰에서 반복성이 높고, 부정 맥락 또는 시급도 근거가 함께 확인되어 출시 전에 우선 점검할 항목",
            },
            {
                "분류": "추가 검토",
                "기준": "반복성은 확인되지만 우선 점검 항목보다 부정 맥락이나 영향 범위가 상대적으로 약한 항목",
            },
            {
                "분류": "참고",
                "기준": "현재 조건에서는 우선도는 낮지만, 기획·QA·운영 점검 시 참고할 수 있는 항목",
            },
        ]
    )

    direction_guide = pd.DataFrame(
        [
            {
                "분류": "확인 필요 요소",
                "의미": "유사 게임에서 부정 맥락으로 반복되어 출시 전 품질 점검이 필요한 요소",
            },
            {
                "분류": "강화 요소",
                "의미": "유저가 긍정적으로 평가한 방향으로 유지하거나 더 강조할 수 있는 강점 후보",
            },
            {
                "분류": "확인 요소",
                "의미": "긍정과 부정이 함께 나타나 실제 게임 맥락에서 추가 확인이 필요한 항목",
            },
            {
                "분류": "참고 요소",
                "의미": "직접적인 리스크는 낮지만, 유사 게임 반응을 이해하는 데 참고할 수 있는 항목",
            },
        ]
    )

    return priority_guide, direction_guide

def render_prelaunch_filter_guide() -> None:
    """출시 전 체크리스트 필터와 카드 배지를 해석하는 기준을 안내합니다."""
    guide_col1, guide_col2 = st.columns(2)

    with guide_col1:
        render_section_lead(
            "점검 유형 설명",
            "확인 필요 요소: 유사 게임의 부정 리뷰 맥락에서 반복되어 출시 전 품질 점검이 필요한 요소입니다.\n"
            "강화 요소: 유저가 긍정적으로 평가한 방향으로, 현재 기획에서 더 살릴 수 있는 강점 후보입니다.\n"
            "확인 요소: 긍정과 부정이 함께 나타나 실제 게임 맥락에서 추가 확인이 필요한 항목입니다.\n"
            "참고 요소: 직접적인 리스크는 낮지만, 유사 게임 반응을 이해하는 데 참고할 수 있는 항목입니다.",
        )

    with guide_col2:
        render_section_lead(
            "점검 우선도 설명",
            "우선 점검: 출시 전에 QA, 튜토리얼, UI·UX, 밸런스처럼 먼저 점검할 필요가 큰 항목입니다.\n"
            "추가 검토: 반복 근거는 있지만, 현재 기획 방향이나 개발 여건에 따라 확인하면 되는 항목입니다.\n"
            "참고: 우선도는 낮지만, 회의나 QA 과정에서 후순위로 참고할 수 있는 항목입니다.",
        )

def render_prelaunch_validation_guide(validation_df: pd.DataFrame) -> None:
    """출시 전 체크리스트 생성 결과가 어떤 기준으로 점검되는지 설명합니다."""
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
            result_message = "생성 결과가 근거 데이터의 점검 우선도 기준과 일치했습니다."
        else:
            result_message = "일부 항목은 근거 데이터 기준으로 다시 확인하거나 보정할 필요가 있습니다."

    st.info(
        "생성 결과가 사전 계산된 점검 우선도와 점검 유형 기준을 유지했는지 확인합니다.      \n"
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

        검증 기준은 출시 전 분석과 동일한 원칙을 따릅니다.

        - 생성 과정은 **점검 우선도**를 새로 판단하지 않습니다.
        - 점검 우선도는 근거 데이터에서 계산한 **우선 점검 / 추가 검토 / 참고** 기준을 그대로 사용합니다.
        - 반복 게임 수, 조건 내 반복 비율, Steam 비추천 맥락 게임 수를 기준으로 계산된 근거를 우선합니다.
        - `High urgency`는 빠르게 확인할 가능성이 있는 보조 신호로만 참고하고, 단독 기준으로 사용하지 않습니다.
        - 생성 과정은 계산된 근거를 바탕으로 개발자가 이해하기 쉬운 **점검 질문과 확인 방법**을 문장화하는 역할을 합니다.

        **검증 결과 요약:** {result_message}
        """
    )

# ============================================================
# 출시 전 체크리스트 필터 도움말
# ============================================================

PRELAUNCH_FILTER_HELP = {
    "priority": (
        "출시 전에 어떤 항목을 먼저 점검할지 선택합니다.\n\n"
        "- 우선 점검: 유사 게임에서 반복성이 높고 부정 맥락도 함께 확인되어, 출시 전에 먼저 확인할 필요가 큰 항목입니다.\n"
        "- 추가 검토: 반복 근거는 있지만 영향 범위나 부정 맥락이 상대적으로 약해, 현재 기획 방향이나 개발 여건에 따라 추가로 확인하면 되는 항목입니다.\n"
        "- 참고: 우선도는 낮지만 회의, QA, 기획 점검 과정에서 후순위로 참고할 수 있는 항목입니다."
    ),
    "check_type": (
        "체크리스트 항목을 어떤 관점에서 볼지 선택합니다.\n\n"
        "- 확인 필요 요소: 유사 게임의 부정 리뷰 맥락에서 반복되어 출시 전 품질 점검이 필요한 요소입니다.\n"
        "- 강화 요소: 유저가 긍정적으로 평가한 방향으로, 현재 기획에서 더 살릴 수 있는 강점 후보입니다.\n"
        "- 확인 요소: 긍정과 부정이 함께 나타나 실제 게임 맥락에서 추가 확인이 필요한 항목입니다.\n"
        "- 참고 요소: 직접적인 리스크는 낮지만 유사 게임 반응을 이해하는 데 참고할 수 있는 항목입니다."
    ),
    "issue_tag": (
        "리뷰에서 반복적으로 언급된 세부 이슈를 기준으로 점검 카드를 좁혀 봅니다.\n\n"
        "예: UI/UX, 버그, 난이도, 밸런스, 콘텐츠 분량, 그래픽·사운드, 가격·가치"
    ),
}

def _available_issue_tag_options(df: pd.DataFrame, issue_col: str = "근거 이슈") -> list[str]:
    """체크리스트 카드에 표시할 이슈 태그 목록을 만듭니다."""
    if df.empty or issue_col not in df.columns:
        return []

    return (
        df[issue_col]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .sort_values()
        .unique()
        .tolist()
    )

def _card_tag_value(row: pd.Series) -> str:
    """카드 배지에 표시할 이슈 태그를 정합니다.

    구분 컬럼이 비어 있더라도 근거 이슈를 태그처럼 보여주어
    카드가 어떤 주제의 점검 항목인지 항상 확인할 수 있게 합니다.
    """
    for col in ["구분", "근거 이슈"]:
        value = row.get(col, "")
        if pd.notna(value) and str(value).strip():
            return str(value).strip()
    return "이슈 태그"

def render_evidence_overview(selected_evidence: pd.DataFrame) -> None:
    """체크리스트 근거를 카드와 그래프로 요약해서 보여줍니다."""
    if selected_evidence.empty:
        return

    st.markdown(
        """
        입력 조건과 유사한 게임들의 출시 초기 리뷰에서 반복적으로 나타난 이슈를 요약합니다.  
        긍정적으로 언급된 요소는 **강화 요소**로, 부정적으로 언급된 요소는 **확인 필요 요소**로 정리됩니다.
        """
    )

    evidence_for_chart = selected_evidence.copy()
    if "priority_level" in evidence_for_chart.columns:
        evidence_for_chart["점검 우선도"] = evidence_for_chart["priority_level"].apply(_priority_display)
    if "issue_direction" in evidence_for_chart.columns:
        evidence_for_chart["점검 유형"] = evidence_for_chart["issue_direction"].apply(_direction_display)

    priority_df = _count_chart_df(
        evidence_for_chart,
        column="점검 우선도",
        order=["우선 점검", "추가 검토", "참고"],
        label="점검 우선도",
    )
    direction_df = _count_chart_df(
        evidence_for_chart,
        column="점검 유형",
        order=["확인 필요 요소", "강화 요소", "확인 요소", "참고 요소"],
        label="점검 유형",
    )

    condition_df = _count_chart_df(
        selected_evidence,
        column="condition_type",
        label="조건 종류",
    )
    if not condition_df.empty:
        condition_df["조건 종류"] = condition_df["조건 종류"].apply(
            lambda x: {
                "genre": "장르",
                "price_group": "가격대",
                "steam_tag": "Steam 태그",
                "play_style": "플레이 방식",
            }.get(str(x), str(x))
        )

    m1, m2, m3, m4 = st.columns(4)
    high_count = int((selected_evidence.get("priority_level", pd.Series(dtype=str)) == "상").sum())
    risk_count = int((selected_evidence.get("issue_direction", pd.Series(dtype=str)) == "리스크 요소").sum())
    avg_ratio = _safe_ratio_series(selected_evidence, "issue_game_ratio").mean()
    with m1:
        render_metric_card("점검 근거 항목", f"{len(selected_evidence):,}개", "체크리스트 작성에 사용한 반복 이슈", tone="info")
    with m2:
        render_metric_card("우선 점검 항목", f"{high_count:,}개", "출시 전에 먼저 점검할 필요가 큰 항목", tone="high")
    with m3:
        render_metric_card("확인 필요 요소", f"{risk_count:,}개", "부정 리뷰 맥락에서 반복된 항목", tone="high")
    with m4:
        render_metric_card("평균 반복 비율", f"{avg_ratio:.1f}%", "유사 게임 중 해당 이슈가 나타난 비율의 평균", tone="info")

    st.caption(
        "점검 근거 항목은 체크리스트 작성에 사용된 반복 이슈입니다. "
        "확인 필요 요소는 부정 리뷰 맥락에서 반복된 항목이고, 강화 요소는 긍정 리뷰에서 강점으로 언급된 항목입니다."
    )

    chart_col1, chart_col2, chart_col3 = st.columns(3)
    with chart_col1:
        st.caption("점검 우선도")
        render_bar_chart(priority_df, x_col="점검 우선도", y_col="건수", x_title="점검 우선도", y_title="건수")

    with chart_col2:
        st.caption("점검 유형")
        render_bar_chart(direction_df, x_col="점검 유형", y_col="건수", x_title="점검 유형", y_title="건수")

    with chart_col3:
        st.caption("근거 조건 출처")
        render_bar_chart(condition_df, x_col="조건 종류", y_col="건수", x_title="조건 종류", y_title="건수")

    top_issue_cols = [
        col for col in ["issue_name_kor", "issue_game_ratio", "issue_game_count", "negative_game_count"]
        if col in selected_evidence.columns
    ]

    if {"issue_name_kor", "issue_game_ratio"}.issubset(selected_evidence.columns):
        top_issue_df = selected_evidence[top_issue_cols].copy()
        top_issue_df["issue_game_ratio"] = pd.to_numeric(top_issue_df["issue_game_ratio"], errors="coerce").fillna(0)
        top_issue_df = (
            top_issue_df
            .sort_values("issue_game_ratio", ascending=False)
            .head(10)
            .rename(columns={
                "issue_name_kor": "이슈",
                "issue_game_ratio": "조건 내 반복 비율",
                "issue_game_count": "반복 게임 수",
                "negative_game_count": "비추천 맥락 게임 수",
            })
        )

        st.caption("상위 반복 이슈 TOP 10")
        render_horizontal_bar_chart(
            top_issue_df,
            label_col="이슈",
            value_col="조건 내 반복 비율",
            label_title="이슈",
            value_title="조건 내 반복 비율",
            height=380,
        )

def build_prelaunch_top_issue_chart_df(
    checklist_df: pd.DataFrame,
    evidence_df: pd.DataFrame | None = None,
    top_n: int = 10,
) -> pd.DataFrame:
    """체크리스트와 근거 데이터를 연결해 출시 전 우선 점검 이슈 TOP N 그래프용 데이터를 만듭니다."""

    columns = [
        "이슈",
        "반복 게임 수",
        "비추천 맥락 게임 수",
        "High urgency 게임 수",
        "조건 내 반복 비율",
        "점검 우선도",
        "_priority_order",
    ]

    if checklist_df.empty:
        return pd.DataFrame(columns=columns)

    # 체크리스트에 실제로 표시된 이슈만 우선 사용합니다.
    checklist_issue_col = "근거 이슈" if "근거 이슈" in checklist_df.columns else None
    target_issues = []

    if checklist_issue_col:
        target_issues = (
            checklist_df[checklist_issue_col]
            .dropna()
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
            .unique()
            .tolist()
        )

    # 1순위: selected_evidence의 실제 반복 근거를 사용합니다.
    if evidence_df is not None and not evidence_df.empty and "issue_name_kor" in evidence_df.columns:
        work = evidence_df.copy()

        if target_issues:
            work = work[work["issue_name_kor"].astype(str).isin(target_issues)].copy()

        if not work.empty:
            for col in [
                "issue_game_count",
                "negative_game_count",
                "high_urgency_game_count",
                "issue_game_ratio",
            ]:
                if col not in work.columns:
                    work[col] = 0
                work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0)

            if "priority_level" not in work.columns:
                work["priority_level"] = "하"

            priority_order_map = {"상": 1, "중": 2, "하": 3}
            priority_display_map = {1: "우선 점검", 2: "추가 검토", 3: "참고"}

            work["_priority_order"] = work["priority_level"].map(priority_order_map).fillna(9).astype(int)

            chart_df = (
                work.groupby("issue_name_kor", as_index=False)
                .agg(
                    {
                        "issue_game_count": "max",
                        "negative_game_count": "max",
                        "high_urgency_game_count": "max",
                        "issue_game_ratio": "max",
                        "_priority_order": "min",
                    }
                )
                .rename(
                    columns={
                        "issue_name_kor": "이슈",
                        "issue_game_count": "반복 게임 수",
                        "negative_game_count": "비추천 맥락 게임 수",
                        "high_urgency_game_count": "High urgency 게임 수",
                        "issue_game_ratio": "조건 내 반복 비율",
                    }
                )
            )

            chart_df["점검 우선도"] = chart_df["_priority_order"].map(priority_display_map).fillna("참고")

            chart_df = chart_df.sort_values(
                ["_priority_order", "반복 게임 수", "비추천 맥락 게임 수", "High urgency 게임 수"],
                ascending=[True, False, False, False],
            ).head(top_n)

            return chart_df[columns]

    # 2순위: evidence_df가 없을 때는 체크리스트의 근거 이슈 등장 횟수로 대체합니다.
    if checklist_issue_col:
        fallback = checklist_df.copy()
        fallback["이슈"] = fallback[checklist_issue_col].fillna("미분류").astype(str)

        if "우선순위" in fallback.columns:
            fallback["_priority_order"] = fallback["우선순위"].map({"상": 1, "중": 2, "하": 3}).fillna(9).astype(int)
        else:
            fallback["_priority_order"] = 9

        chart_df = (
            fallback.groupby("이슈", as_index=False)
            .agg(
                {
                    checklist_issue_col: "count",
                    "_priority_order": "min",
                }
            )
            .rename(columns={checklist_issue_col: "반복 게임 수"})
        )

        chart_df["비추천 맥락 게임 수"] = 0
        chart_df["High urgency 게임 수"] = 0
        chart_df["조건 내 반복 비율"] = 0
        chart_df["점검 우선도"] = chart_df["_priority_order"].map(
            {1: "우선 점검", 2: "추가 검토", 3: "참고"}
        ).fillna("참고")

        chart_df = chart_df.sort_values(
            ["_priority_order", "반복 게임 수"],
            ascending=[True, False],
        ).head(top_n)

        return chart_df[columns]

    return pd.DataFrame(columns=columns)

def render_prelaunch_top_issue_chart(chart_df: pd.DataFrame) -> None:
    """출시 전 우선 점검 이슈 TOP 10 그래프를 출력합니다."""

    if chart_df.empty:
        st.info("표시할 우선 점검 이슈 데이터가 없습니다.")
        return

    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X(
                "반복 게임 수:Q",
                title="반복 게임 수",
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
                alt.Tooltip("반복 게임 수:Q", title="반복 게임 수"),
                alt.Tooltip("비추천 맥락 게임 수:Q", title="비추천 맥락 게임 수"),
                alt.Tooltip("High urgency 게임 수:Q", title="High urgency 게임 수"),
                alt.Tooltip("조건 내 반복 비율:Q", title="조건 내 반복 비율", format=".1f"),
            ],
        )
        .properties(height=340)
    )

    st.altair_chart(apply_dark_chart_theme(chart), use_container_width=True)

def render_checklist_overview(
    checklist_df: pd.DataFrame,
    evidence_df: pd.DataFrame | None = None,
) -> None:
    """필터 적용 전 전체 체크리스트 요약과 그래프를 보여줍니다."""
    if checklist_df.empty:
        st.info("표시할 체크리스트 항목이 없습니다. 입력 조건을 다시 확인해주세요.")
        return

    total_count = len(checklist_df)
    high_count = int((checklist_df["우선순위"] == "상").sum())
    mid_count = int((checklist_df["우선순위"] == "중").sum())
    low_count = int((checklist_df["우선순위"] == "하").sum())

    st.markdown(
        """
        <div class="prelaunch-info-strip">
            ⓘ 점검 카드는 필터를 통해 좁혀 확인할 수 있습니다. 각 카드는 유사 게임 리뷰에서 반복된 이슈를 바탕으로 구성되었습니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    summary_cols = st.columns(4)
    with summary_cols[0]:
        render_metric_card("전체 점검 항목", f"{total_count:,}개", "생성된 출시 전 체크리스트 항목", tone="neutral")
    with summary_cols[1]:
        render_metric_card("우선 점검", f"{high_count:,}개", "출시 전에 우선 점검할 항목", tone="high")
    with summary_cols[2]:
        render_metric_card("추가 검토", f"{mid_count:,}개", "조건에 따라 추가로 확인할 항목", tone="mid")
    with summary_cols[3]:
        render_metric_card("참고", f"{low_count:,}개", "후순위로 참고할 항목", tone="low")

    st.caption(
        "아래 그래프는 전체 체크리스트 기준 요약입니다. "
    )

    chart_df = checklist_df.copy()
    chart_df["점검 우선도"] = chart_df["우선순위"].apply(_priority_display)

    priority_chart_df = _count_chart_df(
        chart_df,
        column="점검 우선도",
        order=["우선 점검", "추가 검토", "참고"],
        label="점검 우선도",
    )

    top_issue_chart_df = build_prelaunch_top_issue_chart_df(
        checklist_df=checklist_df,
        evidence_df=evidence_df,
        top_n=10,
    )

    c1, c2 = st.columns(2)

    with c1:
        st.caption("점검 우선도 분포")
        st.caption("전체 체크리스트 항목이 우선 점검, 추가 검토, 참고 중 어디에 많이 분포하는지 보여줍니다.")
        render_bar_chart(
            priority_chart_df,
            x_col="점검 우선도",
            y_col="건수",
            x_title="점검 우선도",
            y_title="건수",
        )

    with c2:
        st.caption("출시 전 우선 점검 이슈 TOP 10")
        st.caption("유사 게임 리뷰에서 반복적으로 언급된 이슈 중 출시 전에 우선 점검할 항목입니다.")
        render_prelaunch_top_issue_chart(top_issue_chart_df)

def render_checklist_cards(checklist_df: pd.DataFrame) -> None:
    """필터 적용 후 체크리스트를 카드 형태로 보여줍니다."""
    if checklist_df.empty:
        st.info("현재 선택한 필터에 해당하는 체크리스트 항목이 없습니다. 필터를 넓혀서 다시 확인해주세요.")
        return

    priority_order_map = {"상": 1, "중": 2, "하": 3}
    checklist_view = checklist_df.copy()
    checklist_view["_priority_order"] = checklist_view["우선순위"].map(priority_order_map).fillna(9).astype(int)
    if "근거 이슈" in checklist_view.columns:
        checklist_view["_issue_sort"] = checklist_view["근거 이슈"].fillna("").astype(str)
    else:
        checklist_view["_issue_sort"] = ""

    checklist_view = checklist_view.sort_values(
        ["_priority_order", "_issue_sort"],
        ascending=[True, True],
    ).reset_index(drop=True)

    st.markdown('<div class="prelaunch-panel-title"><span class="small-icon">🧾</span>선택한 필터에 해당하는 점검 카드</div>', unsafe_allow_html=True)

    for idx, row in checklist_view.iterrows():
        p_class = _priority_class(row.get("우선순위", "-"))
        tag_label = _card_tag_value(row)
        evidence_summary = strip_high_urgency_note(row.get("근거 요약", "-"))
        repeat_line, negative_line = evidence_lines_for_card(evidence_summary)
        priority_status = priority_status_text(row.get("우선순위", "-"))
        check_method = clean_visible_terms(row.get("확인 방법", "-"))
        badges = "".join(
            [
                render_badge(_priority_display(row.get("우선순위", "-")), p_class),
                render_badge(_direction_display(row.get("해석 방향", "-")), "neutral"),
                render_badge(tag_label, "neutral"),
            ]
        )
        st.markdown(
            f"""
            <div class="check-card {p_class}">
                <div class="check-main">
                    <div class="check-badges">{badges}</div>
                    <div class="check-title">{idx + 1}. {_html_text(row.get('근거 이슈', '-'))}</div>
                    <div class="check-question">{_html_text(row.get('체크 질문', '-'))}</div>
                    <div class="method-block">
                        <div class="method-label">▣ 출시 전 점검 방법</div>
                        <div class="method-text">{_html_text(check_method)}</div>
                    </div>
                </div>
                <div class="evidence-box">
                    <div class="evidence-title">반복 언급 근거</div>
                    <div class="evidence-line"><span class="evidence-icon">▥</span><span>{_html_text(repeat_line)}</span></div>
                    <div class="evidence-line"><span class="evidence-icon">▤</span><span>{_html_text(negative_line)}</span></div>
                    <div class="evidence-line status-{p_class}"><span class="evidence-icon">▱</span><span>{_html_text(priority_status)}</span></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ============================================================
# 페이지 제목
# ============================================================
inject_dashboard_style()

st.markdown(
    """
    <section class="prelaunch-hero">
        <div class="prelaunch-hero-content">
            <div class="prelaunch-hero-icon">🧾</div>
            <div>
                <h1 class="prelaunch-hero-title">출시 전 체크리스트</h1>
                <div class="prelaunch-hero-subtitle">
                    유사 게임의 출시 초기 리뷰를 바탕으로, 출시 전에 점검할 항목을 체크리스트로 정리합니다.
                </div>
            </div>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.expander("이 페이지 설명 자세히 보기", expanded=False):
    st.markdown(
        """
#### 이 페이지는 무엇을 하나요?
준비 중인 게임의 장르, 가격대, Steam 태그, 플레이 방식을 입력하면 비슷한 조건의 인디게임들이 출시 초기에 어떤 점을 칭찬받았고 어떤 부분에서 불만이 반복되었는지 확인합니다. 그 결과를 개발자가 바로 사용할 수 있는 출시 전 점검 카드로 정리합니다.

#### 사용 순서
1. **게임 속성을 선택합니다.**  
   장르, 가격대, Steam 태그, 플레이 방식을 선택합니다.
2. **[조건 적용] 버튼을 누릅니다.**  
   입력 조건과 유사한 게임 리뷰를 바탕으로 체크리스트가 생성됩니다.
3. **점검 카드를 확인합니다.**  
   우선 점검, 추가 검토, 참고 항목을 보고 출시 전에 무엇을 확인할지 정리합니다.
4. **필요하면 필터로 좁혀 봅니다.**  
   점검 우선도, 점검 유형, 이슈 태그를 선택해 필요한 카드만 확인합니다.
5. **근거가 필요하면 상세 근거·검증 보기를 켭니다.**  
   반복 이슈, 매칭 게임, 생성 결과 검증 내용을 추가로 확인할 수 있습니다.

#### 해석할 때 주의할 점
- 이 결과는 성공 가능성 예측이 아니라 출시 전 점검을 돕는 참고 자료입니다.
- 최종 판단에는 실제 기획 의도, 개발 일정, QA 결과를 함께 반영해야 합니다.
        """
    )

st.divider()

# ============================================================
# 사이드바 설정
# ============================================================
run_name = DEFAULT_RUN_NAME

# 사용자 화면에서는 내부 생성 범위/LLM 세부 설정을 숨깁니다.
# 발표·시연에서 결과가 흔들리지 않도록 기본값은 코드에서 고정합니다.
top_n_per_condition = 8
max_total_rows = 40
overall_issue_n = 15
use_cache = True
force_regenerate = False
temperature = 0.0
max_retries = 3

show_debug_info = False

with st.sidebar:
    st.header("🧭 화면 안내")
    st.caption(
        "장르·가격대·Steam 태그·플레이 방식을 선택하면, "
        "유사 게임의 출시 초기 리뷰에서 반복된 이슈를 바탕으로 출시 전 체크리스트를 생성합니다."
    )
    show_detail_sections = st.checkbox(
        "상세 근거·검증 보기",
        value=False,
        help="기본 화면은 체크리스트만 보여줍니다. 켜면 근거 보기와 검증·참고 탭을 추가로 확인할 수 있습니다.",
    )

notify_detail_toggle_change(
    enabled=show_detail_sections,
    page_key="prelaunch",
    detail_label="상세 근거·검증 보기",
)

# ============================================================
# 데이터 로드
# ============================================================
try:
    data = load_prelaunch_data(run_name=run_name)
except FileNotFoundError as e:
    st.error("출시 전 체크리스트에 필요한 분석 데이터 파일을 찾을 수 없습니다.")
    st.info("먼저 출시 전 분석/전처리 과정을 실행해 필요한 CSV 파일을 생성한 뒤 다시 실행해주세요.")
    if show_debug_info:
        with st.expander("상세 오류 확인", expanded=False):
            st.code(str(e))
    st.stop()

game_base = data["game_base"]
issue_repeat_summary = data["issue_repeat_summary"]
condition_issue_summary = data["condition_issue_summary"]
evidence_base = data["evidence_base"]
graded_games = data["graded_games"]

options = get_filter_options(game_base, evidence_base)

if not options["genres"] or not options["price_groups"] or not options["play_styles"]:
    st.error("필터 옵션을 만들 수 없습니다. evidence_base의 condition_type, condition_value 컬럼을 확인해야 합니다.")
    st.stop()

# ============================================================
# 데이터 로드 정보: 개발자 정보 보기에서만 노출
# ============================================================
if show_debug_info:
    with st.expander("📁 불러온 데이터 확인", expanded=False):
        st.write(f"**실행 기준:** `{data['run_name']}`")
        st.write(f"**데이터 폴더:** `{data['data_dir']}`")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("게임 기준 데이터", f"{len(game_base):,}행")

        with col2:
            st.metric("전체 이슈 요약", f"{len(issue_repeat_summary):,}행")

        with col3:
            st.metric("조건별 이슈 요약", f"{len(condition_issue_summary):,}행")

        with col4:
            st.metric("체크리스트 근거", f"{len(evidence_base):,}행")

# ============================================================
# 기본 선택값
# ============================================================
# 첫 화면에서는 특정 조건을 자동으로 선택하지 않습니다.
# 시연자가 직접 조건을 고른 뒤 결과를 생성하도록 비워둡니다.
default_genres = []
default_price_groups = []
default_play_styles = []
default_tags = []

if "prelaunch_tag_match_input" not in st.session_state:
    st.session_state["prelaunch_tag_match_input"] = "any"

def reset_prelaunch_input_state() -> None:
    """입력 조건과 현재 생성 결과를 초기화합니다.

    Streamlit은 위젯이 생성된 뒤 같은 실행 흐름에서 해당 위젯 key를
    직접 수정하면 오류가 발생합니다. 따라서 초기화는 버튼 콜백에서
    먼저 처리합니다.
    """
    for key in [
        "prelaunch_genres_input",
        "prelaunch_price_groups_input",
        "prelaunch_tags_input",
        "prelaunch_play_styles_input",
    ]:
        st.session_state[key] = []

    st.session_state["prelaunch_tag_match_input"] = "any"
    st.session_state.pop("prelaunch_user_condition", None)
    st.session_state.pop("prelaunch_llm_result", None)
    st.session_state.pop("prelaunch_cache_key", None)
    st.session_state["prelaunch_reset_notice"] = True

# ============================================================
# 조건 입력 폼
# ============================================================
st.markdown(
    """
    <div class="prelaunch-panel-title"><span class="small-icon">🎮</span>게임 속성 선택</div>
    <div class="prelaunch-section-caption">
        장르, 가격대, Steam 태그, 플레이 방식을 선택한 뒤 <b>조건 적용</b> 버튼을 누르면 체크리스트가 바로 생성됩니다.
    </div>
    """,
    unsafe_allow_html=True,
)

with st.form("prelaunch_condition_form"):
    col1, col2 = st.columns(2)

    with col1:
        selected_genres = st.multiselect(
            "장르 선택",
            options=options["genres"],
            default=default_genres,
            key="prelaunch_genres_input",
            help=(
                "개발 중인 게임과 가까운 장르를 선택합니다. "
                "여러 장르를 선택하면 선택한 장르 중 하나라도 해당하는 게임을 함께 확인합니다."
            ),
        )

        selected_price_groups = st.multiselect(
            "가격대 선택",
            options=options["price_groups"],
            default=default_price_groups,
            key="prelaunch_price_groups_input",
            help=(
                "출시를 고려 중인 가격대를 선택합니다. "
                "여러 가격대를 선택하면 선택한 가격대 중 하나라도 해당하는 게임을 함께 확인합니다."
            ),
        )

    with col2:
        selected_tags = st.multiselect(
            "Steam 태그 선택",
            options=options["steam_tags"],
            default=default_tags,
            key="prelaunch_tags_input",
            help=(
                "게임의 핵심 특징을 나타내는 Steam 태그를 선택합니다. "
                "태그는 아래 매칭 방식에서 any 또는 all 기준을 직접 고를 수 있습니다."
            ),
        )

        selected_play_styles = st.multiselect(
            "플레이 방식 선택",
            options=options["play_styles"],
            default=default_play_styles,
            key="prelaunch_play_styles_input",
            help=(
                "싱글플레이 중심, 멀티플레이 중심 등 게임의 주요 플레이 방식을 선택합니다. "
                "여러 방식을 선택하면 선택한 방식 중 하나라도 해당하는 게임을 함께 확인합니다."
            ),
        )

    tag_match = st.radio(
        "Steam 태그 매칭 방식",
        options=["any", "all"],
        index=0,
        horizontal=True,
        key="prelaunch_tag_match_input",
        help=(
            "any는 선택한 태그 중 하나라도 포함된 게임을 매칭합니다. "
            "all은 선택한 태그를 모두 포함한 게임만 매칭하므로 결과가 더 좁아집니다."
        ),
    )

    apply_col, reset_col = st.columns([1, 1])
    with apply_col:
        submitted = st.form_submit_button(
            "조건 적용",
            type="primary",
            use_container_width=True,
            help="선택한 조건을 적용하고 유사 게임 리뷰 기반 체크리스트를 바로 생성합니다.",
        )
    with reset_col:
        reset_clicked = st.form_submit_button(
            "입력 조건 초기화",
            use_container_width=True,
            help="선택한 조건과 현재 생성 결과를 모두 지우고 처음 상태로 되돌립니다.",
            on_click=reset_prelaunch_input_state,
        )

# ============================================================
# 조건 저장
# ============================================================
should_generate_prelaunch_result = False

if st.session_state.pop("prelaunch_reset_notice", False):
    st.success("입력 조건과 현재 생성 결과를 초기화했습니다.")

if submitted:
    if not any([selected_genres, selected_price_groups, selected_tags, selected_play_styles]):
        st.warning("조건을 하나 이상 선택한 뒤 다시 적용해주세요.")
        st.stop()

    st.session_state["prelaunch_user_condition"] = {
        "genres": selected_genres,
        "price_groups": selected_price_groups,
        "steam_tags": selected_tags,
        "steam_tag_match": tag_match,
        "play_styles": selected_play_styles,
    }
    # 조건을 바꾸면 이전 생성 결과는 화면에서 제거하고, 새 조건으로 바로 생성합니다.
    st.session_state.pop("prelaunch_llm_result", None)
    st.session_state.pop("prelaunch_cache_key", None)
    should_generate_prelaunch_result = True

if "prelaunch_user_condition" not in st.session_state:
    st.info("게임 속성을 선택한 뒤 **조건 적용** 버튼을 눌러 체크리스트를 생성해주세요.")
    st.stop()

user_condition = st.session_state["prelaunch_user_condition"]

# ============================================================
# 조건 기반 데이터 생성
# ============================================================
with st.spinner("입력 조건에 맞는 근거 데이터를 정리하는 중..."):
    matched_games = filter_matched_games(game_base, user_condition)

    selected_evidence = select_condition_evidence(
        evidence_base=evidence_base,
        user_condition=user_condition,
        top_n_per_condition=top_n_per_condition,
        max_total_rows=max_total_rows,
    )

    overall_issues = get_overall_issues(
        issue_repeat_summary=issue_repeat_summary,
        top_n=overall_issue_n,
    )

    tag_dna_summary = make_tag_dna_summary(
        graded_games=graded_games,
        input_tags=user_condition.get("steam_tags", []),
    )

matched_game_count = matched_games["appid"].nunique() if "appid" in matched_games.columns else len(matched_games)

if "review_count" in matched_games.columns:
    matched_review_count = int(matched_games["review_count"].sum())
else:
    matched_review_count = 0

# ============================================================
# 데이터 부족 안내
# ============================================================
if matched_games.empty:
    st.warning("입력 조건에 맞는 게임이 없습니다. 조건을 조금 넓혀서 다시 시도해주세요.")
    st.stop()

if selected_evidence.empty:
    st.warning("입력 조건에 맞는 반복 이슈 근거 데이터가 없습니다. 조건을 조금 넓혀서 다시 시도해주세요.")
    st.stop()

# ============================================================
# 프롬프트 / 캐시 키 생성
# ============================================================
checklist_prompt = build_checklist_prompt(
    user_condition=user_condition,
    matched_game_count=matched_game_count,
    matched_review_count=matched_review_count,
    selected_evidence_df=selected_evidence,
    overall_issues_df=overall_issues,
    tag_dna_df=tag_dna_summary,
    max_evidence_rows_for_prompt=max_total_rows,
    top_n_overall_issues=overall_issue_n,
)

cache_key = make_prelaunch_cache_key(user_condition, selected_evidence)
st.session_state["prelaunch_cache_key"] = cache_key

# ============================================================
# 체크리스트 자동 생성
# ============================================================
cached_result = load_cached_prelaunch_result(run_name, cache_key) if use_cache and not force_regenerate else None

if should_generate_prelaunch_result:
    if cached_result is not None and not force_regenerate:
        st.session_state["prelaunch_llm_result"] = cached_result
        st.success("동일 조건의 기존 체크리스트 결과를 불러왔습니다.")
    else:
        with st.spinner("선택한 게임 속성을 기준으로 출시 전 체크리스트를 생성하는 중입니다..."):
            try:
                result_dict = generate_prelaunch_checklist_with_llm(
                    checklist_prompt=checklist_prompt,
                    temperature=temperature,
                    max_retries=max_retries,
                )
                save_cached_prelaunch_result(run_name, cache_key, result_dict)
                st.session_state["prelaunch_llm_result"] = result_dict
                st.success("체크리스트 생성이 완료되었습니다.")
            except Exception as e:
                st.error("체크리스트 생성 중 오류가 발생했습니다.")
                st.warning(f"오류 타입: {type(e).__name__}")
                st.code(repr(e), language="text")
                st.exception(e)
                st.stop()
elif cached_result is not None and "prelaunch_llm_result" not in st.session_state:
    st.session_state["prelaunch_llm_result"] = cached_result
    st.success("동일 조건의 기존 체크리스트 결과를 불러왔습니다.")

if "prelaunch_llm_result" not in st.session_state:
    st.info("현재 조건의 체크리스트가 아직 생성되지 않았습니다. 게임 속성을 확인한 뒤 **조건 적용** 버튼을 눌러주세요.")
    st.stop()

checklist_result_dict = st.session_state["prelaunch_llm_result"]

checklist_table_df = make_checklist_table(
    checklist_result_dict,
    evidence_df=selected_evidence,
    drop_unknown_issues=True,
)

validation_df = make_prelaunch_validation_result_df(
    checklist_result_dict,
    selected_evidence,
)

report_markdown = make_prelaunch_report_markdown(
    checklist_result_dict,
    user_condition=user_condition,
    matched_game_count=matched_game_count,
    matched_review_count=matched_review_count,
)
report_markdown = clean_visible_terms(report_markdown)

if checklist_table_df.empty:
    st.warning("생성 결과에서 출력 가능한 체크리스트 항목을 만들지 못했습니다. 근거 데이터를 확인해야 합니다.")
    st.stop()

# ============================================================
# 결과 출력
# ============================================================
st.divider()

if show_detail_sections:
    tab_checklist, tab_evidence, tab_reference = st.tabs(
        [
            "📋 체크리스트",
            "📊 근거 보기",
            "✅ 검증·참고",
        ]
    )
else:
    (tab_checklist,) = st.tabs(["📋 체크리스트"])

# ------------------------------------------------------------
# Tab 1. 체크리스트
# ------------------------------------------------------------
with tab_checklist:
    render_section_lead(
        "점검 카드를 필터로 좁혀 확인합니다.",
        "각 카드는 유사 게임 리뷰에서 반복된 이슈를 개발자가 바로 확인할 수 있는 질문으로 바꾼 결과입니다.  \n"
        "점검 유형, 점검 우선도, 이슈 태그를 선택하면 필요한 카드만 바로 확인할 수 있습니다.",
    )

    render_checklist_overview(checklist_table_df, evidence_df=selected_evidence)

    st.divider()

    st.markdown('<div class="prelaunch-panel-title"><span class="small-icon">🔎</span>점검 카드 필터</div>', unsafe_allow_html=True)
    filter_col1, filter_col2, filter_col3 = st.columns(3)

    filtered_checklist = checklist_table_df.copy()

    with filter_col1:
        priority_options = ["전체", "우선 점검", "추가 검토", "참고"]
        selected_priority_display = st.selectbox(
            "점검 우선도",
            options=priority_options,
            key="prelaunch_checklist_priority_filter",
            help=PRELAUNCH_FILTER_HELP["priority"],
        )
        selected_priority_filter = _priority_raw(selected_priority_display)

    with filter_col2:
        direction_options = ["전체", "확인 필요 요소", "확인 요소", "강화 요소", "참고 요소"]
        selected_direction_display = st.selectbox(
            "점검 유형",
            options=direction_options,
            key="prelaunch_checklist_direction_filter",
            help=PRELAUNCH_FILTER_HELP["check_type"],
        )
        selected_direction_filter = _direction_raw(selected_direction_display)

    with filter_col3:
        issue_tag_options = _available_issue_tag_options(checklist_table_df, issue_col="근거 이슈")
        selected_checklist_issue_tags = st.multiselect(
            "이슈 태그",
            options=issue_tag_options,
            default=[],
            key="prelaunch_checklist_issue_tag_filter",
            help=PRELAUNCH_FILTER_HELP["issue_tag"],
            placeholder="이슈 태그를 선택해주세요",
        )

    if selected_direction_filter != "전체" and "해석 방향" in filtered_checklist.columns:
        filtered_checklist = filtered_checklist[
            filtered_checklist["해석 방향"].astype(str) == selected_direction_filter
        ]

    if selected_priority_filter != "전체" and "우선순위" in filtered_checklist.columns:
        filtered_checklist = filtered_checklist[
            filtered_checklist["우선순위"].astype(str) == selected_priority_filter
        ]

    if selected_checklist_issue_tags and "근거 이슈" in filtered_checklist.columns:
        filtered_checklist = filtered_checklist[
            filtered_checklist["근거 이슈"].astype(str).isin(selected_checklist_issue_tags)
        ]

    st.caption(
        f"현재 선택한 필터에 해당하는 체크리스트 항목: {len(filtered_checklist):,}개 / 전체 {len(checklist_table_df):,}개"
    )

    render_checklist_cards(filtered_checklist)

    with st.expander("표 형태로 보기", expanded=False):
        render_wrapped_table(filtered_checklist, height_px=520)

    csv = filtered_checklist.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="체크리스트 CSV 다운로드",
        data=csv,
        file_name="prelaunch_checklist.csv",
        mime="text/csv",
    )

# ------------------------------------------------------------
# Tab 2. 근거 보기
# ------------------------------------------------------------
if show_detail_sections:
    with tab_evidence:
        render_section_lead(
            "체크리스트가 만들어진 근거를 확인합니다.",
            "이 탭은 입력 조건과 유사한 게임들의 출시 초기 리뷰에서 어떤 이슈가 반복되었는지 보여줍니다.    \n"
            "그래프와 표는 체크리스트의 우선 점검 항목이 왜 나왔는지 확인하는 용도로 사용합니다.",
        )

        with st.expander("유사 게임에서 자주 언급된 이슈 보기", expanded=False):
            st.info(
                "입력 조건과 유사한 게임들의 출시 초기 리뷰에서 반복적으로 언급된 이슈를 요약합니다.    \n"
                "어떤 항목이 체크리스트의 우선 점검 항목으로 연결되었는지 그래프와 지표로 확인할 수 있습니다."
            )
            render_evidence_overview(selected_evidence)

        with st.expander("반복 이슈 근거 표 보기", expanded=False):
            st.info(
                "체크리스트 생성에 사용된 반복 이슈 근거를 표로 확인합니다.     \n"
                "점검 우선도, 점검 유형, 이슈 태그를 기준으로 필터링하면서 어떤 근거가 카드에 반영되었는지 볼 수 있습니다."
            )
            filter_col1, filter_col2, filter_col3 = st.columns(3)

            evidence_view = selected_evidence.copy()

            with filter_col1:
                priority_options = ["전체", "우선 점검", "추가 검토", "참고"]
                selected_priority_display = st.selectbox(
                    "점검 우선도",
                    priority_options,
                    key="prelaunch_priority_filter",
                    help=PRELAUNCH_FILTER_HELP["priority"],
                )
                selected_priority_filter = _priority_raw(selected_priority_display)

            with filter_col2:
                direction_options = ["전체", "확인 필요 요소", "확인 요소", "강화 요소", "참고 요소"]
                selected_direction_display = st.selectbox(
                    "점검 유형",
                    direction_options,
                    key="prelaunch_direction_filter",
                    help=PRELAUNCH_FILTER_HELP["check_type"],
                )
                selected_direction_filter = _direction_raw(selected_direction_display)

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
                    key="prelaunch_issue_tag_filter",
                    help=PRELAUNCH_FILTER_HELP["issue_tag"],
                    placeholder="이슈 태그를 선택해주세요",
                )

            if selected_direction_filter != "전체" and "issue_direction" in evidence_view.columns:
                evidence_view = evidence_view[
                    evidence_view["issue_direction"].astype(str) == selected_direction_filter
                ]

            if selected_priority_filter != "전체" and "priority_level" in evidence_view.columns:
                evidence_view = evidence_view[
                    evidence_view["priority_level"].astype(str) == selected_priority_filter
                ]

            if selected_issue_tags and "issue_name_kor" in evidence_view.columns:
                evidence_view = evidence_view[
                    evidence_view["issue_name_kor"].astype(str).isin(selected_issue_tags)
                ]

            st.caption(f"표시 중인 근거 데이터: {len(evidence_view):,}행 / 전체 {len(selected_evidence):,}행")
            evidence_display_df = make_evidence_display_df(evidence_view)
            render_wrapped_table(evidence_display_df, height_px=560)

            evidence_csv = evidence_display_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="근거 데이터 CSV 다운로드",
                data=evidence_csv,
                file_name="prelaunch_selected_evidence.csv",
                mime="text/csv",
            )

        with st.expander("조건에 맞는 게임 예시 보기", expanded=False):
            st.info(
                "현재 선택한 장르, 가격대, Steam 태그, 플레이 방식 조건에 매칭된 유사 게임 예시입니다.  \n"
                "체크리스트가 어떤 게임군의 리뷰를 참고해 만들어졌는지 확인하는 용도로 사용합니다."
            )
            game_display_cols = [
                "appid",
                "game_name",
                "genres_text",
                "price_group",
                "top_steam_tags_text",
                "play_style",
                "review_count",
                "llm_positive_ratio",
                "llm_negative_ratio",
                "high_urgency_ratio",
            ]
            game_display_cols = [col for col in game_display_cols if col in matched_games.columns]
            game_column_rename_map = {
                "appid": "앱 ID",
                "game_name": "게임명",
                "genres_text": "장르",
                "price_group": "가격대",
                "top_steam_tags_text": "Steam 태그",
                "play_style": "플레이 방식",
                "review_count": "분석 리뷰 수",
                "llm_positive_ratio": "긍정 비율(%)",
                "llm_negative_ratio": "부정 비율(%)",
                "high_urgency_ratio": "High urgency 비율(%)",
            }
            matched_games_display = (
                matched_games[game_display_cols]
                .head(200)
                .rename(columns=game_column_rename_map)
            )
            render_wrapped_table(matched_games_display, height_px=560)
            matched_csv = matched_games[game_display_cols].to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="매칭 게임 CSV 다운로드",
                data=matched_csv,
                file_name="prelaunch_matched_games.csv",
                mime="text/csv",
            )

# ------------------------------------------------------------
# Tab 3. 검증·참고
# ------------------------------------------------------------
if show_detail_sections:
    with tab_reference:
        render_section_lead(
            "체크리스트 생성 결과와 분류 기준을 확인합니다.",
            "이 탭에서는 생성된 체크리스트가 근거 데이터의 점검 우선도와 점검 유형 기준을 유지했는지 확인합니다.    \n필요할 때 점검 우선도와 점검 유형 분류 기준도 함께 참고할 수 있습니다.",
        )

        with st.expander("생성 결과 점검 보기", expanded=False):
            render_prelaunch_validation_guide(validation_df)
            st.markdown("#### 검증 결과표")
            st.caption(
                "생성된 체크리스트가 근거 데이터의 점검 우선도를 그대로 사용했는지 확인한 결과입니다. "
                "확인 필요 항목이 있을 경우, 최종 표에서는 근거 데이터 기준으로 보정합니다."
            )
            render_wrapped_table(validation_df, height_px=360)

        with st.expander("체크리스트 분류 기준 보기", expanded=False):
            st.info(
                "체크리스트 카드의 점검 우선도와 점검 유형을 어떻게 해석해야 하는지 정리한 기준표입니다.    \n"
                "내부 기준값은 화면에서 우선 점검, 추가 검토, 참고로 바꾸어 표시합니다."
            )
            priority_guide_df, direction_guide_df = make_prelaunch_classification_guide_tables()
            guide_col1, guide_col2 = st.columns(2)
            with guide_col1:
                st.markdown("#### 점검 우선도 기준")
                render_wrapped_table(priority_guide_df, height_px=270)
            with guide_col2:
                st.markdown("#### 점검 유형 기준")
                render_wrapped_table(direction_guide_df, height_px=270)
