from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FileUploadResponse(BaseModel):
    id: str = Field(..., description="Unique identifier of the uploaded file")
    filename: str = Field(..., description="Original filename")
    feature_count: int = Field(..., description="Number of extracted geospatial features")
    crs: str = Field(..., description="Source Coordinate Reference System (e.g. EPSG:4326)")
    status: str = Field(..., description="Processing status: COMPLETED or FAILED")
    projected_crs: Optional[str] = Field(None, description="Target projected CRS used for measurements (e.g. EPSG:32643)")
    created_at: Optional[str] = Field(None, description="ISO timestamp of upload")


class MeasurementDetail(BaseModel):
    type: str = Field(..., description="Measurement type: 'area', 'length', or 'none'")
    value: Optional[float] = Field(None, description="Primary measurement value in standard SI units (m² or m)")
    unit: Optional[str] = Field(None, description="Unit of measurement ('sq_meters' or 'meters')")
    formatted: Optional[str] = Field(None, description="Human-readable formatted string")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional breakdown (hectares, km, perimeter)")


class FeatureMeasurementItem(BaseModel):
    feature_index: int = Field(..., description="0-indexed position within the file")
    feature_id: Optional[str] = Field(None, description="Identifier or name assigned to feature")
    geometry_type: str = Field(..., description="Geometry type: Polygon, LineString, Point, etc.")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON geometry dictionary")
    crs: str = Field(..., description="Source coordinate reference system")
    projected_crs: Optional[str] = Field(None, description="Projected coordinate reference system used for metric measurement")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Attributes and properties from file")
    measurement: Optional[MeasurementDetail] = Field(None, description="Calculated measurement or None for unmeasured types like Point")


class MeasurementSummary(BaseModel):
    total_features: int = 0
    polygon_count: int = 0
    linestring_count: int = 0
    point_count: int = 0
    unsupported_count: int = 0
    total_area_sq_meters: float = 0.0
    total_area_hectares: float = 0.0
    total_length_meters: float = 0.0
    total_length_km: float = 0.0


class FileMeasurementsResponse(BaseModel):
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    crs: str = Field(..., description="Source Coordinate Reference System")
    projected_crs: Optional[str] = Field(None, description="Default projected CRS used for dataset")
    status: str = Field(..., description="Processing status")
    feature_count: int = Field(..., description="Total feature count")
    features: List[FeatureMeasurementItem] = Field(..., description="List of feature measurement records")
    summary: MeasurementSummary = Field(..., description="Summary aggregation of measurements")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message explanation")
