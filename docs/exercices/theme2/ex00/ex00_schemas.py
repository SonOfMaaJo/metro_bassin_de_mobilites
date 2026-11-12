import polars as pl
import geopandas as gpd

if __name__ == '__main__':
    persons = pl.scan_parquet('BASSIN_MOBILITE_GE_DE_persons.parquet')
    activities = pl.scan_parquet('BASSIN_MOBILITE_GE_DE_activities.parquet')
    households = pl.scan_parquet('BASSIN_MOBILITE_GE_DE_households.parquet')
    print(f'persons.parquet: {persons.collect_schema()}')
    print(f'activities.parquet: {activities.collect_schema()}')
    print(f'households.parquet: {households.collect_schema()}')

    homes = pl.scan_parquet('BASSIN_MOBILITE_GE_DE_homes.geoparquet')
    activities = pl.scan_parquet('BASSIN_MOBILITE_GE_DE_activities.geoparquet')
    print(f'homes.geoparquet: {homes.collect_schema()}')
    print(f'activities.geoparquet: {activities.collect_schema()}')

    print("colonne type d'acitivité -> purpose")
    print("colonne commune -> commune_id")


