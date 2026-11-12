"""

"""
import polars as pl


if __name__ == "__main__":
    data = pl.read_parquet("BASSIN_MOBILITE_GE_persons.parquet")
    data = data.with_columns(
        pl.when(pl.col("age").is_between(0, 17)).then(1)
        .when(pl.col("age").is_between(18, 24)).then(2)
        .when(pl.col("age").is_between(25, 34)).then(3)
        .when(pl.col("age").is_between(35, 49)).then(4)
        .when(pl.col("age").is_between(50, 64)).then(5)
        .when(pl.col("age") >= 65).then(6)
        .otherwise(0).alias("tranche_age")
    )
    print(data.shape)
    table = (
        data
        .group_by(["tranche_age", "sex"])
        .agg(pl.len().alias("effectif"))
        .pivot(index="tranche_age", on="sex", values="effectif")
        .sort(by=pl.col("tranche_age"))
    )
    print(table)
