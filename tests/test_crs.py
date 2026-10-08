import pytest
import pyproj
from shapely.geometry import Point, Polygon, LineString

from app.services.crs_service import CRSService


def test_utm_zone_determination():
    # Bangalore, India (lon: 77.59, lat: 12.97) -> Zone 43 North -> EPSG:32643
    epsg = CRSService.get_utm_epsg(77.59, 12.97)
    assert epsg == 32643

    # London, UK (lon: -0.12, lat: 51.50) -> Zone 30 North -> EPSG:32630
    epsg_london = CRSService.get_utm_epsg(-0.12, 51.50)
    assert epsg_london == 32630

    # Sydney, Australia (lon: 151.20, lat: -33.86) -> Zone 56 South -> EPSG:32756
    epsg_sydney = CRSService.get_utm_epsg(151.20, -33.86)
    assert epsg_sydney == 32756

    # Rio de Janeiro, Brazil (lon: -43.17, lat: -22.90) -> Zone 23 South -> EPSG:32723
    epsg_rio = CRSService.get_utm_epsg(-43.17, -22.90)
    assert epsg_rio == 32723

    # Polar latitudes
    assert CRSService.get_utm_epsg(0.0, 85.0) == 32661
    assert CRSService.get_utm_epsg(0.0, -85.0) == 32761


def test_crs_parsing():
    crs_4326 = CRSService.parse_crs("EPSG:4326")
    assert crs_4326.to_epsg() == 4326

    # None defaults to 4326
    crs_none = CRSService.parse_crs(None)
    assert crs_none.to_epsg() == 4326

    # Invalid string defaults to 4326
    crs_invalid = CRSService.parse_crs("NOT_A_REAL_CRS")
    assert crs_invalid.to_epsg() == 4326


def test_geometry_reprojection():
    # Square polygon in degrees ~ 0.01 x 0.01 deg
    source_crs = pyproj.CRS("EPSG:4326")
    target_crs = pyproj.CRS("EPSG:32643")

    poly = Polygon([(77.59, 12.97), (77.60, 12.97), (77.60, 12.98), (77.59, 12.98), (77.59, 12.97)])
    
    # In geographic degrees, area is ~ 0.0001 deg^2
    deg_area = poly.area
    assert deg_area < 0.001

    # Reproject to UTM
    projected_poly = CRSService.transform_geometry(poly, source_crs, target_crs)

    # In UTM meters, area is roughly 1.2 million m^2 (~120 hectares)
    proj_area = projected_poly.area
    assert 1_000_000 < proj_area < 1_500_000
