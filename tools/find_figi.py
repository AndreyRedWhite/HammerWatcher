# tools/find_figi.py
from tinkoff.invest import Client, SecurityTradingStatus
from loguru import logger
from dotenv import load_dotenv
import os
import re
from datetime import datetime, timezone

load_dotenv()
TOKEN = os.getenv("TINKOFF_TOKEN", "").strip()
if not TOKEN:
    raise SystemExit("Put TINKOFF_TOKEN into .env")

# Запросы, по которым чаще всего находится фьюч на индекс IMOEX:
QUERIES = [
    "MOEX", "IMOEX", "Индекс МосБиржи", "MX", "MXI"
]

def matches(instr, q: str) -> bool:
    q = q.lower()
    return (
        q in instr.ticker.lower()
        or q in instr.name.lower()
        or q in instr.basic_asset.lower()
    )

with Client(TOKEN) as client:
    futs = client.instruments.futures().instruments

    logger.info("Всего фьючей: {}", len(futs))
    candidates = []
    for f in futs:
        for q in QUERIES:
            if matches(f, q):
                candidates.append(f)
                break

    # Отсортируем: сначала нормальная торговля, потом ближайшая экспирация
    def key(f):
        status_weight = 0 if f.trading_status == SecurityTradingStatus.SECURITY_TRADING_STATUS_NORMAL_TRADING else 1
        exp = f.expiration_date or datetime(2100,1,1,tzinfo=timezone.utc)
        return (status_weight, exp)

    candidates.sort(key=key)

    print("\nКандидаты (лучшие сверху):")
    for f in candidates[:50]:
        print(f"{f.ticker:8s}  FIGI={f.figi}  name={f.name}  basic_asset={f.basic_asset}  exp={f.expiration_date}  status={f.trading_status}")

    print("\nПодсказка: выбери первый с NORMAL_TRADING и ближайшей датой экспирации.")
