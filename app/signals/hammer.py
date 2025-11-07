import pandas as pd
import numpy as np
from .filters import atr, trend_flags, local_extremum_soft, is_clearing_mask, vol_percentile_intraday

def detect_hammers(
    df: pd.DataFrame,
    body_max_frac: float = 0.30,
    wick_mult: float = 2.3,          # чуть мягче, чтобы меньше пропускать
    opp_wick_max_frac: float = 0.70, # позволим верх/низ до 0.7*body
    ext_window: int = 5,
    ext_eps_ticks: float = 1.0,      # «почти экстремум» — 1 тик
    vol_prct_min: float = 0.80,      # P80 по внутридневному профилю
    atr_k_max: float = 2.7,          # чуть шире по всплескам
    min_range_ticks: float = 1.0,    # минимум реального спрэда бара
    confirm_mode: str = "classic"    # "classic" | "pullback"
) -> pd.DataFrame:
    d = df.copy()

    # базовые метрики
    d['atr14'] = atr(d, 14)
    d['vol_prct'] = vol_percentile_intraday(d)
    trend_up, trend_down, ef, es = trend_flags(d, 20, 50)

    rng   = d['high'] - d['low']
    body  = (d['close'] - d['open']).abs()
    upper = d['high'] - np.maximum(d['open'], d['close'])
    lower = np.minimum(d['open'], d['close']) - d['low']

    # оценка «тика» из истории
    diffs = d['close'].diff().abs()
    tick = float(diffs[(diffs>0) & np.isfinite(diffs)].quantile(0.05)) if (diffs>0).any() else 0.5
    rng_ok = rng >= min_range_ticks * tick

    small_body = body <= body_max_frac * rng
    vol_ok     = d['vol_prct'] >= vol_prct_min
    atr_ok     = rng <= d['atr14'] * atr_k_max

    # «мягкий» локальный экстремум
    low_is_local, high_is_local = local_extremum_soft(d, ext_window, ext_eps_ticks * tick)

    # правило соседних тел (твоя исходная формулировка)
    body_low  = np.minimum(d['open'], d['close'])
    body_high = np.maximum(d['open'], d['close'])
    left_body_low  = body_low.shift(1)
    left_body_high = body_high.shift(1)
    right_body_low  = body_low.shift(-1)
    right_body_high = body_high.shift(-1)

    neighbors_ok_bull = (left_body_high <= body_high) & (right_body_high <= body_high)
    neighbors_ok_bear = (left_body_low  >= body_low)  & (right_body_low  >= body_low)

    bull_shape = small_body & (lower >= wick_mult * body) & (upper <= opp_wick_max_frac * body) & low_is_local & neighbors_ok_bull
    bear_shape = small_body & (upper >= wick_mult * body) & (lower <= opp_wick_max_frac * body) & high_is_local & neighbors_ok_bear

    # подтверждение
    next_close = d['close'].shift(-1)
    if confirm_mode == "classic":
        conf_bull = next_close > d['high']
        conf_bear = next_close < d['low']
    else:
        conf_bull = next_close < body_high
        conf_bear = next_close > body_low

    clearing = is_clearing_mask(d['datetime'])

    buy_mask  = bull_shape & trend_down & vol_ok & atr_ok & rng_ok & conf_bull & (~clearing)
    sell_mask = bear_shape & trend_up   & vol_ok & atr_ok & rng_ok & conf_bear & (~clearing)

    out = d.loc[buy_mask | sell_mask, ['datetime','open','high','low','close','volume']].copy()
    out['signal'] = np.where(buy_mask.loc[out.index], 'BUY', 'SELL')
    out['why'] = np.where(out['signal']=='BUY',
                          'bull;neighbors;trend_down;volP80;confirm;no-clearing',
                          'bear;neighbors;trend_up;volP80;confirm;no-clearing')
    return out.reset_index(drop=True)
