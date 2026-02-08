"""
telegram_sender.py - 텔레그램 메시지 및 이미지 전송 모듈
Team E - 텔레그램 전송 개발

기능:
- 텍스트 메시지 전송 (마크다운 지원)
- PNG 이미지 전송
- 일일 리포트 자동 생성 및 전송
- 급변동 알림 전송
- 에러 핸들링 및 재시도 로직
"""

import os
import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

# 환경변수 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# httpx 체크
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AlertType(Enum):
    """알림 유형"""
    PRICE_SURGE = "price_surge"       # 급등
    PRICE_PLUNGE = "price_plunge"     # 급락
    VIX_SPIKE = "vix_spike"           # VIX 급등
    CURRENCY_ALERT = "currency_alert" # 환율 급변동
    RISK_HIGH = "risk_high"           # 리스크 경고
    CUSTOM = "custom"                 # 사용자 정의


@dataclass
class RetryConfig:
    """재시도 설정"""
    max_retries: int = 3          # 최대 재시도 횟수
    base_delay: float = 1.0       # 기본 대기 시간 (초)
    max_delay: float = 30.0       # 최대 대기 시간 (초)
    exponential_base: float = 2.0 # 지수 백오프 배수


@dataclass
class SendResult:
    """전송 결과"""
    success: bool
    message_id: Optional[int] = None
    error: Optional[str] = None
    retry_count: int = 0


# 텔레그램 메시지 제한
MAX_MESSAGE_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024
SAFE_MESSAGE_LENGTH = 4000  # 안전 마진


