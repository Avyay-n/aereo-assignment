import logging
from typing import Optional, Tuple
import pyproj
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

logger = logging.getLogger(__name__)


class CRSService:
    """
    Handles Coordinate Reference System (CRS) identification,
    optimal projected CRS selection (e.g., UTM Zones), and geometry reprojection.
    """

    @staticmethod
    def parse_crs(crs_string_or_wkt: Optional[str]) -> pyproj.CRS:
        """
        Parses a CRS string, authority code (e.g. 'EPSG:4326'), or WKT string.
        Defaults to EPSG:4326 if None or invalid.
        """
        if not crs_string_or_wkt or not crs_string_or_wkt.strip():
            return pyproj.CRS.from_epsg(4326)

        try:
            return pyproj.CRS.from_user_input(crs_string_or_wkt.strip())
        except Exception as e:
            logger.warning(f"Could not parse CRS '{crs_string_or_wkt}', defaulting to EPSG:4326. Error: {e}")
            return pyproj.CRS.from_epsg(4326)

    @staticmethod
    def get_utm_epsg(longitude: float, latitude: float) -> int:
        """
        Determines the optimal UTM (Universal Transverse Mercator) EPSG code
        for a given longitude and latitude centroid.
        - Zone: 1 to 60 based on 6-degree longitudinal slices.
        - Northern Hemisphere: EPSG: 32601 to 32660
        - Southern Hemisphere: EPSG: 32701 to 32760
        - Polar fallbacks: EPSG:32661 (North) / EPSG:32761 (South)
        """
        # Clamp longitude to [-180, 180]
        lon = ((longitude + 180) % 360) - 180
        lat = latitude

        # Handle extreme polar latitudes where UTM is invalid
        if lat > 84.0:
            return 32661  # UPS North
        if lat < -80.0:
            return 32761  # UPS South

        zone = int((lon + 180) / 6.0) + 1
        if zone < 1:
            zone = 1
        elif zone > 60:
            zone = 60

        if lat >= 0:
            return 32600 + zone
        else:
            return 32700 + zone

    @classmethod
    def get_projected_crs(cls, source_crs: pyproj.CRS, centroid_lon: float, centroid_lat: float) -> pyproj.CRS:
        """
        Selects an appropriate projected coordinate reference system (in linear meters).
        If source_crs is already projected, returns source_crs.
        If source_crs is geographic (degrees), finds optimal UTM zone.
        """
        try:
            if source_crs.is_projected:
                return source_crs
        except Exception:
            pass

        # Source is geographic; compute optimal UTM zone
        utm_epsg = cls.get_utm_epsg(centroid_lon, centroid_lat)
        return pyproj.CRS.from_epsg(utm_epsg)

    @classmethod
    def transform_geometry(
        cls,
        geom: BaseGeometry,
        source_crs: pyproj.CRS,
        target_crs: pyproj.CRS,
    ) -> BaseGeometry:
        """
        Reprojects a Shapely geometry from source_crs to target_crs.
        Uses always_xy=True to ensure (x, y) / (lon, lat) tuple order consistency.
        """
        if source_crs == target_crs:
            return geom

        try:
            transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)
            projected_geom = transform(transformer.transform, geom)
            return projected_geom
        except Exception as e:
            logger.error(f"Error reprojecting geometry from {source_crs} to {target_crs}: {e}")
            raise RuntimeError(f"CRS transformation failed: {e}")
