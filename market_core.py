"""
market_core.py - Pure Python market data logic (no Streamlit dependency)

Streamlit 대시보드와 Telegram 봇 모두에서 재사용할 수 있는 핵심 시장 데이터 로직.
"""
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional
import time
import threading

# 지수 데이터 설정
TICKER_MAP = {
    'gold': {'symbol': 'GC=F', 'name': '금 (Gold)', 'ticker': 'XAU/USD'},
    'silver': {'symbol': 'SI=F', 'name': '은 (Silver)', 'ticker': 'XAG/USD'},
    'copper': {'symbol': 'HG=F', 'name': '구리 (Copper)', 'ticker': 'HG/USD'},
    'dxy': {'symbol': 'DX-Y.NYB', 'name': '달러 지수 (DXY)', 'ticker': 'DXY'},
    'us10y': {'symbol': '^TNX', 'name': '미 10년물 채권', 'ticker': 'US10Y'},
    'btc': {'symbol': 'BTC-USD', 'name': '비트코인', 'ticker': 'BTC/USD'},
    'krwjpy': {'symbol': 'KRWJPY=X', 'name': '원-엔 환율', 'ticker': 'KRW/JPY'},
    'krwusd': {'symbol': 'KRW=X', 'name': '원-달러 환율', 'ticker': 'USD/KRW'},
    'usdjpy': {'symbol': 'JPY=X', 'name': '달러-엔 환율', 'ticker': 'USD/JPY'},
    'spx': {'symbol': '^GSPC', 'name': 'S&P 500', 'ticker': 'S&P 500'},
    'ndx': {'symbol': '^NDX', 'name': '나스닥 100', 'ticker': 'NASDAQ 100'},
    'vix': {'symbol': '^VIX', 'name': '변동성 지수 (VIX)', 'ticker': 'VIX'},
}

# Simple in-memory cache
_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = 60  # seconds


def get_unit(symbol):
    if symbol in ['^TNX']:
        return 'percentage'
    elif symbol in ['DX-Y.NYB', '^SKEW', '^VIX', '^GSPC']:
        return 'points'
    return 'currency'


def format_value(value, unit):
    if unit == 'percentage':
        return f"{value:.2f}%"
    elif unit == 'points':
        return f"{value:.2f}"
    else:
        return f"${value:,.2f}"


def get_item(data, key):
    for item in data:
        if item['id'] == key:
            return item
    return None


def fetch_market_data():
    """시장 데이터 가져오기 (캐시 포함)"""
    with _cache_lock:
        cached = _cache.get('market_data')
        if cached and (time.time() - cached['ts']) < CACHE_TTL:
            return cached['data']

    if not HAS_YFINANCE:
        raise RuntimeError("yfinance가 설치되지 않았습니다. pip install yfinance")

    data = []
    for key, info in TICKER_MAP.items():
        try:
            ticker = yf.Ticker(info['symbol'])
            hist = ticker.history(period="2d")

            if len(hist) >= 2:
                current_price = hist['Close'].iloc[-1]
                previous_price = hist['Close'].iloc[-2]
                change_pct = ((current_price - previous_price) / previous_price) * 100
            else:
                current_price = hist['Close'].iloc[-1] if not hist.empty else 0
                previous_price = current_price
                change_pct = 0

            unit = get_unit(info['symbol'])
            status = "안정" if abs(change_pct) < 1 else ("상승" if change_pct > 0 else "하락")

            data.append({
                'id': key,
                'name': info['name'],
                'ticker': info['ticker'],
                'current_value': current_price,
                'previous_value': previous_price,
                'change_pct': change_pct,
                'unit': unit,
                'status': status,
                'formatted_value': format_value(current_price, unit),
            })
        except Exception:
            data.append({
                'id': key,
                'name': info['name'],
                'ticker': info['ticker'],
                'current_value': 0,
                'previous_value': 0,
                'change_pct': 0,
                'unit': get_unit(info['symbol']),
                'status': "오류",
                'formatted_value': "N/A",
            })

    with _cache_lock:
        _cache['market_data'] = {'data': data, 'ts': time.time()}
    return data


