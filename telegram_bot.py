"""
telegram_bot.py - Economic Indicators Dashboard Telegram Bot

Windows PC에서 실행하고, 모바일 텔레그램으로 시장 데이터를 안전하게 조회.

사용법:
    python telegram_bot.py

필요 환경변수 (.env 파일 또는 시스템 환경변수):
    TELEGRAM_BOT_TOKEN  - BotFather에서 받은 봇 토큰
    AUTHORIZED_USERS    - 허용된 텔레그램 유저 ID (쉼표 구분)
    ALERT_CHAT_ID       - 정기 알림을 보낼 채팅 ID (선택)
"""
import os
import sys
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from market_core import (
    fetch_market_data,
    compute_risk_signal,
    calculate_pair_trading_signals,
    clear_cache,
    TICKER_MAP,
)

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
AUTHORIZED_USERS = set()
_raw = os.getenv("AUTHORIZED_USERS", "")
for uid in _raw.split(","):
    uid = uid.strip()
    if uid.isdigit():
        AUTHORIZED_USERS.add(int(uid))

ALERT_CHAT_ID = os.getenv("ALERT_CHAT_ID", "")
# 정기 알림 간격 (초). 기본 1시간
ALERT_INTERVAL = int(os.getenv("ALERT_INTERVAL", "3600"))

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("TelegramBot")


