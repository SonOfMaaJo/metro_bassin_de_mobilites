import argparse
import polars as pl
import resource


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Comparasion Lazy API, query plan and "
                                     "streaming")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-e', '--eager',
                       help="eager mode for read a parquet file.",
                       action="store_true")
    group.add_argument('-l', '--lazy', help="lazy mod for read parquet file.",
                       action="store_true")
    group.add_argument('-s', '--sink', help="write the result in parquet file",
                      action="store_true")
    args = parser.parse_args()
    if args.eager:
        data = pl.read_parquet("route_results.parquet")
        filter_pointe = data.filter(
            (pl.col("entry_time") >= 21600) & (pl.col("entry_time") <= 32400)
        )
        charge = (
            filter_pointe.group_by("edge_id")
            .agg(pl.len())
            .sort(by="edge_id")
        )
        charge.write_parquet("route_results_6h-9h.parquet")
    elif args.lazy:
        data = pl.scan_parquet("route_results.parquet")
        filter_pointe = (
            data
            .filter(
                (pl.col("entry_time") >= 21600) &
                (pl.col("entry_time") <=32400)
            )
        )
        charge = (
            filter_pointe.group_by("edge_id")
            .agg(pl.len())
            .sort(by="edge_id")
        )
        result = charge.collect(engine="streaming")
        result.write_parquet("route_results_6h-9h.parquet")
    elif args.sink:
        data = pl.scan_parquet("route_results.parquet")
        filter_pointe = (
            data
            .filter(
                (pl.col("entry_time") >= 21600) &\
                (pl.col("entry_time") <=32400)
            )
        )
        charge = (
            filter_pointe.group_by("edge_id")
            .agg(pl.len())
            .sort(by="edge_id")
        )
        charge.sink_parquet("route_results_6h-9h.parquet")
    print("utilisation ressource :",
          f"{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}")
