import os
import shutil
import time
import json
import subprocess

import polars as pl
import geopandas as gpd
from shapely.geometry import Point
from scipy.spatial import distance_matrix

# Path to input Geoparquet file with the geometries of the INSEE municipalities.
# NOTE: You can use the file that I provided or your own Geoparquet file with different zone
# definitions (e.g., to use INSSE communes for a different year or to use IRIS zones).
ZONES_FILENAME = "./data/communes/communes.parquet"

# Path to the output Geoparquet file where the zone-level medoids are stored.
# This is only useful if you want to visualize the medoids.
MEDOID_FILENAME = "./data/communes/communes_medoids.parquet"

# CRS to use for geometric operations.
CRS = "EPSG:2154"

# Path to the input Geoparquet file with the edges characteristics and geometries.
EDGES_FILENAME = "./output/road_network/edges_clean.parquet"

# Road types that cannot be used as origin / destination.
FORBIDDEN_ROAD_TYPES = ["motorway", "motorway_link", "trunk", "trunk_link"]

# Path to the input Parquet file with the additive and constant free-flow penalties of the edges.
EDGE_PENALTIES_FILENAME = "./output/road_network/edges_penalties.parquet"

# Path to the input edge-level travel-time functions representing the congestion to be considered.
# Set this to None if you want to compute free-flow travel times only.
# Otherwise, this needs to be set to the path to a Parquet file with the same format as the
# "edge_ttfs" output files of METROPOLIS (see the documentation).
EDGE_TTFS = "./run/main_100iter/output/net_cond_next_exp_edge_ttfs.parquet"

# Path to the routing executable.
# NOTE: The routing executable is provided along side the METROPOLIS executable (download it from
# the website).
# NOTE: On Windows, you need to add ".exe" to the executable path.
ROUTING_EXEC = "./execs/routing_cli"

# Path to the temporary directory where the input / output files for the routing executable are
# stored.
TMP_DIRECTORY = "./tmp/"

# Departure time for the routing queries, in seconds after midnight.
# NOTE: When running without congestion, you can leave it to an arbitrary value (e.g., 0).
# NOTE: Set this to None if you want to retrieve the travel time for *any* departure time.
DEPARTURE_TIME = None

# Path to the output Parquet file of the script, where the computed travel times are stored.
OUTPUT_FILENAME = "./data/communes/communes_travel_times.parquet"


def read_trips():
    print("Reading zones...")
    columns = ["insee_id", "geometry"]
    zones = gpd.read_parquet(ZONES_FILENAME, columns=columns)
    zones.to_crs(CRS, inplace=True)
    zones_df = pl.DataFrame(pl.from_pandas(zones["insee_id"]))
    # Cross product of all zone ids.
    df = zones_df.select(origin="insee_id").join(
        zones_df.select(destination="insee_id"), how="cross"
    )
    print(f"Number of unique origin / destination points: {len(zones):,}")
    print(f"Number of origin / destination pairs: {len(df):,}")
    return df, zones


def read_edges():
    print("Reading edges...")
    gdf = gpd.read_parquet(
        EDGES_FILENAME,
        columns=["edge_id", "source", "target", "length", "speed_limit", "road_type", "geometry"],
    )
    gdf.to_crs(CRS, inplace=True)
    if FORBIDDEN_ROAD_TYPES:
        gdf["allow_od"] = ~gdf["road_type"].isin(FORBIDDEN_ROAD_TYPES)
    else:
        gdf["allow_od"] = True
    if EDGE_PENALTIES_FILENAME is not None:
        penalties = pl.read_parquet(EDGE_PENALTIES_FILENAME)
        if "speed" in penalties.columns:
            print("Using multiplicative penalties")
            gdf = gpd.GeoDataFrame(
                gdf.merge(
                    penalties.select("edge_id", "speed").to_pandas(),
                    on="edge_id",
                    how="left",
                )
            )
            gdf["travel_time"] = gdf["length"] / (gdf["speed"] / 3.6)
        else:
            gdf["travel_time"] = gdf["length"] / (gdf["speed_limit"] / 3.6)
        if "additive_penalty" in penalties.columns:
            print("Using additive penalties")
            gdf = gpd.GeoDataFrame(
                gdf.merge(
                    penalties.select("edge_id", "additive_penalty").to_pandas(),
                    on="edge_id",
                    how="left",
                )
            )
            gdf["travel_time"] += gdf["additive_penalty"].fillna(0.0)
    else:
        gdf["travel_time"] = gdf["length"] / (gdf["speed_limit"] / 3.6)
    return gdf


