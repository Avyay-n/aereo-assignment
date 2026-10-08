import pyproj
from shapely.geometry import Point, Polygon, LineString, MultiPoint, GeometryCollection

from app.services.measurement import MeasurementService


def test_polygon_area_calculation():
    source_crs = pyproj.CRS("EPSG:4326")
    poly = Polygon([(77.59, 12.97), (77.60, 12.97), (77.60, 12.98), (77.59, 12.98), (77.59, 12.97)])

    meas, proj_crs = MeasurementService.calculate_measurement(poly, source_crs)
    assert meas is not None
    assert meas.type == "area"
    assert meas.unit == "sq_meters"
    assert meas.value is not None and meas.value > 1_000_000
    assert "area_hectares" in meas.details
    assert "perimeter_meters" in meas.details
    assert "EPSG:32643" in proj_crs


def test_linestring_length_calculation():
    source_crs = pyproj.CRS("EPSG:4326")
    line = LineString([(77.5900, 12.9700), (77.5950, 12.9750), (77.6000, 12.9800)])

    meas, proj_crs = MeasurementService.calculate_measurement(line, source_crs)
    assert meas is not None
    assert meas.type == "length"
    assert meas.unit == "meters"
    assert meas.value is not None and meas.value > 1000
    assert "length_km" in meas.details
    assert "EPSG:32643" in proj_crs


def test_point_handling_no_measurement():
    source_crs = pyproj.CRS("EPSG:4326")
    pt = Point(77.5946, 12.9716)

    meas, proj_crs = MeasurementService.calculate_measurement(pt, source_crs)
    assert meas is not None
    assert meas.type == "none"
    assert meas.value is None
    assert meas.unit is None
    assert "No measurement required" in meas.formatted


def test_empty_geometry_graceful():
    source_crs = pyproj.CRS("EPSG:4326")
    empty_poly = Polygon()

    meas, proj_crs = MeasurementService.calculate_measurement(empty_poly, source_crs)
    assert meas is not None
    assert meas.type == "none"
    assert meas.value is None


def test_geometry_collection_graceful():
    source_crs = pyproj.CRS("EPSG:4326")
    gc = GeometryCollection([Point(0, 0), LineString([(0, 0), (1, 1)])])

    meas, proj_crs = MeasurementService.calculate_measurement(gc, source_crs)
    assert meas is not None
    assert meas.type == "none"
    assert meas.value is None
    assert "not supported" in meas.details.get("note", "")
