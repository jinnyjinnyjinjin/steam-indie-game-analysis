# Steam 인디게임 분석 Streamlit 앱

Steam 인디게임 리뷰 분석 결과를 바탕으로, 인디게임 개발자가 출시 전 점검 항목과 출시 후 패치·운영 방향을 빠르게 확인할 수 있도록 만든 Streamlit 앱입니다.

## 앱에서 제공하는 기능

| 메뉴 | 역할 |
| --- | --- |
| 홈 | 앱의 목적, 사용 흐름, 주의사항 안내 |
| 출시 전 체크리스트 | 장르·가격대·Steam 태그·플레이 방식을 입력해 출시 전 점검 항목 생성 |
| 출시 후 패치·운영 | 선택 게임의 리뷰 이슈를 바탕으로 패치·운영 방향 생성 |

## 중요한 안내

이 앱은 Steam 리뷰를 실시간으로 수집하는 앱이 아닙니다.  
사전에 전처리·LLM 분류·근거 집계가 완료된 CSV 파일을 불러와, 사용자가 보기 쉬운 체크리스트와 패치·운영 제안으로 정리합니다.

또한 결과는 성공 예측이나 정답이 아니라, 개발자가 빠르게 검토할 수 있는 의사결정 보조 자료입니다.

## 폴더 구조

```text
streamlit_app/
├── main.py
├── pages/
│   ├── home.py
│   ├── prelaunch_checklist.py
│   └── postlaunch_report.py
└── utils/
    ├── __init__.py
    ├── prelaunch_engine.py
    └── postlaunch_engine.py
```

## 필요한 데이터 경로

### 출시 전 체크리스트

```text
data/outputs/prelaunch/master/prelaunch_checklist_data/
├── prelaunch_game_base.csv
├── prelaunch_issue_repeat_summary.csv
├── prelaunch_condition_issue_summary.csv
└── prelaunch_checklist_evidence_base.csv
```

### 출시 후 패치·운영

```text
data/outputs/postlaunch/master/postlaunch_preprocess_data/
├── postlaunch_review_base.csv
├── postlaunch_issue_summary.csv
├── postlaunch_patch_ops_evidence_base.csv
└── tableau_postlaunch_patch_ops_source.csv
```

## LLM 사용 설정

LLM 생성 기능을 사용하려면 환경변수 또는 `.streamlit/secrets.toml`에 Gemini API 키를 설정해야 합니다.

권장 환경변수 예시는 다음과 같습니다.

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-3.1-flash-lite
```

Streamlit secrets를 사용할 경우:

```toml
GEMINI_API_KEY = "your_api_key_here"
GEMINI_MODEL = "gemini-3.1-flash-lite"
```

## 실행 방법

프로젝트 루트에서 실행합니다.

```bash
streamlit run streamlit_app/main.py
```

또는 `streamlit_app` 폴더로 이동한 뒤 실행합니다.

```bash
cd streamlit_app
streamlit run main.py
```

## 제출/공유 시 주의사항

다음 파일은 GitHub나 제출 ZIP에 포함하지 않습니다.

```text
.env
.streamlit/secrets.toml
__pycache__/
*.pyc
```

API 키, DB 접속 문자열, 개인 환경 경로는 README에 직접 적지 않습니다.
