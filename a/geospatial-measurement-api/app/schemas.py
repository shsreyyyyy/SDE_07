from typing import Any
from pydantic import BaseModel, Field

class FileInfo(BaseModel):
    id: str
    filename: str
    feature_count: int
    crs: str | None
    status: str
    created_at: str
    error: str | None = None

class MeasurementFeature(BaseModel):
    feature_id: int | str
    geometry_type: str
    geometry: dict[str, Any]
    crs: str | None
    properties: dict[str, Any] = Field(default_factory=dict)
    measurement: dict[str, Any] | None = None
    measurement_status: str
    message: str | None = None

class MeasurementsResponse(BaseModel):
    file_id: str
    filename: str
    source_crs: str | None
    measurement_crs: str | None
    features: list[MeasurementFeature]
