"""
telegram_bot.py - Economic Indicators Dashboard Telegram Bot (경량 버전)

python-telegram-bot 라이브러리 대신 httpx로 Telegram Bot API를 직접 호출.
외부 의존성 최소화: httpx, python-dotenv만 필요.

사용법:
    python telegram_bot.py

필요 환경변수 (.env 파일 또는 시스템 환경변수):
    TELEGRAM_BOT_TOKEN  - BotFather에서 받은 봇 토큰
    AUTHORIZED_USERS    - 허용된 텔레그램 유저 ID (쉼표 구분)
"""
import os
import sys
import json
import logging
import asyncio
import signal
import time
from datetime import datetime
from dotenv import load_dotenv
import httpx

from market_core import (
    fetch_market_data,
    compute_risk_signal,
    calculate_pair_trading_signals,
    fetch_economy_news,
    fetch_ai_news,
    clear_cache,
)
from visualizer import generate_all_charts

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

AUTHORIZED_USERS = set()
_raw = os.getenv("AUTHORIZED_USERS", "")
for uid in _raw.split(","):
    uid = uid.strip()
    if uid.isdigit():
        AUTHORIZED_USERS.add(int(uid))

ALERT_INTERVAL = int(os.getenv("ALERT_INTERVAL", "1800"))
SIGNAL_CHECK_INTERVAL = 3600

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("TelegramBot")

# 정기 알림 상태 관리
_alert_chats = set()  # 알림이 켜진 chat_id 집합
_running = True


# ──────────────────────────────────────────────
# Telegram API 헬퍼
# ──────────────────────────────────────────────
async def api_call(client: httpx.AsyncClient, method: str, **params):
    """Telegram Bot API 호출"""
    url = f"{API_BASE}/{method}"
    resp = await client.post(url, json=params, timeout=30)
    data = resp.json()
    if not data.get("ok"):
        logger.error("API error [%s]: %s", method, data)
    return data


async def send_message(client: httpx.AsyncClient, chat_id: int, text: str,
                       parse_mode: str = "Markdown"):
    """메시지 전송 (4096자 제한 자동 분할)"""
    MAX_LEN = 4000
    if len(text) <= MAX_LEN:
        return await api_call(client, "sendMessage",
                              chat_id=chat_id, text=text, parse_mode=parse_mode)

    # 긴 메시지 분할
    parts = []
    while text:
        if len(text) <= MAX_LEN:
            parts.append(text)
            break
        # 줄바꿈 기준으로 분할
        idx = text.rfind("\n", 0, MAX_LEN)
        if idx == -1:
            idx = MAX_LEN
        parts.append(text[:idx])
        text = text[idx:].lstrip("\n")

    for part in parts:
        await api_call(client, "sendMessage", chat_id=chat_id, text=part, parse_mode=parse_mode)


async def send_photo(client: httpx.AsyncClient, chat_id: int, photo_path: str, caption: str = None):
    """이미지 전송"""
    url = f"{API_BASE}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            data = {"chat_id": str(chat_id)}
            if caption:
                data["caption"] = caption
                data["parse_mode"] = "Markdown"
            
            resp = await client.post(url, data=data, files=files, timeout=30)
            res = resp.json()
            if not res.get("ok"):
                logger.error("sendPhoto error: %s", res)
            return res
    except Exception as e:
        logger.error("send_photo exception: %s", e)
        return {"ok": False, "description": str(e)}


# ──────────────────────────────────────────────
# 보안: 인증 체크
# ──────────────────────────────────────────────
def is_authorized(user_id: int, user_name: str = "") -> bool:
    """사용자 인증 체크"""
    # AUTHORIZED_USERS가 비어있으면 첫 사용자 자동 등록
    if not AUTHORIZED_USERS:
        AUTHORIZED_USERS.add(user_id)
        logger.warning("AUTHORIZED_USERS 비어있어 첫 사용자 자동 등록: %s (ID: %d)",
                       user_name, user_id)

    if user_id not in AUTHORIZED_USERS:
        logger.warning("미인증 접근 시도: %s (ID: %d)", user_name, user_id)
        return False
    return True