def compute_risk_signal(market_data):
    """위험 점수와 신호등 색상을 계산"""
    score = 0
    factors = []

    spx = get_item(market_data, 'spx')
    if spx:
        spx_chg = spx['change_pct']
        if spx_chg < -3.0:
            score += 3; factors.append(f"S&P500 급락 ({spx_chg:+.2f}%) +3")
        elif spx_chg < -1.5:
            score += 2; factors.append(f"S&P500 하락 ({spx_chg:+.2f}%) +2")
        elif spx_chg < -0.5:
            score += 1; factors.append(f"S&P500 약세 ({spx_chg:+.2f}%) +1")

    ndx = get_item(market_data, 'ndx')
    if ndx:
        ndx_chg = ndx['change_pct']
        if ndx_chg < -3.0:
            score += 3; factors.append(f"나스닥100 급락 ({ndx_chg:+.2f}%) +3")
        elif ndx_chg < -1.5:
            score += 2; factors.append(f"나스닥100 하락 ({ndx_chg:+.2f}%) +2")
        elif ndx_chg < -0.5:
            score += 1; factors.append(f"나스닥100 약세 ({ndx_chg:+.2f}%) +1")

    if spx and ndx:
        divergence = abs(spx['change_pct'] - ndx['change_pct'])
        if divergence > 2.0:
            score += 2; factors.append(f"S&P-나스닥 디버전스 ({divergence:.2f}%p) +2")
        elif divergence > 1.0:
            score += 1; factors.append(f"지수 간 괴리 확대 ({divergence:.2f}%p) +1")

    vix = get_item(market_data, 'vix')
    if vix and vix['current_value']:
        vix_level = vix['current_value']
        if vix_level > 35:
            score += 3; factors.append(f"VIX 매우 높음 ({vix_level:.1f}) +3")
        elif vix_level > 25:
            score += 2; factors.append(f"VIX 높음 ({vix_level:.1f}) +2")
        elif vix_level > 15:
            score += 1; factors.append(f"VIX 다소 높음 ({vix_level:.1f}) +1")

    dxy = get_item(market_data, 'dxy')
    if dxy:
        dxy_chg = dxy['change_pct']
        dxy_level = dxy['current_value']
        if dxy_chg > 1.0:
            score += 2; factors.append(f"달러지수 급등 ({dxy_chg:+.2f}%) +2")
        elif dxy_chg > 0.5:
            score += 1; factors.append(f"달러지수 상승 ({dxy_chg:+.2f}%) +1")
        if dxy_level > 110:
            score += 2; factors.append(f"달러 매우 강세 ({dxy_level:.1f}) +2")
        elif dxy_level > 105:
            score += 1; factors.append(f"달러 강세 ({dxy_level:.1f}) +1")

    krwusd = get_item(market_data, 'krwusd')
    usdjpy = get_item(market_data, 'usdjpy')
    krwjpy = get_item(market_data, 'krwjpy')

    if dxy and krwusd and usdjpy and krwjpy:
        dxy_chg = dxy['change_pct']
        krwjpy_chg = krwjpy['change_pct']
        if dxy_chg > 0.5 and krwjpy_chg < -1.0:
            score += 2; factors.append(f"달러 강세 시 원화 상대적 급락 ({krwjpy_chg:+.2f}%) +2")
        elif dxy_chg > 0.3 and krwjpy_chg < -0.5:
            score += 1; factors.append(f"달러 강세 시 원화 상대적 약세 ({krwjpy_chg:+.2f}%) +1")
        if dxy_chg < -0.5 and krwjpy_chg < -1.0:
            score += 1; factors.append(f"달러 약세에도 원화 부진 ({krwjpy_chg:+.2f}%) +1")

    if krwusd:
        krwusd_chg = krwusd['change_pct']
        if krwusd_chg > 2.0:
            score += 3; factors.append(f"원화 급락 대비 달러 ({krwusd_chg:+.2f}%) +3")
        elif krwusd_chg > 1.0:
            score += 2; factors.append(f"원화 약세 대비 달러 ({krwusd_chg:+.2f}%) +2")
        elif krwusd_chg > 0.5:
            score += 1; factors.append(f"원화 하락 대비 달러 ({krwusd_chg:+.2f}%) +1")
        elif krwusd_chg < -2.0:
            score += 2; factors.append(f"원화 급등 대비 달러 ({krwusd_chg:+.2f}%) +2")
        elif krwusd_chg < -1.0:
            score += 1; factors.append(f"원화 강세 대비 달러 ({krwusd_chg:+.2f}%) +1")

    if usdjpy:
        usdjpy_chg = usdjpy['change_pct']
        if usdjpy_chg > 2.0:
            score += 2; factors.append(f"엔화 급락 ({usdjpy_chg:+.2f}%) +2")
        elif usdjpy_chg > 1.0:
            score += 1; factors.append(f"엔화 약세 ({usdjpy_chg:+.2f}%) +1")
        elif usdjpy_chg < -2.0:
            score += 3; factors.append(f"엔화 급등, 캐리 청산 ({usdjpy_chg:+.2f}%) +3")
        elif usdjpy_chg < -1.0:
            score += 2; factors.append(f"엔화 강세 ({usdjpy_chg:+.2f}%) +2")

    if krwjpy:
        krwjpy_chg = krwjpy['change_pct']
        if krwjpy_chg < -2.0:
            score += 2; factors.append(f"원화 구조적 약세 ({krwjpy_chg:+.2f}%) +2")
        elif krwjpy_chg < -1.0:
            score += 1; factors.append(f"원화 대비 엔화 강세 ({krwjpy_chg:+.2f}%) +1")

    us10y = get_item(market_data, 'us10y')
    if us10y and us10y['current_value'] is not None and us10y['previous_value'] is not None:
        move_bp = abs(us10y['current_value'] - us10y['previous_value'])
        if move_bp > 0.20:
            score += 2; factors.append(f"미10년물 급변 ({move_bp:.2f}p) +2")
        elif move_bp > 0.10:
            score += 1; factors.append(f"미10년물 변동 확대 ({move_bp:.2f}p) +1")

    gold = get_item(market_data, 'gold')
    if gold:
        gchg = gold['change_pct']
        if gchg > 2.0:
            score += 2; factors.append(f"금 강세 ({gchg:+.2f}%) +2")
        elif gchg > 1.0:
            score += 1; factors.append(f"금 상승 ({gchg:+.2f}%) +1")

    silver = get_item(market_data, 'silver')
    if silver:
        schg = silver['change_pct']
        if schg > 3.0:
            score += 2; factors.append(f"은 강세 ({schg:+.2f}%) +2")
        elif schg > 1.5:
            score += 1; factors.append(f"은 상승 ({schg:+.2f}%) +1")

    copper = get_item(market_data, 'copper')
    if copper:
        cchg = copper['change_pct']
        if cchg > 3.0:
            score += 2; factors.append(f"구리 급등 (경기 과열/인플레) ({cchg:+.2f}%) +2")
        elif cchg > 1.5:
            score += 1; factors.append(f"구리 상승 ({cchg:+.2f}%) +1")
        elif cchg < -3.0:
            score += 1; factors.append(f"구리 급락 (경기 침체 우려) ({cchg:+.2f}%) +1")

    btc = get_item(market_data, 'btc')
    if btc:
        bchg = btc['change_pct']
        if bchg > 6.0:
            score += 2; factors.append(f"BTC 급등 ({bchg:+.2f}%) +2")
        elif bchg > 3.0:
            score += 1; factors.append(f"BTC 상승 ({bchg:+.2f}%) +1")

    if score >= 6:
        level = '높음'
        color = '#dc3545'
        emoji = '\U0001f534'  # red circle
    elif score >= 3:
        level = '중간'
        color = '#ffc107'
        emoji = '\U0001f7e1'  # yellow circle
    else:
        level = '낮음'
        color = '#28a745'
        emoji = '\U0001f7e2'  # green circle

    return {'score': score, 'level': level, 'color': color, 'emoji': emoji, 'factors': factors}


