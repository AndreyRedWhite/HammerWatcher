import pandas as pd
from datetime import timedelta

def dedup_multi_tf(df: pd.DataFrame, priority_tf: list[str], within_seconds: int = 180) -> pd.DataFrame:
    """
    Оставляет по кластерам близких сигналов (±within_seconds) одну запись
    с приоритетом по старшинству TF (priority_tf) и, если равны — самую раннюю.
    df: columns ['datetime','tf','signal',...]
    """
    if df.empty:
        return df
    d = df.copy()
    d = d.sort_values('datetime').reset_index(drop=True)
    d['dt_floor'] = pd.to_datetime(d['datetime']).dt.floor(f'{within_seconds}s')
    # приоритет TF — индекс
    tf_rank = {tf:i for i,tf in enumerate(priority_tf)}  # 0 — самый старший
    d['tf_rank'] = d['tf'].map(tf_rank).fillna(len(priority_tf))
    # группируем по окнам времени и направлению
    groups = []
    used = set()
    for i,row in d.iterrows():
        if i in used:
            continue
        # кластер: рядом по времени и тому же направлению
        mask = (d['signal']==row['signal']) & (d['datetime'].between(row['datetime'] - pd.Timedelta(seconds=within_seconds),
                                                                     row['datetime'] + pd.Timedelta(seconds=within_seconds)))
        cluster = d[mask].copy()
        used.update(cluster.index.tolist())
        # выбор лучшего: минимальный tf_rank, при равенстве — минимальная datetime
        cluster = cluster.sort_values(['tf_rank','datetime'])
        groups.append(cluster.iloc[0])
    return pd.DataFrame(groups).drop(columns=['dt_floor','tf_rank'])