# ──────────────────────────────────────────────
# 명령어 핸들러
# ──────────────────────────────────────────────
async def cmd_start(client, chat_id, user):
    first_name = user.get("first_name", "사용자")
    text = (
        f"\U0001f4ca *Economic Indicators Bot*\n\n"
        f"안녕하세요, {first_name}님!\n"
        f"Windows PC 대시보드에 연결되었습니다.\n\n"
        f"*사용 가능한 명령어:*\n"
        f"/risk - \U0001f6a8 위험 신호등 (리스크 점수)\n"
        f"/market - \U0001f4c8 실시간 시장 데이터\n"
        f"/pairs - \U0001f4b1 페어 트레이딩 신호\n"
        f"/summary - \U0001f4cb 전체 요약 리포트\n"
        f"/news - \U0001f4f0 경제 뉴스 TOP 10\n"
        f"/ai - \U0001f916 AI 뉴스 TOP 10\n"
        f"/chart - \U0001f4ca 시각화 차트 전송\n"
        f"/refresh - \U0001f504 데이터 새로고침\n"
        f"/alert - \u23f0 정기 알림 설정\n"
        f"/id - \U0001f194 내 User ID 확인\n"
        f"/help - \u2753 도움말\n"
    )
    await send_message(client, chat_id, text)


async def cmd_help(client, chat_id, user):
    text = (
        "*\U0001f4d6 명령어 안내*\n\n"
        "`/risk` - 위험 신호등과 기여 요인\n"
        "`/market` - 12개 지수 실시간 현황\n"
        "`/pairs` - 4개 페어 트레이딩 신호 (5단계)\n"
        "`/summary` - 위험 + 시장 + 페어 전체 요약\n"
        "`/news` - 경제 뉴스 TOP 10\n"
        "`/ai` - AI 뉴스 TOP 10\n"
        "`/chart` - 주요 지수 및 리스크 차트 (PNG)\n"
        "`/refresh` - 캐시 초기화 후 새 데이터\n"
        "`/alert on` - 정기 알림 켜기\n"
        "`/alert off` - 정기 알림 끄기\n"
        "`/id` - 텔레그램 User ID 확인\n\n"
        "*\U0001f512 보안*\n"
        "인증된 사용자만 사용 가능합니다.\n"
        "`.env` 파일의 `AUTHORIZED_USERS`에 ID를 등록하세요."
    )
    await send_message(client, chat_id, text)


async def cmd_id(client, chat_id, user):
    uid = user.get("id", "?")
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    await send_message(client, chat_id,
                       f"\U0001f194 *User ID:* `{uid}`\n"
                       f"\U0001f464 *이름:* {full_name}")


async def cmd_risk(client, chat_id, user):
    await send_message(client, chat_id, "\u23f3 데이터를 가져오는 중...")
    try:
        data = fetch_market_data()
        risk = compute_risk_signal(data)

        lines = [
            f"\U0001f6a8 *위험 신호등*",
            f"",
            f"{risk['emoji']} 수준: *{risk['level']}* (점수: {risk['score']})",
            f"",
        ]

        if risk['factors']:
            lines.append("*기여 요인:*")
            for f in risk['factors']:
                lines.append(f"  \u2022 {f}")
        else:
            lines.append("_특이 요인 없음_")

        lines.append(f"\n\U0001f552 {datetime.now().strftime('%H:%M:%S')}")
        await send_message(client, chat_id, "\n".join(lines))
    except Exception as e:
        logger.error("cmd_risk error: %s", e)
        await send_message(client, chat_id, f"\u274c 오류: {e}")