def find_origin_destination_node(zones: gpd.GeoDataFrame, edges: gpd.GeoDataFrame):
    print("Finding zone of each road-network node...")
    rn_nodes = (
        edges.loc[edges["allow_od"], ["source", "geometry"]]
        .drop_duplicates(subset="source")
        .rename(columns={"source": "node"})
    )
    rn_nodes["geometry"] = rn_nodes["geometry"].apply(lambda g: Point(g.coords[0]))
    rn_nodes = rn_nodes.sjoin(zones, how="inner", predicate="within").drop(columns=["index_right"])
    print("Finding medoid node in each zone...")
    rn_nodes["x"] = rn_nodes.geometry.x
    rn_nodes["y"] = rn_nodes.geometry.y
    df = pl.from_pandas(rn_nodes.loc[:, ["node", "insee_id", "x", "y"]])
    medoids = dict()
    for (insee_id,), insee_df in df.partition_by(
        "insee_id", as_dict=True, include_key=False
    ).items():
        xy = insee_df.select("x", "y").to_numpy()
        dists = distance_matrix(xy, xy)
        medoid_idx = int(dists.sum(axis=1).argmin())
        medoids[insee_id] = insee_df["node"][medoid_idx]
    medoids_df = pl.DataFrame(pl.from_pandas(zones["insee_id"])).with_columns(
        node=pl.col("insee_id").replace_strict(medoids)
    )
    gdf = gpd.GeoDataFrame(
        medoids_df.to_pandas().merge(rn_nodes[["node", "geometry"]], on="node"), crs=rn_nodes.crs
    )
    gdf.to_parquet(MEDOID_FILENAME)
    return medoids_df


def add_od_to_trips(trips: pl.DataFrame, df: pl.DataFrame):
    print("Assigning origin / destination node to all trips...")
    n = len(trips)
    lztrips = (
        trips.lazy()
        .join(
            df.lazy(),
            left_on="origin",
            right_on="insee_id",
        )
        .rename({"node": "origin_node"})
    )
    trips = (
        lztrips.join(
            df.lazy(),
            left_on="destination",
            right_on="insee_id",
        )
        .rename({"node": "destination_node"})
        .select(
            "origin",
            "destination",
            "origin_node",
            "destination_node",
        )
        .collect()
    )
    assert len(trips) == n
    trips = (
        trips.unique(subset=["origin_node", "destination_node"])
        .filter(pl.col("origin_node") != pl.col("destination_node"))
        .with_columns(query_id=pl.int_range(0, pl.len(), dtype=pl.UInt64))
    )
    return trips


def run_routing(trips: pl.DataFrame, edges: gpd.GeoDataFrame):
    parameters_filename = prepare_routing(trips, edges)
    print("Running routing...")
    return subprocess.run(" ".join([ROUTING_EXEC, parameters_filename]), shell=True)


