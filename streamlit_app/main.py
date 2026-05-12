from pathlib import Path

import streamlit as st

# ============================================================
# 앱 전체 설정
# ============================================================
st.set_page_config(
    page_title="Steam 인디게임 출시 전략 분석",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent

# ============================================================
# 공통 다크 테마 / 디자인 시스템
# ============================================================
st.markdown(
    """
    <style>
    :root {
        --app-bg: #060b14;
        --app-bg-2: #0a1020;
        --app-panel: rgba(15, 23, 42, 0.76);
        --app-panel-strong: rgba(12, 18, 32, 0.92);
        --app-panel-soft: rgba(30, 41, 59, 0.34);
        --app-border: rgba(125, 166, 255, 0.22);
        --app-border-strong: rgba(56, 189, 248, 0.58);
        --app-text: #f8fafc;
        --app-muted: rgba(226, 232, 240, 0.74);
        --app-subtle: rgba(148, 163, 184, 0.7);
        --app-blue: #38bdf8;
        --app-blue-2: #60a5fa;
        --app-purple: #c084fc;
        --app-purple-2: #a855f7;
    }

    .stApp {
        background:
            radial-gradient(circle at 18% 8%, rgba(37, 99, 235, 0.22), transparent 30%),
            radial-gradient(circle at 80% 18%, rgba(168, 85, 247, 0.14), transparent 28%),
            linear-gradient(180deg, #07101d 0%, #060b14 48%, #04070d 100%);
        color: var(--app-text);
    }

    .block-container {
        max-width: 1500px;
        padding-top: 2.1rem;
        padding-bottom: 3rem;
    }

    [data-testid="stHeader"] {
        background: rgba(6, 11, 20, 0.62) !important;
        backdrop-filter: blur(16px);
    }

    /* 기본 텍스트 */
    .stMarkdown, .stText, p, label, span, div {
        color: inherit;
    }

    h1, h2, h3 {
        letter-spacing: -0.045em;
    }

    a {
        color: var(--app-blue);
    }

    /* 사이드바 */
    section[data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 30% 5%, rgba(96, 165, 250, 0.18), transparent 28%),
            linear-gradient(180deg, rgba(15, 23, 42, 0.98) 0%, rgba(8, 13, 24, 0.98) 100%) !important;
        border-right: 1px solid rgba(96, 165, 250, 0.24);
        box-shadow: 18px 0 50px rgba(2, 8, 23, 0.35);
    }

    section[data-testid="stSidebar"] div[data-testid="stSidebarUserContent"] {
        display: flex;
        flex-direction: column;
        min-height: calc(100vh - 3rem);
        padding-top: 1.2rem;
    }

    .sidebar-brand {
        padding: 0.4rem 0.25rem 1.35rem 0.25rem;
    }

    .sidebar-logo {
        width: 58px;
        height: 58px;
        display: grid;
        place-items: center;
        margin-bottom: 1.1rem;
        border-radius: 18px;
        background: radial-gradient(circle, rgba(96,165,250,0.28), rgba(15,23,42,0.45));
        border: 1px solid rgba(96,165,250,0.35);
        box-shadow: 0 0 28px rgba(56,189,248,0.22);
        font-size: 2.05rem;
    }

    .sidebar-brand-title {
        font-size: 1.56rem;
        line-height: 1.22;
        font-weight: 850;
        letter-spacing: -0.055em;
        color: #ffffff;
    }

    .sidebar-brand-caption {
        margin-top: 0.85rem;
        color: rgba(203, 213, 225, 0.72);
        font-size: 0.92rem;
        line-height: 1.7;
    }

    .sidebar-menu-label {
        margin: 0.9rem 0 0.55rem;
        color: rgba(148, 163, 184, 0.82);
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .sidebar-footer {
        margin-top: auto;
        padding-top: 1.2rem;
        color: rgba(203, 213, 225, 0.62);
        font-size: 0.84rem;
        line-height: 1.55;
    }

    /* 사이드바 페이지 링크를 메뉴 버튼처럼 보이게 */
    section[data-testid="stSidebar"] div[data-testid="stPageLink"] a {
        min-height: 3rem;
        border-radius: 14px;
        padding: 0.72rem 0.85rem;
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(15, 23, 42, 0.2);
        transition: all 0.18s ease;
        color: rgba(248, 250, 252, 0.88) !important;
        text-decoration: none;
    }

    section[data-testid="stSidebar"] div[data-testid="stPageLink"] a:hover {
        transform: translateX(2px);
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.28), rgba(14, 165, 233, 0.08));
        border-color: rgba(96, 165, 250, 0.46);
        box-shadow: 0 10px 28px rgba(37, 99, 235, 0.16);
    }

    /* Expander */
    div[data-testid="stExpander"] details {
        background: rgba(15, 23, 42, 0.58) !important;
        border: 1px solid rgba(148, 163, 184, 0.18) !important;
        border-radius: 18px !important;
        box-shadow: 0 16px 38px rgba(2, 8, 23, 0.24);
        overflow: hidden;
    }

    div[data-testid="stExpander"] summary {
        padding: 1rem 1.1rem !important;
        font-weight: 750;
    }

    /* Alert */
    div[data-testid="stAlert"] {
        border-radius: 16px !important;
        border: 1px solid rgba(56, 189, 248, 0.38) !important;
        background: linear-gradient(135deg, rgba(14, 116, 144, 0.26), rgba(15, 23, 42, 0.78)) !important;
        box-shadow: 0 16px 45px rgba(8, 145, 178, 0.12);
    }
    .stButton > button {
        color: #f8fafc !important;
        border-color: rgba(148, 163, 184, 0.38) !important;
        border-radius: 12px !important;
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
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# 페이지 정의
# ============================================================
home_page = st.Page(
    page=str(BASE_DIR / "pages" / "home.py"),
    title="홈",
    icon="🏠",
    url_path="home",
    default=True,
)

prelaunch_page = st.Page(
    page=str(BASE_DIR / "pages" / "prelaunch_checklist.py"),
    title="출시 전 체크리스트",
    icon="🧭",
    url_path="prelaunch_checklist",
)

postlaunch_page = st.Page(
    page=str(BASE_DIR / "pages" / "postlaunch_report.py"),
    title="출시 후 패치·운영 제안",
    icon="🛠️",
    url_path="postlaunch_report",
)

# ============================================================
# 네비게이션 구성
# ============================================================
pg = st.navigation(
    [home_page, prelaunch_page, postlaunch_page],
    position="hidden",
)

# ============================================================
# 공통 사이드바
# ============================================================
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-logo">🎮</div>
            <div class="sidebar-brand-title">Steam<br>인디게임 <br>출시 전략 도우미</div>
            <div class="sidebar-brand-caption">
                리뷰 데이터를 바탕으로<br>
                출시 전 점검과 출시 후 운영 판단을 돕습니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sidebar-menu-label">Menu</div>', unsafe_allow_html=True)
    st.page_link(home_page, label="홈", icon="🏠")
    st.page_link(prelaunch_page, label="출시 전 체크리스트", icon="🧾")
    st.page_link(postlaunch_page, label="출시 후 패치·운영 제안", icon="🛠️")

    st.markdown(
        '<div class="sidebar-footer">Indie Dev Strategy Assistant<br>v0.13.1</div>',
        unsafe_allow_html=True,
    )

# ============================================================
# 선택된 페이지 실행
# ============================================================
pg.run()
