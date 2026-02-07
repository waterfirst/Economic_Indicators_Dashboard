# Economic Indicators Dashboard + Telegram Bot

실시간 경제 지표 대시보드 (Streamlit) + 모바일 텔레그램 봇으로 어디서든 시장 상황을 모니터링합니다.

**Streamlit 대시보드**: https://us-civil-war.streamlit.app/

**Telegram Bot**: [@chummul_bot](https://t.me/chummul_bot)

---

## 주요 기능

### Streamlit 대시보드
- 12개 핵심 지수 실시간 모니터링 (Gold, Silver, Copper, DXY, US10Y, BTC, KRW/USD, USD/JPY, KRW/JPY, S&P500, NASDAQ100, VIX)
- 위험 신호등 (리스크 점수 기반 녹/황/적)
- 4개 페어 트레이딩 신호 (5단계)
- Google Gemini AI 정성 분석

### Telegram Bot
- 모바일에서 명령어 하나로 시장 현황 확인
- PC 또는 클라우드(PythonAnywhere)에서 24/7 운영
- 인증된 사용자만 접근 가능 (User ID 기반 보안)

| 명령어 | 설명 |
|---|---|
| `/start` | 시작 / 도움말 |
| `/risk` | 위험 신호등 (리스크 점수 + 기여 요인) |
| `/market` | 12개 지수 실시간 현황 |
| `/pairs` | 4개 페어 트레이딩 신호 (5단계) |
| `/summary` | 전체 요약 리포트 |
| `/news` | 경제 뉴스 TOP 10 |
| `/ai` | AI 뉴스 TOP 10 |
| `/refresh` | 데이터 캐시 초기화 |
| `/alert on/off` | 정기 알림 설정 (PC 모드만) |
| `/id` | 내 Telegram User ID 확인 |

---

## 프로젝트 구조

```
├── streamlit_dashboard.py   # Streamlit 웹 대시보드
├── market_core.py           # 순수 Python 시장 데이터 로직 (공용 모듈)
├── telegram_bot.py          # Telegram 봇 - Long Polling (PC용)
├── flask_app.py             # Telegram 봇 - Webhook (클라우드용)
├── requirements.txt         # Python 의존성
├── .env.example             # 환경변수 템플릿
├── .gitignore               # Git 제외 파일
├── TELEGRAM_SETUP.md        # PC에서 봇 실행 가이드
└── DEPLOY_PYTHONANYWHERE.md # PythonAnywhere 클라우드 배포 가이드
```

### 아키텍처

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  모바일 텔레그램  │ ──→ │  Telegram Server  │ ──→ │  봇 서버 (PC or  │
│  /risk, /market  │ ←── │                  │ ←── │  PythonAnywhere) │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                                   market_core.py
                                                          │
                                                   Yahoo Finance API
```

**두 가지 운영 모드:**

| 모드 | 파일 | PC 필요? | 방식 |
|---|---|---|---|
| PC 모드 | `telegram_bot.py` | O (PC 켜야 함) | Long Polling |
| 클라우드 모드 | `flask_app.py` | X (24/7 동작) | Webhook |

---

## 빠른 시작

### 1. 환경 설정

```bash
git clone https://github.com/waterfirst/Economic_Indicators_Dashboard.git
cd Economic_Indicators_Dashboard
pip install -r requirements.txt
```

### 2. Telegram 봇 토큰 발급

1. 텔레그램에서 [@BotFather](https://t.me/BotFather) 에게 `/newbot` 전송
2. 봇 이름, username 입력
3. 발급된 토큰 복사

### 3. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일 편집:
```env
TELEGRAM_BOT_TOKEN=여기에_봇_토큰_입력
AUTHORIZED_USERS=여기에_텔레그램_유저ID_입력
WEBHOOK_SECRET=추측불가능한_비밀값
ALERT_INTERVAL=3600
```

> User ID는 봇에게 `/id` 명령으로 확인 가능합니다.
> AUTHORIZED_USERS를 비워두면 첫 사용자가 자동 등록됩니다.

### 4-A. PC에서 실행 (Long Polling)

```bash
python telegram_bot.py
```

PC가 켜져 있는 동안 봇이 동작합니다. `Ctrl+C`로 종료.

### 4-B. PythonAnywhere 클라우드 배포 (Webhook)

PC 없이 24/7 운영하려면 → [DEPLOY_PYTHONANYWHERE.md](DEPLOY_PYTHONANYWHERE.md) 참조

요약:
1. [pythonanywhere.com](https://www.pythonanywhere.com) 무료 가입
2. 파일 업로드 (`flask_app.py`, `market_core.py`, `.env`)
3. Flask Web App 생성 + WSGI 설정
4. `python3 flask_app.py set-webhook https://사용자명.pythonanywhere.com`
5. 모바일에서 `/start` → 완료!

---

## Streamlit 대시보드

```bash
streamlit run streamlit_dashboard.py
```

http://localhost:8501 에서 접속. 또는 배포된 앱: https://us-civil-war.streamlit.app/

- Gemini API 키: 사이드바에서 입력 또는 Streamlit Secrets에 `google_api_key` 설정
- 모델 선택: `gemini-1.5-flash` (기본), `gemini-1.5-pro` 등

---

## 모니터링 지표

| 지표 | 심볼 | 설명 |
|---|---|---|
| Gold | `GC=F` | 금 선물 (안전자산) |
| Silver | `SI=F` | 은 선물 |
| Copper | `HG=F` | 구리 선물 (경기 선행지표) |
| DXY | `DX-Y.NYB` | 달러 인덱스 |
| US10Y | `^TNX` | 미 10년물 국채 금리 |
| BTC | `BTC-USD` | 비트코인 |
| KRW/JPY | `KRWJPY=X` | 원-엔 환율 |
| USD/KRW | `KRW=X` | 원-달러 환율 |
| USD/JPY | `JPY=X` | 달러-엔 환율 |
| S&P 500 | `^GSPC` | S&P 500 지수 |
| NASDAQ 100 | `^NDX` | 나스닥 100 지수 |
| VIX | `^VIX` | 변동성 지수 (공포 지수) |

---

## 보안

- **User ID 인증**: `.env`의 `AUTHORIZED_USERS`에 등록된 사용자만 봇 사용 가능
- **미인증 접근 차단**: 미등록 사용자 접근 시 차단 + 로그 기록
- **봇 토큰 보호**: `.env` 파일은 `.gitignore`에 의해 Git에서 제외
- **Webhook 보안**: URL에 `WEBHOOK_SECRET` 포함으로 외부 호출 방지

---

## 참고

- 데이터는 Yahoo Finance에서 가져오며, 투자 조언이 아닙니다
- PythonAnywhere 무료 티어는 외부 HTTP가 화이트리스트 기반이므로 yfinance가 차단될 수 있습니다 (유료 $5/월 업그레이드 필요할 수 있음)
- 봇 토큰이 노출되었다면 [@BotFather](https://t.me/BotFather)에서 `/revoke`로 즉시 갱신하세요
