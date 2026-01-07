from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium


#DATA_PATH = Path("data/processed/hex_metrics_res6.geojson")
DATA_PATH = Path("data/processed/hex_metrics_res6_deploy.geojson")


st.set_page_config(
    page_title="Infrastructure–Environment Exposure Explorer (São Paulo)",
    layout="wide",
)

st.title("Infrastructure–Environment Exposure Explorer")
with st.expander("About this project"):
    st.markdown(
        """
        **What this app shows**

        This app explores where road infrastructure overlaps with natural environments
        in São Paulo State (Brazil), using open data and H3 hexagonal aggregation.

        **Exposure score**

        The exposure score is a simple, interpretable proxy defined as:

        `exposure_score = road_length_km × (biome_area_pct / 100)`

        It is **not a risk or impact model**, but an exploratory metric to highlight
        areas where infrastructure and natural landscapes spatially intersect.

        **Data sources**
        - São Paulo state boundary: IBGE
        - Biomes: IBGE
        - Roads: OpenStreetMap
        """
    )

st.caption("Case Study: São Paulo State, Brazil — Open data + H3 aggregation (resolution 6)")

# -------- Load data --------
@st.cache_data(show_spinner=False)
def load_hexes() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(DATA_PATH)
    expected = {"h3", "road_length_km", "dominant_biome", "biome_area_pct", "exposure_score"}
    missing = expected - set(gdf.columns)
    if missing:
        raise ValueError(f"Missing columns in hex metrics: {missing}")
    return gdf

hexes = load_hexes()

# -------- Sidebar filters --------
st.sidebar.header("Filters")

biomes = sorted(hexes["dominant_biome"].dropna().unique().tolist())
selected_biomes = st.sidebar.multiselect("Dominant biome", options=biomes, default=biomes)

min_road = st.sidebar.slider("Minimum road length (km)", 0.0, float(max(1.0, hexes["road_length_km"].max())), 0.0, 0.5)
min_exposure = st.sidebar.slider("Minimum exposure score", 0.0, float(max(1.0, hexes["exposure_score"].max())), 0.0, 0.5)

top_n = st.sidebar.slider("Show top N hexagons by exposure (0 = all)", 0, 2000, 600, 50)

filtered = hexes[
    (hexes["dominant_biome"].isin(selected_biomes))
    & (hexes["road_length_km"] >= min_road)
    & (hexes["exposure_score"] >= min_exposure)
].copy()

if top_n > 0 and len(filtered) > top_n:
    filtered = filtered.nlargest(top_n, "exposure_score").copy()

# -------- Metrics summary --------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Hexagons (filtered)", f"{len(filtered):,}")
col2.metric("Max road length (km)", f"{filtered['road_length_km'].max():.2f}" if len(filtered) else "—")
col3.metric("Max biome share (%)", f"{filtered['biome_area_pct'].max():.1f}" if len(filtered) else "—")
col4.metric("Max exposure score", f"{filtered['exposure_score'].max():.2f}" if len(filtered) else "—")

st.divider()

# -------- Map --------
# Center map using hex dataset bounds (no external boundary file required)
minx, miny, maxx, maxy = hexes.total_bounds
center_lat = (miny + maxy) / 2
center_lon = (minx + maxx) / 2

m = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles="CartoDB positron")

# Optional outline derived from hex geometries (lightweight)
outline = hexes.unary_union
outline_gdf = gpd.GeoDataFrame(geometry=[outline], crs="EPSG:4326")

folium.GeoJson(
    outline_gdf,
    name="São Paulo outline (derived)",
    style_function=lambda x: {"weight": 2, "fillOpacity": 0},
).add_to(m)

# Prepare styling by exposure_score (quantiles)
if len(filtered) > 0:
    # quantiles for a simple choropleth-like styling
    q = filtered["exposure_score"].quantile([0.2, 0.4, 0.6, 0.8]).tolist()

    def style_fn(feat):
        v = feat["properties"].get("exposure_score", 0.0) or 0.0
        # bucket -> opacity/weight; color comes from default folium, we use a single color but varying opacity
        # (keeps it simple and avoids hand-picking colors)
        if v <= q[0]:
            return {"weight": 0.3, "fillOpacity": 0.15}
        if v <= q[1]:
            return {"weight": 0.3, "fillOpacity": 0.30}
        if v <= q[2]:
            return {"weight": 0.4, "fillOpacity": 0.45}
        if v <= q[3]:
            return {"weight": 0.5, "fillOpacity": 0.60}
        return {"weight": 0.6, "fillOpacity": 0.75}

    tooltip = folium.GeoJsonTooltip(
        fields=["h3", "dominant_biome", "biome_area_pct", "road_length_km", "exposure_score"],
        aliases=["H3", "Dominant biome", "Biome share (%)", "Road length (km)", "Exposure score"],
        localize=True,
        sticky=False,
        labels=True,
    )

    folium.GeoJson(
        filtered,
        name="Exposure (H3)",
        tooltip=tooltip,
        style_function=style_fn,
    ).add_to(m)

folium.LayerControl(collapsed=True).add_to(m)

st.subheader("Map")
st.write("Hover a hexagon to see metrics. Use the sidebar to filter.")

st_folium(m, use_container_width=True, height=650)

st.divider()

st.subheader("Sample of filtered data")
st.dataframe(
    filtered[["h3", "dominant_biome", "biome_area_pct", "road_length_km", "exposure_score"]].head(50),
    use_container_width=True,
)

st.divider()
st.caption(
    "Developed by Natalie Spanghero — Geospatial Analyst & Python Developer · Open-data portfolio project"
)
