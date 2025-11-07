from dataclasses import dataclass
from dotenv import load_dotenv
from loguru import logger
import os

load_dotenv()

@dataclass
class Settings:
    tinkoff_token: str
    symbol: str
    figi: str | None
    timeframes: list[str]
    history_days: int
    tz: str

def get_settings() -> Settings:
    token = os.getenv("TINKOFF_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TINKOFF_TOKEN is empty. Put it into .env")

    symbol = os.getenv("SYMBOL", "MOEXF").strip()
    figi = os.getenv("FIGI", "").strip() or None
    tfs = [x.strip() for x in os.getenv("TIMEFRAMES", "5m").split(",") if x.strip()]
    days = int(os.getenv("HISTORY_DAYS", "30"))
    tz = os.getenv("TZ", "Europe/Moscow")

    logger.info("Config loaded: SYMBOL={}, FIGI set? {}, TFs={}", symbol, bool(figi), tfs)
    return Settings(
        tinkoff_token=token,
        symbol=symbol,
        figi=figi,
        timeframes=tfs,
        history_days=days,
        tz=tz,
    )
