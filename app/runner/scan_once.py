from pathlib import Path
import pandas as pd
from loguru import logger
from app.signals.hammer import detect_hammers
from app.risk.position import enrich_positions

def scan_parquet(symbol: str, tf: str) -> pd.DataFrame:
    p = Path(f"app/data/{symbol}_{tf}.parquet")
    if not p.exists():
        raise FileNotFoundError(p)
    df = pd.read_parquet(p)
    df = df.sort_values('datetime').reset_index(drop=True)
    sig = detect_hammers(df,
                         body_max_frac=0.30,
                         wick_mult=2.5,
                         opp_wick_max_frac=0.60,
                         ext_window=5,
                         vol_mult=1.2,
                         atr_k_max=2.5,
                         confirm_mode="classic")
    if sig.empty:
        return sig
    pos = enrich_positions(sig, df, R_target=2.0, tick_buf=2)
    pos['tf'] = tf
    # красивый порядок колонок
    cols = ['datetime','tf','signal','entry','stop','tp','R','rub_R','why','open','high','low','close','volume']
    return pos[cols]
