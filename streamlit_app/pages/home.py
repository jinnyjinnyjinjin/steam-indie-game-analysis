from textwrap import dedent

import streamlit as st


# ============================================================
# 홈 화면: 랜딩 페이지 리디자인
# ============================================================
st.markdown(
    """
<style>
.home-wrap { position: relative; }
.hero-panel {
    position: relative;
    min-height: 260px;
    padding: 2.4rem 2.7rem;
    border-radius: 28px;
    overflow: hidden;
    border: 1px solid rgba(96, 165, 250, 0.30);
    background:
        radial-gradient(circle at 18% 45%, rgba(56, 189, 248, 0.20), transparent 18%),
        radial-gradient(circle at 86% 22%, rgba(124, 58, 237, 0.12), transparent 22%),
        linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(2, 8, 23, 0.94));
    box-shadow: 0 28px 80px rgba(2, 8, 23, 0.46), inset 0 0 0 1px rgba(255, 255, 255, 0.03);
}
.hero-panel::before {
    content: "";
    position: absolute;
    inset: 0;
    background-image:
        linear-gradient(rgba(148, 163, 184, 0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(148, 163, 184, 0.05) 1px, transparent 1px);
    background-size: 42px 42px;
    mask-image: linear-gradient(90deg, rgba(0,0,0,0.9), rgba(0,0,0,0.45), transparent);
    pointer-events: none;
}
.hero-content {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-columns: 260px 1fr;
    gap: 2.4rem;
    align-items: center;
}
.hero-visual {
    min-height: 175px;
    display: grid;
    place-items: center;
    border-radius: 28px;
    background: radial-gradient(circle, rgba(56, 189, 248, 0.18), transparent 60%);
}
.gamepad-glow {
    width: 168px;
    height: 168px;
    display: grid;
    place-items: center;
    border-radius: 50%;
    border: 1px solid rgba(96, 165, 250, 0.30);
    background: radial-gradient(circle, rgba(30, 64, 175, 0.30), rgba(15, 23, 42, 0.04) 72%);
    box-shadow: 0 0 58px rgba(56, 189, 248, 0.22);
    font-size: 5.2rem;
}
.hero-kicker {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.9rem;
    padding: 0.42rem 0.78rem;
    border-radius: 999px;
    border: 1px solid rgba(56, 189, 248, 0.32);
    background: rgba(14, 165, 233, 0.12);
    color: #7dd3fc;
    font-weight: 750;
    font-size: 0.9rem;
}
.hero-title {
    margin: 0;
    color: #ffffff;
    font-size: clamp(2.35rem, 4.7vw, 4.4rem);
    line-height: 1.08;
    letter-spacing: -0.07em;
    font-weight: 900;
}
.hero-subtitle {
    margin-top: 0.85rem;
    color: #60a5fa;
    font-size: clamp(1.1rem, 1.8vw, 1.55rem);
    font-weight: 800;
    letter-spacing: -0.045em;
}
.hero-desc {
    max-width: 760px;
    margin-top: 1.15rem;
    color: rgba(226, 232, 240, 0.80);
    font-size: 1.05rem;
    line-height: 1.75;
}
.feature-card {
    min-height: 300px;
    position: relative;
    overflow: hidden;
    border-radius: 24px;
    padding: 1.65rem 1.65rem 1.45rem;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.86), rgba(3, 7, 18, 0.86));
    border: 1px solid rgba(96, 165, 250, 0.36);
    box-shadow: 0 22px 58px rgba(2, 8, 23, 0.35);
}
.feature-card::after {
    content: "";
    position: absolute;
    width: 210px;
    height: 210px;
    top: -80px;
    right: -70px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(59, 130, 246, 0.18), transparent 68%);
    pointer-events: none;
}
.feature-card.purple { border-color: rgba(192, 132, 252, 0.39); }
.feature-card.purple::after { background: radial-gradient(circle, rgba(168, 85, 247, 0.20), transparent 68%); }
.feature-tag {
    display: inline-flex;
    padding: 0.36rem 0.72rem;
    border-radius: 999px;
    border: 1px solid rgba(56, 189, 248, 0.34);
    background: rgba(37, 99, 235, 0.18);
    color: #93c5fd;
    font-size: 0.85rem;
    font-weight: 800;
    margin-bottom: 1.05rem;
}
.feature-tag.purple {
    border-color: rgba(192, 132, 252, 0.44);
    background: rgba(126, 34, 206, 0.18);
    color: #d8b4fe;
}
.feature-body {
    display: grid;
    grid-template-columns: 128px 1fr;
    gap: 1.25rem;
    align-items: center;
}
.feature-icon {
    width: 118px;
    height: 118px;
    display: grid;
    place-items: center;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(59, 130, 246, 0.22), rgba(15, 23, 42, 0.10));
    border: 1px solid rgba(96, 165, 250, 0.35);
    box-shadow: 0 0 40px rgba(59, 130, 246, 0.20);
    font-size: 3.05rem;
}
.feature-icon.purple {
    background: radial-gradient(circle, rgba(168, 85, 247, 0.22), rgba(15, 23, 42, 0.10));
    border-color: rgba(192, 132, 252, 0.38);
    box-shadow: 0 0 40px rgba(168, 85, 247, 0.19);
}
.feature-title {
    color: #ffffff;
    font-size: 1.72rem;
    line-height: 1.2;
    letter-spacing: -0.055em;
    font-weight: 900;
    margin-bottom: 0.85rem;
}
.feature-desc {
    color: rgba(226, 232, 240, 0.78);
    line-height: 1.72;
    font-size: 1rem;
}
.feature-cta {
    position: relative;
    z-index: 2;
    display: block;
    margin-top: 1.25rem;
    padding: 0.9rem 1rem;
    border-radius: 14px;
    color: #dbeafe !important;
    font-weight: 820;
    text-align: center;
    border: 1px solid rgba(96, 165, 250, 0.42);
    background: rgba(15, 23, 42, 0.54);
    text-decoration: none !important;
    transition: all 0.18s ease;
}
.feature-cta:hover {
    transform: translateY(-1px);
    background: rgba(30, 64, 175, 0.34);
    border-color: rgba(56, 189, 248, 0.74);
    box-shadow: 0 12px 34px rgba(14, 165, 233, 0.14);
    color: #ffffff !important;
}
.feature-card.purple .feature-cta {
    color: #f3e8ff !important;
    border-color: rgba(192, 132, 252, 0.42);
}
.home-detail-box {
    color: rgba(226, 232, 240, 0.82);
    line-height: 1.72;
}
@media (max-width: 980px) {
    .hero-content { grid-template-columns: 1fr; gap: 1.2rem; }
    .hero-visual { min-height: 120px; }
    .gamepad-glow { width: 128px; height: 128px; font-size: 4rem; }
    .feature-body { grid-template-columns: 1fr; }
}
</style>
""",
    unsafe_allow_html=True,
)