def calculate_pair_trading_signals(market_data):
    """페어 트레이딩 신호 계산 (5단계)"""
    signals = {}

    gold = get_item(market_data, 'gold')
    silver = get_item(market_data, 'silver')
    if gold and silver:
        gold_value = gold['current_value']
        silver_value = silver['current_value']
        gold_silver_ratio = gold_value / silver_value if silver_value > 0 else 0

        if gold_silver_ratio > 90:
            signal = '\U0001f7e2\U0001f7e2 은 강력매수 / 금 강력매도'
            level = 'strong_buy'
            description = f'금은비율 {gold_silver_ratio:.1f} (매우 높음)'
        elif gold_silver_ratio > 82:
            signal = '\U0001f7e2 은 매수 / 금 매도'
            level = 'buy'
            description = f'금은비율 {gold_silver_ratio:.1f} (높음)'
        elif gold_silver_ratio < 60:
            signal = '\U0001f534\U0001f534 금 강력매수 / 은 강력매도'
            level = 'strong_sell'
            description = f'금은비율 {gold_silver_ratio:.1f} (매우 낮음)'
        elif gold_silver_ratio < 68:
            signal = '\U0001f534 금 매수 / 은 매도'
            level = 'sell'
            description = f'금은비율 {gold_silver_ratio:.1f} (낮음)'
        else:
            signal = '\U0001f7e1 중립'
            level = 'neutral'
            description = f'금은비율 {gold_silver_ratio:.1f} (정상 범위 68-82)'

        signals['gold_silver'] = {
            'name': '금-은 페어',
            'signal': signal, 'level': level, 'description': description,
            'ratio': gold_silver_ratio
        }

    vix = get_item(market_data, 'vix')
    if vix:
        vix_level = vix['current_value']
        vix_chg = vix.get('change_pct', 0)

        if vix_level > 35 or (vix_level > 30 and vix_chg > 10):
            signal = '\U0001f534\U0001f534 주식 강력매수 / 채권 강력매도'
            level = 'strong_buy_stocks'
            description = f'VIX {vix_level:.1f} (극도의 공포)'
        elif vix_level > 25 or (vix_level > 22 and vix_chg > 5):
            signal = '\U0001f534 주식 매수 / 채권 매도'
            level = 'buy_stocks'
            description = f'VIX {vix_level:.1f} (높은 공포)'
        elif vix_level < 12:
            signal = '\U0001f7e2\U0001f7e2 채권 강력매수 / 주식 강력매도'
            level = 'strong_sell_stocks'
            description = f'VIX {vix_level:.1f} (극도의 낙관)'
        elif vix_level < 15:
            signal = '\U0001f7e2 채권 매수 / 주식 매도'
            level = 'sell_stocks'
            description = f'VIX {vix_level:.1f} (낮은 공포)'
        else:
            signal = '\U0001f7e1 중립'
            level = 'neutral'
            description = f'VIX {vix_level:.1f} (정상 범위 15-25)'

        signals['vix_bonds_stocks'] = {
            'name': 'VIX 채권-주식',
            'signal': signal, 'level': level, 'description': description,
            'vix_level': vix_level
        }

    usdjpy = get_item(market_data, 'usdjpy')
    if usdjpy:
        usdjpy_value = usdjpy['current_value']
        usdjpy_chg = usdjpy['change_pct']

        if usdjpy_value > 160 or (usdjpy_value > 155 and usdjpy_chg > 2):
            signal = '\U0001f7e2\U0001f7e2 엔화 강력매수 / 달러 강력매도'
            level = 'strong_buy_jpy'
            description = f'USD/JPY {usdjpy_value:.2f} (엔화 극약세)'
        elif usdjpy_value > 152 or (usdjpy_value > 148 and usdjpy_chg > 1):
            signal = '\U0001f7e2 엔화 매수 / 달러 매도'
            level = 'buy_jpy'
            description = f'USD/JPY {usdjpy_value:.2f} (엔화 과도한 약세)'
        elif usdjpy_value < 135 or (usdjpy_value < 140 and usdjpy_chg < -2):
            signal = '\U0001f534\U0001f534 달러 강력매수 / 엔화 강력매도'
            level = 'strong_sell_jpy'
            description = f'USD/JPY {usdjpy_value:.2f} (엔화 극강세)'
        elif usdjpy_value < 142 or (usdjpy_value < 145 and usdjpy_chg < -1):
            signal = '\U0001f534 달러 매수 / 엔화 매도'
            level = 'sell_jpy'
            description = f'USD/JPY {usdjpy_value:.2f} (엔화 과도한 강세)'
        else:
            signal = '\U0001f7e1 중립'
            level = 'neutral'
            description = f'USD/JPY {usdjpy_value:.2f} (정상 범위 142-152)'

        signals['usd_jpy'] = {
            'name': '달러-엔 캐리',
            'signal': signal, 'level': level, 'description': description,
            'usdjpy_value': usdjpy_value
        }

    spx = get_item(market_data, 'spx')
    ndx = get_item(market_data, 'ndx')
    if spx and ndx:
        performance_gap = ndx['change_pct'] - spx['change_pct']

        if performance_gap > 3.0:
            signal = '\U0001f7e2\U0001f7e2 S&P 강력매수 / 나스닥 강력매도'
            level = 'strong_buy_spx'
            description = f'격차 {performance_gap:+.2f}%p (기술주 극과열)'
        elif performance_gap > 1.5:
            signal = '\U0001f7e2 S&P 매수 / 나스닥 매도'
            level = 'buy_spx'
            description = f'격차 {performance_gap:+.2f}%p (기술주 과열)'
        elif performance_gap < -3.0:
            signal = '\U0001f534\U0001f534 나스닥 강력매수 / S&P 강력매도'
            level = 'strong_buy_ndx'
            description = f'격차 {performance_gap:+.2f}%p (기술주 극약세)'
        elif performance_gap < -1.5:
            signal = '\U0001f534 나스닥 매수 / S&P 매도'
            level = 'buy_ndx'
            description = f'격차 {performance_gap:+.2f}%p (기술주 약세)'
        else:
            signal = '\U0001f7e1 중립'
            level = 'neutral'
            description = f'격차 {performance_gap:+.2f}%p (균형 범위)'

        signals['spx_ndx'] = {
            'name': 'S&P-나스닥 페어',
            'signal': signal, 'level': level, 'description': description,
            'performance_gap': performance_gap
        }

    return signals


