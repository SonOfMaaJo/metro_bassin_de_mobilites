## Liste des variables :
## https://www.insee.fr/fr/statistiques/7637844?sommaire=7637890#dictionnaire

import polars as pl


if __name__ == '__main__':
    data = pl.read_csv('varmod_mobpro_2022.csv', separator=';',
                       ignore_errors=True)
    print(data.head(5))
    # en regardant les données, on constate que ce sont juste des références
    # à des communes et leurs libéllés, il n'ya pas de mention à des individus
    data = pl.scan_parquet('RP2022_mobpro.parquet')
    print(data.collect_schema())
    print("commune de résidence: COMMUNE")
    print("commune frontalière du lieu de travail: DCLT")
    print("commune frontalière du lieu de travil: DCFLT")
    print("poids statistique: IPONDI")
    ## concernant la variable DCLT cela correspond aux individu travaillant à
    ## l'étranger
