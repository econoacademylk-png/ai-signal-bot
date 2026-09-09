import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'enableRateLimit': True,
})

exchange.set_sandbox_mode(True)

try:
    print("Checking connection to Binance Testnet...")
    balance = exchange.fetch_balance()
    print("Connection successful!")
    print(f"USDT Balance: {balance.get('USDT', {}).get('free', 0)}")
    
    markets = exchange.load_markets()
    symbols = [s for s in markets if s.endswith('/USDT')]
    print(f"Available USDT symbols on Testnet: {symbols[:10]}... (Total: {len(symbols)})")
    
    if 'ENSO/USDT' in symbols:
        print("ENSO/USDT is available.")
    else:
        print("ENSO/USDT is NOT available on Testnet.")

except Exception as e:
    print(f"Error: {e}")
