import polars as pl
import matplotlib.pyplot as plt
import argparse
import sys


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Inspect a parquet file")
    parser.add_argument('filepath', type=str,
                        help='path of the required parquet file')
    parser.add_argument('-c', '--column', help='specifying column')
    parser.add_argument('-s', '--schema',
                        help='print the schema of a parquet',
                        action='store_true')
    parser.add_argument('-t', '--stats',
                        help='display a statisitc of a specify row')
    parser.add_argument('-i', '--hist',
                        help='display histograms of a specifier columnsi')
    args = parser.parse_args()
    try:
        data = pl.scan_parquet(args.filepath)
        if args.schema:
            schema = data.collect_schema()
            print("schema of the parquet file: ")
            print(pl.DataFrame({'columns' : schema.names(),
                                'type': schema.dtypes()}))
        if args.stats is not None:
            stat = (
                data
                .select(pl.col(args.stats))
                .collect(engine="streaming")
                .describe()
            )
            print(f"statistics of the column {args.stats}:")
            print(stat)
        if args.hist is not None:
            col = (
                data
                .select(pl.col(args.column))
                .collect(engine="streaming")
            )
            if isinstance(col.schema[args.column], pl.Duration):
                col = col.select(
                    pl.col(args.column).dt.total_seconds().alias(args.column))
            plt.hist(col)
            plt.xlabel(f'{args.column}')
            plt.ylabel('Frequency')
            plt.tight_layout()
            plt.savefig(args.hist)
    except Exception as e:
        print(f"{type(e).__name__} -- {e}")
        sys.exit(1)