# ──────────────────────────────────────────────
# 보안: 인증 데코레이터
# ──────────────────────────────────────────────
def authorized(func):
    """허용된 사용자만 명령을 실행할 수 있도록 하는 데코레이터"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user:
            return

        # AUTHORIZED_USERS가 비어있으면 첫 사용자를 자동 등록 (초기 설정 편의)
        if not AUTHORIZED_USERS:
            AUTHORIZED_USERS.add(user.id)
            logger.warning(
                "AUTHORIZED_USERS가 비어있어 첫 사용자를 자동 등록: %s (ID: %d)",
                user.full_name, user.id,
            )

        if user.id not in AUTHORIZED_USERS:
            logger.warning(
                "미인증 접근 시도: %s (ID: %d)", user.full_name, user.id
            )
            await update.message.reply_text(
                "\u26d4 접근 권한이 없습니다.\n"
                f"당신의 User ID: `{user.id}`\n"
                "관리자에게 이 ID를 전달하세요.",
                parse_mode="Markdown",
            )
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


# ──────────────────────────────────────────────
# 명령어 핸들러
# ──────────────────────────────────────────────
@authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """시작 및 도움말"""
    user = update.effective_user
    text = (
        f"\U0001f4ca *Economic Indicators Bot*\n\n"
        f"안녕하세요, {user.first_name}님!\n"
        f"Windows PC 대시보드에 연결되었습니다.\n\n"
        f"*사용 가능한 명령어:*\n"
        f"/risk - \U0001f6a8 위험 신호등 (리스크 점수)\n"
        f"/market - \U0001f4c8 실시간 시장 데이터\n"
        f"/pairs - \U0001f4b1 페어 트레이딩 신호\n"
        f"/summary - \U0001f4cb 전체 요약 리포트\n"
        f"/refresh - \U0001f504 데이터 새로고침\n"
        f"/alert - \u23f0 정기 알림 설정\n"
        f"/id - \U0001f194 내 User ID 확인\n"
        f"/help - \u2753 도움말\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


@authorized
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """도움말"""
    text = (
        "*\U0001f4d6 명령어 안내*\n\n"
        "`/risk` - 위험 신호등과 기여 요인\n"
        "`/market` - 12개 지수 실시간 현황\n"
        "`/pairs` - 4개 페어 트레이딩 신호 (5단계)\n"
        "`/summary` - 위험 + 시장 + 페어 전체 요약\n"
        "`/refresh` - 캐시 초기화 후 새 데이터\n"
        "`/alert on` - 정기 알림 켜기\n"
        "`/alert off` - 정기 알림 끄기\n"
        "`/id` - 텔레그램 User ID 확인\n\n"
        "*\U0001f512 보안*\n"
        "인증된 사용자만 사용 가능합니다.\n"
        "`.env` 파일의 `AUTHORIZED_USERS`에 ID를 등록하세요."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


@authorized
async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """유저 ID 확인"""
    user = update.effective_user
    await update.message.reply_text(
        f"\U0001f194 *User ID:* `{user.id}`\n"
        f"\U0001f464 *이름:* {user.full_name}",
        parse_mode="Markdown",
    )


@authorized
async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """위험 신호등"""
    await update.message.reply_text("\u23f3 데이터를 가져오는 중...")
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
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        logger.error("cmd_risk error: %s", e)
        await update.message.reply_text(f"\u274c 오류: {e}")


@authorized
async def cmd_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """시장 데이터 요약"""
    await update.message.reply_text("\u23f3 시장 데이터를 가져오는 중...")
    try:
        data = fetch_market_data()

        lines = [f"\U0001f4c8 *실시간 시장 현황*", ""]

        for item in data:
            chg = item['change_pct']
            if chg > 0:
                arrow = "\U0001f53c"  # up
            elif chg < 0:
                arrow = "\U0001f53d"  # down
            else:
                arrow = "\u25ab"  # neutral

            status_icon = ""
            if item['status'] == '상승':
                status_icon = "\U0001f7e2"
            elif item['status'] == '하락':
                status_icon = "\U0001f534"
            else:
                status_icon = "\u26aa"

            lines.append(
                f"{status_icon} *{item['name']}*\n"
                f"   {item['formatted_value']} {arrow} {chg:+.2f}%"
            )

        lines.append(f"\n\U0001f552 {datetime.now().strftime('%H:%M:%S')}")

        text = "\n".join(lines)
        # Telegram 메시지 길이 제한 (4096자)
        if len(text) > 4000:
            # 두 부분으로 나눠 전송
            mid = len(data) // 2
            part1 = [f"\U0001f4c8 *실시간 시장 현황 (1/2)*", ""]
            part2 = [f"\U0001f4c8 *실시간 시장 현황 (2/2)*", ""]

            for i, item in enumerate(data):
                chg = item['change_pct']
                arrow = "\U0001f53c" if chg > 0 else ("\U0001f53d" if chg < 0 else "\u25ab")
                if item['status'] == '상승':
                    si = "\U0001f7e2"
                elif item['status'] == '하락':
                    si = "\U0001f534"
                else:
                    si = "\u26aa"
                line = f"{si} *{item['name']}*\n   {item['formatted_value']} {arrow} {chg:+.2f}%"
                if i < mid:
                    part1.append(line)
                else:
                    part2.append(line)

            await update.message.reply_text("\n".join(part1), parse_mode="Markdown")
            await update.message.reply_text("\n".join(part2), parse_mode="Markdown")
        else:
            await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        logger.error("cmd_market error: %s", e)
        await update.message.reply_text(f"\u274c 오류: {e}")


@authorized
async def cmd_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """페어 트레이딩 신호"""
    await update.message.reply_text("\u23f3 페어 트레이딩 신호를 분석하는 중...")
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
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        logger.error("cmd_pairs error: %s", e)
        await update.message.reply_text(f"\u274c 오류: {e}")


@authorized
async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """전체 요약 리포트"""
    await update.message.reply_text("\u23f3 전체 리포트를 생성하는 중...")
    try:
        data = fetch_market_data()
        risk = compute_risk_signal(data)
        signals = calculate_pair_trading_signals(data)

        # 1. 위험 신호등
        lines = [
            f"\U0001f4cb *전체 시장 요약 리포트*",
            f"{'='*30}",
            f"",
            f"\U0001f6a8 *위험 신호등*",
            f"{risk['emoji']} {risk['level']} (점수: {risk['score']})",
        ]
        if risk['factors']:
            for f in risk['factors'][:5]:  # 상위 5개만
                lines.append(f"  \u2022 {f}")
            if len(risk['factors']) > 5:
                lines.append(f"  _...외 {len(risk['factors'])-5}개_")
        lines.append("")

        # 2. 주요 지수
        lines.append("*\U0001f4c8 주요 지수*")
        key_indices = ['spx', 'ndx', 'vix', 'btc', 'gold', 'dxy', 'krwusd']
        for item in data:
            if item['id'] in key_indices:
                chg = item['change_pct']
                arrow = "\U0001f53c" if chg > 0 else ("\U0001f53d" if chg < 0 else "\u25ab")
                lines.append(f"  {item['name']}: {item['formatted_value']} {arrow}{chg:+.2f}%")
        lines.append("")

        # 3. 페어 트레이딩
        lines.append("*\U0001f4b1 페어 트레이딩*")
        for sig in signals.values():
            lines.append(f"  {sig['name']}: {sig['signal']}")
        lines.append("")

        lines.append(f"\U0001f552 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        logger.error("cmd_summary error: %s", e)
        await update.message.reply_text(f"\u274c 오류: {e}")


@authorized
async def cmd_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """데이터 새로고침"""
    clear_cache()
    await update.message.reply_text(
        "\U0001f504 캐시를 초기화했습니다. 다음 명령에서 최신 데이터를 가져옵니다."
    )


@authorized
async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """정기 알림 설정"""
    args = context.args
    chat_id = update.effective_chat.id

    if not args:
        # 현재 상태 표시
        jobs = context.job_queue.get_jobs_by_name(f"alert_{chat_id}")
        if jobs:
            await update.message.reply_text(
                f"\u23f0 정기 알림이 *켜져* 있습니다.\n"
                f"간격: {ALERT_INTERVAL}초 ({ALERT_INTERVAL // 60}분)\n\n"
                f"`/alert off` 로 끌 수 있습니다.",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                f"\u23f0 정기 알림이 *꺼져* 있습니다.\n\n"
                f"`/alert on` 으로 켤 수 있습니다.",
                parse_mode="Markdown",
            )
        return

    action = args[0].lower()

    if action == "on":
        # 기존 작업 제거
        jobs = context.job_queue.get_jobs_by_name(f"alert_{chat_id}")
        for job in jobs:
            job.schedule_removal()

        context.job_queue.run_repeating(
            scheduled_alert,
            interval=ALERT_INTERVAL,
            first=10,  # 10초 후 첫 전송
            chat_id=chat_id,
            name=f"alert_{chat_id}",
        )
        await update.message.reply_text(
            f"\u2705 정기 알림을 켰습니다.\n"
            f"간격: {ALERT_INTERVAL // 60}분\n"
            f"10초 후 첫 알림이 전송됩니다.",
        )

    elif action == "off":
        jobs = context.job_queue.get_jobs_by_name(f"alert_{chat_id}")
        for job in jobs:
            job.schedule_removal()
        await update.message.reply_text("\u26d4 정기 알림을 껐습니다.")

    else:
        await update.message.reply_text(
            "사용법: `/alert on` 또는 `/alert off`",
            parse_mode="Markdown",
        )


async def scheduled_alert(context: ContextTypes.DEFAULT_TYPE):
    """정기 알림 콜백"""
    chat_id = context.job.chat_id
    try:
        data = fetch_market_data()
        risk = compute_risk_signal(data)
        signals = calculate_pair_trading_signals(data)

        lines = [
            f"\u23f0 *정기 시장 알림*",
            f"",
            f"\U0001f6a8 위험: {risk['emoji']} {risk['level']} (점수: {risk['score']})",
            f"",
        ]

        # 주요 변동 지수만 (1% 이상 변동)
        movers = [item for item in data if abs(item['change_pct']) >= 1.0]
        if movers:
            lines.append("*주요 변동:*")
            for item in movers:
                chg = item['change_pct']
                arrow = "\U0001f53c" if chg > 0 else "\U0001f53d"
                lines.append(f"  {arrow} {item['name']}: {chg:+.2f}%")
            lines.append("")

        # 비중립 페어 신호만
        non_neutral = {k: v for k, v in signals.items() if 'neutral' not in v['level']}
        if non_neutral:
            lines.append("*액티브 신호:*")
            for sig in non_neutral.values():
                lines.append(f"  {sig['name']}: {sig['signal']}")

        lines.append(f"\n\U0001f552 {datetime.now().strftime('%H:%M:%S')}")

        await context.bot.send_message(
            chat_id=chat_id,
            text="\n".join(lines),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("scheduled_alert error: %s", e)


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """알 수 없는 명령어 처리"""
    if update.message and update.message.text and update.message.text.startswith("/"):
        await update.message.reply_text(
            "\u2753 알 수 없는 명령어입니다. `/help`를 입력하세요.",
            parse_mode="Markdown",
        )


# ──────────────────────────────────────────────
# 봇 실행
# ──────────────────────────────────────────────
async def post_init(application: Application):
    """봇 시작 후 명령어 메뉴 등록"""
    commands = [
        BotCommand("start", "시작 / 도움말"),
        BotCommand("risk", "위험 신호등"),
        BotCommand("market", "실시간 시장 데이터"),
        BotCommand("pairs", "페어 트레이딩 신호"),
        BotCommand("summary", "전체 요약 리포트"),
        BotCommand("refresh", "데이터 새로고침"),
        BotCommand("alert", "정기 알림 on/off"),
        BotCommand("id", "내 User ID 확인"),
        BotCommand("help", "도움말"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered. Bot is ready!")


def main():
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
    print()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # 명령어 등록
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("risk", cmd_risk))
    app.add_handler(CommandHandler("market", cmd_market))
    app.add_handler(CommandHandler("pairs", cmd_pairs))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("refresh", cmd_refresh))
    app.add_handler(CommandHandler("alert", cmd_alert))

    # 알 수 없는 명령어
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown))

    # 실행
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
