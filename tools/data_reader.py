import pandas as pd
print(pd.read_parquet("app/data/MOEXF_1m.parquet").tail(5))
