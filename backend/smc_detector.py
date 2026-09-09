import pandas as pd
import numpy as np

def detect_swings(df, window=5):
    """
    Detects Swing Highs and Swing Lows based on a rolling window.
    """
    df['pivot_high'] = df['high'] == df['high'].rolling(window=window*2+1, center=True).max()
    df['pivot_low'] = df['low'] == df['low'].rolling(window=window*2+1, center=True).min()
    
    # Prevent repainting by nullifying pivots that don't have enough future candles to be confirmed
    if len(df) > window:
        df.iloc[-window:, df.columns.get_loc('pivot_high')] = False
        df.iloc[-window:, df.columns.get_loc('pivot_low')] = False
        
    return df

def detect_smc(df, window=5):
    """
    Detects CHoCh (Change of Character) and BOS (Break of Structure).
    Returns a dictionary of SMC data.
    """
    if len(df) < window * 3:
        return {"choch": None, "bos": None, "trend": "Unknown", "support": None, "resistance": None}

    df = detect_swings(df.copy(), window=window)
    
    highs = df[df['pivot_high']]
    lows = df[df['pivot_low']]
    
    if len(highs) < 2 or len(lows) < 2:
        return {"choch": None, "bos": None, "trend": "Unknown", "support": None, "resistance": None}

    recent_highs = highs.tail(3)
    recent_lows = lows.tail(3)
    
    last_h = recent_highs.iloc[-1]
    last_l = recent_lows.iloc[-1]
    
    current_price = df.iloc[-1]['close']
    
    smc_data = {
        "choch": None,  # "BULLISH" or "BEARISH"
        "bos": None,    # "BULLISH" or "BEARISH"
        "trend": "Unknown",
        "support": float(last_l['low']),
        "resistance": float(last_h['high']),
        "pullback_signal": None
    }
    
    # Simple Structure Logic
    # Downtrend: Lower Highs and Lower Lows
    # Uptrend: Higher Highs and Higher Lows
    
    is_downtrend = False
    is_uptrend = False
    
    if len(recent_highs) >= 2 and len(recent_lows) >= 2:
        prev_h = recent_highs.iloc[-2]
        prev_l = recent_lows.iloc[-2]
        
        if last_h['high'] < prev_h['high'] and last_l['low'] < prev_l['low']:
            is_downtrend = True
            smc_data["trend"] = "DOWN"
        elif last_h['high'] > prev_h['high'] and last_l['low'] > prev_l['low']:
            is_uptrend = True
            smc_data["trend"] = "UP"
            
        # Detect CHoCh
        # Bullish CHoCh: In a downtrend, price breaks the last swing high.
        if is_downtrend and current_price > last_h['high']:
            smc_data["choch"] = "BULLISH"
            smc_data["trend"] = "UP" # Trend changes
            
        # Bearish CHoCh: In an uptrend, price breaks the last swing low.
        elif is_uptrend and current_price < last_l['low']:
            smc_data["choch"] = "BEARISH"
            smc_data["trend"] = "DOWN"
            
        # Detect BOS
        # Bullish BOS: In an uptrend, price breaks the previous swing high (continuation)
        if is_uptrend and current_price > last_h['high'] and smc_data["choch"] != "BULLISH":
            smc_data["bos"] = "BULLISH"
            
        # Bearish BOS: In a downtrend, price breaks the previous swing low (continuation)
        if is_downtrend and current_price < last_l['low'] and smc_data["choch"] != "BEARISH":
            smc_data["bos"] = "BEARISH"
            
    # Pullback Signal Logic
    # If recent BOS was Bullish, and price returns near last swing high (which now acts as support)
    # This is a simplified block. A proper OB is more complex, but this uses S/R flipping.
    if smc_data["trend"] == "UP" and last_h['high'] * 0.995 <= current_price <= last_h['high'] * 1.01:
        smc_data["pullback_signal"] = "BULLISH_PULLBACK"
        
    if smc_data["trend"] == "DOWN" and last_l['low'] * 0.99 <= current_price <= last_l['low'] * 1.005:
        smc_data["pullback_signal"] = "BEARISH_PULLBACK"

    return smc_data
