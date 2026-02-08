"""
visualizer.py - 경제 지표 시각화 모듈
Team C - 시각화 담당

모바일 친화적인 다크모드 차트 생성
- market_overview.png: 주요 지수 현황
- currency_chart.png: 환율 동향
- commodities_chart.png: 원자재 차트
- crypto_chart.png: 암호화폐 차트
- risk_indicator.png: 리스크 신호등
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle
import numpy as np
from datetime import datetime
import os

# 한글 폰트 설정
plt.rcParams['font.family'] = ['Malgun Gothic', 'DejaVu Sans', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# 다크모드 스타일 설정
DARK_BG = '#1a1a2e'
DARK_CARD = '#16213e'
DARK_TEXT = '#e8e8e8'
ACCENT_GREEN = '#00d26a'
ACCENT_RED = '#ff4757'
ACCENT_YELLOW = '#ffc107'
ACCENT_BLUE = '#4dabf7'
ACCENT_PURPLE = '#9775fa'
ACCENT_ORANGE = '#ff9f43'

# 출력 디렉토리
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def set_dark_style(ax, fig):
    """다크모드 스타일 적용"""
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_CARD)
    ax.tick_params(colors=DARK_TEXT, labelsize=10)
    ax.spines['bottom'].set_color(DARK_TEXT)
    ax.spines['top'].set_color(DARK_CARD)
    ax.spines['left'].set_color(DARK_TEXT)
    ax.spines['right'].set_color(DARK_CARD)
    ax.xaxis.label.set_color(DARK_TEXT)
    ax.yaxis.label.set_color(DARK_TEXT)
    ax.title.set_color(DARK_TEXT)


def create_market_overview(market_data):
    """주요 지수 현황 차트 생성"""
    fig, ax = plt.subplots(figsize=(5, 8), dpi=100)
    set_dark_style(ax, fig)

    indices = ['spx', 'ndx', 'vix', 'dxy', 'us10y']
    data_items = []

    for idx_id in indices:
        for item in market_data:
            if item['id'] == idx_id:
                data_items.append(item)
                break

    if not data_items:
        ax.text(0.5, 0.5, '데이터 없음', ha='center', va='center',
                fontsize=14, color=DARK_TEXT, transform=ax.transAxes)
        plt.savefig(os.path.join(OUTPUT_DIR, 'market_overview.png'),
                    facecolor=DARK_BG, bbox_inches='tight', pad_inches=0.3)
        plt.close()
        return

    names = [item['name'] for item in data_items]
    changes = [item['change_pct'] for item in data_items]
    colors = [ACCENT_GREEN if c >= 0 else ACCENT_RED for c in changes]

    y_pos = np.arange(len(names))
    bars = ax.barh(y_pos, changes, color=colors, height=0.6, alpha=0.85)

    for i, (bar, item) in enumerate(zip(bars, data_items)):
        width = bar.get_width()
        label_x = width + 0.1 if width >= 0 else width - 0.1
        ha = 'left' if width >= 0 else 'right'
        ax.text(label_x, bar.get_y() + bar.get_height()/2,
                f'{width:+.2f}%', ha=ha, va='center',
                fontsize=11, color=DARK_TEXT, fontweight='bold')
        ax.text(0.98, bar.get_y() + bar.get_height()/2,
                item['formatted_value'], ha='right', va='center',
                fontsize=9, color=ACCENT_BLUE, transform=ax.get_yaxis_transform())

    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=11)
    ax.axvline(x=0, color=DARK_TEXT, linewidth=0.5, alpha=0.5)
    ax.set_xlabel('변동률 (%)', fontsize=11)
    ax.set_title('주요 지수 현황', fontsize=16, fontweight='bold', pad=20)

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    fig.text(0.5, 0.02, f'업데이트: {now}', ha='center', fontsize=9, color=DARK_TEXT, alpha=0.7)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'market_overview.png'),
                facecolor=DARK_BG, bbox_inches='tight', pad_inches=0.3)
    plt.close()
    print("market_overview.png 생성 완료")


def create_currency_chart(market_data):
    """환율 동향 차트 생성"""
    fig, axes = plt.subplots(2, 2, figsize=(5, 7), dpi=100)
    fig.patch.set_facecolor(DARK_BG)

    currency_ids = ['krwusd', 'usdjpy', 'krwjpy', 'dxy']
    currency_colors = [ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_BLUE, ACCENT_GREEN]

    for i, (ax, curr_id, color) in enumerate(zip(axes.flat, currency_ids, currency_colors)):
        ax.set_facecolor(DARK_CARD)

        item = None
        for d in market_data:
            if d['id'] == curr_id:
                item = d
                break

        if item is None:
            ax.text(0.5, 0.5, 'N/A', ha='center', va='center',
                    fontsize=14, color=DARK_TEXT, transform=ax.transAxes)
            ax.set_title(curr_id, fontsize=12, color=DARK_TEXT)
            ax.axis('off')
            continue

        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-0.5, 1.5)
        ax.axis('off')

        ax.text(0, 1.4, item['name'], ha='center', va='center',
                fontsize=11, color=DARK_TEXT, fontweight='bold')
        ax.text(0, 0.8, item['formatted_value'], ha='center', va='center',
                fontsize=18, color=color, fontweight='bold')

        change_color = ACCENT_GREEN if item['change_pct'] >= 0 else ACCENT_RED
        ax.text(0, 0.35, f"{item['change_pct']:+.2f}%", ha='center', va='center',
                fontsize=14, color=change_color, fontweight='bold')

        status_text = item.get('status', 'N/A')
        ax.text(0, 0.05, status_text, ha='center', va='center',
                fontsize=10, color=ACCENT_YELLOW, fontweight='bold')

    fig.suptitle('환율 동향', fontsize=16, color=DARK_TEXT, fontweight='bold', y=0.98)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    fig.text(0.5, 0.02, f'업데이트: {now}', ha='center', fontsize=9, color=DARK_TEXT, alpha=0.7)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(os.path.join(OUTPUT_DIR, 'currency_chart.png'),
                facecolor=DARK_BG, bbox_inches='tight', pad_inches=0.3)
    plt.close()
    print("currency_chart.png 생성 완료")


def create_commodities_chart(market_data):
    """원자재 차트 생성"""
    fig, ax = plt.subplots(figsize=(5, 6), dpi=100)
    set_dark_style(ax, fig)

    commodity_ids = ['gold', 'silver', 'copper']
    commodity_colors = ['#FFD700', '#C0C0C0', '#B87333']

    items = []
    for cid in commodity_ids:
        for d in market_data:
            if d['id'] == cid:
                items.append(d)
                break

    if not items:
        ax.text(0.5, 0.5, '데이터 없음', ha='center', va='center',
                fontsize=14, color=DARK_TEXT, transform=ax.transAxes)
        plt.savefig(os.path.join(OUTPUT_DIR, 'commodities_chart.png'),
                    facecolor=DARK_BG, bbox_inches='tight', pad_inches=0.3)
        plt.close()
        return

    ax.set_xlim(0, 10)
    ax.set_ylim(0, len(items) * 2.5 + 0.5)
    ax.axis('off')

    for i, (item, color) in enumerate(zip(items, commodity_colors[:len(items)])):
        y = len(items) * 2.5 - (i * 2.5) - 1

        card = FancyBboxPatch((0.5, y - 0.8), 9, 2, boxstyle="round,pad=0.1",
                              facecolor=DARK_CARD, edgecolor=color, linewidth=2, alpha=0.8)
        ax.add_patch(card)

        circle = Circle((1.5, y + 0.2), 0.5, facecolor=color, alpha=0.3, edgecolor=color)
        ax.add_patch(circle)

        ax.text(2.5, y + 0.5, item['name'], fontsize=12, color=DARK_TEXT,
                fontweight='bold', va='center')
        ax.text(2.5, y - 0.1, item['formatted_value'], fontsize=16, color=color,
                fontweight='bold', va='center')

        change_color = ACCENT_GREEN if item['change_pct'] >= 0 else ACCENT_RED
        ax.text(8.5, y + 0.2, f"{item['change_pct']:+.2f}%",
                fontsize=14, color=change_color, fontweight='bold',
                ha='right', va='center')

    ax.set_title('원자재 시세', fontsize=16, fontweight='bold', pad=20, color=DARK_TEXT)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    fig.text(0.5, 0.02, f'업데이트: {now}', ha='center', fontsize=9, color=DARK_TEXT, alpha=0.7)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'commodities_chart.png'),
                facecolor=DARK_BG, bbox_inches='tight', pad_inches=0.3)
    plt.close()
    print("commodities_chart.png 생성 완료")


def create_crypto_chart(market_data):
    """비트코인 차트"""
    fig, ax = plt.subplots(figsize=(5, 5), dpi=100)
    set_dark_style(ax, fig)

    btc = None
    for d in market_data:
        if d['id'] == 'btc':
            btc = d
            break

    if btc is None:
        ax.text(0.5, 0.5, '데이터 없음', ha='center', va='center',
                fontsize=14, color=DARK_TEXT, transform=ax.transAxes)
        plt.savefig(os.path.join(OUTPUT_DIR, 'crypto_chart.png'),
                    facecolor=DARK_BG, bbox_inches='tight', pad_inches=0.3)
        plt.close()
        return

    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis('off')

    btc_color = '#F7931A'

    card = FancyBboxPatch((0.5, 0.5), 9, 5, boxstyle="round,pad=0.15",
                          facecolor=DARK_CARD, edgecolor=btc_color, linewidth=3, alpha=0.9)
    ax.add_patch(card)

    circle = Circle((2, 4), 0.8, facecolor=btc_color, alpha=0.2, edgecolor=btc_color, linewidth=2)
    ax.add_patch(circle)
    ax.text(2, 4, '₿', fontsize=28, color=btc_color, ha='center', va='center', fontweight='bold')

    ax.text(5, 4.5, 'Bitcoin (BTC)', fontsize=14, color=DARK_TEXT,
            fontweight='bold', ha='center', va='center')
    ax.text(5, 3.2, btc['formatted_value'], fontsize=24, color=btc_color,
            fontweight='bold', ha='center', va='center')

    change_color = ACCENT_GREEN if btc['change_pct'] >= 0 else ACCENT_RED

    change_box = FancyBboxPatch((3.5, 1.5), 3, 1, boxstyle="round,pad=0.1",
                                facecolor=change_color, alpha=0.2, edgecolor=change_color)
    ax.add_patch(change_box)
    ax.text(5, 2, f"{btc['change_pct']:+.2f}%", fontsize=16,
            color=change_color, fontweight='bold', ha='center', va='center')

    ax.set_title('암호화폐', fontsize=16, fontweight='bold', pad=20, color=DARK_TEXT)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    fig.text(0.5, 0.02, f'업데이트: {now}', ha='center', fontsize=9, color=DARK_TEXT, alpha=0.7)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'crypto_chart.png'),
                facecolor=DARK_BG, bbox_inches='tight', pad_inches=0.3)
    plt.close()
    print("crypto_chart.png 생성 완료")


def create_risk_indicator(risk_signal):
    """리스크 신호등 시각화"""
    fig, ax = plt.subplots(figsize=(5, 7), dpi=100)
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)

    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis('off')

    ax.text(5, 11.5, '리스크 신호등', fontsize=18, color=DARK_TEXT,
            fontweight='bold', ha='center', va='center')

    light_bg = FancyBboxPatch((3, 6.5), 4, 4.5, boxstyle="round,pad=0.2",
                              facecolor='#2d2d2d', edgecolor='#444', linewidth=3)
    ax.add_patch(light_bg)

    colors_off = ['#3d1010', '#3d3d10', '#103d10']
    colors_on = [ACCENT_RED, ACCENT_YELLOW, ACCENT_GREEN]
    positions = [9.8, 8.5, 7.2]

    level = risk_signal.get('level', '낮음')
    level_map = {'높음': 0, '중간': 1, '낮음': 2}
    active_idx = level_map.get(level, 2)

    for i, (y, off_color, on_color) in enumerate(zip(positions, colors_off, colors_on)):
        is_active = (i == active_idx)
        color = on_color if is_active else off_color
        alpha = 1.0 if is_active else 0.3

        circle = Circle((5, y), 0.5, facecolor=color, alpha=alpha,
                        edgecolor='#555' if not is_active else color, linewidth=2)
        ax.add_patch(circle)

        if is_active:
            glow = Circle((5, y), 0.7, facecolor=color, alpha=0.3, edgecolor='none')
            ax.add_patch(glow)

    level_colors = {'높음': ACCENT_RED, '중간': ACCENT_YELLOW, '낮음': ACCENT_GREEN}
    level_color = level_colors.get(level, DARK_TEXT)

    ax.text(5, 5.8, f'리스크: {level}', fontsize=16, color=level_color,
            fontweight='bold', ha='center', va='center')

    score = risk_signal.get('score', 0)
    ax.text(5, 5.2, f'점수: {score}점', fontsize=12, color=DARK_TEXT,
            ha='center', va='center', alpha=0.8)

    factors = risk_signal.get('factors', [])
    if factors:
        ax.text(5, 4.3, '주요 요인:', fontsize=11, color=DARK_TEXT,
                fontweight='bold', ha='center', va='center')

        for i, factor in enumerate(factors[:5]):
            display_text = factor if len(factor) < 35 else factor[:32] + '...'
            ax.text(5, 3.6 - i * 0.6, f'• {display_text}', fontsize=9,
                    color=DARK_TEXT, ha='center', va='center', alpha=0.8)
    else:
        ax.text(5, 3.5, '특별한 위험 요인 없음', fontsize=11, color=ACCENT_GREEN,
                ha='center', va='center')

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    fig.text(0.5, 0.02, f'업데이트: {now}', ha='center', fontsize=9, color=DARK_TEXT, alpha=0.7)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'risk_indicator.png'),
                facecolor=DARK_BG, bbox_inches='tight', pad_inches=0.3)
    plt.close()
    print("risk_indicator.png 생성 완료")


def create_historical_trend(symbol, name):
    """지정된 심볼의 과거 트렌드 차트 생성 (3년, 1년, 6개월, 1개월)"""
    import yfinance as yf
    import pandas as pd
    
    periods = [
        ('3y', '3년'),
        ('1y', '1년'),
        ('6mo', '6개월'),
        ('1mo', '1개월')
    ]
    
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), dpi=100)
    fig.patch.set_facecolor(DARK_BG)
    
    try:
        ticker = yf.Ticker(symbol)
        # 3년 데이터를 한 번에 가져와서 슬라이싱 (성능 최적화)
        full_hist = ticker.history(period="3y")
        
        if full_hist.empty:
            raise ValueError("데이터를 가져올 수 없습니다.")

        for i, (period_code, period_name) in enumerate(periods):
            ax = axes.flat[i]
            set_dark_style(ax, fig)
            
            # 기간별 데이터 슬라이싱
            if period_code == '3y':
                data = full_hist
            elif period_code == '1y':
                data = full_hist.last('365D')
            elif period_code == '6mo':
                data = full_hist.last('180D')
            else:
                data = full_hist.last('30D')
            
            if not data.empty:
                ax.plot(data.index, data['Close'], color=ACCENT_BLUE, linewidth=1.5)
                # 시가/종가 강조
                ax.fill_between(data.index, data['Close'], data['Close'].min(), color=ACCENT_BLUE, alpha=0.1)
                ax.set_title(f"{name} ({period_name})", fontsize=12, color=DARK_TEXT, fontweight='bold')
                
                # 가독성을 위한 그리드
                ax.grid(True, linestyle='--', alpha=0.2, color=DARK_TEXT)
            else:
                ax.text(0.5, 0.5, '데이터 없음', ha='center', va='center', color=DARK_TEXT, transform=ax.transAxes)

        filename = f"history_{symbol.replace('^', '').replace('=', '')}.png"
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.savefig(os.path.join(OUTPUT_DIR, filename), facecolor=DARK_BG, bbox_inches='tight', pad_inches=0.3)
        plt.close()
        print(f"{filename} 생성 완료")
        return filename
    except Exception as e:
        print(f"Historical chart error for {symbol}: {e}")
        plt.close()
        return None


def create_pair_trading_board(pair_signals):
    """페어 트레이딩 신호등 보드 생성 (Streamlit 스타일 2x2 카드)"""
    fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)
    
    # 축 숨기기
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # 4개 페어 순서 및 위치 좌표 (x, y)
    # 좌상(0, 5), 우상(10.5, 5), 좌하(0, 0), 우하(10.5, 0)
    layout = [
        ('gold_silver', '금-은 페어', 0, 5.2),
        ('usd_jpy', '달러-엔 캐리', 10.2, 5.2),
        ('vix_bonds_stocks', 'VIX 채권-주식', 0, 0.2),
        ('spx_ndx', 'S&P-나스닥 페어', 10.2, 0.2)
    ]
    
    # 색상 정의
    COLOR_RED = '#ff2b2b'
    COLOR_GREEN = '#00d060'
    COLOR_YELLOW = '#f7c800'  # 가독성 좋은 노랑
    
    def get_style(level):
        """레벨에 따른 색상 및 텍스트 색상 반환"""
        level = level.lower()
        if 'strong_buy' in level or 'buy_jpy' in level: return COLOR_GREEN, 'white'
        if 'buy' in level and 'stocks' not in level and 'spx' not in level and 'ndx' not in level: return COLOR_GREEN, 'white' # 단순 buy
        
        if 'strong_sell' in level or 'sell_jpy' in level: return COLOR_RED, 'white'
        if 'sell' in level and 'stocks' not in level and 'spx' not in level and 'ndx' not in level: return COLOR_RED, 'white' # 단순 sell

        # 주식/채권, 지수 간 페어는 buy/sell 의미가 상대적이어서 색상 지정이 다를 수 있으나
        # 사용자 요청 이미지 기준: 매수(초록), 매도(빨강), 중립(노랑)
        if 'buy' in level: return COLOR_GREEN, 'white'
        if 'sell' in level: return COLOR_RED, 'white'
        
        return COLOR_YELLOW, 'black'

    for key, title, x, y in layout:
        sig = pair_signals.get(key, {'signal': '데이터 없음', 'level': 'neutral', 'description': '-'})
        
        bg_color, txt_color = get_style(sig['level'])
        
        # 카드 그리기 (둥근 사각형)
        # width=9.8, height=4.6
        card = FancyBboxPatch((x, y), 9.8, 4.6, boxstyle="round,pad=0.2", 
                              facecolor=bg_color, edgecolor='none', zorder=1)
        ax.add_patch(card)
        
        # 텍스트 전처리 (이모지 제거)
        raw_signal = sig['signal']
        clean_signal = raw_signal.replace('\U0001f7e2', '').replace('\U0001f534', '').replace('\U0001f7e1', '').strip()
        
        # 1. 타이틀 (좌측 상단)
        ax.text(x + 0.5, y + 3.8, title, fontsize=12, color=txt_color, fontweight='bold', ha='left', va='center', zorder=2)
        
        # 2. 메인 신호 (중앙, 크게)
        # 글자가 길면 줄이기
        display_signal = clean_signal
        if len(display_signal) > 15:
            ax.text(x + 4.9, y + 2.5, display_signal, fontsize=14, color=txt_color, fontweight='bold', ha='center', va='center', zorder=2)
        else:
            ax.text(x + 4.9, y + 2.5, display_signal, fontsize=16, color=txt_color, fontweight='bold', ha='center', va='center', zorder=2)
            
        # 3. 상세 설명 (좌측 하단, 작게)
        ax.text(x + 0.5, y + 1.0, sig['description'], fontsize=10, color=txt_color, alpha=0.9, ha='left', va='center', zorder=2)
        
        # 아이콘 효과 (우측 상단 투명 원)
        circle = Circle((x + 8.8, y + 3.5), 0.6, color='white', alpha=0.2, zorder=2)
        ax.add_patch(circle)

    # 전체 제목
    plt.suptitle('페어 트레이딩 신호 (5단계)', fontsize=16, color='white', fontweight='bold', y=0.98)
    
    # 하단 범례 (간단히)
    legend_y = -1.5
    # ax.text(5, legend_y, "● 매수/강력매수  ● 매도/강력매도  ● 중립", color='white', ha='center', fontsize=10)
    
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    plt.savefig(os.path.join(OUTPUT_DIR, 'pair_trading_board.png'), 
                facecolor=DARK_BG, bbox_inches='tight', pad_inches=0.3)
    plt.close()
    print("pair_trading_board.png 생성 완료")


def generate_all_charts():
    """모든 차트 생성"""
    print("=" * 50)
    print("경제 지표 시각화 시작")
    print("=" * 50)

    try:
        from market_core import fetch_market_data, compute_risk_signal

        print("\n시장 데이터 가져오는 중...")
        market_data = fetch_market_data()
        print(f"  -> {len(market_data)}개 지표 로드 완료")

        print("\n리스크 신호 계산 중...")
        risk_signal = compute_risk_signal(market_data)
        
        print("\n페어 신호 분석 중...")
        from market_core import calculate_pair_trading_signals
        pair_signals = calculate_pair_trading_signals(market_data)

        print("\n차트 생성 중...")
        create_market_overview(market_data)
        # create_currency_chart(market_data) # 제거 요청
        # create_commodities_chart(market_data) # 제거 요청
        # create_crypto_chart(market_data) # 제거 요청
        create_risk_indicator(risk_signal)
        create_pair_trading_board(pair_signals) # 신규 추가
        
        print("\n과거 트렌드 차트 생성 중...")
        create_historical_trend('^GSPC', 'S&P 500')
        create_historical_trend('^NDX', 'NASDAQ 100')
        create_historical_trend('BTC-USD', 'Bitcoin')
        create_historical_trend('KRW=X', '원/달러 환율')
        create_historical_trend('GC=F', 'Gold (금 선물)')
        create_historical_trend('SI=F', 'Silver (은 선물)')

        print("\n" + "=" * 50)
        print("모든 차트 생성 완료!")
        print("=" * 50)

        return market_data, risk_signal

    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None, None


if __name__ == "__main__":
    generate_all_charts()
