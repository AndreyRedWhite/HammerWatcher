from app.config import get_settings
from app.runner.scan_once import scan_parquet
from loguru import logger
import pandas as pd
from pathlib import Path

if __name__ == "__main__":
    cfg = get_settings()
    all_parts = []
    for tf in cfg.timeframes:
        try:
            part = scan_parquet(cfg.symbol, tf)
            if not part.empty:
                all_parts.append(part)
                logger.info("Signals on {}: {}", tf, len(part))
            else:
                logger.info("No signals on {}", tf)
        except Exception as e:
            logger.warning("Scan failed on {}: {}", tf, e)

    if all_parts:
        out = pd.concat(all_parts).sort_values(['datetime','tf'])
        Path("out").mkdir(exist_ok=True, parents=True)
        out_path = Path("out/signals.csv")
        out.to_csv(out_path, index=False)
        logger.info("Saved signals to {}", out_path)
        print(out.tail(10).to_string(index=False))
    else:
        logger.info("No signals found on selected TFs")
