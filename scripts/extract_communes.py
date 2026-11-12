import sys

import geopandas as gpd
import osmium
from osmium.filter import TagFilter
from osmium.geom import WKBFactory

OSM_FILE = "/root/stage_simulation/bassin/data/bassin_mobilites_grand_est.osm.pbf"
OUT_FILE = "/root/stage_simulation/bassin/data/simulation_area_communes.geojson"
CODES_FILE = "/root/stage_simulation/bassin/data/bassin_mobilite_insee_codes.txt"

with open(CODES_FILE) as f:
    target_codes = set(line.strip() for line in f if line.strip())

print(f"Target commune codes: {len(target_codes)}")

fab = WKBFactory()
found = {}
for area in (
    osmium.FileProcessor(OSM_FILE)
    .with_filter(TagFilter(("admin_level", "8")))
    .with_areas()
):
    if not area.is_area():
        continue
    insee = area.tags.get("ref:INSEE")
    if insee in target_codes:
        found[insee] = (area.tags.get("name"), fab.create_multipolygon(area))

missing = target_codes - set(found.keys())
print(f"Found: {len(found)} / {len(target_codes)}")
if missing:
    print(f"Missing ({len(missing)}): {sorted(missing)}")

names = [v[0] for v in found.values()]
polys = [v[1] for v in found.values()]
codes = list(found.keys())
gdf = gpd.GeoDataFrame(
    {"insee": codes, "name": names},
    geometry=gpd.GeoSeries.from_wkb(polys, crs="EPSG:4326"),
)
gdf.to_crs("EPSG:2154", inplace=True)
gdf.to_file(OUT_FILE, driver="GeoJSON")
print(f"Written: {OUT_FILE}")
print(f"Total area (km2): {gdf.area.sum() / 1e6:.1f}")