def render_html(html: str) -> None:
    """HTML이 들여쓰기 때문에 코드블록처럼 보이지 않도록 정리해서 출력합니다."""
    st.markdown(dedent(html).strip(), unsafe_allow_html=True)


render_html(
    """
    <div class="home-wrap">
    <section class="hero-panel">
    <div class="hero-content">
    <div class="hero-visual"><div class="gamepad-glow">🎮</div></div>
    <div>
    <div class="hero-kicker">Steam Review Intelligence</div>
    <h1 class="hero-title">Steam 인디게임<br>출시 전략 도우미</h1>
    <div class="hero-subtitle">Steam 리뷰를 출시 전략과 운영 판단으로 연결합니다.</div>
    <div class="hero-desc">
    게임의 출시 초기 리뷰와 실제 유저 리뷰를 바탕으로,<br>
    개발자가 <b> 출시 전에 점검할 항목과</b>과 <b>출시 후 먼저 확인할 이슈를</b>을 빠르게 정리합니다.
    </div>
    </div>
    </div>
    </section>
    </div>
    """
)

st.info(
    "이 앱은 Steam 리뷰를 실시간으로 새로 수집하지 않습니다.  \n"
    "사전에 수집·전처리·리뷰 분류가 완료된 데이터를 바탕으로 결과를 생성합니다."
)

