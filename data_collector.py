"""
data_collector.py - Economic Indicators Data Collector
Team B - 경제 데이터 수집 담당

수집 대상:
- 미국: S&P500, NASDAQ, 다우존스, 10년물 국채금리, VIX
- 한국: KOSPI, KOSDAQ, 원/달러 환율
- 원자재: 금(Gold), 은(Silver), 구리(Copper), 원유(WTI)
- 암호화폐: Bitcoin, Ethereum
- 환율: USD/KRW, USD/JPY, EUR/USD
"""

import yfinance as yf
import json
from datetime import datetime
from typing import Dict, Any, List


INDICATORS = {
    "us_indices": {
        "SP500": {"symbol": "^GSPC", "name": "S&P 500", "category": "미국 주가지수"},
        "NASDAQ": {"symbol": "^IXIC", "name": "NASDAQ Composite", "category": "미국 주가지수"},
        "DOW": {"symbol": "^DJI", "name": "Dow Jones Industrial", "category": "미국 주가지수"},
        "VIX": {"symbol": "^VIX", "name": "VIX (변동성 지수)", "category": "미국 주가지수"},
        "US10Y": {"symbol": "^TNX", "name": "미국 10년물 국채금리", "category": "채권"},
    },
    "kr_indices": {
        "KOSPI": {"symbol": "^KS11", "name": "KOSPI", "category": "한국 주가지수"},
        "KOSDAQ": {"symbol": "^KQ11", "name": "KOSDAQ", "category": "한국 주가지수"},
    },
    "commodities": {
        "GOLD": {"symbol": "GC=F", "name": "금 (Gold)", "category": "원자재"},
        "SILVER": {"symbol": "SI=F", "name": "은 (Silver)", "category": "원자재"},
        "COPPER": {"symbol": "HG=F", "name": "구리 (Copper)", "category": "원자재"},
        "WTI": {"symbol": "CL=F", "name": "원유 (WTI)", "category": "원자재"},
    },
    "crypto": {
        "BTC": {"symbol": "BTC-USD", "name": "Bitcoin", "category": "암호화폐"},
        "ETH": {"symbol": "ETH-USD", "name": "Ethereum", "category": "암호화폐"},
    },
    "forex": {
        "USDKRW": {"symbol": "KRW=X", "name": "USD/KRW (원/달러)", "category": "환율"},
        "USDJPY": {"symbol": "JPY=X", "name": "USD/JPY (엔/달러)", "category": "환율"},
        "EURUSD": {"symbol": "EURUSD=X", "name": "EUR/USD (유로/달러)", "category": "환율"},
    },
}


def determine_trend(change_pct: float) -> str:
    """변동률에 따른 트렌드 결정"""
    if change_pct > 2.0:
        return "급등"
    elif change_pct > 0.5:
        return "상승"
    elif change_pct > -0.5:
        return "보합"
    elif change_pct > -2.0:
        return "하락"
    else:
        return "급락"


def get_trend_emoji(trend: str) -> str:
    """트렌드에 해당하는 이모지 반환"""
    emoji_map = {"급등": "🔺🔺", "상승": "🔺", "보합": "➡️", "하락": "🔻", "급락": "🔻🔻"}
    return emoji_map.get(trend, "?")


