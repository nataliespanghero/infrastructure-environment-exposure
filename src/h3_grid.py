from __future__ import annotations

from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
import h3
from h3.api.basic_str import LatLngPoly, LatLngMultiPoly


PROJECT_CRS = "EPSG:4326"


def _ring_lonlat_to_latlng(ring_coords):
    """
    Shapely rings come as (lon, lat). H3 expects (lat, lon).
    """
    return [(lat, lon) for lon, lat in ring_coords]


def _polygon_to_latlngpoly(poly: Polygon) -> LatLngPoly:
    exterior = _ring_lonlat_to_latlng(list(poly.exterior.coords))
    holes = []
    for interior in poly.interiors:
        holes.append(_ring_lonlat_to_latlng(list(interior.coords)))
    return LatLngPoly(exterior, holes)


def _geom_to_h3_cells(geom, resolution: int) -> list[str]:
    """
    Converts shapely Polygon/MultiPolygon to H3 cells using h3-py v4 shapes.
    """
    if geom is None or geom.is_empty:
        return []

    # Fix occasional invalid geometries
    try:
        if not geom.is_valid:
            geom = geom.buffer(0)
    except Exception:
        pass

    if geom.geom_type == "Polygon":
        h3shape = _polygon_to_latlngpoly(geom)
        return list(h3.polygon_to_cells(h3shape, res=resolution))

    if geom.geom_type == "MultiPolygon":
        polys = [_polygon_to_latlngpoly(p) for p in geom.geoms]
        h3shape = LatLngMultiPoly(*polys)
        return list(h3.polygon_to_cells(h3shape, res=resolution))

    raise TypeError(f"Unsupported geometry type: {geom.geom_type}")



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
