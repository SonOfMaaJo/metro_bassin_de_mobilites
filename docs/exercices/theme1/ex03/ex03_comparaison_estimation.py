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
        .with_columns(
            pl.col('DCFLT').cast(pl.Utf8).str.extract(r'(^.{2})*', 1)
            .alias('pref')
        )
        .group_by('pref')
        .agg(pl.len().alias('count'))
    )
    al_trans = (
        pays_trans
        .filter(
            pl.col('pref') == 'AL'
        )
    )
    fron_al_est = pl.read_csv('frontaliers_allemagne_estimation.csv',
                              ignore_errors=True, comment_prefix='#')
    print('lignes DCFLT=AL (dept 67+57, RP2022, non pondéré) :'
          f' {al_trans.row(0)[1]}')
    print('somme estimation bassin (fichier CSV, RP2018)'
          f': {fron_al_est.select(pl.col('frontaliers_allemagne_2018_estimation_bassin').sum()).row(0)[0]}')
    ## j'ai trouvé le fichier ac_cp_2023_ina_167.pdf en tapant Insee Analyses
    ## Grand Est n167
    ## les raisons de la différences peuvent provenir de la pondération,
    ## nous n'avons pas tenir compte de la pondération dans notre calcul avec
    ## RP2022, aussi la différence des années entre les deux comptes.
