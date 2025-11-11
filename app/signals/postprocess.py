# app/signals/postprocess.py
from __future__ import annotations

import os
import pandas as pd
import numpy as np

# ==== Параметры по умолчанию (можно переопределить в .env) ====
# целевой риск-профит (сколько "R" берем по цели)
RR_TARGET = float(os.getenv("RR_TARGET", "1.80"))          # типично 1.8..2.0
# стоимость 1 п.п. (для MOEXF — 10 ₽)
RUB_PER_PP = float(os.getenv("RUB_PER_PP", "10"))
# комиссия на фьючерсы в долях (за один трейд/плечо), по умолчанию 0.025%:
COMMISSION_FRAC = float(os.getenv("COMMISSION_FRAC", "0.00025"))  # 0.025% = 0.00025
# учитывать комиссии при расчёте R в рублях
INCLUDE_FEES = os.getenv("INCLUDE_FEES", "1").strip() in {"1", "true", "yes", "on"}


def _calc_one_side(row: pd.Series) -> pd.Series:
    """
    Рассчитывает entry/stop/tp и метрики для одной строки сигнала.
    Правило:
      BUY  -> entry = high, stop = low,  tp = entry + RR*(entry - stop)
      SELL -> entry = low,  stop = high, tp = entry - RR*(stop - entry)
    """

    side = row["signal"]
    high = float(row["high"])
    low  = float(row["low"])

    if side == "BUY":
        entry = high
        stop  = low
        dist  = max(entry - stop, 0.0)
        tp    = entry + RR_TARGET * dist
    else:  # SELL
        entry = low
        stop  = high
        dist  = max(stop - entry, 0.0)
        tp    = entry - RR_TARGET * dist

    # п.п. и ₽
    pp_stop   = dist
    pp_target = abs(tp - entry)
    rub_stop  = pp_stop   * RUB_PER_PP
    rub_targ  = pp_target * RUB_PER_PP

    # Комиссии (грубо: проценты от "номинала" входа в рублях),
    # считаем round-trip (2 плеча: вход+выход).
    # Номинал 1 контракта в рублях оцениваем как entry * RUB_PER_PP.
    # Это приближение, но для MOEXF (1 п.п. = 10 ₽) даёт корректный порядок.
    roundtrip_fees = 0.0
    if INCLUDE_FEES and COMMISSION_FRAC > 0.0:
        notional_rub = entry * RUB_PER_PP
        roundtrip_fees = 2.0 * COMMISSION_FRAC * notional_rub

    # метрики "в R": одно "R" = риск до стопа в рублях
    rub_R = rub_targ - roundtrip_fees
    R = (rub_R / rub_stop) if rub_stop > 0 else np.nan

    row_out = row.copy()
    row_out["entry"] = entry
    row_out["stop"]  = stop
    row_out["tp"]    = tp
    row_out["pp_stop"]   = pp_stop
    row_out["pp_target"] = pp_target
    row_out["rub_stop"]  = rub_stop
    row_out["rub_target"] = rub_targ
    row_out["fees_rub_round"] = roundtrip_fees
    row_out["R"] = R
    row_out["rub_R"] = rub_R
    # причину дополним краткой меткой RR
    row_out["why"] = f"{row.get('why','')};RR{RR_TARGET}".strip(";")
    return row_out


def enrich_positions(df_signals: pd.DataFrame) -> pd.DataFrame:
    """
    На вход — сигналы (datetime, open, high, low, close, volume, signal, why)
    На выход — добавлены entry/stop/tp, pp_*, rub_* и метрики R.
    """
    if df_signals.empty:
        return df_signals

    # упорядочим и прогоним построчно (векторизация тут не критична)
    cols_needed = ["datetime", "open", "high", "low", "close", "volume", "signal", "why"]
    for c in cols_needed:
        if c not in df_signals.columns:
            df_signals[c] = np.nan

    out = df_signals.apply(_calc_one_side, axis=1)
    # финальная сортировка по времени
    out = out.sort_values("datetime").reset_index(drop=True)
    return out
