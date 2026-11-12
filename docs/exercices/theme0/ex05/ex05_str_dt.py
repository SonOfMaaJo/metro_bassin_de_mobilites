## Cette exercice nous apprend la manipulation du texte et du temps
## à travers les methodes de pl.Expr
## comme méthode pas utilisé dans cette exercice nous avons :
## pl.Expr.dt.cast_time_unit pour convertir le temps en une autre unité de temps
## comme ns, us or ms
## pl.Expr.dt.date qui permet d'extraire la date dans une donnée de type
## DateTime
## pl.Expr.dt.hour extraire l'heure pour une donnée de type DateTime



import polars as pl
import geopandas as gpd


if __name__ == "__main__":
    gdf = gpd.read_file(
        "bassin_mobilite_ge_transfrontalier_simulation_area.geojson")
    data = pl.from_pandas(gdf.drop(columns="geometry"))
    data = (
        data
        .with_columns(
            pl.when(pl.col("insee").str.len_chars() == 5)
            .then(pl.lit("FR"))
            .otherwise(pl.lit("DE"))
            .alias("code")
        )
    )
    print(data.head(5))

    data = pl.read_parquet("trips.parquet")
    data = (
        data
        .with_columns(
            pl.col("departure_time").dt.total_hours().alias("heure")
        )
    )
    data = (
        data
        .with_columns(
            pl
            .when(pl.col("heure").is_between(6, 9))
            .then(pl.lit("pointe_matin"))
            .when(pl.col("heure").is_between(16, 9))
            .then(pl.lit("pointe_soir"))
            .otherwise(pl.lit("hors_pointe")).alias("periode")
        )
    )
    print(data.head(5))
