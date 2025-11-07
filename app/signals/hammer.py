import pandas as pd
import numpy as np
from .filters import atr, vol_sma, trend_flags, local_extremum_flags, is_clearing_mask

def detect_hammers(
    df: pd.DataFrame,
    body_max_frac: float = 0.30,
    wick_mult: float = 2.5,
    opp_wick_max_frac: float = 0.60,
    ext_window: int = 5,
    vol_mult: float = 1.2,
    atr_k_max: float = 2.5,
    confirm_mode: str = "classic"  # "classic" | "pullback"
) -> pd.DataFrame:
    """
    Возвращает df с колонками:
    ['datetime','signal','entry','stop','tp','R','rub_R','why','tf']
    Без расчёта стоп/тейк это «сырые» сигналы — их досчитает risk/position.
    """
    d = df.copy()

    # базовые метрики и фильтры
    d['atr14'] = atr(d, 14)
    d['vol_sma20'] = vol_sma(d, 20)
    trend_up, trend_down, ef, es = trend_flags(d, 20, 50)
    low_is_local, high_is_local = local_extremum_flags(d, ext_window)

    rng   = d['high'] - d['low']
    body  = (d['close'] - d['open']).abs()
    upper = d['high'] - np.maximum(d['open'], d['close'])
    lower = np.minimum(d['open'], d['close']) - d['low']

    small_body = body <= body_max_frac * rng
    vol_ok     = d['volume'] >= vol_mult * d['vol_sma20']
    atr_ok     = rng <= d['atr14'] * atr_k_max

    bull_shape = small_body & (lower >= wick_mult * body) & (upper <= opp_wick_max_frac * body) & low_is_local
    bear_shape = small_body & (upper >= wick_mult * body) & (lower <= opp_wick_max_frac * body) & high_is_local

    # подтверждение следующей свечой
    next_close = d['close'].shift(-1)
    if confirm_mode == "classic":
        conf_bull = next_close > d['high']
        conf_bear = next_close < d['low']
    else:  # pullback
        body_low  = np.minimum(d['open'], d['close'])
        body_high = np.maximum(d['open'], d['close'])
        conf_bull = next_close < body_high
        conf_bear = next_close > body_low

    clearing = is_clearing_mask(d['datetime'])

    buy_mask  = bull_shape & trend_down & vol_ok & atr_ok & conf_bull & (~clearing)
    sell_mask = bear_shape & trend_up   & vol_ok & atr_ok & conf_bear & (~clearing)

    out = d.loc[buy_mask | sell_mask, ['datetime','open','high','low','close','volume']].copy()
    out['signal'] = np.where(buy_mask.loc[out.index], 'BUY', 'SELL')
    out['why'] = np.where(out['signal']=='BUY',
                          'bull-hammer;trend_down;vol;confirm;no-clearing',
                          'bear-invhammer;trend_up;vol;confirm;no-clearing')
    return out.reset_index(drop=True)
