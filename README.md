# Steam 인디게임 시장 분석

> Steam 인디게임 15,406개를 분석해 '발견의 장벽'을 데이터로 진단하고,  
> 인디 개발자의 출시 전략 수립과 출시 후 운영 개선을 지원하는 프로젝트

**[Streamlit 대시보드 바로가기](https://steam-indie-streamlit-408101610132.asia-northeast3.run.app/)**

---

## 분석 배경

Steam Direct 도입 이후 누구나 게임을 출시할 수 있게 됐지만, 출시된 인디게임의 43%는 Steam 공식 등급을 받기 위한 최소 임계값인 리뷰 10개조차 넘지 못한다.

이 프로젝트는 다음 질문에 답한다.

- 무반응(리뷰 0~9개) 게임과 첫 반응(리뷰 10~49개) 게임은 **장르·가격·태그·언어 지원** 측면에서 무엇이 달랐는가?
- 초기 유저 반응을 이끄는 조건을 데이터로 찾아 인디 개발자가 출시 전 의사결정에 활용할 수 있는 가이드를 제공할 수 있는가?

---

## 분석 흐름

```
[데이터 수집 및 전처리]
  SteamSpy / Steam Store / Steam Review API
        ↓
[Part 1. 시장현황]
  연도별 출시 추이 · 장르·태그·가격 분포 · 성과 등급 분포
        ↓
[Part 2. 무관심의 장벽]
  무반응 그룹(리뷰 0~9개)의 장르·가격·태그·언어 지원 패턴 분석
        ↓
[Part 3. 반응을 얻은 게임]
  첫 반응군(리뷰 10~49개) vs 무반응군 비교 · 반응 확보 조건 탐색
        ↓
[Part 4. LLM 리뷰 분석]
  초기 리뷰를 카테고리별로 분류해 출시 전후 의사결정 지원
```

---

## 레포지토리 구조

```
game-analysis/
├── src/
│   ├── collect/                     # 데이터 수집 스크립트
│   └── notebooks/                   # 분석 노트북 (번호 순 실행)
│       ├── 00_preprocessing.ipynb
│       ├── 01_stratified_sampling.ipynb
│       ├── 02_preprocess_reviews.ipynb
│       ├── 03_performance_grade.ipynb
│       ├── 04_yearly_release_trend.ipynb       # Part 1 시작
│       ├── 05_full_genre_distribution.ipynb
│       ├── 06_genre_market_size.ipynb
│       ├── 07_tag_distribution.ipynb
│       ├── 08_price_distribution.ipynb
│       ├── 09_silence_genre_distribution.ipynb # Part 2 시작
│       ├── 10_language_support_distribution.ipynb
│       ├── 11_tag_statistical_verification.ipynb
│       ├── 12_initial_satisfaction_determinants.ipynb # Part 3 시작
│       ├── 13_review_count_determinants.ipynb
│       ├── 14_genre_price_response_matrix.ipynb
│       ├── 15_trust_signal_analysis.ipynb
│       └── llm/                                # Part 4 LLM 분석
│           ├── 01_preprocess_reviews_final.ipynb
│           ├── 02_run_llm_allgames_analysis_final.ipynb
│           ├── 02-1_llm_sentiment_allgames_PreLaunch_report_final.ipynb
│           ├── 02-2_prelaunch_checklist_llm_generate_final.ipynb
│           ├── 03_run_llm_postlaunch_analysis_final.ipynb
│           ├── 03-1_postlaunch_llm_preprocess_with_total_final.ipynb
│           └── 03-2_postlaunch_patch_ops_llm_generate_final.ipynb
├── streamlit/                       # Streamlit 대시보드
│   ├── main.py
│   ├── pages/
│   │   ├── home.py
│   │   ├── prelaunch_checklist.py   # 출시 전 전략 가이드
│   │   └── postlaunch_report.py     # 출시 후 리뷰 분석 리포트
│   └── utils/
├── data/
│   ├── raw/                         # 원본 수집 데이터 (수정 금지)
│   └── preprocessed/                # 전처리 완료 데이터
├── docs/
│   └── erd.md                       # 데이터베이스 ERD
├── _context/                        # 프로젝트 가이드 문서
└── pyproject.toml
```

---

## 데이터 소스

| API | 수집 내용 | 인증 |
|---|---|---|
| SteamSpy API | 인디게임 목록, 태그, 소유자 수, 플레이타임 | 불필요 |
| Steam Store API | 장르, 카테고리, 가격, 출시일, 언어 지원 | 불필요 |
| Steam Review API | 리뷰 텍스트, 긍정/부정, 타임스탬프 | 불필요 |

- **분석 대상:** 2023~2025년 출시 Indie 태그 게임 (Early Access·F2P 제외)
- **전체 표본:** 15,406개
- **리뷰 분석 표본:** 장르 × 리뷰 신뢰도 층화 추출 200개

### 데이터 다운로드

분석에 사용된 CSV 파일은 아래 Google Drive에서 받을 수 있다.  
다운로드한 파일은 `data/raw/` 폴더에 위치시킨 뒤 노트북을 실행한다.

**[Google Drive 데이터 다운로드](https://drive.google.com/drive/folders/1v6ufW8Kks5MOc4QjC_yzFvm2PHy3Z5DG?usp=drive_link)**

| 파일 | 설명 | 출처 |
|---|---|---|
| `steamspy_indie_games.csv` | 인디게임 목록, 소유자 수, 리뷰 수, 가격, 태그 | SteamSpy API |
| `steam_app_details.csv` | 게임 상세 정보 (장르, 카테고리, 언어 지원, 출시일 등) | Steam Store API |
| `steam_indie_tags.csv` | 게임별 태그 및 투표 수 | SteamSpy API |
| `steam_indie_reviews.csv` | 리뷰 원문, 긍정/부정 여부, 작성일 | Steam Review API |
| `steam_indie_review_summary.csv` | 게임별 리뷰 요약 통계 (review_score 등) | Steam Review API |
| `steam_indie_review_histogram.csv` | 게임별 월별·일별 리뷰 집계 | Steam Review API |

---

## 환경 설정

```bash
# Python 3.12 가상환경 생성 및 의존성 설치
uv sync

# 가상환경 활성화
source .venv/bin/activate
```

`.env.local` 파일에 DB 접속 정보를 설정한다.

```
DATABASE_URL=your_database_url
```

---

## 실행 방법

### 노트북

`src/notebooks/` 하위 노트북을 번호 순서대로 실행한다.

```
00 → 01 → 02 → 03 (전처리·기반)
04 → 05 → 06 → 07 → 08 (Part 1. 시장현황)
09 → 10 → 11 (Part 2. 무관심의 장벽)
12 → 13 → 14 → 15 (Part 3. 반응을 얻은 게임)
llm/01 → llm/02 → llm/02-1 → llm/02-2 → llm/03 → llm/03-1 → llm/03-2 (Part 4. LLM 분석)
```

> `data/raw/`에 원본 데이터가 있어야 `00_preprocessing.ipynb`부터 실행 가능하다.

### Streamlit 대시보드

```bash
streamlit run streamlit/main.py
```

로컬 실행 후 `http://localhost:8501`에서 확인한다.

---

## 기술 스택

| 구분 | 도구 |
|---|---|
| 언어 | Python 3.12 |
| 데이터 수집 | requests, python-dotenv |
| 데이터 처리 | pandas, numpy |
| 분석·통계 | scikit-learn, scipy, statsmodels |
| LLM 분석 | pydantic-ai |
| 시각화 | plotly, seaborn |
| 대시보드 | Streamlit |
| 환경 관리 | uv |