def prepare_routing(trips: pl.DataFrame, edges: gpd.GeoDataFrame):
    print("Saving queries...")
    queries = (
        trips.unique(subset=["origin_node", "destination_node"])
        .filter(pl.col("origin_node") != pl.col("destination_node"))
        .select(
            "query_id",
            origin=pl.col("origin_node"),
            destination=pl.col("destination_node"),
            departure_time=DEPARTURE_TIME,
        )
    )
    print(f"Number of unique origin-destination pairs: {len(queries):,}")
    queries.write_parquet(os.path.join(TMP_DIRECTORY, "queries.parquet"))
    print("Saving graph...")
    edges_df = pl.from_pandas(edges.loc[:, ["edge_id", "source", "target", "travel_time"]])
    # Parallel edges are removed, keeping in priority edges with smallest travel time.
    edges_df.sort("travel_time", descending=False).unique(
        subset=["source", "target"], keep="first"
    ).sort("edge_id").select("edge_id", "source", "target", "travel_time").write_parquet(
        os.path.join(TMP_DIRECTORY, f"edges.parquet")
    )
    if EDGE_TTFS is not None:
        print("Reading edge ttfs")
        edge_ttfs = (
            pl.scan_parquet(EDGE_TTFS)
            .filter(vehicle_id=1)
            .select("edge_id", "departure_time", "travel_time")
            .collect()
        )
        edge_ttfs.write_parquet(os.path.join(TMP_DIRECTORY, "edge_ttfs.parquet"))
    print("Saving parameters...")
    parameters = {
        # NOTE: You can change this to:
        # - Dijkstra: Faster when running only few queries.
        # - TCH: Faster when running many queries over different origins and destinations.
        # - Intersect: Faster when running many queries with few origins / destinations (uses more
        #   memory).
        "algorithm": "Intersect",
        # NOTE: You can change this to True if you want to retrieve the fastest path for the queries
        # (as a sequence of edge ids).
        "output_route": False,
        "input_files": {
            "queries": "queries.parquet",
            "edges": "edges.parquet",
        },
        "output_directory": "output",
        "saving_format": "Parquet",
    }
    if EDGE_TTFS is not None:
        parameters["input_files"]["edge_ttfs"] = "edge_ttfs.parquet"
    parameters_filename = os.path.join(TMP_DIRECTORY, "parameters.json")
    with open(parameters_filename, "w") as f:
        json.dump(parameters, f)
    return parameters_filename


def load_results():
    print("Reading routing results...")
    if DEPARTURE_TIME is None:
        filename = os.path.join(TMP_DIRECTORY, "output", "profile_results.parquet")
        results = pl.scan_parquet(filename).group_by("query_id").agg(pl.all()).collect()
    else:
        filename = os.path.join(TMP_DIRECTORY, "output", "ea_results.parquet")
        results = (
            pl.scan_parquet(filename)
            .with_columns(
                departure_time=pl.lit(DEPARTURE_TIME),
                travel_time=(pl.col("arrival_time") - DEPARTURE_TIME).fill_null(0.0),
            )
            .collect()
        )
    return results


def merge(trips: pl.DataFrame, results: pl.DataFrame):
    print("Merging trips data...")
    trips = trips.join(
        results,
        on="query_id",
        how="left",
        coalesce=False,
    ).select(
        "origin",
        "destination",
        "origin_node",
        "destination_node",
        "departure_time",
        "travel_time",
    )
    trips = trips.sort("origin", "destination")
    if DEPARTURE_TIME is not None:
        print("Travel time:\n{}".format(trips["travel_time"].describe()))
    return trips


if __name__ == "__main__":
    if not os.path.isdir(TMP_DIRECTORY):
        os.makedirs(TMP_DIRECTORY)

    t0 = time.time()

    trips, nodes = read_trips()

    edges = read_edges()

    df = find_origin_destination_node(nodes, edges)

    trips = add_od_to_trips(trips, df)

    res = run_routing(trips, edges)

    if res.returncode == 0:
        results = load_results()

        df = merge(trips, results)

        df.write_parquet(OUTPUT_FILENAME)

        # Clean the temporary directory.
        try:
            shutil.rmtree(TMP_DIRECTORY)
        except OSError as e:
            print(e)

    t = time.time() - t0
    print("Total running time: {:.2f} seconds".format(t))
