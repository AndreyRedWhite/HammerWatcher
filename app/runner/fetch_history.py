from datetime import datetime, timedelta, timezone
from loguru import logger
from tinkoff.invest import Client
from app.config import get_settings
from app.brokers.tinkoff_client import figure_out_figi, load_candles_df
from app.utils.storage import save_append_dedup

def run_history():
    cfg = get_settings()
    with Client(cfg.tinkoff_token) as client:
        figi = figure_out_figi(client, cfg.symbol, cfg.figi)
        utc_now = datetime.now(timezone.utc)
        start_utc = utc_now - timedelta(days=cfg.history_days)

        for tf in cfg.timeframes:
            logger.info("Fetching {} history for FIGI={} ({} days)…", tf, figi, cfg.history_days)
            df = load_candles_df(client, figi, tf, start_utc, utc_now, cfg.tz)
            if df.empty:
                logger.warning("No candles returned for {}", tf)
                continue
            n = save_append_dedup(df, cfg.symbol, tf)
            logger.info("Saved {} new candles [{}]", n, tf)

if __name__ == "__main__":
    run_history()
