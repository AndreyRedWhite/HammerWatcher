from datetime import datetime, timedelta, timezone
from typing import Iterable, List
import pandas as pd
from loguru import logger
from tinkoff.invest import Client, CandleInterval, SecurityTradingStatus
import pytz

TF_MAP = {
    "1m": CandleInterval.CANDLE_INTERVAL_1_MIN,
    "5m": CandleInterval.CANDLE_INTERVAL_5_MIN,
    "15m": CandleInterval.CANDLE_INTERVAL_15_MIN,
    "1h": CandleInterval.CANDLE_INTERVAL_HOUR,
}

# Максимальная длина интервала для одного GetCandles по Тинькофф
# (ориентиры из доков/практики)
MAX_SPAN = {
    "1m": timedelta(days=1),
    "5m": timedelta(days=7),
    "15m": timedelta(days=31),
    "1h": timedelta(days=365),
}

def _interval_to_api(tf: str) -> CandleInterval:
    if tf not in TF_MAP:
        raise ValueError(f"Unsupported timeframe: {tf}")
    return TF_MAP[tf]

def _span_for(tf: str) -> timedelta:
    if tf not in MAX_SPAN:
        raise ValueError(f"No MAX_SPAN configured for {tf}")
    return MAX_SPAN[tf]

def _q(n) -> float:
    return n.units + n.nano / 1e9

def _get_candles_once(client: Client, figi: str, tf: str, start_utc: datetime, end_utc: datetime):
    interval = _interval_to_api(tf)
    resp = client.market_data.get_candles(
        figi=figi,
        from_=start_utc.replace(tzinfo=timezone.utc),
        to=end_utc.replace(tzinfo=timezone.utc),
        interval=interval,
    ).candles
    rows = [{
        "datetime": pd.Timestamp(c.time.replace(tzinfo=timezone.utc)),
        "open":  _q(c.open),
        "high":  _q(c.high),
        "low":   _q(c.low),
        "close": _q(c.close),
        "volume": c.volume,
    } for c in resp]
    return rows

def load_candles_df(client: Client, figi: str, tf: str, start_dt_utc: datetime, end_dt_utc: datetime, tz: str) -> pd.DataFrame:
    """Чанкуем диапазон на куски допустимой длины и склеиваем."""
    chunk = _span_for(tf)
    cur_start = start_dt_utc
    all_rows: List[dict] = []

    while cur_start < end_dt_utc:
        cur_end = min(cur_start + chunk, end_dt_utc)
        try:
            rows = _get_candles_once(client, figi, tf, cur_start, cur_end)
            all_rows.extend(rows)
            logger.debug("Fetched {}..{} [{}]: {} candles",
                         cur_start.isoformat(), cur_end.isoformat(), tf, len(rows))
        except Exception as e:
            logger.warning("Chunk failed {}..{} [{}]: {}", cur_start, cur_end, tf, e)
        # шаг вперёд — без перекрытия
        cur_start = cur_end

    if not all_rows:
        return pd.DataFrame(columns=["datetime","open","high","low","close","volume"])

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["datetime"]).sort_values("datetime")
    msk = pytz.timezone(tz)
    df["datetime"] = df["datetime"].dt.tz_convert(msk)
    return df

# --------- Поиск FIGI (как раньше) ---------
def search_figi(client: Client, query: str):
    res = []
    futs = client.instruments.futures().instruments
    for f in futs:
        if query.upper() in (f.ticker.upper(), f.name.upper()):
            res.append((f.ticker, f.figi))
    shares = client.instruments.shares().instruments
    for s in shares:
        if query.upper() in (s.ticker.upper(), s.name.upper()):
            res.append((s.ticker, s.figi))
    return res

from datetime import datetime as dt
def figure_out_figi(client: Client, symbol: str, preferred: str | None = None) -> str:
    if preferred:
        logger.info("Using FIGI from config: {}", preferred)
        return preferred
    matches = search_figi(client, symbol)
    if not matches:
        raise RuntimeError(f"Cannot find instrument by SYMBOL={symbol}. Provide FIGI.")
    ticker, figi = matches[0]
    logger.info("Selected {} / FIGI={}", ticker, figi)
    return figi
