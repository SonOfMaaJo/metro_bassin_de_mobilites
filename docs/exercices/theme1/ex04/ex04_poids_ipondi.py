import polars as pl
from math import ceil


if __name__ == '__main__':
    data = pl.read_parquet('RP2022_mobpro.parquet')
    trans = data.filter(pl.col('DCLT') == '99999')
    pays_trans = (
        trans
        .filter(
            (pl.col('COMMUNE').cast(pl.Utf8).str.starts_with('67')) |
            (pl.col('COMMUNE').cast(pl.Utf8).str.starts_with('57'))
        )
        .with_columns(
            pl.col('DCFLT').cast(pl.Utf8).str.extract(r'(^.{2})*', 1)
            .alias('pref'),
            pl.col('COMMUNE').cast(pl.Utf8).str.extract(r'(^.{2})*', 1)
            .alias('dept')
        )
    )
    al_trans = (
        pays_trans
        .filter(
            pl.col('pref') == 'AL'
        )
    )
    print(f'lignes (brut): {al_trans.shape[0]}')
    weight = (
        al_trans
        .select(
            pl.col('IPONDI').sum().alias('sum'),
            pl.col('IPONDI').mean().alias('mean')
        )
    )
    print(f'somme IPONDI: {ceil(weight.row(0)[0])}')
    print(f'poids moyen global: {weight.row(0)[1]}')
    weight_per_dept = (
        al_trans
        .group_by('dept')
        .agg(pl.col('IPONDI').mean())
    )
    row = weight_per_dept.row(0)
    print(f'poids moyen dept {row[0]}: {row[1]}')
    row = weight_per_dept.row(1)
    print(f'poids moyen dept {row[0]}: {row[1]}')
    ## selon https://www.insee.fr/fr/information/2383202, la variable
    ## IPONDI représente le poids d'un individu, cela fait référence en réalité
    ## au nombre d'invidu que représente un enregistrement statistiquement
    ## dans le jeu de données.
