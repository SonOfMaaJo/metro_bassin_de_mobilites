import polars as pl


if __name__ == '__main__':
    data = pl.read_parquet('RP2022_mobpro.parquet')
    trans = data.filter(pl.col('DCLT') == '99999')
    pays_trans = (
        trans
        .filter(
            (pl.col('COMMUNE').cast(pl.Utf8).str.starts_with('67')) |
            (pl.col('COMMUNE').cast(pl.Utf8).str.starts_with('57'))
        )
        .select(
            pl.col('DCFLT').cast(pl.Utf8).str.extract(r'(^.{2})*', 1)
            .alias('pref')
        )
        .group_by('pref')
        .agg(pl.len().alias('count'))
    )
    print(pays_trans)
    # le site pour télécharger le document est celui de l'ex00 et le nom du
    # document est exactement contenu_RP2022.pdf
    # AL pour l'allemagne, BE pour la belgique, LU pour luxembourg, SU pour la
    # suisse, ZZ pour le sans object.