async def cmd_market(client, chat_id, user):
    await send_message(client, chat_id, "\u23f3 시장 데이터를 가져오는 중...")
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
        await send_message(client, chat_id, "\n".join(lines))
    except Exception as e:
        logger.error("cmd_market error: %s", e)
        await send_message(client, chat_id, f"\u274c 오류: {e}")


async def cmd_pairs(client, chat_id, user):
    await send_message(client, chat_id, "\u23f3 페어 트레이딩 신호를 분석하는 중...")
    try:
        data = fetch_market_data()
        signals = calculate_pair_trading_signals(data)

        lines = [f"\U0001f4b1 *페어 트레이딩 신호 (5단계)*", ""]
        pair_emojis = {
            'gold_silver': '\U0001f4b0',
            'vix_bonds_stocks': '\U0001f4ca',
            'usd_jpy': '\U0001f4b4',
            'spx_ndx': '\U0001f4c8',
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
        await send_message(client, chat_id, "\n".join(lines))
    except Exception as e:
        logger.error("cmd_pairs error: %s", e)
        await send_message(client, chat_id, f"\u274c 오류: {e}")


async def cmd_summary(client, chat_id, user):
    await send_message(client, chat_id, "\u23f3 전체 리포트를 생성하는 중...")
    try:
        data = fetch_market_data()
        risk = compute_risk_signal(data)
        signals = calculate_pair_trading_signals(data)

        lines = [
            f"\U0001f4cb *전체 시장 요약 리포트*",
            f"{'='*30}",
            f"",
            f"\U0001f6a8 *위험 신호등*",
            f"{risk['emoji']} {risk['level']} (점수: {risk['score']})",
        ]
        if risk['factors']:
            for f in risk['factors'][:5]:
                lines.append(f"  \u2022 {f}")
            if len(risk['factors']) > 5:
                lines.append(f"  _...외 {len(risk['factors'])-5}개_")
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
        await send_message(client, chat_id, "\n".join(lines))
    except Exception as e:
        logger.error("cmd_summary error: %s", e)
        await send_message(client, chat_id, f"\u274c 오류: {e}")


async def cmd_news(client, chat_id, user):
    await send_message(client, chat_id, "\u23f3 경제 뉴스를 가져오는 중...")
    try:
        news = fetch_economy_news(10)
        if not news:
            await send_message(client, chat_id, "\u274c 뉴스를 가져올 수 없습니다.")
            return
        lines = ["\U0001f4f0 *경제 뉴스 TOP 10*", ""]
        for i, item in enumerate(news, 1):
            lines.append(f"{i}. [{item['title']}]({item['link']})")
        lines.append(f"\n\U0001f552 {datetime.now().strftime('%H:%M:%S')}")
        await send_message(client, chat_id, "\n".join(lines))
    except Exception as e:
        logger.error("cmd_news error: %s", e)
        await send_message(client, chat_id, f"\u274c 오류: {e}")


async def cmd_ai(client, chat_id, user):
    await send_message(client, chat_id, "\u23f3 AI 뉴스를 가져오는 중...")
    try:
        news = fetch_ai_news(10)
        if not news:
            await send_message(client, chat_id, "\u274c AI 뉴스를 가져올 수 없습니다.")
            return
        lines = ["\U0001f916 *AI 뉴스 TOP 10*", ""]
        for i, item in enumerate(news, 1):
            src = f" ({item['source']})" if item.get('source') else ""
            lines.append(f"{i}. [{item['title']}]({item['link']}){src}")
        lines.append(f"\n\U0001f552 {datetime.now().strftime('%H:%M:%S')}")
        await send_message(client, chat_id, "\n".join(lines))
    except Exception as e:
        logger.error("cmd_ai error: %s", e)
        await send_message(client, chat_id, f"\u274c 오류: {e}")


async def cmd_refresh(client, chat_id, user):
    clear_cache()
    await send_message(client, chat_id,
                       "\U0001f504 캐시를 초기화했습니다. 다음 명령에서 최신 데이터를 가져옵니다.")


async def cmd_chart(client, chat_id, user):
    await send_message(client, chat_id, "\u23f3 차트를 생성하는 중... (약 5-10초 소요)")
    try:
        # 비동기 환경에서 차트 생성 실행 (블로킹 방지 위해 run_in_executor 사용 권장되나 여기선 단순 구현)
        # generate_all_charts는 내부적으로 파일을 저장함
        generate_all_charts()
        
        base_path = os.path.dirname(os.path.abspath(__file__))
        charts = [
            ("risk_indicator.png", "리스크 신호등"),
            ("market_overview.png", "주요 지수 현황"),
            ("pair_trading_board.png", "페어 트레이딩 신호등 (5단계)"),
            ("history_GSPC.png", "S&P 500 장기 트렌드"),
            ("history_NDX.png", "NASDAQ 100 장기 트렌드"),
            ("history_BTC-USD.png", "Bitcoin 장기 트렌드"),
            ("history_KRWX.png", "원/달러 환율 장기 트렌드"),
            ("history_GCF.png", "Gold(금) 장기 트렌드"),
            ("history_SIF.png", "Silver(은) 장기 트렌드"),
        ]
        
        for filename, caption in charts:
            path = os.path.join(base_path, filename)
            if os.path.exists(path):
                await send_photo(client, chat_id, path, caption=f"*{caption}*")
                await asyncio.sleep(0.5)  # 전송 간격
            else:
                logger.warning("Chart file not found: %s", path)
                
    except Exception as e:
        logger.error("cmd_chart error: %s", e)
        await send_message(client, chat_id, f"\u274c 차트 생성 중 오류 발생: {e}")


async def cmd_alert(client, chat_id, user, args=""):
    args = args.strip().lower()

    if not args:
        status = "켜져" if chat_id in _alert_chats else "꺼져"
        await send_message(client, chat_id,
                           f"\u23f0 정기 알림이 *{status}* 있습니다.\n"
                           f"`/alert on` 또는 `/alert off`")
    elif args == "on":
        _alert_chats.add(chat_id)
        await send_message(client, chat_id,
                           f"\u2705 정기 알림을 켰습니다.\n"
                           f"간격: 30분 (매 시각 정기 보고)\n"
                           f"트레이딩 신호: 1시간마다 리프레쉬 후 알림")
    elif args == "off":
        _alert_chats.discard(chat_id)
        await send_message(client, chat_id, "\u26d4 정기 알림을 껐습니다.")
    else:
        await send_message(client, chat_id,
                           "사용법: `/alert on` 또는 `/alert off`")


# 명령어 라우팅 테이블
COMMANDS = {
    '/start': cmd_start,
    '/help': cmd_help,
    '/id': cmd_id,
    '/risk': cmd_risk,
    '/market': cmd_market,
    '/pairs': cmd_pairs,
    '/summary': cmd_summary,
    '/news': cmd_news,
    '/ai': cmd_ai,
    '/chart': cmd_chart,
    '/refresh': cmd_refresh,
}


# ──────────────────────────────────────────────
# 메시지 처리
# ──────────────────────────────────────────────
async def process_update(client: httpx.AsyncClient, update: dict):
    """수신된 업데이트 처리"""
    msg = update.get("message")
    if not msg:
        return

    text = msg.get("text", "")
    chat_id = msg["chat"]["id"]
    user = msg.get("from", {})
    user_id = user.get("id", 0)
    user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()

    if not text.startswith("/"):
        return

    # 인증 체크
    if not is_authorized(user_id, user_name):
        await send_message(client, chat_id,
                           f"\u26d4 접근 권한이 없습니다.\n"
                           f"당신의 User ID: `{user_id}`\n"
                           f"관리자에게 이 ID를 전달하세요.")
        return

    # 명령어 파싱 (/command@botname args 형태 지원)
    parts = text.split(None, 1)
    cmd = parts[0].split("@")[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    # /alert은 특별 처리 (args 전달)
    if cmd == "/alert":
        await cmd_alert(client, chat_id, user, args)
        return

    handler = COMMANDS.get(cmd)
    if handler:
        await handler(client, chat_id, user)
    else:
        await send_message(client, chat_id,
                           "\u2753 알 수 없는 명령어입니다. `/help`를 입력하세요.")


# ──────────────────────────────────────────────
# 정기 알림 루프
# ──────────────────────────────────────────────
async def alert_loop(client: httpx.AsyncClient):
    """정기 알림 및 매수/매도 타이밍 알림 루프"""
    last_signal_check = 0
    
    while _running:
        await asyncio.sleep(60) # 1분 간격으로 체크
        
        now_ts = time.time()
        
        # 1. 매 시간(3600초)마다 데이터 강제 리프레쉬 및 신호 체크
        if now_ts - last_signal_check >= SIGNAL_CHECK_INTERVAL:
            last_signal_check = now_ts
            try:
                clear_cache()
                data = fetch_market_data()
                signals = calculate_pair_trading_signals(data)
                
                # 중립이 아닌 신호만 추출
                active_signals = {k: v for k, v in signals.items() if 'neutral' not in v['level']}
                
                if active_signals:
                    for cid in list(_alert_chats):
                        lines = [
                            f"\U0001f6a8 *트레이딩 신호 알림 (1시간 주기)*",
                            f"",
                            f"*강력 신호 포착:*" if any('strong' in v['level'] for v in active_signals.values()) else "*매수/매도 신호 포착:*",
                            f""
                        ]
                        for sig in active_signals.values():
                            lines.append(f"  {sig['name']}: {sig['signal']}")
                            lines.append(f"  _{sig['description']}_")
                            lines.append("")
                        
                        lines.append(f"\U0001f552 {datetime.now().strftime('%H:%M:%S')}")
                        await send_message(client, cid, "\n".join(lines))
            except Exception as e:
                logger.error("Signal check error: %s", e)

        # 2. 30분(ALERT_INTERVAL)마다 정기 상태 보고
        # (단순 구현을 위해 루프 시작 시점 기준 modulo 연산 대신 타임스탬프 관리 권장되나 여기선 기존 패턴 유지)
        if int(now_ts) % ALERT_INTERVAL < 60: # 30분 마다 (1분 오차)
            if not _alert_chats:
                continue

            try:
                data = fetch_market_data()
                risk = compute_risk_signal(data)
                
                lines = [
                    f"\u23f0 *30분 정기 시장 브리핑*",
                    f"",
                    f"\U0001f6a8 위험: {risk['emoji']} {risk['level']} (점수: {risk['score']})",
                    f"",
                ]

                # 주요 지수 3개만 요약
                key_ids = ['spx', 'ndx', 'btc']
                for item in data:
                    if item['id'] in key_ids:
                        chg = item['change_pct']
                        arrow = "\U0001f53c" if chg > 0 else "\U0001f53d"
                        lines.append(f"  {arrow} {item['name']}: {chg:+.2f}%")
                
                lines.append(f"\n/chart 명령으로 상세 차트를 확인하세요.")
                lines.append(f"\U0001f552 {datetime.now().strftime('%H:%M:%S')}")
                text = "\n".join(lines)

                for cid in list(_alert_chats):
                    try:
                        await send_message(client, cid, text)
                    except Exception as e:
                        logger.error("Regular alert to %d failed: %s", cid, e)
            except Exception as e:
                logger.error("alert_loop summary error: %s", e)


# ──────────────────────────────────────────────
# 메인 폴링 루프
# ──────────────────────────────────────────────
async def register_commands(client: httpx.AsyncClient):
    """봇 명령어 메뉴를 텔레그램에 등록"""
    commands = [
        {"command": "start", "description": "시작 / 도움말"},
        {"command": "risk", "description": "위험 신호등"},
        {"command": "market", "description": "실시간 시장 데이터"},
        {"command": "pairs", "description": "페어 트레이딩 신호"},
        {"command": "summary", "description": "전체 요약 리포트"},
        {"command": "news", "description": "경제 뉴스 TOP 10"},
        {"command": "ai", "description": "AI 뉴스 TOP 10"},
        {"command": "chart", "description": "시각화 차트 전송"},
        {"command": "refresh", "description": "데이터 새로고침"},
        {"command": "alert", "description": "정기 알림 on/off"},
        {"command": "id", "description": "내 User ID 확인"},
        {"command": "help", "description": "도움말"},
    ]
    result = await api_call(client, "setMyCommands", commands=commands)
    if result.get("ok"):
        logger.info("Bot commands menu registered successfully")
    return result


async def polling_loop():
    """Long polling으로 업데이트 수신"""
    global _running
    offset = 0

    async with httpx.AsyncClient() as client:
        # 봇 정보 확인
        me = await api_call(client, "getMe")
        if not me.get("ok"):
            logger.error("Failed to connect to Telegram API. Check your BOT_TOKEN.")
            return

        bot_info = me["result"]
        logger.info("Bot connected: @%s (%s)",
                    bot_info.get("username"), bot_info.get("first_name"))
        print(f"\n  Connected as: @{bot_info.get('username')}")
        print(f"  Send /start to your bot in Telegram!\n")

        # 명령어 메뉴 등록
        await register_commands(client)

        # 정기 알림 백그라운드 태스크
        alert_task = asyncio.create_task(alert_loop(client))

        try:
            while _running:
                try:
                    url = f"{API_BASE}/getUpdates"
                    resp = await client.post(
                        url,
                        json={"offset": offset, "timeout": 30},
                        timeout=60,  # httpx timeout > Telegram long poll timeout
                    )
                    updates = resp.json()

                    if not updates.get("ok"):
                        await asyncio.sleep(5)
                        continue

                    for upd in updates.get("result", []):
                        offset = upd["update_id"] + 1
                        try:
                            await process_update(client, upd)
                        except Exception as e:
                            logger.error("Error processing update: %s", e)

                except httpx.TimeoutException:
                    continue
                except httpx.ConnectError:
                    logger.warning("Connection lost. Retrying in 5s...")
                    await asyncio.sleep(5)
                except Exception as e:
                    logger.error("Polling error: %s", e)
                    await asyncio.sleep(3)
        finally:
            _running = False
            alert_task.cancel()


def main():
    global _running

    if not BOT_TOKEN:
        print("\n[ERROR] TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
        print("다음 중 하나를 수행하세요:")
        print("  1. .env 파일에 TELEGRAM_BOT_TOKEN=your_token 추가")
        print("  2. 환경변수로 설정: set TELEGRAM_BOT_TOKEN=your_token (Windows)")
        print("\n봇 토큰은 Telegram @BotFather에서 생성할 수 있습니다.")
        sys.exit(1)

    if not AUTHORIZED_USERS:
        print("\n[WARNING] AUTHORIZED_USERS가 설정되지 않았습니다.")
        print("첫 번째로 /start를 보내는 사용자가 자동 등록됩니다.")
        print("보안을 위해 .env 파일에 AUTHORIZED_USERS=your_id를 설정하세요.\n")

    print("=" * 50)
    print("  Economic Indicators - Telegram Bot")
    print("=" * 50)
    print(f"  Authorized Users: {AUTHORIZED_USERS or '(auto-register first user)'}")
    print(f"  Alert Interval: {ALERT_INTERVAL}s ({ALERT_INTERVAL // 60}min)")
    print("=" * 50)
    print("  Bot is starting... Press Ctrl+C to stop.")

    # Ctrl+C 처리
    def shutdown(sig, frame):
        global _running
        print("\n\nShutting down...")
        _running = False

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, shutdown)

    asyncio.run(polling_loop())
    print("Bot stopped.")


if __name__ == "__main__":
    main()
