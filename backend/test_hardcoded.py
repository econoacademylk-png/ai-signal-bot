import ccxt

import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
})

exchange.set_sandbox_mode(True)

try:
    print("Testing hardcoded keys...")
    balance = exchange.fetch_balance()
    print("Success!")
    print(balance['total']['USDT'])
except Exception as e:
    print(f"Failed: {e}")
