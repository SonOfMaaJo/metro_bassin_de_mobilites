## Selon https://www.danilchenko.dev/posts/duckdb-vs-polars/
## L'utilisation d'un DataFrame pour des opérations de type Groupby est
## préféré sur polars que sur duckdb

import polars as pl
import pandas as pd
from time import perf_counter
import matplotlib.pyplot as plt
import duckdb
import numpy as np

if __name__ == '__main__':
    number: int = 10
    times:  list[list[float]] = []
    data_p = pl.read_parquet("BASSIN_MOBILITE_GE_DE_trips.parquet")
    data_l = pl.scan_parquet("BASSIN_MOBILITE_GE_DE_trips.parquet")
    data_pd = pd.read_parquet("BASSIN_MOBILITE_GE_DE_trips.parquet")
    for i in range(number):
        times.append([])
        start = perf_counter()
        trajets_per_fpurpose = (
            data_p
            .group_by("following_purpose")
            .agg(pl.len())
            .sort("following_purpose", descending=True)
        )
        end = perf_counter()
        times[i].append(end - start)

        start = perf_counter()
        schema = (
            data_l
            .group_by("following_purpose")
            .agg(pl.len())
            .sort("following_purpose", descending=True)
        )
        trajets_per_fpurpose = schema.collect(engine="streaming")
        end = perf_counter()
        times[i].append(end - start)

        start = perf_counter()
        trajets_per_fpurpose = (
            data_pd.groupby("following_purpose")
            .size()
            .reset_index(name='count')
            .sort_values(by='count', ascending=False)
            .reset_index(drop=True)
        )
        end = perf_counter()
        times[i].append(end - start)

        start = perf_counter()
        trajets = duckdb.sql(f"""
            SELECT following_purpose, COUNT(*) As n
            FROM read_parquet('BASSIN_MOBILITE_GE_DE_trips.parquet')
            GROUP BY following_purpose
            ORDER by n DESC
        """).fetchall()
        end = perf_counter()
        times[i].append(end - start)
    times = np.array(times)
    mean = times[1:, :].mean(axis=0)
    std = times[1:, :].std(axis=0)
    plt.bar(['eager_p', 'lazy_p', 'pandas', 'duckdb'], mean,
            yerr=std, color=['red', 'blue', 'green', 'orange'])
    plt.xlabel("method")
    plt.ylabel('mean time')
    plt.title('benchmark')
    plt.savefig('ex07_benchmark.png', dpi=300, bbox_inches='tight')
