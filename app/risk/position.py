import pandas as pd
import numpy as np

PP_RUB = 10.0          # 1 п.п. = 10 ₽
ROUND_TRIP_COMMS = 0.0005  # вход+выход ≈ 0.05% (0.025% на сторону)

def infer_tick(series: pd.Series) -> float:
    diffs = series.diff().abs()
    diffs = diffs[(diffs > 0) & np.isfinite(diffs)]
    if len(diffs) == 0:
        return 0.5
    return float(diffs.quantile(0.05))

def enrich_positions(df_src: pd.DataFrame, full_df: pd.DataFrame, R_target: float = 2.0, tick_buf: int = 2) -> pd.DataFrame:
    """
    df_src — результат detect_hammers (строки с datetime, O/H/L/C, signal)
    full_df — исходные свечи (для оценки тика и подтверждающей цены)
    """
    d = df_src.copy()
    # входим ценой закрытия следующей свечи (подтверждающей)
    next_close_map = full_df.set_index('datetime')['close'].shift(-1)
    # сопоставим по индексу времени; если нет — используем close текущего
    d['entry'] = d['datetime'].map(next_close_map).fillna(d['close'])

    tick = infer_tick(full_df['close'])
    buf = tick_buf * tick

    d['stop'] = np.where(d['signal']=='BUY', d['low']  - buf, d['high'] + buf)
    risk_abs  = (d['entry'] - d['stop']).abs()

    d['tp'] = np.where(d['signal']=='BUY', d['entry'] + R_target * risk_abs,
                                       d['entry'] - R_target * risk_abs)

    # R (без/с комиссии)
    gross_R = (d['tp'] - d['entry']).abs() / (d['entry'] - d['stop']).abs()
    # учтём ~0.05% round-trip как снижение прибыли в п.п.
    comm_pp = d['entry'] * ROUND_TRIP_COMMS   # «в п.п.» в ценах инструмента
    net_reward_pp = (d['tp'] - d['entry']).abs() - comm_pp
    net_R = net_reward_pp / (d['entry'] - d['stop']).abs()

    d['R'] = net_R.round(2)
    d['pp_risk'] = (risk_abs).round(2)
    d['pp_target'] = (np.abs(d['tp'] - d['entry'])).round(2)
    d['rub_R'] = (d['pp_target'] * PP_RUB).round(0)

    return d
