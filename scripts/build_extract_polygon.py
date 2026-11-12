import geopandas as gpd

IN_FILE = "/root/stage_simulation/bassin/data/simulation_area_communes.geojson"
OUT_FILE = "/root/stage_simulation/bassin/data/extract_polygon_buffered.geojson"
BUFFER_M = 10000

gdf = gpd.read_file(IN_FILE)
geom = gdf.union_all().buffer(BUFFER_M)
out = gpd.GeoDataFrame({"id": [1]}, geometry=[geom], crs=gdf.crs)
out.to_crs("EPSG:4326", inplace=True)
out.to_file(OUT_FILE, driver="GeoJSON")
print("area km2 (buffered):", gpd.GeoSeries([geom], crs=gdf.crs).area.sum() / 1e6)
print("written:", OUT_FILE)
