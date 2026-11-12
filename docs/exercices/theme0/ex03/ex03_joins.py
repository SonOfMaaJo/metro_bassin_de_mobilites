import polars as pl


if __name__ == "__main__":
    trips = pl.read_parquet("trips.parquet")
    zones = pl.read_parquet("trips_zones.parquet")

    inner_join = trips.join(zones, on="trip_id", how='inner', validate='1:1')
    print(inner_join)
    anti_join = trips.join(zones, on="trip_id", how='anti')
    print(anti_join)
    inner_join = zones.join(trips, on="trip_id", how='inner', validate='1:1')
    print(inner_join)
    anti_join = zones.join(trips, on="trip_id", how='anti')
    print(anti_join)
