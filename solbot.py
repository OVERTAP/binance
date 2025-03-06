import requests

# API 요청 URL
url = "https://api.dexscreener.com/latest/dex/pairs/solana"

# API 요청
response = requests.get(url)
if response.status_code != 200:
    print(f"API 요청 실패: {response.status_code}")
    exit()

data = response.json()

# 조건 필터링
filtered_pairs = [
    pair for pair in data["pairs"]
    if float(pair["volume"]["24h"]) > 100000 and float(pair["liquidity"]["usd"]) > 50000
]

# 결과 출력
if filtered_pairs:
    print("조건을 만족하는 코인:")
    for pair in filtered_pairs:
        print(f"페어 이름: {pair['baseToken']['name']}, 가격: {pair['priceUsd']}")
else:
    print("조건에 맞는 코인이 없습니다.")
