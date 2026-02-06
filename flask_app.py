"""
flask_app.py - PythonAnywhere용 Telegram Bot (Webhook 방식)

PythonAnywhere 무료 티어에서 24/7 동작.
Telegram이 메시지를 직접 이 웹앱으로 보내주므로 상시 프로세스 불필요.

PythonAnywhere 설정:
  1. Web App → Add a new web app → Flask → Python 3.10
  2. Source code: /home/yourusername/telegram-bot/flask_app.py
  3. WSGI 설정 파일에서 경로 수정
"""
import os
import sys
import json
import logging
from datetime import datetime

from flask import Flask, request, jsonify
import httpx

# 프로젝트 경로 추가
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_dir, '.env'))

from market_core import (
    fetch_market_data,
    compute_risk_signal,
    calculate_pair_trading_signals,
    clear_cache,
)

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "my-secret-token-change-this")

AUTHORIZED_USERS = set()
_raw = os.getenv("AUTHORIZED_USERS", "")
for uid in _raw.split(","):
    uid = uid.strip()
    if uid.isdigit():
        AUTHORIZED_USERS.add(int(uid))

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("TelegramBot")

app = Flask(__name__)


# ──────────────────────────────────────────────
# Telegram API 헬퍼 (동기 - Flask에서 사용)
# ──────────────────────────────────────────────
def send_message(chat_id: int, text: str, parse_mode: str = "Markdown"):
    """메시지 전송 (4096자 제한 자동 분할)"""
    MAX_LEN = 4000
    parts = []
    while text:
        if len(text) <= MAX_LEN:
            parts.append(text)
            break
        idx = text.rfind("\n", 0, MAX_LEN)
        if idx == -1:
            idx = MAX_LEN
        parts.append(text[:idx])
        text = text[idx:].lstrip("\n")

    for part in parts:
        try:
            resp = httpx.post(
                f"{API_BASE}/sendMessage",
                json={"chat_id": chat_id, "text": part, "parse_mode": parse_mode},
                timeout=15,
            )
            if not resp.json().get("ok"):
                logger.error("sendMessage error: %s", resp.json())
        except Exception as e:
            logger.error("sendMessage exception: %s", e)


# ──────────────────────────────────────────────
# 보안: 인증 체크
# ──────────────────────────────────────────────
def is_authorized(user_id: int, user_name: str = "") -> bool:
    if not AUTHORIZED_USERS:
        AUTHORIZED_USERS.add(user_id)
        logger.warning("첫 사용자 자동 등록: %s (ID: %d)", user_name, user_id)
    if user_id not in AUTHORIZED_USERS:
        logger.warning("미인증 접근 시도: %s (ID: %d)", user_name, user_id)
        return False
    return True


# ──────────────────────────────────────────────
# 명령어 핸들러
# ──────────────────────────────────────────────
def cmd_start(chat_id, user):
    first_name = user.get("first_name", "사용자")
    send_message(chat_id,
        f"\U0001f4ca *Economic Indicators Bot*\n\n"
        f"안녕하세요, {first_name}님!\n"
        f"클라우드에서 24/7 운영 중입니다.\n\n"
        f"*사용 가능한 명령어:*\n"
        f"/risk - \U0001f6a8 위험 신호등 (리스크 점수)\n"
        f"/market - \U0001f4c8 실시간 시장 데이터\n"
        f"/pairs - \U0001f4b1 페어 트레이딩 신호\n"
        f"/summary - \U0001f4cb 전체 요약 리포트\n"
        f"/refresh - \U0001f504 데이터 새로고침\n"
        f"/id - \U0001f194 내 User ID 확인\n"
        f"/help - \u2753 도움말\n"
    )


def cmd_help(chat_id, user):
    send_message(chat_id,
        "*\U0001f4d6 명령어 안내*\n\n"
        "`/risk` - 위험 신호등과 기여 요인\n"
        "`/market` - 12개 지수 실시간 현황\n"
        "`/pairs` - 4개 페어 트레이딩 신호 (5단계)\n"
        "`/summary` - 위험 + 시장 + 페어 전체 요약\n"
        "`/refresh` - 캐시 초기화 후 새 데이터\n"
        "`/id` - 텔레그램 User ID 확인\n\n"
        "*\U0001f512 보안*\n"
        "인증된 사용자만 사용 가능합니다."
    )


