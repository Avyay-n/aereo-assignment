import logging
from typing import Any, Dict, Optional, Tuple
from shapely.geometry.base import BaseGeometry
import pyproj

from app.models.schemas import MeasurementDetail
from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)


class MeasurementService:
    """
    Computes metric measurements for geospatial geometries
    (Polygon Area, LineString Length, Point skipped, unhandled gracefully).
    """

    @classmethod
    def calculate_measurement(
        cls,
        geom: BaseGeometry,
        source_crs: pyproj.CRS,
        projected_crs: Optional[pyproj.CRS] = None,
    ) -> Tuple[Optional[MeasurementDetail], Optional[str]]:
        """
        Calculates measurement for a given Shapely geometry.
        Returns:
            (MeasurementDetail or None, projected_crs_string)
        """
        if geom is None or geom.is_empty:
            return (
                MeasurementDetail(
                    type="none",
                    value=None,
                    unit=None,
                    formatted="Empty geometry",
                    details={"note": "Geometry is empty"},
                ),
                None,
            )

        geom_type = geom.geom_type

        # Point: No measurement required per specification
        if geom_type in ("Point", "MultiPoint"):
            return (
                MeasurementDetail(
                    type="none",
                    value=None,
                    unit=None,
                    formatted="No measurement required for Point",
                    details={"note": "Points represent dimensionless zero-area coordinates; no measurement required."},
                ),
                None,
            )

        # Unsupported / Collection types handled gracefully
        if geom_type not in ("Polygon", "MultiPolygon", "LineString", "MultiLineString", "LinearRing"):
            return (
                MeasurementDetail(
                    type="none",
                    value=None,
                    unit=None,
                    formatted=f"Measurement not supported for {geom_type}",
                    details={"note": f"Geometry type '{geom_type}' is not supported for measurement calculation."},
                ),
                None,
            )

        # Reproject geometry to projected CRS (UTM / linear meters)
        if projected_crs is None:
            # Determine optimal projected CRS from centroid
            centroid = geom.centroid
            projected_crs = CRSService.get_projected_crs(source_crs, centroid.x, centroid.y)

        try:
            proj_geom = CRSService.transform_geometry(geom, source_crs, projected_crs)
        except Exception as e:
            logger.error(f"Failed to transform geometry for measurement: {e}")
            return (
                MeasurementDetail(
                    type="error",
                    value=None,
                    unit=None,
                    formatted="Reprojection error",
                    details={"error": str(e)},
                ),
                str(projected_crs),
            )

        proj_crs_str = f"EPSG:{projected_crs.to_epsg()}" if projected_crs.to_epsg() else projected_crs.to_string()

        # Polygon / MultiPolygon -> Area
        if geom_type in ("Polygon", "MultiPolygon"):
            area_sq_m = round(proj_geom.area, 2)
            perimeter_m = round(proj_geom.length, 2)
            area_ha = round(area_sq_m / 10000.0, 4)
            area_sq_km = round(area_sq_m / 1000000.0, 6)

            formatted_str = f"{area_sq_m:,.2f} m² ({area_ha:,.2f} ha)"

            return (
                MeasurementDetail(
                    type="area",
                    value=area_sq_m,
                    unit="sq_meters",
                    formatted=formatted_str,
                    details={
                        "area_sq_meters": area_sq_m,
                        "area_hectares": area_ha,
                        "area_sq_km": area_sq_km,
                        "perimeter_meters": perimeter_m,
                    },
                ),
                proj_crs_str,
            )

        # LineString / MultiLineString / LinearRing -> Length
        if geom_type in ("LineString", "MultiLineString", "LinearRing"):
            length_m = round(proj_geom.length, 2)
            length_km = round(length_m / 1000.0, 4)

            formatted_str = f"{length_m:,.2f} m ({length_km:,.3f} km)"

            return (
                MeasurementDetail(
                    type="length",
                    value=length_m,
                    unit="meters",
                    formatted=formatted_str,
                    details={
                        "length_meters": length_m,
                        "length_km": length_km,
                    },
                ),
                proj_crs_str,
            )

        return (None, proj_crs_str)
