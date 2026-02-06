# Telegram Bot 설정 가이드

Windows PC에서 봇을 실행하고, 모바일 텔레그램으로 시장 데이터를 조회하는 워크플로우입니다.

## 아키텍처

```
[모바일 텔레그램] <---> [Telegram 서버] <---> [Windows PC: telegram_bot.py]
                                                      |
                                                [Yahoo Finance API]
```

- Windows PC에서 `telegram_bot.py`가 상시 실행
- 모바일 텔레그램 앱에서 명령어를 보내면 PC가 데이터를 가져와 응답
- 인증된 사용자만 접근 가능

## 설정 단계

### 1단계: 텔레그램 봇 생성 (모바일에서)

1. 텔레그램에서 `@BotFather` 검색
2. `/newbot` 입력
3. 봇 이름 입력 (예: `My Market Bot`)
4. 봇 사용자명 입력 (예: `my_market_indicator_bot`)
5. **Bot Token을 복사** (형식: `1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ`)

### 2단계: User ID 확인

1. 텔레그램에서 `@userinfobot` 검색
2. `/start` 입력
3. **표시되는 ID 번호를 복사** (예: `123456789`)

### 3단계: Windows PC에서 환경 설정

```powershell
# 프로젝트 폴더로 이동
cd Economic_Indicators_Dashboard

# .env 파일 생성
copy .env.example .env

# .env 파일을 메모장으로 열어서 편집
notepad .env
```

`.env` 파일에 아래 내용을 입력:

```
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
AUTHORIZED_USERS=123456789
ALERT_INTERVAL=3600
```

### 4단계: 의존성 설치

```powershell
pip install -r requirements.txt
```

### 5단계: 봇 실행

```powershell
python telegram_bot.py
```

성공하면 아래와 같이 표시됩니다:

```
==================================================
  Economic Indicators - Telegram Bot
==================================================
  Authorized Users: {123456789}
  Alert Interval: 3600s (60min)
==================================================
  Bot is starting... Press Ctrl+C to stop.
```

### 6단계: 모바일에서 테스트

텔레그램 앱에서 생성한 봇을 검색하고 `/start`를 입력합니다.

## 사용 가능한 명령어

| 명령어 | 설명 |
|--------|------|
| `/start` | 시작 및 도움말 |
| `/risk` | 위험 신호등 (리스크 점수) |
| `/market` | 12개 지수 실시간 현황 |
| `/pairs` | 페어 트레이딩 신호 (5단계) |
| `/summary` | 전체 요약 리포트 |
| `/refresh` | 캐시 초기화 후 새 데이터 |
| `/alert on` | 정기 알림 켜기 |
| `/alert off` | 정기 알림 끄기 |
| `/id` | 내 User ID 확인 |

## 보안 기능

- **사용자 인증**: `AUTHORIZED_USERS`에 등록된 ID만 명령 실행 가능
- **미인증 접근 차단**: 미등록 사용자는 자동 차단 및 로그 기록
- **토큰 보호**: `.env` 파일은 `.gitignore`에 포함하여 Git에 업로드되지 않도록 관리

## 백그라운드 실행 (Windows)

### 방법 1: 시작 프로그램에 등록

1. `Win + R` -> `shell:startup` 입력
2. `start_bot.bat` 파일 생성:

```bat
@echo off
cd /d "C:\경로\Economic_Indicators_Dashboard"
python telegram_bot.py
```

### 방법 2: Windows 작업 스케줄러

1. 작업 스케줄러 열기 (taskschd.msc)
2. 기본 작업 만들기
3. 트리거: 로그온할 때
4. 동작: `python telegram_bot.py` 실행

### 방법 3: pythonw (콘솔 창 없이)

```powershell
pythonw telegram_bot.py
```

## 문제 해결

### 봇이 응답하지 않을 때
- `.env` 파일의 `TELEGRAM_BOT_TOKEN`이 올바른지 확인
- 인터넷 연결 확인
- `python telegram_bot.py`를 직접 실행하여 에러 메시지 확인

### "접근 권한이 없습니다" 메시지
- `/id` 명령으로 User ID를 확인
- `.env`의 `AUTHORIZED_USERS`에 해당 ID가 있는지 확인
- 여러 사용자는 쉼표로 구분: `AUTHORIZED_USERS=111,222,333`

### 데이터가 오래된 것 같을 때
- `/refresh` 명령으로 캐시 초기화
- 캐시 TTL은 60초 (자동 갱신)
