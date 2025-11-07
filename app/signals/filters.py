import pandas as pd
import numpy as np

def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df['high'], df['low'], df['close']
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def vol_percentile_intraday(df: pd.DataFrame) -> pd.Series:
    # ранжируем объёмы по часу/минуте (внутридневной профиль)
    t = df['datetime']
    key = t.dt.hour.astype(str) + ":" + t.dt.minute.astype(str)
    # percent-rank по каждому (час:минута)
    def prct(s):
        return s.rank(pct=True)
    return df.groupby(key, group_keys=False)['volume'].apply(prct)

def trend_flags(df: pd.DataFrame, fast=20, slow=50):
    ef = ema(df['close'], fast); es = ema(df['close'], slow)
    return (ef > es), (ef < es), ef, es

def is_clearing_mask(dt: pd.Series) -> pd.Series:
    t = dt.dt.tz_convert('Europe/Moscow') if dt.dt.tz is not None else dt
    m1 = (t.dt.hour == 13) & (t.dt.minute >= 55)
    m2 = (t.dt.hour == 14) & (t.dt.minute <= 5)
    e1 = (t.dt.hour == 18) & (t.dt.minute >= 45)
    e2 = (t.dt.hour == 19) & (t.dt.minute <= 5)
    return m1 | m2 | e1 | e2

def local_extremum_soft(df: pd.DataFrame, window: int, eps: float):
    # почти-экстремум: допустить погрешность eps (в тиках/цене)
    low_min = df['low'].rolling(window, min_periods=1).min()
    high_max = df['high'].rolling(window, min_periods=1).max()
    low_ok  = df['low']  <= (low_min + eps)
    high_ok = df['high'] >= (high_max - eps)
    return low_ok, high_ok
