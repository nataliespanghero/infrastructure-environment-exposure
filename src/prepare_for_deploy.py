from pathlib import Path
import geopandas as gpd

DATA_IN = Path("data/processed/hex_metrics_res6.geojson")
DATA_OUT = Path("data/processed/hex_metrics_res6_deploy.geojson")

# Load
gdf = gpd.read_file(DATA_IN)

# Keep only essential columns
gdf = gdf[
    [
        "h3",
        "dominant_biome",
        "biome_area_pct",
        "road_length_km",
        "exposure_score",
        "geometry",
    ]
].copy()

# Simplify geometry for web (IMPORTANT)
gdf["geometry"] = gdf.geometry.simplify(
    tolerance=0.001, preserve_topology=True
)

# Save lightweight GeoJSON
DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
gdf.to_file(DATA_OUT, driver="GeoJSON")

print(f"Saved deploy-ready file: {DATA_OUT}")
print(f"Hexagons: {len(gdf)}")
