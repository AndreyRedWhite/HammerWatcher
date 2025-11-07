from dataclasses import dataclass
import os

@dataclass
class HammerParams:
    body_max_frac: float
    wick_mult: float
    opp_wick_max_frac: float
    ext_window: int
    ext_eps_ticks: float
    vol_prct_min: float
    atr_k_max: float
    min_range_ticks: float
    confirm_mode: str

def get_hammer_params() -> HammerParams:
    env = os.getenv
    return HammerParams(
        body_max_frac=float(env("HAMMER_BODY_MAX_FRAC", "0.35")),
        wick_mult=float(env("HAMMER_WICK_MULT", "2.1")),
        opp_wick_max_frac=float(env("HAMMER_OPP_WICK_MAX_FRAC", "0.90")),
        ext_window=int(env("HAMMER_EXT_WINDOW", "4")),
        ext_eps_ticks=float(env("HAMMER_EXT_EPS_TICKS", "1.5")),
        vol_prct_min=float(env("HAMMER_VOL_PRCT_MIN", "0.65")),
        atr_k_max=float(env("HAMMER_ATR_K_MAX", "3.2")),
        min_range_ticks=float(env("HAMMER_MIN_RANGE_TICKS", "0.5")),
        confirm_mode=env("HAMMER_CONFIRM_MODE", "pullback"),
    )
