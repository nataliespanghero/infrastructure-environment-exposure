from __future__ import annotations

from pathlib import Path
import geopandas as gpd
import pandas as pd

PROJECT_CRS = "EPSG:4326"
METRIC_CRS = "EPSG:31983"  # SIRGAS 2000 / UTM zone 23S (works well for SP)


def _pick_biome_name_col(biomes: gpd.GeoDataFrame) -> str:
    for c in ["BIOMA", "Bioma", "NOME", "NOME_BIO", "BIO_NOME", "NM_BIOMA"]:
        if c in biomes.columns:
            return c
    raise ValueError("No biome name column found in biomes layer.")


def main():
    data_processed = Path("data/processed")

    hex_path = data_processed / "h3_sp_res6.geojson"
    roads_path = data_processed / "roads_major.geojson"
    biomes_path = data_processed / "biomes.geojson"
    out_path = data_processed / "hex_metrics_res6.geojson"

    print("[1/6] Loading layers...")
    hexes = gpd.read_file(hex_path).to_crs(PROJECT_CRS)
    roads = gpd.read_file(roads_path).to_crs(PROJECT_CRS)
    biomes = gpd.read_file(biomes_path).to_crs(PROJECT_CRS)

    biome_col = _pick_biome_name_col(biomes)

    print("[2/6] Reprojecting to metric CRS for accurate length/area...")
    hexes_m = hexes.to_crs(METRIC_CRS)
    roads_m = roads.to_crs(METRIC_CRS)
    biomes_m = biomes.to_crs(METRIC_CRS)

    print("[3/6] Road length per hex (km)...")
    roads_in_hex = gpd.overlay(
        roads_m[["geometry"]],
        hexes_m[["h3", "geometry"]],
        how="intersection",
        keep_geom_type=True,
    )
    roads_in_hex["seg_len_km"] = roads_in_hex.length / 1000.0
    road_len = (
        roads_in_hex.groupby("h3")["seg_len_km"]
        .sum()
        .reset_index()
        .rename(columns={"seg_len_km": "road_length_km"})
    )

    print("[4/6] Biome area share per hex (% by biome)...")
    # Intersect biomes with hexes
    bio_in_hex = gpd.overlay(
        biomes_m[[biome_col, "geometry"]],
        hexes_m[["h3", "geometry"]],
        how="intersection",
        keep_geom_type=True,
    )
    bio_in_hex["area_m2"] = bio_in_hex.area

    # Total hex area
    hex_area = hexes_m.copy()
    hex_area["hex_area_m2"] = hex_area.area
    hex_area = hex_area[["h3", "hex_area_m2"]]

    # Area by biome within each hex
    bio_area = (
        bio_in_hex.groupby(["h3", biome_col])["area_m2"]
        .sum()
        .reset_index()
        .merge(hex_area, on="h3", how="left")
    )
    bio_area["biome_area_pct"] = (bio_area["area_m2"] / bio_area["hex_area_m2"]) * 100.0

    # Keep only the dominant biome per hex (cleaner for MVP)
    dominant_biome = (
        bio_area.sort_values(["h3", "biome_area_pct"], ascending=[True, False])
        .groupby("h3")
        .head(1)
        .rename(columns={biome_col: "dominant_biome"})
    )[["h3", "dominant_biome", "biome_area_pct"]]

    print("[5/6] Merging metrics + exposure score...")
    out = hexes.merge(road_len, on="h3", how="left").merge(dominant_biome, on="h3", how="left")
    out["road_length_km"] = out["road_length_km"].fillna(0.0)
    out["biome_area_pct"] = out["biome_area_pct"].fillna(0.0)
    out["dominant_biome"] = out["dominant_biome"].fillna("Unknown")

    # Simple, interpretable proxy
    out["exposure_score"] = out["road_length_km"] * (out["biome_area_pct"] / 100.0)

    print("[6/6] Saving output GeoJSON...")
    out = out.to_crs(PROJECT_CRS)
    out.to_file(out_path, driver="GeoJSON")
    print(f"Saved: {out_path}")
    print(out[["h3", "road_length_km", "dominant_biome", "biome_area_pct", "exposure_score"]].head())


if __name__ == "__main__":
    main()
