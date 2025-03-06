import requests
import pandas as pd
import time
from datetime import datetime
from binance.client import Client
from binance.enums import *

# 바이낸스 API 키
API_KEY = 'tCHe32fujcnwtUspPdeIDkLGcGsH0v7MFwz45b5hB0L71PPEbqIRbNJF1iH7CkPl'
SECRET_KEY = 'y4f8qeeL9QUTN4pFbHrq4TmWaWOzIg84pSqqu71jsWDzReDgrUubvh9ywtEL9uq6'

# 바이낸스 클라이언트 초기화
client = Client(API_KEY, SECRET_KEY)

# 손절된 코인 기록
stopped_symbols = set()

# API 연결 상태 확인
def check_api_connection():
    try:
        client.ping()
        print(f"[{datetime.now()}] API connection successful.")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] Failed to connect to API: {e}")
        return False

# 주요 코인 심볼 가져오기 (선물 시장에 존재하는 심볼만)
def get_top_symbols():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    response = requests.get(url).json()
    symbols = [item['symbol'] for item in response['symbols'] if item['contractType'] == "PERPETUAL"]
    return symbols

# 신규 코인 및 음봉 필터링
def filter_symbols(symbols):
    filtered_symbols = []
    for symbol in symbols:
        try:
            # 손절된 코인은 제외
            if symbol in stopped_symbols:
                print(f"Excluding {symbol}: Previously stopped out.")
                continue

            # 1일 봉 데이터 가져오기
            df = fetch_binance_data(symbol, interval='1d', limit=7)
            
            # 데이터 포인트가 7개 이하인 코인 제외
            if len(df) < 7:
                print(f"Excluding {symbol}: Less than 7 days of data ({len(df)} days)")
                continue

            # 데이터 타입 변환
            df['open'] = df['open'].astype(float)
            df['close'] = df['close'].astype(float)

            # 직전 1일 봉이 음봉인 경우 제외
            # if df['close'].iloc[-2] < df['open'].iloc[-2]:
            #     print(f"Excluding {symbol}: Previous daily candle is bearish")
            #     continue

            filtered_symbols.append(symbol)
        except Exception as e:
            print(f"Error fetching daily data for {symbol}: {e}")
    return filtered_symbols

# 바이낸스 API에서 데이터 수집
def fetch_binance_data(symbol, interval='1h', limit=100):
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

# 포지션 진입 정보 저장하기
positions = {}

# 포지션 관리: 손절 조건 확인 d
def check_stop_loss():
    try:
        for symbol, position_data in list(positions.items()):
            current_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
            entry_price = position_data['entry_price']
            if current_price <= entry_price:  # 현재 가격이 진입 시가 이하
                print(f"[{datetime.now()}] {symbol} hit stop-loss at {current_price}, closing position.")
                
                # 시장가 손절
                client.futures_create_order(
                    symbol=symbol,
                    side=SIDE_SELL,  # 롱 포지션을 종료
                    type=ORDER_TYPE_MARKET,
                    quantity=position_data['quantity']
                )
                # 손절된 코인으로 기록
                stopped_symbols.add(symbol)
                # 포지션 삭제
                del positions[symbol]
    except Exception as e:
        print(f"[{datetime.now()}] Error in stop-loss check: {e}")

# 매수 및 익절 실행
def place_order(symbol, leverage=5, target_profit=10):
    try:
        # 레버리지 설정
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
        print(f"[{datetime.now()}] Leverage set to {leverage}x for {symbol}")
        
        # 계좌 잔고 확인 및 주문 수량 계산
        balance = float(client.futures_account_balance()[0]['balance'])
        market_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
        quantity = round(balance / market_price * leverage * 0.99, 3)  # 99% 자산 사용
        
        # 시장가 매수
        order = client.futures_create_order(
            symbol=symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=quantity
        )
        print(f"[{datetime.now()}] Market buy order placed for {symbol}: {order}")

        # 포지션 진입 정보 저장
        positions[symbol] = {'entry_price': market_price, 'quantity': quantity}
        print(f"[{datetime.now()}] Position opened for {symbol} at entry price {market_price}")

        # 익절 주문
        take_profit_price = round(market_price * (1 + target_profit / 100), 2)
        tp_order = client.futures_create_order(
            symbol=symbol,
            side=SIDE_SELL,
            type=ORDER_TYPE_LIMIT,
            quantity=quantity,
            price=take_profit_price,
            timeInForce=TIME_IN_FORCE_GTC
        )
        print(f"[{datetime.now()}] Take-profit order placed at {take_profit_price} for {symbol}")

    except Exception as e:
        print(f"[{datetime.now()}] Error placing order for {symbol}: {e}")

# 1시간 봉 데이터를 기반으로 양봉만 필터링하여 변화율 계산
def prepare_data(symbols):
    for symbol in symbols:
        try:
            # 손절된 코인 제외
            if symbol in stopped_symbols:
                print(f"Skipping {symbol}: Previously stopped out.")
                continue

            df = fetch_binance_data(symbol, interval='1h', limit=5)
            df['open'] = df['open'].astype(float)
            df['close'] = df['close'].astype(float)
            
            # 양봉 필터링: 종가(close) > 시가(open)
            if df['close'].iloc[-1] <= df['open'].iloc[-1]:  # 마지막 봉이 양봉이 아닌 경우 제외
                continue

            # 변화율 계산
            df['change_rate'] = df['close'].pct_change() * 100
            change_rate = df['change_rate'].iloc[-1]  # 마지막 봉의 변화율
            
            # 변화율이 4% 이상인 경우 매수 및 익절 실행
            if change_rate >= 4:
                print(f"[{datetime.now()}] {symbol} has a change rate of {change_rate:.2f}% - placing order")
                place_order(symbol)
            else:
                print(f"[{datetime.now()}] {symbol} change rate {change_rate:.2f}% below 4%")
        except Exception as e:
            print(f"[{datetime.now()}] Error processing {symbol}: {e}")

# 실시간 동작
def monitor_market(filtered_symbols):
    while True:
        try:
            print(f"[{datetime.now()}] Monitoring filtered symbols...")
            prepare_data(filtered_symbols)
            check_stop_loss()  # 손절 조건 확인
        except Exception as e:
            print(f"[{datetime.now()}] Error in monitor_market: {e}")
        time.sleep(60)  # 1분마다 실행

# 실행
if __name__ == "__main__":
    if check_api_connection():  # API 연결 확인
        all_symbols = get_top_symbols()
        filtered_symbols = filter_symbols(all_symbols)  # 필터링 1회만 수행
        monitor_market(filtered_symbols)
    else:
        print(f"[{datetime.now()}] Unable to start monitoring. API connection failed.")