def fetch_single_indicator(symbol: str, name: str, category: str) -> Dict[str, Any]:
    """단일 지표 데이터 수집"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        if hist.empty:
            return {"name": name, "symbol": symbol, "category": category, "status": "error", "error": "데이터 없음"}

        current_price = float(hist['Close'].iloc[-1])
        if len(hist) >= 2:
            previous_price = float(hist['Close'].iloc[-2])
            change = current_price - previous_price
            change_pct = ((current_price - previous_price) / previous_price) * 100
        else:
            previous_price = current_price
            change = 0
            change_pct = 0

        high_5d = float(hist['High'].max())
        low_5d = float(hist['Low'].min())
        avg_5d = float(hist['Close'].mean())
        trend = determine_trend(change_pct)

        return {
            "name": name, "symbol": symbol, "category": category,
            "current_price": round(current_price, 4), "previous_price": round(previous_price, 4),
            "change": round(change, 4), "change_pct": round(change_pct, 2),
            "trend": trend, "trend_emoji": get_trend_emoji(trend),
            "high_5d": round(high_5d, 4), "low_5d": round(low_5d, 4), "avg_5d": round(avg_5d, 4),
            "status": "success", "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        return {"name": name, "symbol": symbol, "category": category, "status": "error", "error": str(e)}


def collect_all_data() -> Dict[str, Any]:
    """모든 경제 지표 데이터 수집"""
    print("=" * 60)
    print("경제 지표 데이터 수집 시작")
    print(f"수집 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    collected_data = {
        "collection_timestamp": datetime.now().isoformat(),
        "collection_date": datetime.now().strftime("%Y-%m-%d"),
        "collection_time": datetime.now().strftime("%H:%M:%S"),
        "data": {},
        "summary": {"total_indicators": 0, "successful": 0, "failed": 0, "categories": {}}
    }

    total_count = success_count = fail_count = 0

    for group_name, indicators in INDICATORS.items():
        print(f"\n[{group_name}] 수집 중...")
        collected_data["data"][group_name] = {}

        for indicator_id, info in indicators.items():
            total_count += 1
            print(f"  - {info['name']} ({info['symbol']})...", end=" ")

            result = fetch_single_indicator(info["symbol"], info["name"], info["category"])
            collected_data["data"][group_name][indicator_id] = result

            if result["status"] == "success":
                success_count += 1
                print(f"완료 [{result['current_price']:.2f}] ({result['change_pct']:+.2f}%)")
            else:
                fail_count += 1
                print(f"실패 - {result.get('error', 'Unknown error')}")

    collected_data["summary"]["total_indicators"] = total_count
    collected_data["summary"]["successful"] = success_count
    collected_data["summary"]["failed"] = fail_count

    # 카테고리별 요약
    for group_name, indicators in collected_data["data"].items():
        category_summary = []
        for indicator_id, data in indicators.items():
            if data["status"] == "success":
                category_summary.append({
                    "id": indicator_id,
                    "name": data["name"],
                    "price": data["current_price"],
                    "change_pct": data["change_pct"],
                    "trend": data["trend"]
                })
        collected_data["summary"]["categories"][group_name] = category_summary

    print("\n" + "=" * 60)
    print(f"데이터 수집 완료: 총 {total_count}개 지표 중 {success_count}개 성공, {fail_count}개 실패")
    print("=" * 60)

    return collected_data


def save_to_json(data: Dict[str, Any], filepath: str = "collected_data.json") -> None:
    """수집된 데이터를 JSON 파일로 저장"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n데이터가 {filepath}에 저장되었습니다.")


def print_summary_table(data: Dict[str, Any]) -> None:
    """수집된 데이터 요약 테이블 출력"""
    print("\n" + "=" * 80)
    print("                          경제 지표 요약 테이블")
    print("=" * 80)
    print(f"{'카테고리':<15} | {'지표명':<25} | {'현재가':<15} | {'변동률':<10} | {'트렌드'}")
    print("-" * 80)

    for group_name, indicators in data["data"].items():
        for indicator_id, info in indicators.items():
            if info["status"] == "success":
                print(f"{info['category']:<15} | {info['name']:<25} | {info['current_price']:<15.4f} | {info['change_pct']:+.2f}% | {info['trend']}")

    print("=" * 80)


def get_market_status(data: Dict[str, Any]) -> Dict[str, str]:
    """시장 상태 분석"""
    status = {
        "overall": "정상",
        "us_market": "정상",
        "kr_market": "정상",
        "commodities": "정상",
        "crypto": "정상",
        "forex": "정상"
    }

    try:
        vix = data["data"]["us_indices"]["VIX"]
        if vix["status"] == "success":
            vix_level = vix["current_price"]
            if vix_level > 30:
                status["overall"] = "고위험"
                status["us_market"] = "고위험"
            elif vix_level > 20:
                status["overall"] = "주의"
                status["us_market"] = "주의"
    except KeyError:
        pass

    return status


if __name__ == "__main__":
    data = collect_all_data()
    save_to_json(data, "collected_data.json")
    print_summary_table(data)
    status = get_market_status(data)
    print(f"\n시장 상태: {status['overall']}")
