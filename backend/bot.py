import ccxt
import pandas as pd
import numpy as np
import time
import os
from dotenv import load_dotenv
from ta.trend import MACD
from ta.momentum import RSIIndicator
from sklearn.ensemble import RandomForestClassifier
import json
import requests
from pattern_detector import detect_pattern_coordinates
from smc_detector import detect_smc

# Global storage for status
bot_status = {
    "symbol": "BTC/USDT",
    "price": 0,
    "signal": "HOLD",
    "prediction": "N/A",
    "history": [],
    "candles": [],
    "balance": 100.0,
    "last_update": ""
}

# Global storage for active position management
active_position = {
    "is_open": False,
    "symbol": None,
    "entry_price": 0,
    "amount": 0,
    "sl": 0,
    "tp": 0,
    "highest_price": 0,
    "buy_time": None
}

# Load environment variables
load_dotenv()

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(BASE_DIR, 'status.json')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
SIGNALS_FILE = os.path.join(BASE_DIR, 'signals.json')
HISTORY_FILE = os.path.join(BASE_DIR, 'signal_history.json')

API_KEY = os.getenv('BINANCE_API_KEY')
SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')
USE_TESTNET = os.getenv('USE_TESTNET', 'True') == 'True'

# Initialize Binance client for Trading
exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

if USE_TESTNET:
    exchange.set_sandbox_mode(True)

# Initialize Public Binance client for Data Fetching (Mainnet - more reliable)
public_exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

def fetch_data(symbol='BTC/USDT', timeframe='1h', limit=1000):
    try:
        ohlcv = public_exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Data Fetch Error for {symbol}: {e}")
        return pd.DataFrame()

