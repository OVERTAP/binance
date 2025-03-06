import math
from binance.client import Client
import pandas as pd
import time

API_KEY = 'iX0l2IzUSK9gBUKB7guCeb11eObPnVWKddjC8wMWR3utvGKZcEyWIXcbOCCA7JyP'
API_SECRET = 'I8N4tKiCdZ42yyI8YIV5pNjDxucZGsuzJm6rKp8UNt00p4yYCkeisZZRfq5KhMDN'

client = Client(API_KEY, API_SECRET)

def check_api_access():
    """API 키와 비밀번호가 유효하며 계정에 접근 가능한지 확인"""
    try:
        account_info = client.futures_account_balance()
        print("API 키와 비밀번호가 유효하며 계정에 접근 가능합니다.")
        return True
    except Exception as e:
        print(f"API 접근 실패: {e}")
        return False

def get_active_futures_symbols():
    """활성화된 선물 심볼만 가져오기"""
    exchange_info = client.futures_exchange_info()
    return [
        symbol['symbol'] for symbol in exchange_info['symbols']
        if symbol['status'] == 'TRADING'  # 활성화된 심볼만 포함
    ]

def get_60m_klines(symbol):
    """1시간봉 데이터를 가져옵니다."""
    klines = client.futures_klines(symbol=symbol, interval='1h', limit=5)
    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    df['close'] = df['close'].astype(float)
    return df

def detect_spike(symbol, df):
    """급등 조건 감지"""
    closes = df['close']
    changes = ((closes.diff() / closes.shift(1)) * 100).iloc[:-1]
    if all(abs(changes[-4:-1]) <= 3):  # 이전 5개 캔들 변화율이 ±3% 이하
        last_change = (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100
        if last_change >= 4.5:  # 마지막 캔들에서 4.5% 이상 상승
            return True
    return False

def set_leverage(symbol, leverage):
    """레버리지 설정"""
    try:
        response = client.futures_change_leverage(symbol=symbol, leverage=leverage)
        print(f"{symbol} 레버리지 설정 성공: {response}")
    except Exception as e:
        print(f"레버리지 설정 실패: {e}")

def get_balance():
    """USDT 잔고 가져오기"""
    account_info = client.futures_account_balance()
    for asset in account_info:
        if asset['asset'] == 'USDT':
            return float(asset['balance'])
    return 0

def place_limit_sell_order(symbol, quantity, price):
    """지정가 매도 주문"""
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side='SELL',
            type='LIMIT',
            quantity=quantity,
            price=price,
            positionSide='LONG',  # 헤지 모드에서 롱 포지션 지정
            timeInForce='GTC'
        )
        print(f"지정가 매도 주문 성공: {order}")
    except Exception as e:
        print(f"지정가 매도 주문 실패: {e}")

def execute_trade(symbol):
    """매수 및 지정가 매도 설정"""
    try:
        leverage = 5
        set_leverage(symbol, leverage)

        # 현재 시장 가격 가져오기
        ticker = client.futures_symbol_ticker(symbol=symbol)
        current_price = float(ticker['price'])
        print(f"{symbol} 현재 시장 가격: {current_price} USDT")

        # 잔고 가져오기 및 매수 수량 계산
        balance = get_balance()
        trade_amount = balance * 0.99  # 잔고의 99%
        quantity = trade_amount * leverage / current_price
        quantity = math.floor(quantity * 1000) / 1000  # 최소 수량 단위로 조정

        # 시장가 매수 주문
        order = client.futures_create_order(
            symbol=symbol,
            side='BUY',
            type='MARKET',
            quantity=quantity,
            positionSide='LONG'  # 헤지 모드에서 롱 포지션 지정
        )
        print(f"시장가 매수 주문 성공: {order}")

        # 목표 수익 가격 계산 및 지정가 매도 주문 설정
        target_price = current_price * 1.25  # 25% 상승 목표
        target_price = round(target_price, 2)  # 가격 단위 조정
        place_limit_sell_order(symbol, quantity, target_price)

    except Exception as e:
        print(f"거래 실행 실패: {e}")

def find_spike_and_trade():
    """조건에 맞는 종목을 찾으면 거래 실행"""
    symbols = get_active_futures_symbols()
    for symbol in symbols:
        try:
            df = get_60m_klines(symbol)
            if detect_spike(symbol, df):
                print(f"급등 감지: {symbol}, 거래 실행")
                execute_trade(symbol)
                break  # 첫 번째 종목을 찾으면 중단
        except Exception as e:
            print(f"데이터를 가져오는 중 오류 발생 ({symbol}): {e}")
        time.sleep(10)  # API 요청 제한 방지

if __name__ == "__main__":
    print("API 키와 계정 접근 유효성 확인 중...4")
    if check_api_access():
        print("1시간봉에서 급등한 종목 찾기 및 거래 실행 시작...")
        find_spike_and_trade()