st.markdown("## 핵심 기능")

pre_col, post_col = st.columns(2, gap="large")

with pre_col:
    render_html(
        """
        <div class="feature-card">
        <div class="feature-tag">출시 전</div>
        <div class="feature-body">
        <div class="feature-icon">🧾</div>
        <div>
        <div class="feature-title">출시 전 체크리스트</div>
        <div class="feature-desc">
        출시 전 확인할 리스크와 강점을 체크리스트 카드로 정리합니다.
        </div>
        </div>
        </div>
        <a class="feature-cta" href="./prelaunch_checklist" target="_self">체크리스트 보러가기 →</a>
        </div>
        """
    )
    with st.expander("출시 전 체크리스트 자세히 보기", expanded=False):
        st.markdown(
            """
            <div class="home-detail-box">
            준비 중인 게임의 <b>장르, 가격대, Steam 태그, 플레이 방식</b>을 입력하면<br>
            게임의 출시 초기 리뷰에서 반복된 강점과 리스크를 체크리스트로 정리합니다.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            **이럴 때 사용합니다**
            - 출시 전에 UX, 난이도, 콘텐츠, 가격 관련 리스크를 점검하고 싶을 때
            - 비슷한 게임에서 자주 칭찬받거나 비판받은 요소를 확인하고 싶을 때
            - 팀 회의나 QA 과정에서 사용할 출시 전 체크리스트 초안이 필요할 때
            """
        )

with post_col:
    render_html(
        """
        <div class="feature-card purple">
        <div class="feature-tag purple">출시 후</div>
        <div class="feature-body">
        <div class="feature-icon purple">🛠️</div>
        <div>
        <div class="feature-title">출시 후 패치·운영 제안</div>
        <div class="feature-desc">
        출시 후 반복 이슈를 패치·운영 제안 카드로 정리합니다.
        </div>
        </div>
        </div>
        <a class="feature-cta" href="./postlaunch_report" target="_self">패치·운영 제안 보러가기 →</a>
        </div>
        """
    )
    with st.expander("출시 후 패치·운영 제안 자세히 보기", expanded=False):
        st.markdown(
            """
            <div class="home-detail-box">
            이미 출시된 게임의 리뷰를 바탕으로 반복 이슈를 정리하고,<br>
            패치·운영에서 먼저 확인할 항목을 제안 카드로 보여줍니다.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            **이럴 때 사용합니다**
            - 부정 리뷰가 쌓였지만 원인을 빠르게 정리하기 어려울 때
            - 버그, 밸런스, 콘텐츠, 최적화 중 무엇을 먼저 볼지 정해야 할 때
            - 패치 노트나 운영 공지의 방향성을 잡기 위한 근거가 필요할 때
            """
        )

with st.expander("📄 앱 설명 자세히 보기", expanded=False):
    st.markdown(
        """
        #### 이 앱이 사용하는 데이터
        - 사전에 수집한 Steam 인디게임 메타데이터와 리뷰 분석 결과를 사용합니다.
        - 앱 화면에서 Steam 리뷰를 실시간으로 새로 수집하지는 않습니다.
        - 새 리뷰를 반영하려면 별도의 수집, 전처리, 리뷰 분류 과정을 먼저 실행해야 합니다.

        #### 결과를 어떻게 봐야 하나요?
        - 결과는 최종 정답이 아니라 개발자가 빠르게 검토할 수 있도록 정리한 **근거 기반 초안**입니다.
        - 최종 의사결정에는 개발 일정, 팀 리소스, 게임의 기획 의도, 커뮤니티 상황을 함께 고려해야 합니다.

        #### 출시 전과 출시 후의 차이
        - **출시 전 체크리스트**는 게임의 초기 리뷰를 참고해 출시 전에 확인할 항목을 정리합니다.
        - **출시 후 패치·운영 제안**은 선택한 게임의 실제 리뷰를 바탕으로 패치와 운영 우선순위를 정리합니다.
        """
    )
