import requests
import pandas as pd
import matplotlib.pyplot as plt
import time
from datetime import datetime

# 바이낸스 API에서 데이터 수집
def fetch_binance_data(symbol, interval='1d', limit=100):
    url = f"https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }
    response = requests.get(url, params=params)
    data = response.json()
    if isinstance(data, list):
        return pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume', 
                                           'close_time', 'quote_asset_volume', 'trades', 
                                           'taker_buy_base', 'taker_buy_quote', 'ignore'])
    else:
        raise ValueError(f"Failed to fetch data for {symbol}: {data}")

# 주요 코인 심볼 가져오기
def get_top_symbols():
    url = "https://fapi.binance.com/fapi/v1/ticker/price"
    response = requests.get(url).json()
    symbols = [item['symbol'] for item in response if item['symbol'].endswith('USDT')]

    # 신규 코인 및 음봉 필터링
    filtered_symbols = []
    for symbol in symbols:
        try:
            # 1일 봉 데이터 가져오기
            df = fetch_binance_data(symbol, interval='1d', limit=7)
            if len(df) < 7:  # 데이터 포인트가 7개 이하인 코인 제외
                print(f"Excluding {symbol}: Less than 7 days of data ({len(df)} days)")
                continue

            # 직전 1일 봉 확인
            df['open'] = df['open'].astype(float)
            df['close'] = df['close'].astype(float)
            if df['close'].iloc[-2] < df['open'].iloc[-2]:  # 두 번째 마지막 봉 확인
                print(f"Excluding {symbol}: Previous daily candle is bearish")
                continue

            filtered_symbols.append(symbol)
        except Exception as e:
            print(f"Error fetching daily data for {symbol}: {e}")
    return filtered_symbols

# 1시간 봉 데이터를 기반으로 양봉만 필터링하여 변화율 계산
def prepare_data(symbols):
    data = {}
    for symbol in symbols:
        try:
            df = fetch_binance_data(symbol, interval='1h', limit=5)
            df['open'] = df['open'].astype(float)
            df['close'] = df['close'].astype(float)
            
            # 데이터 포인트가 충분하지 않으면 제외
            if len(df) < 5:
                print(f"Skipping {symbol}: Insufficient data")
                continue
            
            # 양봉 필터링: 종가(close) > 시가(open)
            if df['close'].iloc[-1] <= df['open'].iloc[-1]:  # 마지막 봉이 양봉이 아닌 경우 제외
                print(f"Excluding {symbol}: Not a bullish candle")
                continue

            # 변화율 계산
            df['change_rate'] = df['close'].pct_change() * 100
            change_rate = df['change_rate'].iloc[-1]  # 마지막 봉의 변화율
            
            # 변화율이 4% 이상인 경우만 포함
            if change_rate >= 4:
                data[symbol] = change_rate
            else:
                print(f"Excluding {symbol}: Change rate {change_rate:.2f}% below 4%")
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
    return pd.Series(data).sort_values(ascending=False).head(10)

# 실시간 차트 표시
def update_chart_live():
    symbols = get_top_symbols()
    plt.ion()  # 인터랙티브 모드 활성화
    fig, ax = plt.subplots(figsize=(10, 6))

    while True:
        print(f"Fetching data at {datetime.now()}")
        top_data = prepare_data(symbols)

        # 데이터 준비
        df = pd.DataFrame(top_data).reset_index()
        df.columns = ['symbol', 'change_rate']
        df = df.sort_values('change_rate', ascending=True)  # 가장 큰 값을 맨 위에 오도록 정렬

        # 차트 업데이트
        ax.clear()
        ax.barh(df['symbol'], df['change_rate'], color='skyblue')
        ax.set_title(f"Top 10 Bullish Coins (Change Rate ≥ 4%) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        ax.set_xlabel("Change Rate (%)")
        ax.set_ylabel("Coin Symbol")
        plt.tight_layout()

        # 화면 갱신
        plt.pause(60)

# 실행
if __name__ == "__main__":
    update_chart_live()
