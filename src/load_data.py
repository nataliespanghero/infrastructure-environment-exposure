from __future__ import annotations

from pathlib import Path
import geopandas as gpd

# Optional: used only if you decide to read OSM PBF locally
try:
    from pyrosm import OSM
except Exception:
    OSM = None


PROJECT_CRS = "EPSG:4326"  # keep WGS84 for H3 + web maps


def read_boundary_sp(boundary_path: str | Path) -> gpd.GeoDataFrame:
    """
    Reads São Paulo state boundary (IBGE) and returns a single dissolved geometry in WGS84.
    """
    boundary_path = Path(boundary_path)
    gdf = gpd.read_file(boundary_path)

    # Common IBGE fields: "SIGLA_UF" may exist in some products.
    # But if you download a UF-only file, it's already SP.
    gdf = gdf.to_crs(PROJECT_CRS)
    gdf["__dissolve__"] = 1
    out = gdf.dissolve(by="__dissolve__").reset_index(drop=True)
    out = out[["geometry"]]
    out["name"] = "Sao Paulo"
    return out


def read_biomes(biomes_path: str | Path) -> gpd.GeoDataFrame:
    """
    Reads IBGE biomes vector and returns polygons in WGS84.
    """
    biomes_path = Path(biomes_path)
    gdf = gpd.read_file(biomes_path).to_crs(PROJECT_CRS)

    # IBGE biome field names vary by dataset version.
    # We'll keep only geometry + the most likely name columns if present.
    keep_cols = ["geometry"]
    for c in ["BIOMA", "Bioma", "NOME", "NOME_BIO", "BIO_NOME", "NM_BIOMA"]:
        if c in gdf.columns:
            keep_cols.append(c)
            break

    return gdf[keep_cols].copy()


def read_osm_roads_from_pbf(
    pbf_path: str | Path,
    boundary: gpd.GeoDataFrame,
    highway_types: tuple[str, ...] = ("motorway", "trunk", "primary"),
) -> gpd.GeoDataFrame:
    """
    Reads OSM roads from a local PBF file using pyrosm (custom criteria),
    filters major highways, clips to SP boundary, and returns a GeoDataFrame in WGS84.
    """
    if OSM is None:
        raise ImportError("pyrosm is not available. Install it with: pip install pyrosm")

    pbf_path = Path(pbf_path)
    osm = OSM(str(pbf_path))

    # Read OSM ways that match highway tag (more robust than get_network)
    roads = osm.get_data_by_custom_criteria(
        custom_filter={"highway": list(highway_types)},
        filter_type="keep",
        keep_nodes=False,
        keep_relations=False,
        extra_attributes=["name", "ref", "highway", "maxspeed", "oneway", "bridge", "tunnel", "layer"],
    )

    roads = roads.to_crs(PROJECT_CRS)

    # Clip to SP boundary
    sp_geom = boundary.geometry.iloc[0]
    roads = gpd.clip(roads, sp_geom)

    # Cleanup
    roads = roads[~roads.geometry.is_empty & roads.geometry.notna()].copy()
    roads.reset_index(drop=True, inplace=True)

    return roads


def main():
    # --- Update these paths to match your local folders ---
    data_raw = Path("data/raw")
    data_processed = Path("data/processed")
    data_processed.mkdir(parents=True, exist_ok=True)

    # Examples (adjust filenames after you download/unzip)
    sp_boundary_file = data_raw / "ibge_sp_boundary" / "SP.shp"
    biomes_file = data_raw / "ibge_biomes" / "Biomas_250mil.shp"
    sp_pbf_file = data_raw / "osm" / "sao-paulo-latest.osm.pbf"

    print("[1/3] Reading São Paulo boundary...")
    sp_boundary = read_boundary_sp(sp_boundary_file)
    sp_boundary.to_file(data_processed / "sp_boundary.geojson", driver="GeoJSON")

    print("[2/3] Reading biomes...")
    biomes = read_biomes(biomes_file)
    biomes.to_file(data_processed / "biomes.geojson", driver="GeoJSON")

    print("[3/3] Reading OSM roads (PBF) and clipping to SP...")
    roads = read_osm_roads_from_pbf(sp_pbf_file, sp_boundary)
    roads.to_file(data_processed / "roads_major.geojson", driver="GeoJSON")

    print("Done. Outputs saved in data/processed/.")


if __name__ == "__main__":
    main()