def add_indicators(df):
    df['rsi'] = RSIIndicator(close=df['close'], window=14).rsi()
    macd = MACD(close=df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_hist'] = macd.macd_diff()
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    
    # VWAP
    q = df['volume'] * ((df['high'] + df['low'] + df['close']) / 3)
    df['vwap'] = q.cumsum() / df['volume'].cumsum()
    
    # SuperTrend Approximation
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(10).mean()
    df['atr'] = atr.fillna(0)
    hl2 = (df['high'] + df['low']) / 2
    
    upper_band = hl2 + (3 * atr)
    lower_band = hl2 - (3 * atr)
    
    # Simplified vectorized SuperTrend logic
    df['supertrend_up'] = df['close'] > hl2 # Base state
    for i in range(1, len(df)):
        if df['close'].iloc[i] > upper_band.iloc[i-1]:
            df.iat[i, df.columns.get_loc('supertrend_up')] = True
        elif df['close'].iloc[i] < lower_band.iloc[i-1]:
            df.iat[i, df.columns.get_loc('supertrend_up')] = False
        else:
            df.iat[i, df.columns.get_loc('supertrend_up')] = df['supertrend_up'].iloc[i-1]

    return df.fillna(0)

def train_simple_model(df):
    df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
    features = ['rsi', 'macd', 'macd_signal', 'sma_20', 'sma_50']
    X = df[features][:-2]
    y = df['target'][:-2]
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    return model, features

def get_signal(df, model, features):
    # Use the LAST CLOSED CANDLE (-2) for strict confirmation to prevent repainting
    last_closed_row = df.iloc[-2:-1]
    prediction = model.predict(last_closed_row[features])[0]
    rsi = last_closed_row['rsi'].values[0]
    macd = last_closed_row['macd'].values[0]
    macd_signal = last_closed_row['macd_signal'].values[0]
    sma_20 = last_closed_row['sma_20'].values[0]
    sma_50 = last_closed_row['sma_50'].values[0]
    close = last_closed_row['close'].values[0]
    
    # Enhanced, stricter logic for higher win rate
    # Buy when: Short trend is up (Close > SMA20), Momentum is up (MACD > Signal), Not overbought (RSI < 70)
    buy_condition = (
        close > sma_20 and
        macd > macd_signal and
        rsi > 40 and rsi < 70 and
        prediction == 1
    )
    
    # Sell when: Short trend is down (Close < SMA20), Momentum is down (MACD < Signal), Not oversold (RSI > 30)
    sell_condition = (
        close < sma_20 and
        macd < macd_signal and
        rsi < 60 and rsi > 30 and
        prediction == 0
    )

    if buy_condition:
        return 'BUY', 'UP'
    elif sell_condition:
        return 'SELL', 'DOWN'
    else:
        return 'HOLD', ('UP' if prediction == 1 else 'DOWN')

def load_signal_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except: pass
    return []

def save_signal_history(hist):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(hist, f)

def run_bot():
    print("--- SUPIRI BINANCE AI MULTI-SCANNER STARTED ---")
    current_signals = []
    
    while True:
        try:
            # 1. Load configuration to see what the user is watching and auto_trade status
            active_symbol = 'BTC/USDT'
            active_timeframe = '1h'
            auto_trade = False
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config_data = json.load(f)
                    active_symbol = config_data.get('symbol', 'BTC/USDT')
                    active_timeframe = config_data.get('timeframe', '1h')
                    auto_trade = config_data.get('auto_trade', False)
            except: pass

            # 2. Get Balance (using authorized exchange)
            try:
                balance_data = exchange.fetch_balance()
                usdt_balance = float(balance_data.get('USDT', {}).get('free', 0))
                if usdt_balance == 0: usdt_balance = 100.0
            except:
                usdt_balance = 100.0

            # 3. Get list of symbols to scan (using public exchange)
            markets = public_exchange.load_markets()
            all_usdt_symbols = [s for s in markets if s.endswith('/USDT') and markets[s].get('active', True)]
            
            with open(os.path.join(BASE_DIR, 'symbols.json'), 'w') as f:
                json.dump(sorted(all_usdt_symbols), f)
            
            # Prioritize: Active Symbol first, then others
            symbols_to_scan = [active_symbol] + [s for s in all_usdt_symbols if s != active_symbol][:15] # Limit to 15 coins to avoid rate limit with 3 timeframes
            timeframes_to_scan = ['15m', '1h', '4h']
            
            new_signals = []
            signal_hist = load_signal_history()
            
            for symbol in symbols_to_scan:
                # 1. Fetch MTF context for Trend alignment
                mtf_data = {}
                try:
                    for mtf_tf in ['1d', '4h', '1h', '15m']:
                        df_mtf = fetch_data(symbol, mtf_tf, limit=200)
                        if not df_mtf.empty:
                            mtf_data[mtf_tf] = detect_smc(df_mtf)
                except: pass
                
                mtf_trends = [mtf_data.get(t, {}).get("trend", "Unknown") for t in ['1d', '4h', '1h', '15m']]
                # Require at least one UP/DOWN trend and no contradictory trends for MTF alignment
                is_mtf_bullish = all(t in ["UP", "Unknown"] for t in mtf_trends) and "UP" in mtf_trends
                is_mtf_bearish = all(t in ["DOWN", "Unknown"] for t in mtf_trends) and "DOWN" in mtf_trends

                for tf in timeframes_to_scan:
                    try:
                        print(f"[{time.strftime('%H:%M:%S')}] Scanning {symbol} on {tf}...")
                        df = fetch_data(symbol, tf, limit=1000)
                        if df.empty or len(df) < 50: 
                            continue
                    
                        df = add_indicators(df)
                        
                        # --- AI MODEL PREDICTION (Filter 1) ---
                        try:
                            model, features = train_simple_model(df.copy())
                            last_closed_row = df.iloc[-2:-1]
                            prediction = model.predict(last_closed_row[features])[0]
                        except Exception as e:
                            prediction = -1
                        # --------------------------------------

                        current_price = float(df['close'].iloc[-1])
                        signal = 'HOLD'
                        prediction_str = "N/A"
                        
                        history_updated = False
                        existing_pending_long = False
                        existing_pending_short = False
                        for h in signal_hist:
                            if h['symbol'] == symbol and h['status'] == 'PENDING':
                                if h['type'] == 'LONG':
                                    if current_price >= h['tp']:
                                        h['status'] = 'PROFIT'
                                        history_updated = True
                                    elif current_price <= h['sl']:
                                        h['status'] = 'LOSS'
                                        history_updated = True
                                    else:
                                        existing_pending_long = True
                                elif h['type'] == 'SHORT':
                                    if current_price <= h['tp']:
                                        h['status'] = 'PROFIT'
                                        history_updated = True
                                    elif current_price >= h['sl']:
                                        h['status'] = 'LOSS'
                                        history_updated = True
                                    else:
                                        existing_pending_short = True
                        if history_updated:
                            save_signal_history(signal_hist)
                    
                        # Use the closed candle for calculating ATR so it doesn't fluctuate
                        confirmed_close = float(df['close'].iloc[-2])
                        confirmed_atr = float(df['atr'].iloc[-2]) if 'atr' in df.columns else (confirmed_close * 0.02)
                            
                        support = float(df['low'].tail(20).min())
                        resistance = float(df['high'].tail(20).max())
                    
                        bearish_patterns = []
                        bullish_patterns = []
                        if len(df) >= 3:
                            c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
                        
                            body1 = abs(c1['close'] - c1['open'])
                            body2 = abs(c2['close'] - c2['open'])
                            body3 = abs(c3['close'] - c3['open'])
                            uw3 = c3['high'] - max(c3['open'], c3['close'])
                            lw3 = min(c3['open'], c3['close']) - c3['low']
                        
                            # Bearish Engulfing
                            if c2['close'] > c2['open'] and c3['close'] < c3['open'] and c3['open'] >= c2['close'] and c3['close'] <= c2['open']:
                                bearish_patterns.append("Bearish Engulfing")
                            # Shooting Star
                            if body3 > 0 and uw3 > body3 * 2 and lw3 < body3 * 0.5 and c3['close'] < c3['open']:
                                bearish_patterns.append("Shooting Star")
                            
                            # Bullish Engulfing
                            if c2['close'] < c2['open'] and c3['close'] > c3['open'] and c3['open'] <= c2['close'] and c3['close'] >= c2['open']:
                                bullish_patterns.append("Bullish Engulfing")
                            # Hammer
                            if body3 > 0 and lw3 > body3 * 2 and uw3 < body3 * 0.5 and c3['close'] > c3['open']:
                                bullish_patterns.append("Hammer")
                            # Morning Star (Simplified)
                            if c1['close'] < c1['open'] and body2 < body1 * 0.3 and c3['close'] > c3['open'] and c3['close'] > c1['close']:
                                bullish_patterns.append("Morning Star")
                        
                        is_near_res = current_price >= resistance * 0.985
                        is_near_sup = current_price <= support * 1.015
                        
                        divergence = None
                        if len(df) > 30:
                            recent_rsi_min = float(df['rsi'].iloc[-10:].min())
                            past_rsi_min = float(df['rsi'].iloc[-30:-10].min())
                            past_price_min = float(df['low'].iloc[-30:-10].min())
                            
                            recent_rsi_max = float(df['rsi'].iloc[-10:].max())
                            past_rsi_max = float(df['rsi'].iloc[-30:-10].max())
                            past_price_max = float(df['high'].iloc[-30:-10].max())
                            
                            if current_price < past_price_min and recent_rsi_min > past_rsi_min + 2:
                                divergence = "Bullish Divergence"
                            elif current_price > past_price_max and recent_rsi_max < past_rsi_max - 2:
                                divergence = "Bearish Divergence"
                    
                        # VWAP & SuperTrend Checks
                        vwap_val = float(df['vwap'].iloc[-1])
                        is_above_vwap = current_price > vwap_val
                        is_supertrend_up = bool(df['supertrend_up'].iloc[-1])
                        
                        # Fibonacci & SMC
                        recent_high = float(df['high'].tail(50).max())
                        recent_low = float(df['low'].tail(50).min())
                        fib_618 = recent_high - ((recent_high - recent_low) * 0.618)
                        fib_382 = recent_high - ((recent_high - recent_low) * 0.382)
                        
                        # Find Order Blocks (simplified)
                        bull_ob = recent_low * 1.005 # Approximated demand zone
                        bear_ob = recent_high * 0.995 # Approximated supply zone

                        # --- RELAXED CONFLUENCE TRADING LOGIC ---
                        # We require AI Prediction + VWAP + SuperTrend to align.
                        
                        # Filter 1: AI Prediction
                        is_ai_bullish = (prediction == 1)
                        is_ai_bearish = (prediction == 0)

                        # Filter 2: VWAP
                        is_above_vwap = current_price > vwap_val

                        # Filter 3: SuperTrend
                        # (is_supertrend_up is already a boolean from earlier)

                        # Optional Filters for stronger confluence
                        has_bull_div = (divergence == "Bullish Divergence")
                        has_bear_div = (divergence == "Bearish Divergence")
                        
                        near_bull_ob = (current_price <= fib_618 * 1.01) and (current_price >= bull_ob * 0.99)
                        near_bear_ob = (current_price >= fib_618 * 0.99) and (current_price <= bear_ob * 1.01)

                        # --- 1:3 RISK/REWARD EXECUTION PLAN (ATR BASED) ---
                        # Prevent massive SL by using ATR instead of distant OBs
                        buy_sl = current_price - (confirmed_atr * 2) 
                        buy_tp = current_price + (confirmed_atr * 6) # 1:3 RR TP
                        
                        sell_sl = current_price + (confirmed_atr * 2) 
                        sell_tp = current_price - (confirmed_atr * 6) # 1:3 RR TP

                        # --- SMC LOGIC INTEGRATION ---
                        smc_info = detect_smc(df)
                        has_choch = smc_info["choch"]
                        has_bos = smc_info["bos"]
                        pullback = smc_info["pullback_signal"]
                        choch_detected = has_choch
                        
                        is_special_htf_choch = False
                        if tf in ['4h', '1d'] and has_choch:
                            is_special_htf_choch = True

                        # --- FINAL SIGNAL EVALUATION ---
                        # Check SMC Signals first
                        if (has_choch == "BULLISH" or pullback == "BULLISH_PULLBACK") and is_mtf_bullish:
                            signal = 'BUY'
                            if has_choch:
                                prediction_str = "SMC CHoCh (BUY)"
                            else:
                                prediction_str = "SMC BOS Pullback (BUY)"
                            tp = buy_tp
                            sl = buy_sl
                        elif (has_choch == "BEARISH" or pullback == "BEARISH_PULLBACK") and is_mtf_bearish:
                            signal = 'SELL'
                            if has_choch:
                                prediction_str = "SMC CHoCh (SELL)"
                            else:
                                prediction_str = "SMC BOS Pullback (SELL)"
                            tp = sell_tp
                            sl = sell_sl
                        # Fallback to AI Confluence Logic
                        elif is_ai_bullish and is_above_vwap and is_supertrend_up:
                            signal = 'BUY'
                            if has_bull_div or near_bull_ob:
                                prediction_str = "Strong Confluence (BUY)"
                            else:
                                prediction_str = "Trend Confirmation (BUY)"
                            tp = buy_tp
                            sl = buy_sl
                        elif is_ai_bearish and not is_above_vwap and not is_supertrend_up:
                            signal = 'SELL'
                            if has_bear_div or near_bear_ob:
                                prediction_str = "Strong Confluence (SELL)"
                            else:
                                prediction_str = "Trend Confirmation (SELL)"
                            tp = sell_tp
                            sl = sell_sl
                        else:
                            # Set default display for HOLD state
                            tp = buy_tp if is_supertrend_up else sell_tp
                            sl = buy_sl if is_supertrend_up else sell_sl
                            
                        # Basic trend status for UI reporting
                        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
                        trend_status = "Uptrend" if current_price > df['ema200'].iloc[-1] else "Downtrend"

                        # --- PENDING SIGNAL MANAGEMENT & REVERSAL CLOSING ---
                        if signal == 'BUY':
                            if existing_pending_long:
                                signal = 'HOLD' # Block duplicate
                            elif existing_pending_short:
                                for h in signal_hist:
                                    if h['symbol'] == symbol and h['status'] == 'PENDING' and h['type'] == 'SHORT':
                                        h['status'] = 'CLOSED (REVERSAL)'
                                        history_updated = True
                                        print(f"🔄 REVERSAL on {symbol}: Closed SHORT early.")
                        elif signal == 'SELL':
                            if existing_pending_short:
                                signal = 'HOLD' # Block duplicate
                            elif existing_pending_long:
                                for h in signal_hist:
                                    if h['symbol'] == symbol and h['status'] == 'PENDING' and h['type'] == 'LONG':
                                        h['status'] = 'CLOSED (REVERSAL)'
                                        history_updated = True
                                        print(f"🔄 REVERSAL on {symbol}: Closed LONG early.")
                                        
                        if history_updated:
                            save_signal_history(signal_hist)
                            
                        bearish_alert = {"patterns": bearish_patterns, "near_resistance": bool(is_near_res)} if bearish_patterns else None
                        bullish_alert = {"patterns": bullish_patterns, "near_support": bool(is_near_sup)} if bullish_patterns else None
                    
                        # ----------------------------------------
                        # Position Management (Trailing SL & Exits)
                        # ----------------------------------------
                        position_status_text = "No Active Trade"
                        if auto_trade and symbol == active_symbol and tf == active_timeframe:
                            if active_position["is_open"] and active_position["symbol"] == symbol:
                                # Update highest price for Trailing SL
                                if current_price > active_position["highest_price"]:
                                    active_position["highest_price"] = current_price
                                    # Trail the SL (highest price - 2 ATR)
                                    new_sl = active_position["highest_price"] - (confirmed_atr * 2)
                                    if new_sl > active_position["sl"]:
                                        active_position["sl"] = new_sl
                                        print(f"📈 TRAILING SL UPDATED to {new_sl:.4f} for {symbol}")
                                
                                position_status_text = f"Open (Entry: {active_position['entry_price']:.4f}, TSL: {active_position['sl']:.4f})"
                                
                                # Check Exits
                                should_sell = False
                                sell_reason = ""
                                if current_price <= active_position["sl"]:
                                    should_sell = True
                                    sell_reason = "STOP LOSS / TRAILING SL HIT"
                                elif current_price >= active_position["tp"]:
                                    should_sell = True
                                    sell_reason = "TAKE PROFIT HIT"
                                elif signal == 'SELL':
                                    should_sell = True
                                    sell_reason = "SELL SIGNAL RECEIVED"
                                    
                                if should_sell:
                                    print(f"🛑 {sell_reason} for {symbol} at {current_price}")
                                    try:
                                        # exchange.create_market_sell_order(symbol, active_position["amount"]) # UNCOMMENT TO TRADE
                                        print(f"✅ SOLD {active_position['amount']:.6f} {symbol} (Simulated)")
                                        active_position["is_open"] = False
                                        active_position["amount"] = 0
                                        signal = 'HOLD' # Reset signal to avoid immediate rebuy
                                        position_status_text = f"Closed ({sell_reason})"
                                    except Exception as e:
                                        print(f"❌ Sell Error: {e}")

                        # Fetch recent trade history for active symbol
                        recent_history = []
                        if symbol == active_symbol and tf == active_timeframe:
                            try:
                                # Fetch last 10 closed orders
                                orders = exchange.fetch_closed_orders(symbol, limit=10)
                                for o in reversed(orders):
                                    recent_history.append({
                                        "type": o['side'].upper(),
                                        "price": o['price'] or o['average'] or current_price,
                                        "time": o['datetime'].split('T')[1][:8] if 'T' in o['datetime'] else ''
                                    })
                            except: pass
                        
                            tsl_display = f"{active_position['sl']:.4f} (Active)" if active_position["is_open"] else f"{sl:.4f} (Planned)"
                            current_hist = float(df['macd_hist'].iloc[-1])
                            prev_hist = float(df['macd_hist'].iloc[-2])
                            hist_momentum = "Increasing" if abs(current_hist) > abs(prev_hist) else "Weakening"
                            
                            recent_candles = []
                            for _, row in df.tail(1000).iterrows():
                                recent_candles.append({
                                    "time": int(row['timestamp'].timestamp()),
                                    "open": float(row['open']),
                                    "high": float(row['high']),
                                    "low": float(row['low']),
                                    "close": float(row['close'])
                                })
                            
                            pattern_name, pattern_lines = detect_pattern_coordinates(df)
                            
                            bot_status.update({
                                "symbol": symbol,
                                "price": current_price,
                                "signal": signal,
                                "balance": usdt_balance,
                                "prediction": prediction_str,
                                "auto_trade": auto_trade,
                                "trade_plan": {
                                    "entry": active_position["entry_price"] if active_position["is_open"] else confirmed_close, 
                                    "tp": active_position["tp"] if active_position["is_open"] else tp, 
                                    "sl": active_position["sl"] if active_position["is_open"] else sl, 
                                    "trailing_sl": tsl_display, 
                                    "status": position_status_text
                                },
                                "analysis": {"trend": trend_status, "choch": choch_detected, "pattern": pattern_name or "Consolidating", "pattern_points": pattern_lines, "levels": {"support": support, "resistance": resistance}, "bearish_alert": bearish_alert, "bullish_alert": bullish_alert, "divergence": divergence},
                                "indicators": {"rsi": float(df['rsi'].iloc[-1]), "macd": float(df['macd'].iloc[-1]), "macd_signal": float(df['macd_signal'].iloc[-1]), "macd_hist": current_hist, "hist_momentum": hist_momentum, "vwap": vwap_val, "supertrend": "UP" if is_supertrend_up else "DOWN"},
                                "pro_data": {"fib_618": fib_618, "fib_382": fib_382, "bull_ob": bull_ob, "bear_ob": bear_ob},
                                "history": recent_history,
                                "candles": recent_candles,
                                "last_update": time.strftime('%H:%M:%S')
                            })
                            with open(STATUS_FILE, 'w') as f:
                                json.dump(bot_status, f)

                        if signal != 'HOLD':
                            if auto_trade and symbol == active_symbol and tf == active_timeframe and signal == 'BUY':
                                if not active_position["is_open"]:
                                    print(f"🚀 AUTO-TRADE ATTEMPTING: {signal} {symbol} at {current_price}")
                                    try:
                                        # Risk management: 10% of balance per trade
                                        trade_amount_usdt = usdt_balance * 0.10
                                        if trade_amount_usdt < 10: trade_amount_usdt = 10.0 # Min order size
                                        
                                        if usdt_balance >= trade_amount_usdt:
                                            amount_to_buy = trade_amount_usdt / current_price
                                            # exchange.create_market_buy_order(symbol, amount_to_buy)  # <-- UNCOMMENT TO REALLY TRADE
                                            print(f"✅ BOUGHT {amount_to_buy:.6f} {symbol} (Simulated)")
                                            
                                            # Save Position
                                            active_position["is_open"] = True
                                            active_position["symbol"] = symbol
                                            active_position["entry_price"] = current_price
                                            active_position["amount"] = amount_to_buy
                                            active_position["sl"] = sl
                                            active_position["tp"] = tp
                                            active_position["highest_price"] = current_price
                                            active_position["buy_time"] = time.strftime('%H:%M:%S')
                                    except Exception as ex:
                                        print(f"❌ Auto-Trade Error: {ex}")
                            
                            # tp and sl calculation already done above
                            # Just append to new_signals
                            signal_type = "LONG" if signal == 'BUY' else "SHORT"
                            new_signals.append({
                                "symbol": symbol,
                                "timeframe": tf,
                                "type": signal_type,
                                "signal": signal,
                                "price": current_price,
                                "prediction": prediction_str,
                                "divergence": divergence,
                                "supertrend": "UP" if is_supertrend_up else "DOWN",
                                "vwap": vwap_val,
                                "fib_618": fib_618,
                                "bull_ob": bull_ob,
                                "bear_ob": bear_ob,
                                "tp": tp,
                                "sl": sl,
                                "rsi": float(df['rsi'].iloc[-1]),
                                "time": time.strftime('%Y-%m-%d %H:%M:%S'),
                                "is_special_htf_choch": is_special_htf_choch
                            })
                        
                        
                        
                            # Save signals frequently so user doesn't wait
                            with open(SIGNALS_FILE, 'w') as f:
                                json.dump(new_signals, f)
                    
                        time.sleep(0.2) # Small delay to respect rate limits
                    except Exception as e:
                        print(f"Error on {symbol} {tf}: {e}")
                        continue

            # Ensure old signals are cleared if no longer valid
            with open(SIGNALS_FILE, 'w') as f:
                json.dump(new_signals, f)
            print(f"Scan batch complete. Found {len(new_signals)} signals.")
            time.sleep(10)
            
        except Exception as e:
            print(f"Bot Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_bot()
