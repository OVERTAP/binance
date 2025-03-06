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

    # 신규 코인 제외 (1일 봉 데이터가 30개 이하인 코인)
    filtered_symbols = []
    for symbol in symbols:
        try:
            df = fetch_binance_data(symbol, interval='1d', limit=30)
            if len(df) >= 30:  # 데이터 포인트가 30개 이상인 코인만 포함
                filtered_symbols.append(symbol)
            else:
                print(f"Excluding {symbol}: Less than 30 days of data ({len(df)} days)")
        except Exception as e:
            print(f"Error fetching daily data for {symbol}: {e}")
    return filtered_symbols

# 1시간 봉 데이터를 기반으로 변화율 계산
def prepare_data(symbols):
    data = {}
    for symbol in symbols:
        try:
            df = fetch_binance_data(symbol, interval='1h', limit=5)
            df['close'] = df['close'].astype(float)
            
            if len(df) < 5:
                print(f"Skipping {symbol}: Insufficient data")
                continue
            
            df['change_rate'] = df['close'].pct_change() * 100
            data[symbol] = df['change_rate'].iloc[-1]  # 마지막 봉의 변화율
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
        df = df.sort_values('change_rate', ascending=True)

        # 차트 업데이트
        ax.clear()
        ax.barh(df['symbol'], df['change_rate'], color='skyblue')
        ax.set_title(f"Top 10 Coins by Change Rate - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        ax.set_xlabel("Change Rate (%)")
        ax.set_ylabel("Coin Symbol")
        plt.tight_layout()

        # 화면 갱신
        plt.pause(60)

# 실행
if __name__ == "__main__":
    update_chart_live()
