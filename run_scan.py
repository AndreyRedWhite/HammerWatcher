from app.config import get_settings
from app.runner.scan_once import scan_parquet
from app.utils.dedup import dedup_multi_tf
from loguru import logger
import pandas as pd
from pathlib import Path

if __name__ == "__main__":
    cfg = get_settings()
    parts = []
    for tf in cfg.timeframes:
        try:
            part = scan_parquet(cfg.symbol, tf)
            if not part.empty:
                parts.append(part)
                logger.info("Signals on {}: {}", tf, len(part))
            else:
                logger.info("No signals on {}", tf)
        except Exception as e:
            logger.warning("Scan failed on {}: {}", tf, e)

    if parts:
        out = pd.concat(parts).sort_values(['datetime','tf']).reset_index(drop=True)
        # приоритет: 5m старше 1m; дополни при необходимости
        out = dedup_multi_tf(out, priority_tf=['15m','5m','1m'], within_seconds=180)
        Path("out").mkdir(exist_ok=True, parents=True)
        out_path = Path("out/signals.csv")
        out.to_csv(out_path, index=False)
        logger.info("Saved signals to {}", out_path)
        print(out.tail(10).to_string(index=False))
    else:
        logger.info("No signals found on selected TFs")
