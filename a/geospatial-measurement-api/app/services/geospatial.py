from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

import geopandas as gpd
from pyproj import CRS
from shapely.geometry import mapping

SUPPORTED_GEOMETRIES = {"Point", "LineString", "Polygon"}


def _safe_zip_members(zf: zipfile.ZipFile) -> list[str]:
    names = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = Path(info.filename)
        if name.is_absolute() or ".." in name.parts:
            raise ValueError("Unsafe ZIP entry detected")
        names.append(info.filename)
    return names


def extract_shapefile(zip_path: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        if zf.testzip() is not None:
            raise ValueError("Corrupted ZIP archive")
        members = _safe_zip_members(zf)
        shp_members = [m for m in members if m.lower().endswith(".shp")]
        if len(shp_members) != 1:
            raise ValueError("ZIP must contain exactly one .shp file")
        for member in members:
            destination = target_dir / Path(member).name
            with zf.open(member) as source, destination.open("wb") as dest:
                shutil.copyfileobj(source, dest)
        shp_name = Path(shp_members[0]).name
        shp_path = target_dir / shp_name
        base = shp_path.with_suffix("")
        required = [base.with_suffix(".shp"), base.with_suffix(".shx"), base.with_suffix(".dbf")]
        missing = [p.suffix for p in required if not p.exists()]
        if missing:
            raise ValueError(f"Shapefile is missing required components: {', '.join(missing)}")
        return shp_path


def load_geodata(file_path: Path, original_suffix: str) -> gpd.GeoDataFrame:
    if original_suffix == ".kml":
        # Fiona/GDAL may need the KML driver explicitly selected.
        try:
            return gpd.read_file(file_path, driver="KML")
        except Exception:
            return gpd.read_file(file_path)
    return gpd.read_file(file_path)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return value
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def choose_measurement_crs(gdf: gpd.GeoDataFrame) -> CRS | None:
    """Choose a metric CRS.

    If the source CRS is projected in metres, keep it. Otherwise use a local
    UTM CRS based on the dataset centroid. For datasets spanning a very large
    area, Web Mercator is used as a stable fallback; this is not intended for
    high-precision surveying.
    """
    if gdf.empty:
        return None
    if gdf.crs is None:
        return None
    source = CRS.from_user_input(gdf.crs)
    if source.is_projected:
        unit_names = {str(a.name).lower() for a in source.axis_info if a.unit_name}
        if any("metre" in u or "meter" in u for u in unit_names):
            return source

    geographic = gdf.to_crs("EPSG:4326")
    centroid = geographic.geometry.union_all().centroid
    lon, lat = centroid.x, centroid.y
    if -80 <= lat <= 84 and -180 <= lon <= 180:
        zone = int((lon + 180) // 6) + 1
        epsg = (32600 if lat >= 0 else 32700) + zone
        return CRS.from_epsg(epsg)
    return CRS.from_epsg(3857)


def process_geodata(gdf: gpd.GeoDataFrame) -> tuple[list[dict[str, Any]], str | None, str | None]:
    source_crs = str(gdf.crs) if gdf.crs else None
    measurement_crs = choose_measurement_crs(gdf)
    metric_gdf = gdf.to_crs(measurement_crs) if measurement_crs else gdf

    features = []
    for idx, (_, row) in enumerate(gdf.iterrows()):
        geom = row.geometry
        geom_type = geom.geom_type if geom is not None else "Unknown"
        properties = {k: _json_safe(v) for k, v in row.drop(labels=["geometry"]).to_dict().items()}
        item: dict[str, Any] = {
            "feature_id": idx,
            "geometry_type": geom_type,
            "geometry": mapping(geom) if geom is not None and not geom.is_empty else {},
            "crs": source_crs,
            "properties": properties,
            "measurement": None,
            "measurement_status": "NOT_REQUIRED",
            "message": None,
        }
        if geom is None or geom.is_empty:
            item["measurement_status"] = "UNAVAILABLE"
            item["message"] = "Geometry is empty or missing."
        elif geom_type == "Polygon":
            item["measurement"] = {"type": "area", "value": float(metric_gdf.iloc[idx].geometry.area), "unit": "m²"}
            item["measurement_status"] = "COMPLETED"
        elif geom_type == "LineString":
            item["measurement"] = {"type": "length", "value": float(metric_gdf.iloc[idx].geometry.length), "unit": "m"}
            item["measurement_status"] = "COMPLETED"
        elif geom_type == "Point":
            item["measurement_status"] = "NOT_REQUIRED"
            item["message"] = "Point geometry does not require a measurement."
        else:
            item["measurement_status"] = "UNSUPPORTED"
            item["message"] = f"Measurement is not implemented for geometry type '{geom_type}'."
        item["geometry"] = _json_safe(item["geometry"])
        features.append(item)
    return features, source_crs, str(measurement_crs) if measurement_crs else None


def process_file(file_path: Path, suffix: str, work_dir: Path) -> tuple[list[dict[str, Any]], str | None, str | None]:
    source_path = file_path
    if suffix == ".zip":
        source_path = extract_shapefile(file_path, work_dir / "shapefile")
    gdf = load_geodata(source_path, suffix)
    return process_geodata(gdf)
