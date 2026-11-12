## https://colab.research.google.com/github/linogaliana/python-datascientist-notebooks-colab/blob/main/notebooks/manipulation/03_geopandas_intro.ipynb#scrollTo=d98dfb71
##https://sempervent.github.io/deep-dives/polars-vs-pandas-geospatial/#polars-spatial-extensions


import polars as pl
import geopandas as gpd
import numpy as np


class GeometryError(Exception):
    pass


if __name__ == "__main__":
    try:
        gdf = gpd.read_file(
            "bassin_mobilite_ge_transfrontalier_simulation_area.geojson")
        if gdf.crs.is_geographic:
            raise GeometryError("Consider to project in EPSG:2154 before")
        first_surf = np.sum(gdf.area)
        print(f"The area of the zone in {gdf.crs} is: {first_surf} UA")
        gdf = gdf.to_crs("EPSG:2154")
        second_surf = np.sum(gdf.area)
        print(f"The area of zone after reprojection in {gdf.crs}"
              f" is: {second_surf} UA")
        print(f"The ecart is {(second_surf - first_surf) / first_surf * 100}%")
    except GeometryError as e:
        print(f"GeometryError: {e}")
