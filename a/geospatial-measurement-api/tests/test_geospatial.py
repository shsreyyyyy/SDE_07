import geopandas as gpd
from shapely.geometry import LineString, Polygon

from app.services.geospatial import process_geodata


def test_polygon_area_uses_projected_units():
    gdf = gpd.GeoDataFrame({"name": ["square"]}, geometry=[Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])], crs="EPSG:4326")
    features, source_crs, measurement_crs = process_geodata(gdf)
    assert source_crs == "EPSG:4326"
    assert measurement_crs.startswith("EPSG:326")
    assert features[0]["measurement"]["type"] == "area"
    assert features[0]["measurement"]["value"] > 1e9


def test_linestring_length():
    gdf = gpd.GeoDataFrame({"name": ["line"]}, geometry=[LineString([(0, 0), (0, 1)])], crs="EPSG:4326")
    features, _, _ = process_geodata(gdf)
    assert features[0]["measurement"]["type"] == "length"
    assert 110_000 < features[0]["measurement"]["value"] < 112_000