class TelegramSender:
    """
    텔레그램 메시지 및 이미지 전송 클래스

    비동기 방식으로 메시지와 이미지를 전송하며,
    에러 발생 시 자동 재시도 로직을 포함합니다.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 30.0
    ):
        """
        TelegramSender 초기화

        Args:
            bot_token: 텔레그램 봇 토큰 (없으면 환경변수에서 로드)
            retry_config: 재시도 설정
            timeout: API 호출 타임아웃 (초)
        """
        if not HAS_HTTPX:
            raise ImportError("httpx 라이브러리가 필요합니다. pip install httpx")

        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")

        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"
        self.retry_config = retry_config or RetryConfig()
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 반환 (필요시 생성)"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def _api_call(
        self,
        method: str,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Telegram Bot API 호출

        Args:
            method: API 메서드명
            data: 전송할 데이터
            files: 전송할 파일

        Returns:
            API 응답 딕셔너리
        """
        url = f"{self.api_base}/{method}"
        client = await self._get_client()

        try:
            if files:
                # 파일 전송 시 multipart/form-data 사용
                resp = await client.post(url, data=data, files=files)
            else:
                # JSON 데이터 전송
                resp = await client.post(url, json=data)

            result = resp.json()

            if not result.get("ok"):
                error_code = result.get("error_code", "unknown")
                description = result.get("description", "No description")
                logger.error(
                    "API 에러 [%s]: code=%s, desc=%s",
                    method, error_code, description
                )

            return result

        except httpx.TimeoutException as e:
            logger.error("API 타임아웃 [%s]: %s", method, e)
            return {"ok": False, "error_code": "timeout", "description": str(e)}
        except httpx.ConnectError as e:
            logger.error("연결 에러 [%s]: %s", method, e)
            return {"ok": False, "error_code": "connection", "description": str(e)}
        except Exception as e:
            logger.error("예외 발생 [%s]: %s", method, e)
            return {"ok": False, "error_code": "exception", "description": str(e)}

    async def _retry_operation(
        self,
        operation,
        *args,
        **kwargs
    ) -> SendResult:
        """
        재시도 로직이 포함된 작업 실행

        Args:
            operation: 실행할 비동기 함수
            *args, **kwargs: 함수에 전달할 인자

        Returns:
            SendResult 객체
        """
        last_error = None
        retry_count = 0

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                result = await operation(*args, **kwargs)

                if result.get("ok"):
                    message_id = None
                    if "result" in result:
                        message_id = result["result"].get("message_id")

                    return SendResult(
                        success=True,
                        message_id=message_id,
                        retry_count=retry_count
                    )

                # 재시도 불가능한 에러 체크
                error_code = result.get("error_code", "")
                description = result.get("description", "")

                # 치명적 에러는 재시도하지 않음
                fatal_errors = [
                    "Unauthorized",      # 토큰 오류
                    "Forbidden",         # 권한 없음
                    "chat not found",    # 채팅방 없음
                    "bot was blocked",   # 봇 차단됨
                ]
                if any(err in str(description) for err in fatal_errors):
                    logger.error("치명적 에러, 재시도 중단: %s", description)
                    return SendResult(
                        success=False,
                        error=description,
                        retry_count=retry_count
                    )

                last_error = description

            except Exception as e:
                last_error = str(e)
                logger.warning("시도 %d/%d 실패: %s",
                              attempt + 1,
                              self.retry_config.max_retries + 1,
                              e)

            # 마지막 시도가 아니면 대기 후 재시도
            if attempt < self.retry_config.max_retries:
                retry_count += 1
                delay = min(
                    self.retry_config.base_delay * (
                        self.retry_config.exponential_base ** attempt
                    ),
                    self.retry_config.max_delay
                )
                logger.info("%.1f초 후 재시도 (%d/%d)...",
                           delay, retry_count, self.retry_config.max_retries)
                await asyncio.sleep(delay)

        return SendResult(
            success=False,
            error=last_error or "Unknown error",
            retry_count=retry_count
        )

    def _split_message(self, text: str, max_length: int = SAFE_MESSAGE_LENGTH) -> List[str]:
        """
        긴 메시지를 분할

        Args:
            text: 분할할 텍스트
            max_length: 최대 길이

        Returns:
            분할된 텍스트 리스트
        """
        if len(text) <= max_length:
            return [text]

        parts = []
        while text:
            if len(text) <= max_length:
                parts.append(text)
                break

            # 줄바꿈 기준으로 분할
            idx = text.rfind("\n", 0, max_length)
            if idx == -1:
                # 줄바꿈이 없으면 공백 기준
                idx = text.rfind(" ", 0, max_length)
            if idx == -1:
                # 공백도 없으면 강제 분할
                idx = max_length

            parts.append(text[:idx])
            text = text[idx:].lstrip("\n ")

        return parts

    def _escape_markdown(self, text: str) -> str:
        """
        마크다운 특수문자 이스케이프 (MarkdownV2용)

        Args:
            text: 원본 텍스트

        Returns:
            이스케이프된 텍스트
        """
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    async def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        parse_mode: str = "Markdown",
        disable_notification: bool = False,
        reply_to_message_id: Optional[int] = None
    ) -> SendResult:
        """
        텍스트 메시지 전송

        Args:
            chat_id: 채팅 ID
            text: 메시지 내용
            parse_mode: 파싱 모드 ("Markdown", "MarkdownV2", "HTML")
            disable_notification: 알림 비활성화 여부
            reply_to_message_id: 답장할 메시지 ID

        Returns:
            SendResult 객체
        """
        if not self.bot_token:
            return SendResult(success=False, error="Bot token not configured")

        parts = self._split_message(text)
        last_result = None

        for i, part in enumerate(parts):
            data = {
                "chat_id": chat_id,
                "text": part,
                "parse_mode": parse_mode,
                "disable_notification": disable_notification,
            }

            if reply_to_message_id and i == 0:
                data["reply_to_message_id"] = reply_to_message_id

            async def _send():
                return await self._api_call("sendMessage", data)

            last_result = await self._retry_operation(_send)

            if not last_result.success:
                logger.error("메시지 전송 실패 (파트 %d/%d): %s",
                            i + 1, len(parts), last_result.error)
                return last_result

            # 여러 파트일 경우 약간의 딜레이
            if i < len(parts) - 1:
                await asyncio.sleep(0.5)

        return last_result or SendResult(success=False, error="No parts to send")

    async def send_photo(
        self,
        chat_id: Union[int, str],
        photo: Union[str, Path, bytes],
        caption: Optional[str] = None,
        parse_mode: str = "Markdown",
        disable_notification: bool = False
    ) -> SendResult:
        """
        이미지 전송

        Args:
            chat_id: 채팅 ID
            photo: 이미지 경로, URL, 또는 바이트 데이터
            caption: 이미지 설명
            parse_mode: 파싱 모드
            disable_notification: 알림 비활성화 여부

        Returns:
            SendResult 객체
        """
        if not self.bot_token:
            return SendResult(success=False, error="Bot token not configured")

        # 캡션 길이 제한
        if caption and len(caption) > MAX_CAPTION_LENGTH:
            caption = caption[:MAX_CAPTION_LENGTH - 3] + "..."

        data = {
            "chat_id": str(chat_id),
            "disable_notification": str(disable_notification).lower(),
        }

        if caption:
            data["caption"] = caption
            data["parse_mode"] = parse_mode

        files = None

        # 이미지 타입 판별
        if isinstance(photo, bytes):
            # 바이트 데이터
            files = {"photo": ("chart.png", photo, "image/png")}
        elif isinstance(photo, (str, Path)):
            photo_path = Path(photo)
            if photo_path.exists():
                # 로컬 파일
                files = {"photo": (photo_path.name, open(photo_path, "rb"), "image/png")}
            elif str(photo).startswith(("http://", "https://")):
                # URL
                data["photo"] = str(photo)
            else:
                return SendResult(success=False, error=f"파일을 찾을 수 없음: {photo}")
        else:
            return SendResult(success=False, error=f"지원하지 않는 이미지 타입: {type(photo)}")

        async def _send():
            return await self._api_call("sendPhoto", data, files)

        try:
            result = await self._retry_operation(_send)
            return result
        finally:
            # 파일 핸들 정리
            if files and "photo" in files:
                file_tuple = files["photo"]
                if len(file_tuple) > 1 and hasattr(file_tuple[1], 'close'):
                    file_tuple[1].close()

    async def send_document(
        self,
        chat_id: Union[int, str],
        document: Union[str, Path, bytes],
        caption: Optional[str] = None,
        filename: Optional[str] = None,
        parse_mode: str = "Markdown",
        disable_notification: bool = False
    ) -> SendResult:
        """
        문서/파일 전송

        Args:
            chat_id: 채팅 ID
            document: 파일 경로 또는 바이트 데이터
            caption: 파일 설명
            filename: 파일명 (바이트 데이터 전송 시)
            parse_mode: 파싱 모드
            disable_notification: 알림 비활성화 여부

        Returns:
            SendResult 객체
        """
        if not self.bot_token:
            return SendResult(success=False, error="Bot token not configured")

        data = {
            "chat_id": str(chat_id),
            "disable_notification": str(disable_notification).lower(),
        }

        if caption:
            data["caption"] = caption[:MAX_CAPTION_LENGTH]
            data["parse_mode"] = parse_mode

        files = None

        if isinstance(document, bytes):
            fname = filename or "file.dat"
            files = {"document": (fname, document)}
        elif isinstance(document, (str, Path)):
            doc_path = Path(document)
            if doc_path.exists():
                files = {"document": (doc_path.name, open(doc_path, "rb"))}
            else:
                return SendResult(success=False, error=f"파일을 찾을 수 없음: {document}")
        else:
            return SendResult(success=False, error=f"지원하지 않는 파일 타입: {type(document)}")

        async def _send():
            return await self._api_call("sendDocument", data, files)

        try:
            result = await self._retry_operation(_send)
            return result
        finally:
            if files and "document" in files:
                file_tuple = files["document"]
                if len(file_tuple) > 1 and hasattr(file_tuple[1], 'close'):
                    file_tuple[1].close()

    async def send_daily_report(
        self,
        chat_id: Union[int, str],
        market_data: Optional[List[Dict]] = None,
        risk_data: Optional[Dict] = None,
        pair_signals: Optional[Dict] = None,
        include_timestamp: bool = True
    ) -> SendResult:
        """
        일일 시장 리포트 전송

        Args:
            chat_id: 채팅 ID
            market_data: 시장 데이터 (없으면 fetch_market_data 호출)
            risk_data: 리스크 데이터 (없으면 compute_risk_signal 호출)
            pair_signals: 페어 트레이딩 신호 (없으면 calculate_pair_trading_signals 호출)
            include_timestamp: 타임스탬프 포함 여부

        Returns:
            SendResult 객체
        """
        try:
            # 데이터가 없으면 market_core에서 가져오기
            if market_data is None or risk_data is None or pair_signals is None:
                from market_core import (
                    fetch_market_data,
                    compute_risk_signal,
                    calculate_pair_trading_signals,
                )

                if market_data is None:
                    market_data = fetch_market_data()
                if risk_data is None:
                    risk_data = compute_risk_signal(market_data)
                if pair_signals is None:
                    pair_signals = calculate_pair_trading_signals(market_data)

            # 리포트 생성
            lines = [
                "\U0001f4cb *Daily Market Report*",
                "=" * 28,
                "",
                "\U0001f6a8 *Risk Signal*",
                f"{risk_data['emoji']} Level: *{risk_data['level']}* (Score: {risk_data['score']})",
                "",
            ]

            # 리스크 요인
            if risk_data.get('factors'):
                lines.append("*Key Factors:*")
                for factor in risk_data['factors'][:5]:
                    lines.append(f"  \u2022 {factor}")
                if len(risk_data['factors']) > 5:
                    lines.append(f"  _...and {len(risk_data['factors']) - 5} more_")
                lines.append("")

            # 주요 지수
            lines.append("\U0001f4c8 *Major Indices*")
            key_indices = ['spx', 'ndx', 'vix', 'btc', 'gold', 'dxy', 'krwusd']
            for item in market_data:
                if item['id'] in key_indices:
                    chg = item['change_pct']
                    arrow = "\U0001f53c" if chg > 0 else ("\U0001f53d" if chg < 0 else "\u25ab")
                    lines.append(
                        f"  {item['name']}: {item['formatted_value']} {arrow}{chg:+.2f}%"
                    )
            lines.append("")

            # 페어 트레이딩 신호
            lines.append("\U0001f4b1 *Pair Trading Signals*")
            for sig in pair_signals.values():
                lines.append(f"  {sig['name']}: {sig['signal']}")
            lines.append("")

            # 급변동 종목
            movers = [item for item in market_data if abs(item['change_pct']) >= 2.0]
            if movers:
                lines.append("\u26a1 *Significant Movers*")
                for item in movers:
                    chg = item['change_pct']
                    emoji = "\U0001f53c" if chg > 0 else "\U0001f53d"
                    lines.append(f"  {emoji} {item['name']}: {chg:+.2f}%")
                lines.append("")

            # 타임스탬프
            if include_timestamp:
                lines.append(f"\U0001f552 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            report_text = "\n".join(lines)
            return await self.send_message(chat_id, report_text)

        except Exception as e:
            logger.error("Daily report 생성 실패: %s", e)
            return SendResult(success=False, error=str(e))

    async def send_chart_images(
        self,
        chat_id: Union[int, str],
        image_paths: List[Union[str, Path]],
        captions: Optional[List[str]] = None
    ) -> List[SendResult]:
        """
        차트 이미지들 전송

        Args:
            chat_id: 채팅 ID
            image_paths: 이미지 경로 리스트
            captions: 각 이미지의 캡션 (옵션)

        Returns:
            SendResult 리스트
        """
        results = []

        for i, path in enumerate(image_paths):
            caption = None
            if captions and i < len(captions):
                caption = captions[i]

            result = await self.send_photo(chat_id, path, caption=caption)
            results.append(result)

            if result.success:
                logger.info("이미지 전송 성공: %s", path)
            else:
                logger.error("이미지 전송 실패: %s - %s", path, result.error)

            # 연속 전송 시 딜레이
            if i < len(image_paths) - 1:
                await asyncio.sleep(0.5)

        return results

    async def send_alert(
        self,
        chat_id: Union[int, str],
        alert_type: AlertType,
        data: Dict[str, Any],
        urgency: str = "normal"
    ) -> SendResult:
        """
        급변동 알림 전송

        Args:
            chat_id: 채팅 ID
            alert_type: 알림 유형
            data: 알림 데이터
            urgency: 긴급도 ("low", "normal", "high", "critical")

        Returns:
            SendResult 객체
        """
        # 긴급도별 이모지
        urgency_emoji = {
            "low": "\U0001f7e2",      # green
            "normal": "\U0001f7e1",   # yellow
            "high": "\U0001f7e0",     # orange
            "critical": "\U0001f534", # red
        }

        emoji = urgency_emoji.get(urgency, "\U0001f7e1")

        # 알림 유형별 메시지 템플릿
        if alert_type == AlertType.PRICE_SURGE:
            title = "\u26a1 Price Surge Alert"
            body = (
                f"*{data.get('name', 'Unknown')}* surged *{data.get('change', 0):+.2f}%*\n"
                f"Current: {data.get('current', 'N/A')}\n"
                f"Previous: {data.get('previous', 'N/A')}"
            )

        elif alert_type == AlertType.PRICE_PLUNGE:
            title = "\U0001f4c9 Price Plunge Alert"
            body = (
                f"*{data.get('name', 'Unknown')}* dropped *{data.get('change', 0):+.2f}%*\n"
                f"Current: {data.get('current', 'N/A')}\n"
                f"Previous: {data.get('previous', 'N/A')}"
            )

        elif alert_type == AlertType.VIX_SPIKE:
            title = "\U0001f6a8 VIX Spike Alert"
            body = (
                f"VIX spiked to *{data.get('vix_level', 0):.1f}*\n"
                f"Change: *{data.get('change', 0):+.2f}%*\n"
                f"Market fear level: *{data.get('fear_level', 'Unknown')}*"
            )

        elif alert_type == AlertType.CURRENCY_ALERT:
            title = "\U0001f4b1 Currency Alert"
            body = (
                f"*{data.get('pair', 'Unknown')}* moved *{data.get('change', 0):+.2f}%*\n"
                f"Current: {data.get('current', 'N/A')}"
            )

        elif alert_type == AlertType.RISK_HIGH:
            title = "\u26a0\ufe0f High Risk Alert"
            body = (
                f"Risk score: *{data.get('score', 0)}* ({data.get('level', 'Unknown')})\n"
                f"\n*Factors:*"
            )
            factors = data.get('factors', [])
            for factor in factors[:5]:
                body += f"\n  \u2022 {factor}"

        else:  # CUSTOM
            title = data.get('title', 'Alert')
            body = data.get('body', 'No details')

        # 메시지 조합
        message = f"{emoji} *{title}*\n\n{body}\n\n\U0001f552 {datetime.now().strftime('%H:%M:%S')}"

        return await self.send_message(
            chat_id,
            message,
            disable_notification=(urgency == "low")
        )

    async def send_media_group(
        self,
        chat_id: Union[int, str],
        media: List[Dict[str, Any]]
    ) -> SendResult:
        """
        미디어 그룹 전송 (여러 이미지를 한번에)

        Args:
            chat_id: 채팅 ID
            media: 미디어 리스트 [{"type": "photo", "media": "path_or_url", "caption": "..."}]

        Returns:
            SendResult 객체
        """
        if not self.bot_token:
            return SendResult(success=False, error="Bot token not configured")

        if not media or len(media) < 2:
            return SendResult(success=False, error="최소 2개의 미디어가 필요합니다")

        if len(media) > 10:
            return SendResult(success=False, error="최대 10개까지만 전송 가능합니다")

        import json

        data = {"chat_id": str(chat_id)}
        files = {}
        media_list = []

        for i, item in enumerate(media):
            media_entry = {
                "type": item.get("type", "photo"),
            }

            path = item.get("media")
            if isinstance(path, (str, Path)) and Path(path).exists():
                attach_name = f"attach_{i}"
                files[attach_name] = (Path(path).name, open(path, "rb"))
                media_entry["media"] = f"attach://{attach_name}"
            else:
                media_entry["media"] = str(path)

            if item.get("caption"):
                media_entry["caption"] = item["caption"]
                media_entry["parse_mode"] = item.get("parse_mode", "Markdown")

            media_list.append(media_entry)

        data["media"] = json.dumps(media_list)

        async def _send():
            return await self._api_call("sendMediaGroup", data, files)

        try:
            return await self._retry_operation(_send)
        finally:
            for file_tuple in files.values():
                if hasattr(file_tuple[1], 'close'):
                    file_tuple[1].close()


# 유틸리티 함수
async def quick_send_message(
    chat_id: Union[int, str],
    text: str,
    bot_token: Optional[str] = None
) -> SendResult:
    """
    빠른 메시지 전송 (일회성)

    Args:
        chat_id: 채팅 ID
        text: 메시지 내용
        bot_token: 봇 토큰 (옵션)

    Returns:
        SendResult 객체
    """
    async with TelegramSender(bot_token=bot_token) as sender:
        return await sender.send_message(chat_id, text)


async def quick_send_photo(
    chat_id: Union[int, str],
    photo: Union[str, Path, bytes],
    caption: Optional[str] = None,
    bot_token: Optional[str] = None
) -> SendResult:
    """
    빠른 이미지 전송 (일회성)

    Args:
        chat_id: 채팅 ID
        photo: 이미지
        caption: 캡션
        bot_token: 봇 토큰 (옵션)

    Returns:
        SendResult 객체
    """
    async with TelegramSender(bot_token=bot_token) as sender:
        return await sender.send_photo(chat_id, photo, caption=caption)


# 테스트 및 예제
async def _example_usage():
    """사용 예제 (실제 전송하지 않음)"""
    print("TelegramSender 사용 예제")
    print("=" * 50)

    # 1. 기본 사용법
    print("\n1. 기본 메시지 전송:")
    print('''
    async with TelegramSender() as sender:
        result = await sender.send_message(
            chat_id=123456789,
            text="Hello, World!"
        )
        print(f"Success: {result.success}")
    ''')

    # 2. 이미지 전송
    print("\n2. 이미지 전송:")
    print('''
    async with TelegramSender() as sender:
        result = await sender.send_photo(
            chat_id=123456789,
            photo="chart.png",
            caption="Daily Chart"
        )
    ''')

    # 3. 일일 리포트
    print("\n3. 일일 리포트 전송:")
    print('''
    async with TelegramSender() as sender:
        result = await sender.send_daily_report(
            chat_id=123456789
        )
    ''')

    # 4. 알림 전송
    print("\n4. 알림 전송:")
    print('''
    async with TelegramSender() as sender:
        result = await sender.send_alert(
            chat_id=123456789,
            alert_type=AlertType.VIX_SPIKE,
            data={
                "vix_level": 35.5,
                "change": 15.2,
                "fear_level": "Extreme Fear"
            },
            urgency="high"
        )
    ''')

    # 5. 여러 차트 전송
    print("\n5. 여러 차트 이미지 전송:")
    print('''
    async with TelegramSender() as sender:
        results = await sender.send_chart_images(
            chat_id=123456789,
            image_paths=["chart1.png", "chart2.png"],
            captions=["S&P 500", "NASDAQ 100"]
        )
    ''')

    print("\n" + "=" * 50)
    print("실제 전송을 위해서는 TELEGRAM_BOT_TOKEN 환경변수가 필요합니다.")


if __name__ == "__main__":
    # 문법 체크 및 예제 출력
    print("telegram_sender.py - 문법 검증 완료")
    print(f"Python 모듈 로드 성공: {__name__}")

    # 예제 실행
    asyncio.run(_example_usage())
