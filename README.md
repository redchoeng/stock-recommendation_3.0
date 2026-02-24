# AI Stock Discovery Engine (AI 종목 발굴 엔진)

## 프로젝트 개요

3가지 핵심 엔진으로 구성된 미국 주식 종목 발굴 시스템

| 엔진 | 역할 | 핵심 기술 |
|------|------|-----------|
| **Engine 1** | 퀀트 필터링 (돈의 흐름 추적) | Python + pandas + yfinance |
| **Engine 2** | 매크로 & 헷지 (시장 방어) | FRED API + 룰 기반 알고리즘 |
| **Engine 3** | NLP 실체 검증 (허마주 걸러치기) | 로컬 LLM (Ollama) + SEC Edgar |

---

## 디렉토리 구조

```
stock-recommendation_3.0/
│
├── config/
│   ├── settings.yaml              # 전역 설정 (API 키, 임계값 등)
│   ├── watchlist.yaml             # 감시 종목 리스트
│   └── alert_rules.yaml           # 알림 규칙 설정
│
├── engine1_quant/                 # 퀀트 필터링 엔진
│   ├── __init__.py
│   ├── volume_analyzer.py         # 거래대금 폭증 감지
│   ├── peak_detector.py           # 고점 경고 (이동평균선 이탈)
│   └── neglected_scanner.py       # 소외주 스캐너
│
├── engine2_macro/                 # 매크로 & 헷지 엔진
│   ├── __init__.py
│   ├── macro_fetcher.py           # FRED API (CPI, 실업률, VIX)
│   ├── risk_scorer.py             # 시장 리스크 점수 산출
│   └── hedge_allocator.py         # 방어주 스위칭 룰 엔진
│
├── engine3_nlp/                   # NLP 실체 검증 엔진
│   ├── __init__.py
│   ├── sec_scraper.py             # SEC Edgar 10-K/10-Q 수집
│   ├── llm_analyzer.py            # 로컬 LLM 분석 (Ollama)
│   └── prompts/
│       └── substance_check.txt    # 실체 검증 프롬프트
│
├── pipeline/                      # 통합 파이프라인
│   ├── __init__.py
│   └── orchestrator.py            # 3개 엔진 통합 실행
│
├── alerts/                        # 알림 시스템
│   ├── __init__.py
│   └── notifier.py                # 알림 발송 (Slack/Telegram)
│
├── storage/                       # 데이터 저장
│   ├── __init__.py
│   ├── db.py                      # SQLite/PostgreSQL 연동
│   └── models.py                  # DB 스키마 (SQLAlchemy)
│
├── dashboard/                     # 대시보드
│   ├── app.py                     # Streamlit 대시보드
│   └── pages/
│
├── tests/                         # 테스트
├── scripts/                       # 유틸리티 스크립트
├── data/reports/                  # 리포트 저장
│
├── requirements.txt
├── docker-compose.yaml
├── .env.example
└── README.md
```

---

## Engine 1: 퀀트 필터링

### 핵심 지표
```
거래대금 = 종가(Close) × 거래량(Volume)
```

### 3가지 필터

- **Filter 1-A**: 거래대금 폭증 감지 — 과거 1년 평균 대비 N배 이상 급증
- **Filter 1-B**: 고점 경고 — 52주 고점 부근 + 거래대금 이동평균 하향 이탈
- **Filter 1-C**: 소외주 스캐너 — 시총 상위 대형주 중 거래대금 지속 하락

---

## Engine 2: 매크로 & 헷지

### 데이터 소스
| 지표 | API | 업데이트 주기 |
|------|-----|-------------|
| CPI (물가지수) | FRED `CPIAUCSL` | 월간 |
| 실업률 | FRED `UNRATE` | 월간 |
| VIX (변동성) | yfinance `^VIX` | 실시간 |
| 10Y 국채금리 | FRED `DGS10` | 일간 |

### 리스크 점수 → 방어 모드 트리거 시 방어주 스위칭

---

## Engine 3: NLP 실체 검증 (로컬 LLM)

### 아키텍처
```
SEC Edgar / Earnings Call → 텍스트 수집 → Ollama 로컬 LLM → 키워드 스코어링 → 종합 점수
```

### 로컬 LLM 설정 (Ollama)
```bash
ollama pull llama3.1:8b        # 범용 (8GB VRAM)
ollama pull deepseek-r1:8b     # 추론 특화
ollama pull mistral:7b          # 경량 & 빠름
```

---

## 통합 스코어링

| 엔진 | 가중치 |
|------|--------|
| Engine 1 (퀀트) | 30% |
| Engine 2 (매크로) | 20% |
| Engine 3 (NLP) | 50% |

시그널: STRONG_BUY / BUY / HOLD / SELL / AVOID

---

## 빠른 시작

```bash
# 1. 클론 & 환경 설정
git clone https://github.com/redchoeng/stock-recommendation_3.0.git
cd stock-recommendation_3.0
pip install -r requirements.txt
cp .env.example .env  # API 키 설정

# 2. Ollama 설치 & 모델 다운로드
bash scripts/setup_ollama.sh

# 3. 첫 실행
python -m pipeline.orchestrator --mode full

# 4. 대시보드 실행
streamlit run dashboard/app.py
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 언어 | Python 3.11+ |
| 데이터 수집 | yfinance, fredapi, requests, SEC Edgar API |
| 데이터 처리 | pandas, numpy, scipy |
| 로컬 LLM | Ollama (llama3.1 / deepseek-r1 / mistral) |
| DB | SQLite (개발) → PostgreSQL (운영) |
| 대시보드 | Streamlit |
| 알림 | Slack Webhook / Telegram Bot API |
| 컨테이너 | Docker Compose |
