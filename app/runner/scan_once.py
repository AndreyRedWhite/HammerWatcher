from pathlib import Path
import pandas as pd
from loguru import logger
from app.signals.hammer import detect_hammers
from app.risk.position import enrich_positions
from app.config_params import get_hammer_params

def scan_parquet(symbol: str, tf: str) -> pd.DataFrame:
    p = Path(f"app/data/{symbol}_{tf}.parquet")
    if not p.exists():
        raise FileNotFoundError(p)
    df = pd.read_parquet(p)
    df = df.sort_values('datetime').reset_index(drop=True)

    # Новый вызов: vol_prct_min вместо vol_mult, и т.д.
    hp = get_hammer_params()
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
    )

    if sig.empty:
        return sig

    pos = enrich_positions(sig, df, R_target=2.0, tick_buf=2)
    pos['tf'] = tf
    cols = ['datetime','tf','signal','entry','stop','tp','R','rub_R','why','open','high','low','close','volume']
    return pos[cols]
