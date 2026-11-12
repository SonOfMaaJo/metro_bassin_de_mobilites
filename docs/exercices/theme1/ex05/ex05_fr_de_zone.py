import polars as pl
import geopandas as gpd

if __name__ == '__main__':
    data = gpd.read_file(
        'bassin_mobilite_ge_transfrontalier_simulation_area.geojson')
    data = pl.from_pandas(data.drop(columns="geometry"))
    long = (
        data
        .select(
            pl.col('insee').str.len_chars().alias('len')
        )
        .group_by('len')
        .agg(pl.len().alias('count'))
    )
    print(long)
    data = pl.read_csv('bassin_mobilite_insee_codes.txt', has_header=False)
    print(f'lignes dans bassin_mobilite_insee_codes.txt: {data.shape[0]}')
    ### str.len_chars() est suffisant car il donne la longueur des chaines de
    ### la colonne et les codes INSEE et AGS allemand sont différent.
