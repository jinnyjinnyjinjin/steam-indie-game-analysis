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
# 사이드바 스타일
# ============================================================
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] div[data-testid="stSidebarUserContent"] {
        display: flex;
        flex-direction: column;
        height: 100%;
    }

    .sidebar-footer {
        margin-top: auto;
        padding-top: 1rem;
        color: rgba(250, 250, 250, 0.65);
        font-size: 0.85rem;
    }

    .sidebar-menu-title {
        font-size: 1rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
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
    default=True,
)

prelaunch_page = st.Page(
    page=str(BASE_DIR / "pages" / "prelaunch_checklist.py"),
    title="출시 전 체크리스트",
    icon="🧭",
)

postlaunch_page = st.Page(
    page=str(BASE_DIR / "pages" / "postlaunch_report.py"),
    title="출시 후 패치·운영 제안",
    icon="🛠️",
)

# ============================================================
# 네비게이션 구성
# 기본 Streamlit 네비게이션 UI는 숨기고
# 사이드바를 직접 구성한다.
# ============================================================
pg = st.navigation(
    [home_page, prelaunch_page, postlaunch_page],
    position="hidden",
)

# ============================================================
# 공통 사이드바
# ============================================================
with st.sidebar:
    st.markdown("## 🎮 Steam 인디게임 분석")
    st.caption("개발자를 위한 출시 전/출시 후 의사결정 지원")

    st.divider()

    st.markdown("### 메뉴")
    st.page_link(home_page, label="홈", icon="🏠")
    st.page_link(prelaunch_page, label="출시 전 체크리스트", icon="🧭")
    st.page_link(postlaunch_page, label="출시 후 패치·운영 제안", icon="🛠️")

    st.divider()
    st.markdown('<div class="sidebar-footer">버전 0.11.1</div>', unsafe_allow_html=True)

# ============================================================
# 선택된 페이지 실행
# ============================================================
pg.run()