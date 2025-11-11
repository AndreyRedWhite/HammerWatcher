# app/signals/hammer.py
import pandas as pd
import numpy as np

from .filters import (
    atr,
    trend_flags,
    local_extremum_soft,
    is_clearing_mask,
    vol_percentile_intraday,
    ema as ema_fn,
)

def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1 / period, adjust=False).mean()
    roll_down = down.ewm(alpha=1 / period, adjust=False).mean()
    rs = roll_up / (roll_down + 1e-12)
    return 100 - (100 / (1 + rs))


def detect_hammers(
    df: pd.DataFrame,
    # Геометрия свечи
    body_max_frac: float = 0.30,
    wick_mult: float = 2.5,
    opp_wick_max_frac: float = 0.60,
    # «Почти экстремум»
    ext_window: int = 5,
    ext_eps_ticks: float = 1.0,
    # Ликвидность/волатильность
    vol_prct_min: float = 0.80,   # внутридневной перцентиль объёма
    atr_k_max: float = 2.5,       # ограничение «взрывных» баров
    min_range_ticks: float = 1.0, # минимальный реальный спред бара в тиках
    # Подтверждение
    confirm_mode: str = "classic",   # "classic" | "pullback" | "classic2"
    confirm_horizon: int = 1,        # 1..2
    # «Соседи» (тела слева/справа относительно тела молота)
    neighbor_mode: str = "both",     # "both" | "left_or_right"
    neighbor_eps_ticks: float = 0.0, # допуск для соседей в тиках
    # Контекст уровней/EMA
    level_touch_enable: bool = False,
    level_lookback: int = 120,
    level_tol_ticks: float = 2.0,
    ema_confl_enable: bool = False,
    ema_period: int = 50,
    ema_tol_ticks: float = 3.0,
    # Двойной объём (PoD ИЛИ локальная статистика)
    vol_dual_enable: bool = False,
    vol_dual_window: int = 60,
    vol_dual_prct: float = 0.70,
    # RSI-контекст
    rsi_enable: bool = False,
    rsi_period: int = 14,
    rsi_ob: float = 65.0,
    rsi_os: float = 35.0,
) -> pd.DataFrame:
    """
    Возвращает DataFrame с колонками:
    ['datetime','open','high','low','close','volume','signal','why']
    Геометрия молота/перевёрнутого молота + подтверждение + контекст уровней/EMA/RSI.
    """
    d = df.copy().sort_values("datetime").reset_index(drop=True)

    # --- Базовые метрики ---
    d["atr14"] = atr(d, 14)
    d["vol_prct"] = vol_percentile_intraday(d)
    trend_up, trend_down, _, _ = trend_flags(d, 20, 50)

    rng   = d["high"] - d["low"]
    body  = (d["close"] - d["open"]).abs()
    upper = d["high"] - np.maximum(d["open"], d["close"])
    lower = np.minimum(d["open"], d["close"]) - d["low"]

    # Оценка «тика» из истории
    diffs = d["close"].diff().abs()
    tick = float(diffs[(diffs > 0) & np.isfinite(diffs)].quantile(0.05)) if (diffs > 0).any() else 0.5
    rng_ok = rng >= (min_range_ticks * tick)

    small_body = body <= (body_max_frac * rng)
    atr_ok     = rng <= (d["atr14"] * atr_k_max)

    # Объём: PoD или локальная статистика
    vol_ok_pod = d["vol_prct"] >= vol_prct_min
    if vol_dual_enable:
        loc_thr = (
            d["volume"]
            .rolling(vol_dual_window, min_periods=10)
            .apply(lambda x: np.nanpercentile(x, vol_dual_prct * 100), raw=False)
        )
        vol_ok_loc = d["volume"] >= loc_thr.fillna(method="bfill").fillna(method="ffill")
        vol_ok = vol_ok_pod | vol_ok_loc
    else:
        vol_ok = vol_ok_pod

    # «Мягкий» локальный экстремум
    low_is_local, high_is_local = local_extremum_soft(d, ext_window, ext_eps_ticks * tick)

    # Тела текущей/соседних свечей
    body_low  = np.minimum(d["open"], d["close"])
    body_high = np.maximum(d["open"], d["close"])
    left_body_low   = body_low.shift(1)
    left_body_high  = body_high.shift(1)
    right_body_low  = body_low.shift(-1)
    right_body_high = body_high.shift(-1)

    # Правило «соседей» с допуском
    eps = neighbor_eps_ticks * tick
    left_ok_bull  = left_body_high  <= body_high + eps
    right_ok_bull = right_body_high <= body_high + eps
    left_ok_bear  = left_body_low   >= body_low  - eps
    right_ok_bear = right_body_low  >= body_low  - eps

    if neighbor_mode == "left_or_right":
        neighbors_ok_bull = left_ok_bull | right_ok_bull
        neighbors_ok_bear = left_ok_bear | right_ok_bear
    else:
        neighbors_ok_bull = left_ok_bull & right_ok_bull
        neighbors_ok_bear = left_ok_bear & right_ok_bear

    # Геометрия «молота»
    bull_shape = (
        small_body
        & (lower >= wick_mult * body)
        & (upper <= opp_wick_max_frac * body)
        & low_is_local
        & neighbors_ok_bull
    )
    bear_shape = (
        small_body
        & (upper >= wick_mult * body)
        & (lower <= opp_wick_max_frac * body)
        & high_is_local
        & neighbors_ok_bear
    )

    # --- Контекст: уровни, EMA, RSI ---
    if level_touch_enable:
        recent_high = body_high.rolling(level_lookback, min_periods=2).max().shift(1)
        recent_low  = body_low.rolling(level_lookback,  min_periods=2).min().shift(1)
        tol = level_tol_ticks * tick
        touch_res = (d["high"] >= recent_high - tol) & (d["high"] <= recent_high + tol)
        touch_sup = (d["low"]  >= recent_low  - tol) & (d["low"]  <= recent_low  + tol)
    else:
        touch_res = pd.Series(False, index=d.index)
        touch_sup = pd.Series(False, index=d.index)

    if ema_confl_enable:
        ema_line = ema_fn(d["close"], ema_period)
        ema_near = ((d["high"] - ema_line).abs() <= ema_tol_ticks * tick) | \
                   ((d["low"]  - ema_line).abs() <= ema_tol_ticks * tick)
    else:
        ema_near = pd.Series(False, index=d.index)

    if rsi_enable:
        rsi_s = _rsi(d["close"], rsi_period)
        rsi_buy_ok  = rsi_s <= rsi_os     # перепроданность
        rsi_sell_ok = rsi_s >= rsi_ob     # перекупленность
    else:
        rsi_buy_ok  = pd.Series(False, index=d.index)
        rsi_sell_ok = pd.Series(False, index=d.index)

    # Любой из контекстов даёт «зелёный свет»
    context_buy  = (trend_down | touch_sup | ema_near | rsi_buy_ok)
    context_sell = (trend_up   | touch_res | ema_near | rsi_sell_ok)

    # --- Подтверждение ---
    next_close1 = d["close"].shift(-1)
    next_close2 = d["close"].shift(-2)

    if confirm_mode == "classic":
        conf1_bull = next_close1 > d["high"]
        conf1_bear = next_close1 < d["low"]
        if confirm_horizon >= 2:
            conf2_bull = next_close2 > d["high"]
            conf2_bear = next_close2 < d["low"]
            conf_bull = conf1_bull | conf2_bull
            conf_bear = conf1_bear | conf2_bear
        else:
            conf_bull, conf_bear = conf1_bull, conf1_bear

    elif confirm_mode == "pullback":
        conf1_bull = next_close1 < body_high
        conf1_bear = next_close1 > body_low
        if confirm_horizon >= 2:
            conf2_bull = next_close2 < body_high
            conf2_bear = next_close2 > body_low
            conf_bull = conf1_bull | conf2_bull
            conf_bear = conf1_bear | conf2_bear
        else:
            conf_bull, conf_bear = conf1_bull, conf1_bear

    elif confirm_mode == "classic2":
        conf1_bull = (next_close1 > d["high"]) | (d["high"].shift(-1) > d["high"])
        conf1_bear = (next_close1 < d["low"])  | (d["low"].shift(-1)  < d["low"])
        if confirm_horizon >= 2:
            conf2_bull = (next_close2 > d["high"]) | (d["high"].shift(-2) > d["high"])
            conf2_bear = (next_close2 < d["low"])  | (d["low"].shift(-2)  < d["low"])
            conf_bull = conf1_bull | conf2_bull
            conf_bear = conf1_bear | conf2_bear
        else:
            conf_bull, conf_bear = conf1_bull, conf1_bear
    else:
        conf_bull = pd.Series(False, index=d.index)
        conf_bear = pd.Series(False, index=d.index)

    # Доп. кейс: «молот → inside-bar» как альтернативное подтверждение
    inside_next = (body_low.shift(-1) >= body_low) & (body_high.shift(-1) <= body_high)

    clearing = is_clearing_mask(d["datetime"])

    buy_mask  = bull_shape & context_buy  & vol_ok & atr_ok & rng_ok & (~clearing) & conf_bull
    sell_mask = bear_shape & context_sell & vol_ok & atr_ok & rng_ok & (~clearing) & conf_bear

    buy_mask  = buy_mask  | (bull_shape & inside_next & context_buy  & vol_ok & atr_ok & rng_ok & (~clearing))
    sell_mask = sell_mask | (bear_shape & inside_next & context_sell & vol_ok & atr_ok & rng_ok & (~clearing))

    out = d.loc[buy_mask | sell_mask, ["datetime","open","high","low","close","volume"]].copy()
    out["signal"] = np.where(buy_mask.loc[out.index], "BUY", "SELL")
    out["why"] = np.where(
        out["signal"] == "BUY",
        "bull;neighbors;context(EMA/level/trend/RSI);vol;confirm",
        "bear;neighbors;context(EMA/level/trend/RSI);vol;confirm",
    )

    # --- DEBUG: почти-кандидаты и причины отсева ---
    debug_mask = small_body & ((lower >= (2.0 * body)) | (upper >= (2.0 * body)))
    if debug_mask.any():
        dbg = d.loc[debug_mask, ["datetime","open","high","low","close","volume"]].copy()
        dbg["tick"]  = tick
        dbg["rng"]   = rng[debug_mask]
        dbg["body"]  = body[debug_mask]
        dbg["upper"] = upper[debug_mask]
        dbg["lower"] = lower[debug_mask]

        dbg["small_body"]   = small_body[debug_mask]
        dbg["vol_ok"]       = vol_ok[debug_mask]
        dbg["atr_ok"]       = atr_ok[debug_mask]
        dbg["rng_ok"]       = rng_ok[debug_mask]
        dbg["low_is_local"]  = low_is_local[debug_mask]
        dbg["high_is_local"] = high_is_local[debug_mask]
        dbg["neighbors_ok_bull"] = neighbors_ok_bull[debug_mask]
        dbg["neighbors_ok_bear"] = neighbors_ok_bear[debug_mask]
        dbg["bull_shape"] = bull_shape[debug_mask]
        dbg["bear_shape"] = bear_shape[debug_mask]
        dbg["context_buy"]  = context_buy[debug_mask]
        dbg["context_sell"] = context_sell[debug_mask]

        # безопасное присвоение bool через reindex
        cb = pd.Series(False, index=dbg.index)
        cs = pd.Series(False, index=dbg.index)
        cb_full = pd.Series(False, index=d.index)
        cs_full = pd.Series(False, index=d.index)
        try:
            cb_full = pd.Series(conf_bull).reindex(d.index).fillna(False).astype(bool)
            cs_full = pd.Series(conf_bear).reindex(d.index).fillna(False).astype(bool)
        except Exception:
            pass
        dbg.loc[:, "conf_bull"] = cb_full.reindex(dbg.index).fillna(False).astype(bool)
        dbg.loc[:, "conf_bear"] = cs_full.reindex(dbg.index).fillna(False).astype(bool)

        def reason(row):
            if not row["small_body"]: return "body"
            if not (row["neighbors_ok_bull"] or row["neighbors_ok_bear"]): return "neighbors"
            if not (row["low_is_local"] or row["high_is_local"]): return "local_ext"
            if not row["vol_ok"]: return "volume"
            if not (row["atr_ok"] and row["rng_ok"]): return "atr/range"
            if not (row["context_buy"] or row["context_sell"]): return "context"
            if not (row["conf_bull"] or row["conf_bear"]): return "confirm"
            return "pass"

        dbg["fail_reason"] = dbg.apply(reason, axis=1)
        from pathlib import Path
        Path("out").mkdir(parents=True, exist_ok=True)
        dbg.to_csv("out/debug_candidates.csv", index=False)

    return out.reset_index(drop=True)
