# app/config_params.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


def _getenv(name: str, default: str | None = None) -> str:
    v = os.getenv(name)
    if v is None:
        return "" if default is None else default
    return v.strip()


def _as_bool(name: str, default: bool) -> bool:
    raw = _getenv(name, "1" if default else "0").lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _as_int(name: str, default: int) -> int:
    raw = _getenv(name, str(default))
    try:
        return int(float(raw))
    except Exception:
        return default


def _as_float(name: str, default: float) -> float:
    raw = _getenv(name, str(default))
    try:
        return float(raw.replace(",", "."))
    except Exception:
        return default


def _as_choice(name: str, default: str, choices: tuple[str, ...]) -> str:
    raw = _getenv(name, default).lower()
    return raw if raw in choices else default


@dataclass(frozen=True)
class HammerParams:
    # Геометрия
    body_max_frac: float
    wick_mult: float
    opp_wick_max_frac: float

    # «Почти экстремум»
    ext_window: int
    ext_eps_ticks: float

    # Ликвидность/волатильность
    vol_prct_min: float
    atr_k_max: float
    min_range_ticks: float

    # Подтверждение
    confirm_mode: Literal["classic", "pullback", "classic2"]
    confirm_horizon: int

    # «Соседи»
    neighbor_mode: Literal["both", "left_or_right"]
    neighbor_eps_ticks: float

    # Контекст уровней/EMA
    level_touch_enable: bool
    level_lookback: int
    level_tol_ticks: float
    ema_confl_enable: bool
    ema_period: int
    ema_tol_ticks: float

    # Двойной объём
    vol_dual_enable: bool
    vol_dual_window: int
    vol_dual_prct: float

    # RSI-контекст
    rsi_enable: bool
    rsi_period: int
    rsi_ob: float
    rsi_os: float


def get_hammer_params() -> HammerParams:
    return HammerParams(
        # Геометрия
        body_max_frac=_as_float("HAMMER_BODY_MAX_FRAC", 0.30),
        wick_mult=_as_float("HAMMER_WICK_MULT", 2.5),
        opp_wick_max_frac=_as_float("HAMMER_OPP_WICK_MAX_FRAC", 0.60),
        # «Почти экстремум»
        ext_window=_as_int("HAMMER_EXT_WINDOW", 5),
        ext_eps_ticks=_as_float("HAMMER_EXT_EPS_TICKS", 1.0),
        # Ликвидность/волатильность
        vol_prct_min=_as_float("HAMMER_VOL_PRCT_MIN", 0.80),
        atr_k_max=_as_float("HAMMER_ATR_K_MAX", 2.5),
        min_range_ticks=_as_float("HAMMER_MIN_RANGE_TICKS", 1.0),
        # Подтверждение
        confirm_mode=_as_choice("HAMMER_CONFIRM_MODE", "classic", ("classic", "pullback", "classic2")),  # type: ignore[arg-type]
        confirm_horizon=max(1, min(2, _as_int("HAMMER_CONFIRM_HORIZON", 1))),
        # «Соседи»
        neighbor_mode=_as_choice("HAMMER_NEIGHBOR_MODE", "both", ("both", "left_or_right")),  # type: ignore[arg-type]
        neighbor_eps_ticks=_as_float("NEIGHBOR_EPS_TICKS", 0.0),
        # Контекст уровней/EMA
        level_touch_enable=_as_bool("LEVEL_TOUCH_ENABLE", False),
        level_lookback=_as_int("LEVEL_LOOKBACK", 120),
        level_tol_ticks=_as_float("LEVEL_TOL_TICKS", 2.0),
        ema_confl_enable=_as_bool("EMA_CONFL_ENABLE", False),
        ema_period=_as_int("EMA_PERIOD", 50),
        ema_tol_ticks=_as_float("EMA_TOL_TICKS", 3.0),
        # Двойной объём
        vol_dual_enable=_as_bool("VOLUME_DUAL_ENABLE", False),
        vol_dual_window=_as_int("VOLUME_DUAL_WINDOW", 60),
        vol_dual_prct=_as_float("VOLUME_DUAL_PRCT", 0.70),
        # RSI-контекст
        rsi_enable=_as_bool("RSI_ENABLE", False),
        rsi_period=_as_int("RSI_PERIOD", 14),
        rsi_ob=_as_float("RSI_OB", 65.0),
        rsi_os=_as_float("RSI_OS", 35.0),
    )
