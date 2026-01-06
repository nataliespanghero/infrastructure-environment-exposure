from __future__ import annotations

from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon
import h3

PROJECT_CRS = "EPSG:4326"


def _geom_to_h3_cells(geom, resolution: int) -> list[str]:
    """
    Converts a shapely geometry to a list of H3 cell IDs (polyfill).
    """
    if geom.is_empty:
        return []

    # h3 expects GeoJSON-like mapping in (lon, lat)
    geojson = {
        "type": "Polygon",
        "coordinates": [list(geom.exterior.coords)],
    }

    return list(h3.polygon_to_cells(geojson, res=resolution))


def h3_cells_to_gdf(cells: list[str]) -> gpd.GeoDataFrame:
    """
    Converts H3 cell IDs to GeoDataFrame polygons in WGS84.
    """
    polys = []
    for cell in cells:
        boundary = h3.cell_to_boundary(cell)  # list of (lat, lon)
        coords = [(lon, lat) for lat, lon in boundary]
        polys.append(Polygon(coords))

    gdf = gpd.GeoDataFrame({"h3": cells, "geometry": polys}, crs=PROJECT_CRS)
    return gdf


def main():
    data_processed = Path("data/processed")
    sp_boundary_path = data_processed / "sp_boundary.geojson"
    out_path = data_processed / "h3_sp_res6.geojson"

    resolution = 6  # fixed for MVP (good balance for a state case study)

    boundary = gpd.read_file(sp_boundary_path).to_crs(PROJECT_CRS)
    geom = boundary.geometry.iloc[0]

    print(f"Generating H3 grid for São Paulo at resolution {resolution}...")
    cells = _geom_to_h3_cells(geom, resolution=resolution)
    print(f"Generated {len(cells):,} hexagons.")

    h3_gdf = h3_cells_to_gdf(cells)
    h3_gdf.to_file(out_path, driver="GeoJSON")

    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
