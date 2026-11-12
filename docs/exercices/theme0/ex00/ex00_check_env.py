import polars as pl
import geopandas as gpd
import matplotlib as mpl
import pyarrow as pyw
import duckdb as db
import sys


if __name__ == "__main__":
    try:
        print(f"polars: {pl.__version__}")
        print(f"geopandas: {gpd.__version__}")
        print(f"matplotlib: {mpl.__version__}")
        print(f"pyarrow: {pyw.__version__}")
        print(f"duckdb: {db.__version__}")
    except Exception:
        sys.exit(1)