def fetch_economy_news(count=10):
    """네이버 경제 뉴스 가져오기"""
    try:
        url = "https://news.naver.com/section/101"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        news_items = soup.select("div.sa_text a.sa_text_title")

        results = []
        for item in news_items[:count]:
            title = item.get_text(strip=True)
            link = item['href']
            title = re.sub(r'[<>&"]', '', title)
            results.append({'title': title, 'link': link})
        return results
    except Exception:
        return []


def fetch_ai_news(count=10):
    """Google News RSS에서 AI 뉴스 가져오기"""
    try:
        url = "https://news.google.com/rss/search?q=AI+%EC%9D%B8%EA%B3%B5%EC%A7%80%EB%8A%A5&hl=ko&gl=KR&ceid=KR:ko"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(res.text, "xml")
        items = soup.find_all("item")

        results = []
        for item in items[:count]:
            title = item.title.get_text(strip=True)
            link = str(item.link.string or "")
            source = item.source
            source_name = source.get_text(strip=True) if source else ""
            title = re.sub(r'[<>&"]', '', title)
            if source_name:
                title = re.sub(r'\s*-\s*' + re.escape(source_name) + r'$', '', title)
            results.append({'title': title, 'link': link, 'source': source_name})
        return results
    except Exception:
        return []


def clear_cache():
    """캐시 초기화"""
    with _cache_lock:
        _cache.clear()
