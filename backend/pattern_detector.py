import pandas as pd
import numpy as np

def detect_pattern_coordinates(df):
    """
    Analyzes the dataframe and returns line coordinates for charting if a pattern is found.
    Returns: pattern_name, list_of_lines 
    where list_of_lines = [ [{'time': t1, 'value': p1}, {'time': t2, 'value': p2}], ... ]
    """
    if len(df) < 150:
        return None, []
        
    # Get last 150 candles for pattern detection
    recent_df = df.tail(150).copy()
    
    # Calculate macro pivots
    window = 12
    recent_df['pivot_high'] = recent_df['high'] == recent_df['high'].rolling(window=window*2+1, center=True).max()
    recent_df['pivot_low'] = recent_df['low'] == recent_df['low'].rolling(window=window*2+1, center=True).min()
    
    highs = recent_df[recent_df['pivot_high']]
    lows = recent_df[recent_df['pivot_low']]
    
    lines = []
    pattern_name = None
    
    if len(highs) >= 2 and len(lows) >= 2:
        last_h = highs.iloc[-1]
        prev_h = highs.iloc[-2]
        
        last_l = lows.iloc[-1]
        prev_l = lows.iloc[-2]
        
        # Determine time scale (in seconds) to extend lines
        time_diff = int((recent_df.iloc[-1]['timestamp'] - recent_df.iloc[-2]['timestamp']).total_seconds())
        future_time = int(recent_df.iloc[-1]['timestamp'].timestamp()) + (time_diff * 15)
        start_time = int(recent_df.iloc[0]['timestamp'].timestamp())
        
        # Double Top Detection
        if abs(last_h['high'] - prev_h['high']) / prev_h['high'] < 0.005:
            mid_lows = lows[(lows['timestamp'] > prev_h['timestamp']) & (lows['timestamp'] < last_h['timestamp'])]
            if len(mid_lows) > 0:
                mid_low = mid_lows.iloc[0]
                pattern_name = "Bearish Double Top"
                
                # Line 1: Top Resistance
                lines.append([
                    {'time': start_time, 'value': float(prev_h['high'])},
                    {'time': future_time, 'value': float(last_h['high'])}
                ])
                # Line 2: Neckline Support
                lines.append([
                    {'time': start_time, 'value': float(mid_low['low'])},
                    {'time': future_time, 'value': float(mid_low['low'])}
                ])
                # Line 3: The 'M' Shape outline
                lines.append([
                    {'time': int(prev_h['timestamp'].timestamp()) - (time_diff*2), 'value': float(mid_low['low'])},
                    {'time': int(prev_h['timestamp'].timestamp()), 'value': float(prev_h['high'])},
                    {'time': int(mid_low['timestamp'].timestamp()), 'value': float(mid_low['low'])},
                    {'time': int(last_h['timestamp'].timestamp()), 'value': float(last_h['high'])},
                    {'time': int(last_h['timestamp'].timestamp()) + (time_diff*2), 'value': float(mid_low['low'])}
                ])
                return pattern_name, lines
                
        # Double Bottom Detection
        if abs(last_l['low'] - prev_l['low']) / prev_l['low'] < 0.005:
            mid_highs = highs[(highs['timestamp'] > prev_l['timestamp']) & (highs['timestamp'] < last_l['timestamp'])]
            if len(mid_highs) > 0:
                mid_high = mid_highs.iloc[0]
                pattern_name = "Bullish Double Bottom"
                # Bottom Support
                lines.append([
                    {'time': start_time, 'value': float(prev_l['low'])},
                    {'time': future_time, 'value': float(last_l['low'])}
                ])
                # Neckline Resistance
                lines.append([
                    {'time': start_time, 'value': float(mid_high['high'])},
                    {'time': future_time, 'value': float(mid_high['high'])}
                ])
                # The 'W' Shape outline
                lines.append([
                    {'time': int(prev_l['timestamp'].timestamp()) - (time_diff*2), 'value': float(mid_high['high'])},
                    {'time': int(prev_l['timestamp'].timestamp()), 'value': float(prev_l['low'])},
                    {'time': int(mid_high['timestamp'].timestamp()), 'value': float(mid_high['high'])},
                    {'time': int(last_l['timestamp'].timestamp()), 'value': float(last_l['low'])},
                    {'time': int(last_l['timestamp'].timestamp()) + (time_diff*2), 'value': float(mid_high['high'])}
                ])
                return pattern_name, lines
                
        # Symmetrical Triangle
        if last_h['high'] < prev_h['high'] and last_l['low'] > prev_l['low']:
            pattern_name = "Symmetrical Triangle"
            slope_h = (float(last_h['high']) - float(prev_h['high'])) / ((last_h['timestamp'] - prev_h['timestamp']).total_seconds())
            slope_l = (float(last_l['low']) - float(prev_l['low'])) / ((last_l['timestamp'] - prev_l['timestamp']).total_seconds())
            
            line_h = []
            line_l = []
            for _, row in recent_df.iterrows():
                t = int(row['timestamp'].timestamp())
                val_h = float(last_h['high']) + slope_h * (t - last_h['timestamp'].timestamp())
                val_l = float(last_l['low']) + slope_l * (t - last_l['timestamp'].timestamp())
                line_h.append({'time': t, 'value': val_h})
                line_l.append({'time': t, 'value': val_l})
            
            # Add future point
            line_h.append({'time': future_time, 'value': float(last_h['high']) + slope_h * (future_time - last_h['timestamp'].timestamp())})
            line_l.append({'time': future_time, 'value': float(last_l['low']) + slope_l * (future_time - last_l['timestamp'].timestamp())})
            
            lines.append(line_h)
            lines.append(line_l)
            return pattern_name, lines
            
        # Falling Wedge (Bullish)
        if last_h['high'] < prev_h['high'] and last_l['low'] < prev_l['low']:
            pattern_name = "Falling Wedge (Bullish)"
            slope_h = (float(last_h['high']) - float(prev_h['high'])) / ((last_h['timestamp'] - prev_h['timestamp']).total_seconds())
            slope_l = (float(last_l['low']) - float(prev_l['low'])) / ((last_l['timestamp'] - prev_l['timestamp']).total_seconds())
            
            line_h = []
            line_l = []
            for _, row in recent_df.iterrows():
                t = int(row['timestamp'].timestamp())
                val_h = float(last_h['high']) + slope_h * (t - last_h['timestamp'].timestamp())
                val_l = float(last_l['low']) + slope_l * (t - last_l['timestamp'].timestamp())
                line_h.append({'time': t, 'value': val_h})
                line_l.append({'time': t, 'value': val_l})
            
            # Add future point
            line_h.append({'time': future_time, 'value': float(last_h['high']) + slope_h * (future_time - last_h['timestamp'].timestamp())})
            line_l.append({'time': future_time, 'value': float(last_l['low']) + slope_l * (future_time - last_l['timestamp'].timestamp())})
            
            lines.append(line_h)
            lines.append(line_l)
            return pattern_name, lines

    # Default Parallel Channel (Consolidation)
    support = float(recent_df['low'].min())
    resistance = float(recent_df['high'].max())
    time_diff = int((recent_df.iloc[-1]['timestamp'] - recent_df.iloc[-2]['timestamp']).total_seconds())
    future_time = int(recent_df.iloc[-1]['timestamp'].timestamp()) + (time_diff * 10)
    
    line_r = []
    line_s = []
    for _, row in recent_df.iterrows():
        t = int(row['timestamp'].timestamp())
        line_r.append({'time': t, 'value': resistance})
        line_s.append({'time': t, 'value': support})
    
    line_r.append({'time': future_time, 'value': resistance})
    line_s.append({'time': future_time, 'value': support})
    
    lines.append(line_r)
    lines.append(line_s)
    return "Consolidating Channel", lines
