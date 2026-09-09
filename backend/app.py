from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
import ccxt

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(BASE_DIR, 'status.json')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
SIGNALS_FILE = os.path.join(BASE_DIR, 'signals.json')
HISTORY_FILE = os.path.join(BASE_DIR, 'signal_history.json')

@app.route('/api/status', methods=['GET'])
def get_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'r') as f:
            data = json.load(f)
            # Ensure auto_trade state is instantly reflected from config
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as cf:
                    config = json.load(cf)
                    data['auto_trade'] = config.get('auto_trade', False)
            return jsonify(data)
    return jsonify({"error": "No data available"}), 404

@app.route('/api/change_symbol', methods=['POST'])
def change_symbol():
    data = request.get_json()
    symbol = data.get('symbol', 'BTC/USDT')
    timeframe = data.get('timeframe', '1h')
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"symbol": symbol, "timeframe": timeframe}, f)
    return jsonify({"status": "success", "symbol": symbol, "timeframe": timeframe})

@app.route('/api/toggle_trade', methods=['POST'])
def toggle_trade():
    data = request.get_json()
    auto_trade = data.get('auto_trade', False)
    
    config = {"symbol": "BTC/USDT", "timeframe": "1h", "auto_trade": False}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            
    config['auto_trade'] = auto_trade
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)
    return jsonify({"status": "success", "auto_trade": auto_trade})

@app.route('/api/config', methods=['GET'])
def get_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return jsonify(json.load(f))
    return jsonify({"symbol": "BTC/USDT", "timeframe": "1h", "auto_trade": False})

SYMBOLS_FILE = os.path.join(BASE_DIR, 'symbols.json')

@app.route('/api/symbols', methods=['GET'])
def get_symbols():
    try:
        if os.path.exists(SYMBOLS_FILE):
            with open(SYMBOLS_FILE, 'r') as f:
                return jsonify(json.load(f))
    except Exception as e:
        pass
    # Fallback if file doesn't exist yet
    return jsonify(["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"])

@app.route('/api/all_signals', methods=['GET'])
def get_all_signals():
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE, 'r') as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route('/api/signal_history', methods=['GET'])
def get_signal_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
                # Sort newest first based on id (timestamp)
                history.sort(key=lambda x: x.get('id', '0'), reverse=True)
                return jsonify(history)
        except Exception as e:
            pass
    return jsonify([])

@app.route('/api/add_trade', methods=['POST'])
def add_trade():
    import time
    data = request.json
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
        except Exception:
            pass
            
    new_trade = {
        "id": str(int(time.time() * 1000)),
        "symbol": data.get('symbol'),
        "timeframe": data.get('timeframe'),
        "type": data.get('type'),
        "entry": data.get('entry'),
        "tp": data.get('tp'),
        "sl": data.get('sl'),
        "status": "PENDING",
        "time": time.strftime('%Y-%m-%d %H:%M:%S')
    }
    history.append(new_trade)
    
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)
        
    return jsonify({"status": "success"})

@app.route('/api/trade', methods=['POST'])
def manual_trade():
    try:
        from dotenv import load_dotenv
        load_dotenv()
        data = request.json
        symbol = data.get('symbol', 'BTC/USDT')
        side = data.get('side', 'BUY').lower()
        amount_usdt = float(data.get('amount_usdt', 10.0))
        
        API_KEY = os.getenv('BINANCE_API_KEY')
        SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')
        USE_TESTNET = os.getenv('USE_TESTNET', 'True') == 'True'
        
        exchange = ccxt.binance({
            'apiKey': API_KEY,
            'secret': SECRET_KEY,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        if USE_TESTNET:
            exchange.set_sandbox_mode(True)
            
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']
        amount = amount_usdt / price
        
        if side == 'buy':
            order = exchange.create_market_buy_order(symbol, amount)
        else:
            order = exchange.create_market_sell_order(symbol, amount)
            
        return jsonify({"status": "success", "message": f"Successfully placed {side.upper()} order for {amount:.4f} {symbol}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/delete_trade/<string:trade_id>', methods=['DELETE'])
def delete_trade(trade_id):
    history_file = os.path.join(BASE_DIR, 'signal_history.json')
    try:
        with open(history_file, 'r') as f:
            history = json.load(f)
            
        history = [h for h in history if str(h.get("id")) != str(trade_id)]
        
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=4)
            
        return jsonify({"status": "success", "message": "Trade deleted"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    env_path = os.path.join(BASE_DIR, '.env')
    if request.method == 'GET':
        from dotenv import dotenv_values
        config = dotenv_values(env_path)
        return jsonify({
            "api_key": config.get("BINANCE_API_KEY", ""),
            "secret_key": config.get("BINANCE_SECRET_KEY", ""),
            "use_testnet": config.get("USE_TESTNET", "True") == "True",
            "telegram_token": config.get("TELEGRAM_TOKEN", ""),
            "telegram_chat_id": config.get("TELEGRAM_CHAT_ID", "")
        })
    elif request.method == 'POST':
        data = request.json
        with open(env_path, 'w') as f:
            f.write(f"BINANCE_API_KEY={data.get('api_key', '')}\n")
            f.write(f"BINANCE_SECRET_KEY={data.get('secret_key', '')}\n")
            f.write(f"USE_TESTNET={'True' if data.get('use_testnet') else 'False'}\n")
            f.write(f"TELEGRAM_TOKEN={data.get('telegram_token', '')}\n")
            f.write(f"TELEGRAM_CHAT_ID={data.get('telegram_chat_id', '')}\n")
        return jsonify({"status": "success", "message": "Settings saved successfully! Please restart the backend terminal (bot.py and app.py) to apply."})

@app.route('/api/new_coins', methods=['GET'])
def get_new_coins():
    try:
        import requests
        res = requests.get('https://api.binance.com/api/v3/exchangeInfo')
        data = res.json()
        usdt_symbols = [s['symbol'] for s in data.get('symbols', []) if s['symbol'].endswith('USDT') and s['status'] == 'TRADING']
        # The newest ones are at the end of the list
        new_coins = usdt_symbols[-15:]
        new_coins.reverse()  # Newest first
        return jsonify(new_coins)
    except Exception as e:
        return jsonify([])

@app.route('/api/trend_analysis', methods=['GET'])
def get_trend_analysis():
    symbol = request.args.get('symbol', 'BTC/USDT')
    try:
        import pandas as pd
        exchange = ccxt.binance({'enableRateLimit': True})
        timeframes = ['1d', '4h', '1h', '15m']
        trends = {}
        
        for tf in timeframes:
            ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=100)
            if not ohlcv:
                trends[tf] = "N/A"
                continue
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            if len(df) >= 20:
                current_price = df['close'].iloc[-1]
                ema50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
                trends[tf] = "UP" if current_price > ema50 else "DOWN"
            else:
                trends[tf] = "N/A"
                
        return jsonify(trends)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)
