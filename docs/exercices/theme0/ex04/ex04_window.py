## group_by ou over permet de faire des operations par groupe de données
## spécifié mais le cas d'utilisation est différent au niveau où nous voulons
## garder la même longueur de la trame de données car un group_by
## réduit généralement la taille du DataFrame tant en nombre de ligne qu'en
## nombre de colonnes.


import polars as pl


if __name__ == '__main__':
    data = pl.read_parquet("trips.parquet")
    data = data.with_columns(
        pl.len().over("person_id").alias("nb_trajets_personne"),
        pl.col("departure_time").rank().over("person_id").alias("rank")
    )
    trip_zones = pl.read_parquet("trips_zones.parquet")
    data = data.join(trip_zones, on="trip_id", how='inner', validate='1:1',
                     maintain_order="left")
    work_trips = data.filter(pl.col("destination_purpose_group") == "work")
    work_trips = (
        work_trips
        .with_columns(
            pl
            .col("destination_zone4")
            .rank()
            .over("person_id").alias("rank_d_com")
        )
    )
    print(work_trips.head(5))
