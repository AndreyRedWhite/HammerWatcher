from pathlib import Path
import pandas as pd

DATA_DIR = Path("app/data")

def path_for(symbol: str, tf: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / f"{symbol}_{tf}.parquet"

def save_append_dedup(df_new: pd.DataFrame, symbol: str, tf: str) -> int:
    """Добавляет новые свечи к локальному файлу и удаляет дубликаты по datetime."""
    p = path_for(symbol, tf)
    if p.exists():
        df_old = pd.read_parquet(p)
        df = pd.concat([df_old, df_new], ignore_index=True)
        df = df.drop_duplicates(subset=["datetime"]).sort_values("datetime")
    else:
        df = df_new.drop_duplicates(subset=["datetime"]).sort_values("datetime")
    df.to_parquet(p, index=False)
    return len(df_new)
