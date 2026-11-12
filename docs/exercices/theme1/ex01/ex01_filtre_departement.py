import polars as pl


if __name__ == '__main__':
    data = pl.read_parquet('RP2022_mobpro.parquet')
    trans = data.filter(pl.col('DCLT') == '99999')
    zone = (
        trans
        .filter(
            (pl.col('COMMUNE').cast(pl.Utf8).str.starts_with('67')) |
            (pl.col('COMMUNE').cast(pl.Utf8).str.starts_with('57'))
        )
        .select(
            pl.col('COMMUNE').cast(pl.Utf8).str.extract(r'(^.{2})*', 1)
            .alias('dept')
        )
        .group_by('dept')
        .agg(pl.len().alias('count'))
    )
    print(zone)