def cmd_id(chat_id, user):
    uid = user.get("id", "?")
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    send_message(chat_id,
        f"\U0001f194 *User ID:* `{uid}`\n"
        f"\U0001f464 *이름:* {full_name}")


def cmd_risk(chat_id, user):
    send_message(chat_id, "\u23f3 데이터를 가져오는 중...")
    try:
        data = fetch_market_data()
        risk = compute_risk_signal(data)
        lines = [
            f"\U0001f6a8 *위험 신호등*", "",
            f"{risk['emoji']} 수준: *{risk['level']}* (점수: {risk['score']})", "",
        ]
        if risk['factors']:
            lines.append("*기여 요인:*")
            for f in risk['factors']:
                lines.append(f"  \u2022 {f}")
        else:
            lines.append("_특이 요인 없음_")
        lines.append(f"\n\U0001f552 {datetime.now().strftime('%H:%M:%S')}")
        send_message(chat_id, "\n".join(lines))
    except Exception as e:
        logger.error("cmd_risk error: %s", e)
        send_message(chat_id, f"\u274c 오류: {e}")


def cmd_market(chat_id, user):
    send_message(chat_id, "\u23f3 시장 데이터를 가져오는 중...")
    try:
        data = fetch_market_data()
        lines = [f"\U0001f4c8 *실시간 시장 현황*", ""]
        for item in data:
            chg = item['change_pct']
            arrow = "\U0001f53c" if chg > 0 else ("\U0001f53d" if chg < 0 else "\u25ab")
            if item['status'] == '상승':
                si = "\U0001f7e2"
            elif item['status'] == '하락':
                si = "\U0001f534"
            else:
                si = "\u26aa"
            lines.append(
                f"{si} *{item['name']}*\n"
                f"   {item['formatted_value']} {arrow} {chg:+.2f}%"
            )
        lines.append(f"\n\U0001f552 {datetime.now().strftime('%H:%M:%S')}")
        send_message(chat_id, "\n".join(lines))
    except Exception as e:
        logger.error("cmd_market error: %s", e)
        send_message(chat_id, f"\u274c 오류: {e}")


def cmd_pairs(chat_id, user):
    send_message(chat_id, "\u23f3 페어 트레이딩 신호를 분석하는 중...")
    try:
        data = fetch_market_data()
        signals = calculate_pair_trading_signals(data)
        lines = [f"\U0001f4b1 *페어 트레이딩 신호 (5단계)*", ""]
        pair_emojis = {
            'gold_silver': '\U0001f4b0', 'vix_bonds_stocks': '\U0001f4ca',
            'usd_jpy': '\U0001f4b4', 'spx_ndx': '\U0001f4c8',
        }
        for key, sig in signals.items():
            emoji = pair_emojis.get(key, '\U0001f4a1')
            lines.append(
                f"{emoji} *{sig['name']}*\n"
                f"   {sig['signal']}\n"
                f"   _{sig['description']}_"
            )
            lines.append("")
        lines.append(f"\U0001f552 {datetime.now().strftime('%H:%M:%S')}")
        send_message(chat_id, "\n".join(lines))
    except Exception as e:
        logger.error("cmd_pairs error: %s", e)
        send_message(chat_id, f"\u274c 오류: {e}")


