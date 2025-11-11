# app/runner/scan_once.py
from __future__ import annotations

import pandas as pd
from pathlib import Path

from app.config import get_settings
from app.config_params import get_hammer_params
from app.signals.hammer import detect_hammers
from app.signals.postprocess import enrich_positions


def _read_tf(tf: str, tz: str) -> pd.DataFrame:
    """
    Читает data/{tf}.parquet, гарантирует сортировку и локальный TZ.
    Ожидаемые колонки: datetime, open, high, low, close, volume.
    """
    p = Path(f"data/{tf}.parquet")
    if not p.exists():
        return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])

    df = pd.read_parquet(p).sort_values("datetime").reset_index(drop=True)

    # TZ → UTC → локальный tz (для корректной маски клиринга)
    if "datetime" not in df.columns:
        return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
    if str(df["datetime"].dtype) != "datetime64[ns, UTC]":
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

    df["datetime"] = df["datetime"].dt.tz_convert(tz)
    return df


def scan_once() -> pd.DataFrame:
    """
    Склеивает сигналы по всем ТФ из конфигурации и возвращает итоговый DataFrame.
    Ничего не пишет на диск.
    """
    cfg = get_settings()
    hp = get_hammer_params()

    all_out: list[pd.DataFrame] = []
    for tf in cfg.timeframes:
        df = _read_tf(tf, cfg.tz)
        if df.empty or len(df) < 50:
            continue

        sig = detect_hammers(
            df,
            body_max_frac=hp.body_max_frac,
            wick_mult=hp.wick_mult,
            opp_wick_max_frac=hp.opp_wick_max_frac,
            ext_window=hp.ext_window,
            ext_eps_ticks=hp.ext_eps_ticks,
            vol_prct_min=hp.vol_prct_min,
            atr_k_max=hp.atr_k_max,
            min_range_ticks=hp.min_range_ticks,
            confirm_mode=hp.confirm_mode,
            confirm_horizon=hp.confirm_horizon,
            neighbor_mode=hp.neighbor_mode,
            neighbor_eps_ticks=hp.neighbor_eps_ticks,
            level_touch_enable=hp.level_touch_enable,
            level_lookback=hp.level_lookback,
            level_tol_ticks=hp.level_tol_ticks,
            ema_confl_enable=hp.ema_confl_enable,
            ema_period=hp.ema_period,
            ema_tol_ticks=hp.ema_tol_ticks,
            vol_dual_enable=hp.vol_dual_enable,
            vol_dual_window=hp.vol_dual_window,
            vol_dual_prct=hp.vol_dual_prct,
            rsi_enable=hp.rsi_enable,
            rsi_period=hp.rsi_period,
            rsi_ob=hp.rsi_ob,
            rsi_os=hp.rsi_os,
        )

        if not sig.empty:
            sig.insert(1, "tf", tf)  # колонка сразу после datetime
            all_out.append(sig)

    if not all_out:
        return pd.DataFrame()

    out = pd.concat(all_out, ignore_index=True)
    out = enrich_positions(out)

    # Отсечка «копеечных» целей — включай после диагностики:
    # out = out[out["pp_target"] >= 12]  # ≥ 12 п.п.

    out = out.sort_values("datetime").reset_index(drop=True)
    return out


def scan_parquet(output_csv: str = "out/signals.csv") -> pd.DataFrame:
    """
    Backward-compatible: собирает сигналы и сохраняет их в CSV.
    Возвращает тот же DataFrame.
    """
    df = scan_once()
    Path("out").mkdir(parents=True, exist_ok=True)

    if df.empty:
        print("No signals found on selected TFs")
        return df

    df.to_csv(output_csv, index=False)
    # Короткая сводка в stdout (как раньше)
    tf_counts = df["tf"].value_counts().to_dict()
    for tf in sorted(tf_counts.keys(), key=lambda x: (len(x), x)):
        print(f"Signals on {tf}: {tf_counts[tf]}")
    print(f"Saved signals to {output_csv}")
    # Показать хвост в консоль для удобства
    try:
        print(df.tail(10).to_string())
    except Exception:
        pass
    return df
