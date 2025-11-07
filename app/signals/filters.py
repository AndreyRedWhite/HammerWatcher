import pandas as pd
import numpy as np

def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    # True Range
    h, l, c = df['high'], df['low'], df['close']
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def vol_sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
    return df['volume'].rolling(period).mean()

def trend_flags(df: pd.DataFrame, fast=20, slow=50):
    ef = ema(df['close'], fast)
    es = ema(df['close'], slow)
    trend_up = ef > es
    trend_down = ef < es
    return trend_up, trend_down, ef, es

def is_clearing_mask(dt: pd.Series) -> pd.Series:
    # исключаем бары, попадающие в окна клиринга: 13:55–14:05 и 18:45–19:05 МСК
    t = dt.dt.tz_convert('Europe/Moscow') if dt.dt.tz is not None else dt
    m1 = (t.dt.hour == 13) & (t.dt.minute >= 55)
    m2 = (t.dt.hour == 14) & (t.dt.minute <= 5)
    e1 = (t.dt.hour == 18) & (t.dt.minute >= 45)
    e2 = (t.dt.hour == 19) & (t.dt.minute <= 5)
    return m1 | m2 | e1 | e2

def local_extremum_flags(df: pd.DataFrame, window: int = 5):
    low_local  = df['low']  == df['low'].rolling(window, min_periods=1).min()
    high_local = df['high'] == df['high'].rolling(window, min_periods=1).max()
    return low_local, high_local
