import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import pyproj
from shapely.geometry import MultiPolygon, GeometryCollection

from app.models.schemas import FileUploadResponse, MeasurementSummary
from app.services.crs_service import CRSService
from app.services.measurement import MeasurementService
from app.services.parser import GeospatialParser, ParsedFeature
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


class FileProcessingService:
    """
    Coordinates file parsing, CRS reprojection, measurement calculation,
    and storage persistence.
    """

    @classmethod
    def process_file(cls, file_path: Path, filename: str) -> FileUploadResponse:
        file_id = uuid.uuid4().hex[:12]
        ext = Path(filename).suffix.lower()

        try:
            # 1. Parse features and detect source CRS
            parsed_features, source_crs_str = GeospatialParser.parse(file_path, filename)
            source_crs = CRSService.parse_crs(source_crs_str)

            # 2. Determine optimal dataset-level projected CRS from feature centroids
            dataset_projected_crs: Optional[pyproj.CRS] = None
            if parsed_features:
                centroids_x = [f.shapely_geometry.centroid.x for f in parsed_features if not f.shapely_geometry.is_empty]
                centroids_y = [f.shapely_geometry.centroid.y for f in parsed_features if not f.shapely_geometry.is_empty]

                if centroids_x and centroids_y:
                    avg_lon = sum(centroids_x) / len(centroids_x)
                    avg_lat = sum(centroids_y) / len(centroids_y)
                    dataset_projected_crs = CRSService.get_projected_crs(source_crs, avg_lon, avg_lat)

            proj_crs_str = None
            if dataset_projected_crs:
                proj_crs_str = (
                    f"EPSG:{dataset_projected_crs.to_epsg()}"
                    if dataset_projected_crs.to_epsg()
                    else dataset_projected_crs.to_string()
                )

            # 3. Compute measurements for each feature
            features_to_save: List[Dict[str, Any]] = []
            summary = MeasurementSummary(total_features=len(parsed_features))

            for feat in parsed_features:
                measurement_detail, feat_proj_crs = MeasurementService.calculate_measurement(
                    geom=feat.shapely_geometry,
                    source_crs=source_crs,
                    projected_crs=dataset_projected_crs,
                )

                # Aggregate summary metrics
                gtype = feat.geometry_type
                if gtype in ("Polygon", "MultiPolygon"):
                    summary.polygon_count += 1
                    if measurement_detail and measurement_detail.value is not None:
                        summary.total_area_sq_meters += measurement_detail.value
                elif gtype in ("LineString", "MultiLineString", "LinearRing"):
                    summary.linestring_count += 1
                    if measurement_detail and measurement_detail.value is not None:
                        summary.total_length_meters += measurement_detail.value
                elif gtype in ("Point", "MultiPoint"):
                    summary.point_count += 1
                else:
                    summary.unsupported_count += 1

                feature_dict = {
                    "feature_index": feat.feature_index,
                    "feature_id": feat.feature_id,
                    "geometry_type": feat.geometry_type,
                    "geometry": feat.geometry_geojson,
                    "crs": feat.crs,
                    "projected_crs": feat_proj_crs or proj_crs_str,
                    "properties": feat.properties,
                    "measurement": measurement_detail.model_dump() if measurement_detail else None,
                }
                features_to_save.append(feature_dict)

            summary.total_area_sq_meters = round(summary.total_area_sq_meters, 2)
            summary.total_area_hectares = round(summary.total_area_sq_meters / 10000.0, 4)
            summary.total_length_meters = round(summary.total_length_meters, 2)
            summary.total_length_km = round(summary.total_length_meters / 1000.0, 4)

            # 4. Save file metadata and features to SQLite
            StorageService.save_file_record(
                file_id=file_id,
                filename=filename,
                file_format=ext,
                feature_count=len(parsed_features),
                crs=source_crs_str,
                projected_crs=proj_crs_str,
                status="COMPLETED",
                summary=summary.model_dump(),
            )

            if features_to_save:
                StorageService.save_features(file_id, features_to_save)

            return FileUploadResponse(
                id=file_id,
                filename=filename,
                feature_count=len(parsed_features),
                crs=source_crs_str,
                status="COMPLETED",
                projected_crs=proj_crs_str,
            )

        except Exception as e:
            logger.error(f"Failed to process file {filename}: {e}", exc_info=True)
            StorageService.save_file_record(
                file_id=file_id,
                filename=filename,
                file_format=ext,
                feature_count=0,
                crs="UNKNOWN",
                projected_crs=None,
                status="FAILED",
                error_message=str(e),
                summary=None,
            )
            raise ValueError(f"File processing failed: {str(e)}")