def cmd_summary(chat_id, user):
    send_message(chat_id, "\u23f3 전체 리포트를 생성하는 중...")
    try:
        data = fetch_market_data()
        risk = compute_risk_signal(data)
        signals = calculate_pair_trading_signals(data)
        lines = [
            f"\U0001f4cb *전체 시장 요약 리포트*",
            f"{'='*30}", "",
            f"\U0001f6a8 *위험 신호등*",
            f"{risk['emoji']} {risk['level']} (점수: {risk['score']})",
        ]
        if risk['factors']:
            for f in risk['factors'][:5]:
                lines.append(f"  \u2022 {f}")
        lines.append("")
        lines.append("*\U0001f4c8 주요 지수*")
        key_indices = ['spx', 'ndx', 'vix', 'btc', 'gold', 'dxy', 'krwusd']
        for item in data:
            if item['id'] in key_indices:
                chg = item['change_pct']
                arrow = "\U0001f53c" if chg > 0 else ("\U0001f53d" if chg < 0 else "\u25ab")
                lines.append(f"  {item['name']}: {item['formatted_value']} {arrow}{chg:+.2f}%")
        lines.append("")
        lines.append("*\U0001f4b1 페어 트레이딩*")
        for sig in signals.values():
            lines.append(f"  {sig['name']}: {sig['signal']}")
        lines.append("")
        lines.append(f"\U0001f552 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        send_message(chat_id, "\n".join(lines))
    except Exception as e:
        logger.error("cmd_summary error: %s", e)
        send_message(chat_id, f"\u274c 오류: {e}")


def cmd_refresh(chat_id, user):
    clear_cache()
    send_message(chat_id,
        "\U0001f504 캐시를 초기화했습니다. 다음 명령에서 최신 데이터를 가져옵니다.")


COMMANDS = {
    '/start': cmd_start, '/help': cmd_help, '/id': cmd_id,
    '/risk': cmd_risk, '/market': cmd_market, '/pairs': cmd_pairs,
    '/summary': cmd_summary, '/refresh': cmd_refresh,
}


# ──────────────────────────────────────────────
# Flask 라우트
# ──────────────────────────────────────────────
@app.route(f"/webhook/{WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    """Telegram Webhook 수신 엔드포인트"""
    update = request.get_json(force=True)

    msg = update.get("message")
    if not msg:
        return jsonify({"ok": True})

    text = msg.get("text", "")
    chat_id = msg["chat"]["id"]
    user = msg.get("from", {})
    user_id = user.get("id", 0)
    user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()

    if not text.startswith("/"):
        return jsonify({"ok": True})

    if not is_authorized(user_id, user_name):
        send_message(chat_id,
            f"\u26d4 접근 권한이 없습니다.\n"
            f"당신의 User ID: `{user_id}`\n"
            f"관리자에게 이 ID를 전달하세요.")
        return jsonify({"ok": True})

    parts = text.split(None, 1)
    cmd = parts[0].split("@")[0].lower()

    handler = COMMANDS.get(cmd)
    if handler:
        handler(chat_id, user)
    else:
        send_message(chat_id, "\u2753 알 수 없는 명령어입니다. `/help`를 입력하세요.")

    return jsonify({"ok": True})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "bot": "chummul_bot", "time": datetime.now().isoformat()})


# ──────────────────────────────────────────────
# Webhook 설정 스크립트 (직접 실행 시)
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "set-webhook":
        # 사용법: python flask_app.py set-webhook https://yourusername.pythonanywhere.com
        if len(sys.argv) < 3:
            print("Usage: python flask_app.py set-webhook https://yourusername.pythonanywhere.com")
            sys.exit(1)

        base_url = sys.argv[2].rstrip("/")
        webhook_url = f"{base_url}/webhook/{WEBHOOK_SECRET}"
        resp = httpx.post(
            f"{API_BASE}/setWebhook",
            json={"url": webhook_url},
            timeout=15,
        )
        result = resp.json()
        print(f"setWebhook: {result}")
        if result.get("ok"):
            print(f"Webhook set to: {webhook_url}")
            print("Bot is now running via webhook!")
        else:
            print("Failed to set webhook.")

    elif len(sys.argv) > 1 and sys.argv[1] == "delete-webhook":
        resp = httpx.post(f"{API_BASE}/deleteWebhook", timeout=15)
        print(f"deleteWebhook: {resp.json()}")
        print("Webhook removed. You can now use long-polling mode (telegram_bot.py).")

    else:
        print("Local dev server (use Ctrl+C to stop)")
        app.run(debug=True, port=5000)
