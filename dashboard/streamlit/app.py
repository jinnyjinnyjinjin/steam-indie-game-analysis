import ast
import json

import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import (
    LANGUAGE_SILENCE_RATE,
    get_all_genres,
    get_similar_games,
    get_top_tags,
)
from utils.risk_scorer import compute_reach

st.set_page_config(
    page_title="인디게임 출시 전 진단 도구",
    page_icon="🎮",
    layout="wide",
)

# ── 스타일 ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.kpi-card {
    background: #f8f9fa;
    border-radius: 12px;
    padding: 20px 24px;
    text-align: center;
    border: 1px solid #e9ecef;
}
.kpi-value { font-size: 2.2rem; font-weight: 700; line-height: 1.1; }
.kpi-label { font-size: 0.85rem; color: #6c757d; margin-top: 4px; }
.strength-card {
    background: #f0fdf4;
    border-left: 4px solid #22c55e;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    margin-bottom: 8px;
}
.opportunity-card {
    background: #eff6ff;
    border-left: 4px solid #3b82f6;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    margin-bottom: 8px;
}
.lang-card {
    background: #fefce8;
    border-left: 4px solid #eab308;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    margin-bottom: 8px;
}
.card-title { font-weight: 600; font-size: 0.9rem; margin-bottom: 2px; }
.card-detail { font-size: 0.82rem; color: #4b5563; }
.card-hint { font-size: 0.78rem; color: #2563eb; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# ── 헤더 ──────────────────────────────────────────────────────────────────────
st.title("🎮 인디게임 출시 전 진단 도구")
st.caption("Steam 인디게임 15,406개 데이터 기반 · 선택한 속성 조합의 반응 도달 가능성 분석")
st.divider()

# ── 입력 폼 ───────────────────────────────────────────────────────────────────
with st.form("prelaunch_form"):
    st.subheader("게임 속성 입력")
    col_left, col_right = st.columns(2)

    with col_left:
        selected_genres = st.multiselect(
            "장르 선택 (최대 3개)",
            options=get_all_genres(),
            max_selections=3,
            placeholder="장르를 선택하세요",
        )
        selected_tags = st.multiselect(
            "핵심 태그 선택 (최대 5개, 5개 이상 권장)",
            options=get_top_tags(80),
            max_selections=5,
            placeholder="태그를 선택하세요",
        )
        game_description = st.text_area(
            "게임 한 줄 설명 (선택 입력)",
            placeholder="예: 탑뷰 시점의 픽셀 아트 로그라이크 RPG. 절차적 생성 던전과 빌드 다양성이 특징.",
            height=80,
        )

    with col_right:
        price_input = st.slider(
            "예상 출시 가격 (USD)",
            min_value=0.99,
            max_value=30.0,
            value=9.99,
            step=0.50,
            format="$%.2f",
        )
        language_option = st.radio(
            "지원 언어 수",
            options=list(LANGUAGE_SILENCE_RATE.keys()),
            index=0,
            help="Steam은 언어 지원을 핵심 노출 요소로 공식 명시합니다.",
        )
        st.selectbox(
            "주요 플레이 방식",
            options=["싱글플레이어", "멀티플레이어", "협동 (Co-op)", "혼합"],
        )

    submitted = st.form_submit_button("🔍 분석하기", use_container_width=True)

# ── 결과 출력 ─────────────────────────────────────────────────────────────────
if submitted:
    if not selected_genres:
        st.warning("장르를 1개 이상 선택해주세요.")
        st.stop()

    result = compute_reach(selected_genres, selected_tags, price_input, language_option)
    similar = get_similar_games(selected_genres, selected_tags, price_input, top_n=5)

    # 유사 게임 중위 리뷰 수
    median_reviews = int(similar["total_reviews"].median()) if not similar.empty else 0

    st.divider()

    # ── KPI 카드 ──────────────────────────────────────────────────────────────
    level_color = {
        "매우 높음": "#16a34a",
        "높음":    "#2563eb",
        "보통":    "#d97706",
        "낮음":    "#dc2626",
    }[result.reach_level]

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value" style="color:{level_color}">{result.reach_score}%</div>
            <div class="kpi-label">반응 도달 가능성 · <b>{result.reach_level}</b></div>
        </div>""", unsafe_allow_html=True)
    with k2:
        pass_count = len(result.strengths)
        total_items = len(result.strengths) + len(result.opportunities)
        k2_color = "#16a34a" if pass_count == total_items else "#d97706"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value" style="color:{k2_color}">{pass_count} / {total_items}</div>
            <div class="kpi-label">강점 항목 (장르·가격·태그 기준)</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        k3_val = f"{median_reviews:,}개" if median_reviews else "–"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value" style="color:#2563eb">{k3_val}</div>
            <div class="kpi-label">유사 게임 중위 리뷰 수</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 게이지 + 컴포넌트 기여도 ──────────────────────────────────────────────
    col_gauge, col_bars = st.columns([1, 1])

    with col_gauge:
        gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=result.reach_score,
            number={"suffix": "%", "font": {"size": 44}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickvals": [0, 35, 50, 65, 100]},
                "bar": {"color": level_color},
                "steps": [
                    {"range": [0, 35],  "color": "#fee2e2"},
                    {"range": [35, 50], "color": "#fef3c7"},
                    {"range": [50, 65], "color": "#dbeafe"},
                    {"range": [65, 100], "color": "#dcfce7"},
                ],
                "threshold": {
                    "line": {"color": "#374151", "width": 3},
                    "thickness": 0.75,
                    "value": result.reach_score,
                },
            },
            title={"text": "반응 도달 가능성", "font": {"size": 16}},
        ))
        gauge.update_layout(height=280, margin=dict(t=40, b=0, l=20, r=20))
        st.plotly_chart(gauge, use_container_width=True)
        st.caption(
            "반응 도달 가능성 = 선택 속성 조합에서 리뷰 10개 이상 "
            "반응군에 속할 확률 추정치 (Steam 인디게임 15,406개 기준)"
        )

    with col_bars:
        st.markdown("**컴포넌트별 기여도**")
        st.caption("각 속성이 반응 도달 가능성에 기여하는 정도 (높을수록 유리)")

        baseline = round((1 - 0.433) * 100, 1)  # 56.7%

        labels = list(result.contributions.keys())
        values = list(result.contributions.values())
        colors = [
            "#22c55e" if v >= baseline else "#f59e0b" if v >= 45 else "#ef4444"
            for v in values
        ]

        bar_fig = go.Figure(go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{v:.1f}%" for v in values],
            textposition="outside",
        ))
        bar_fig.add_vline(
            x=baseline,
            line_dash="dot",
            line_color="#9ca3af",
            annotation_text=f"시장 평균 {baseline}%",
            annotation_position="top right",
            annotation_font_size=11,
        )
        bar_fig.update_layout(
            height=240,
            margin=dict(t=10, b=10, l=10, r=60),
            xaxis=dict(range=[0, 100], showgrid=False),
            yaxis=dict(autorange="reversed"),
            showlegend=False,
            plot_bgcolor="white",
        )
        st.plotly_chart(bar_fig, use_container_width=True)

    st.divider()

    # ── 강점 / 개선 기회 ──────────────────────────────────────────────────────
    col_strength, col_oppo = st.columns(2)

    with col_strength:
        st.markdown("#### ✅ 강점")
        if result.strengths:
            for s in result.strengths:
                st.markdown(f"""
                <div class="strength-card">
                    <div class="card-title">{s['label']}</div>
                    <div class="card-detail">{s['detail']}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown(
                "<div class='opportunity-card'><div class='card-detail'>강점으로 분류된 항목이 없습니다.</div></div>",
                unsafe_allow_html=True,
            )

    with col_oppo:
        st.markdown("#### 💡 개선 기회")
        for o in result.opportunities:
            hint_html = (
                f"<div class='card-hint'>→ {o['gain_hint']}</div>"
                if o.get("gain_hint") else ""
            )
            st.markdown(f"""
            <div class="opportunity-card">
                <div class="card-title">{o['label']}</div>
                <div class="card-detail">{o['detail']}</div>
                {hint_html}
            </div>""", unsafe_allow_html=True)

        # 언어 어드바이저리 (항상 표시)
        adv = result.language_advisory
        if adv["tip"]:
            st.markdown(f"""
            <div class="lang-card">
                <div class="card-title">🌐 언어 지원 확대 기회</div>
                <div class="card-detail">{adv['message']}</div>
                <div class="card-hint">→ {adv['tip']}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="strength-card">
                <div class="card-title">🌐 언어 지원</div>
                <div class="card-detail">{adv['message']}</div>
            </div>""", unsafe_allow_html=True)

    st.divider()

    # ── 유사 게임 사례 ────────────────────────────────────────────────────────
    st.markdown("#### 📊 유사 게임 사례 (반응군 기준)")
    st.caption(
        "장르 일치(필수) + 태그 유사도 40% · 가격 근접도 30% · 장르 겹침 30% 복합 점수 기준 Top 5"
    )

    if similar.empty:
        st.info("선택 조건과 일치하는 유사 게임이 없습니다.")
    else:
        display = similar.copy()
        display["유사도"] = display["_similarity"].map("{:.0%}".format)
        display["긍정률"] = display["positive_rate"].map("{:.1%}".format)
        display["가격"] = display["price"].map("${:.2f}".format)
        display["리뷰 수"] = display["total_reviews"].map("{:,}".format)

        def top3_tags(val: str) -> str:
            try:
                return ", ".join(list(json.loads(val).keys())[:3])
            except Exception:
                return ""

        def clean_genres(val: str) -> str:
            try:
                return ", ".join(g for g in ast.literal_eval(val) if g != "Indie")
            except Exception:
                return val

        display["주요 태그"] = display["tags"].apply(top3_tags)
        display["장르"] = display["genres"].apply(clean_genres)

        st.dataframe(
            display[["name", "장르", "가격", "유사도", "리뷰 수", "긍정률", "주요 태그"]].rename(
                columns={"name": "게임명"}
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # ── 전략 요약 ─────────────────────────────────────────────────────────────
    st.markdown("#### 🗺️ 전략 요약")

    summary_lines = []

    # 도달 가능성 한 줄 평
    reach_comment = {
        "매우 높음": "현재 속성 조합은 반응군 도달에 매우 유리합니다.",
        "높음":    "현재 속성 조합은 반응군 도달에 유리한 편입니다.",
        "보통":    "현재 속성 조합은 시장 평균 수준입니다. 아래 개선 기회를 적용하면 도달 가능성을 높일 수 있습니다.",
        "낮음":    "현재 속성 조합은 경쟁이 치열한 구간에 집중되어 있습니다. 개선 기회 항목을 우선 검토하세요.",
    }[result.reach_level]
    summary_lines.append(f"**도달 가능성 {result.reach_score}% ({result.reach_level})** — {reach_comment}")

    # 가장 높은 기여도 강점
    best_component = max(result.contributions, key=result.contributions.get)
    best_val = result.contributions[best_component]
    summary_lines.append(f"- **가장 유리한 요소**: {best_component} ({best_val:.1f}%)")

    # 가장 낮은 기여도 개선 포인트
    worst_component = min(result.contributions, key=result.contributions.get)
    worst_val = result.contributions[worst_component]
    summary_lines.append(f"- **우선 개선 요소**: {worst_component} ({worst_val:.1f}%) — 기여도가 가장 낮습니다.")

    # 언어 팁
    adv = result.language_advisory
    if adv["tip"]:
        summary_lines.append(f"- **언어 지원**: {adv['tip']}")

    # 유사 게임 벤치마크
    if not similar.empty:
        avg_positive = similar["positive_rate"].mean()
        summary_lines.append(
            f"- **유사 게임 벤치마크**: 평균 긍정률 {avg_positive:.1%}, 중위 리뷰 수 {median_reviews:,}개"
        )

    # 게임 설명 참고
    if game_description.strip():
        summary_lines.append(f"\n> {game_description[:120]}{'...' if len(game_description) > 120 else ''}")

    st.markdown("\n".join(summary_lines))

    st.divider()
    st.caption("데이터 출처: SteamSpy · Steam Store API · 2023~2025년 Indie 태그 게임 기준")
