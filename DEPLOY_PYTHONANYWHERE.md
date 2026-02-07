# PythonAnywhere 배포 가이드

PC를 끄고도 Telegram 봇이 24/7 동작하도록 PythonAnywhere에 배포합니다.

## 1단계: PythonAnywhere 가입

1. https://www.pythonanywhere.com 접속
2. "Start running Python online" → 무료 계정 생성
3. 사용자명을 기억하세요 (예: `nakcho`)

## 2단계: 파일 업로드

PythonAnywhere 대시보드에서:

1. **Files** 탭 클릭
2. `/home/사용자명/` 경로에서 **New directory** → `telegram-bot` 생성
3. `/home/사용자명/telegram-bot/` 에 아래 파일들을 업로드:
   - `flask_app.py`
   - `market_core.py`
   - `.env`
   - `requirements.txt`

또는 **Bash console** 열어서 git clone:
```bash
cd ~
git clone https://github.com/waterfirst/Economic_Indicators_Dashboard.git telegram-bot
cd telegram-bot
```

## 3단계: 패키지 설치

**Bash console**에서:
```bash
pip3 install --user httpx python-dotenv yfinance flask beautifulsoup4 lxml requests
```

## 4단계: .env 파일 생성

```bash
cd ~/telegram-bot
nano .env
```

아래 내용 입력 (Ctrl+O 저장, Ctrl+X 종료):
```
TELEGRAM_BOT_TOKEN=8038365174:AAGtednZFGtbj8YjDOoe1i_rOrk4EuxzrB4
AUTHORIZED_USERS=5767743818
WEBHOOK_SECRET=my-secret-token-change-this
ALERT_INTERVAL=3600
```

**중요**: `WEBHOOK_SECRET`을 추측 불가능한 값으로 변경하세요!

## 5단계: Web App 생성

1. **Web** 탭 → **Add a new web app**
2. "Next" → **Flask** 선택 → **Python 3.10** 선택
3. Flask app 경로: `/home/사용자명/telegram-bot/flask_app.py`

## 6단계: WSGI 설정

**Web** 탭에서 **WSGI configuration file** 링크 클릭.
내용을 아래로 교체:

```python
import sys
import os

project_dir = '/home/사용자명/telegram-bot'
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

os.chdir(project_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_dir, '.env'))

from flask_app import app as application
```

**`사용자명`을 실제 PythonAnywhere 사용자명으로 변경하세요!**

저장 후 **Web** 탭에서 **Reload** 버튼 클릭.

## 7단계: Webhook 설정

**Bash console**에서:
```bash
cd ~/telegram-bot
python3 flask_app.py set-webhook https://사용자명.pythonanywhere.com
```

성공하면 `Webhook set to: ...` 메시지가 나옵니다.

## 8단계: 테스트

모바일 텔레그램에서 @chummul_bot에게 `/start` 전송!

## 문제 해결

### 응답이 안 올 때
- **Web** 탭 → **Error log** 확인
- **Reload** 버튼 클릭 후 재시도

### PC에서 다시 사용하고 싶을 때
Webhook을 삭제하고 long-polling으로 전환:
```bash
python flask_app.py delete-webhook
python telegram_bot.py
```

### yfinance가 안 될 때
PythonAnywhere 무료 티어는 외부 HTTP 연결이 화이트리스트 기반입니다.
api.telegram.org은 허용되지만, Yahoo Finance API가 차단될 수 있습니다.
이 경우 유료($5/월) 업그레이드가 필요합니다.
