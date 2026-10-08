import os
import zipfile
from pathlib import Path
import shapefile

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)


def generate_kml():
    kml_path = SAMPLE_DIR / "sample_drone_survey.kml"
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Aereo Drone Mission Survey</name>
    <description>Sample flight survey data with polygons, lines, and points</description>
    
    <!-- Survey Polygon 1: Agricultural Field Alpha (Bangalore area: UTM Zone 43N) -->
    <Placemark id="poly_01">
      <name>Survey Zone Alpha (Field)</name>
      <description>High-resolution multispectral mapping zone</description>
      <ExtendedData>
        <Data name="crop_type"><value>Wheat</value></Data>
        <Data name="target_gsd_cm"><value>2.5</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5900,12.9700,0
              77.6000,12.9700,0
              77.6000,12.9800,0
              77.5900,12.9800,0
              77.5900,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>

    <!-- Survey Polygon 2: Solar Farm Beta -->
    <Placemark id="poly_02">
      <name>Solar Farm Beta</name>
      <description>Thermal inspection solar array polygon</description>
      <ExtendedData>
        <Data name="capacity_mw"><value>15.0</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.6050,12.9720,0
              77.6120,12.9720,0
              77.6120,12.9780,0
              77.6050,12.9780,0
              77.6050,12.9720,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>

    <!-- LineString 1: Linear Infrastructure Transect -->
    <Placemark id="line_01">
      <name>Linear Pipeline Corridor</name>
      <description>Pipeline right-of-way inspection line</description>
      <ExtendedData>
        <Data name="voltage_kv"><value>66</value></Data>
      </ExtendedData>
      <LineString>
        <coordinates>
          77.5850,12.9650,0
          77.5920,12.9710,0
          77.5980,12.9790,0
          77.6050,12.9850,0
        </coordinates>
      </LineString>
    </Placemark>

    <!-- LineString 2: Perimeter Fence Line -->
    <Placemark id="line_02">
      <name>Perimeter Security Boundary Line</name>
      <description>Facility perimeter boundary line</description>
      <LineString>
        <coordinates>
          77.6150,12.9700,0
          77.6200,12.9700,0
          77.6200,12.9750,0
        </coordinates>
      </LineString>
    </Placemark>

    <!-- Point 1: Takeoff & Landing Pad (Should have no measurement) -->
    <Placemark id="pt_01">
      <name>Drone Takeoff Pad LZ-1</name>
      <description>Primary RTK Base Station and Launch Location</description>
      <Point>
        <coordinates>77.5946,12.9716,920</coordinates>
      </Point>
    </Placemark>

    <!-- Point 2: Ground Control Point GCP-01 (Should have no measurement) -->
    <Placemark id="pt_02">
      <name>Ground Control Point GCP-01</name>
      <description>Survey grade GNSS calibration target</description>
      <Point>
        <coordinates>77.5985,12.9755,918</coordinates>
      </Point>
    </Placemark>

  </Document>
</kml>
"""
    with open(kml_path, "w", encoding="utf-8") as f:
        f.write(kml_content)
    print(f"Generated sample KML at: {kml_path}")


def generate_polygon_shapefile_zip():
    base_name = "parcels"
    temp_dir = SAMPLE_DIR / "temp_shp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    shp_path = temp_dir / base_name

    # WKT for WGS84 EPSG:4326
    wgs84_prj = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'

    with shapefile.Writer(str(shp_path), shapeType=shapefile.POLYGON) as w:
        w.field("parcel_id", "C", size=50)
        w.field("owner", "C", size=50)
        w.field("land_use", "C", size=50)

        # Polygon 1: Parcel A
        # Note: Shapefile polygons exterior rings are clockwise
        poly1 = [
            [77.5900, 12.9700],
            [77.5900, 12.9800],
            [77.6000, 12.9800],
            [77.6000, 12.9700],
            [77.5900, 12.9700],
        ]
        w.poly([poly1])
        w.record("P-101", "Aereo Agricultural Trust", "Farmland")

        # Polygon 2: Parcel B
        poly2 = [
            [77.6050, 12.9720],
            [77.6050, 12.9780],
            [77.6120, 12.9780],
            [77.6120, 12.9720],
            [77.6050, 12.9720],
        ]
        w.poly([poly2])
        w.record("P-102", "Green Energy Corp", "Solar Infrastructure")

    # Write PRJ file
    prj_file = temp_dir / f"{base_name}.prj"
    with open(prj_file, "w", encoding="utf-8") as f:
        f.write(wgs84_prj)

    # Package into zip
    zip_path = SAMPLE_DIR / "sample_parcels_shapefile.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for ext in [".shp", ".shx", ".dbf", ".prj"]:
            file_to_add = temp_dir / f"{base_name}{ext}"
            if file_to_add.exists():
                z.write(file_to_add, arcname=f"{base_name}{ext}")
                file_to_add.unlink()

    # Cleanup temp dir
    try:
        temp_dir.rmdir()
    except Exception:
        pass

    print(f"Generated sample Shapefile ZIP at: {zip_path}")


def generate_lines_shapefile_zip():
    base_name = "flight_lines"
    temp_dir = SAMPLE_DIR / "temp_lines"
    temp_dir.mkdir(parents=True, exist_ok=True)

    shp_path = temp_dir / base_name
    wgs84_prj = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'

    with shapefile.Writer(str(shp_path), shapeType=shapefile.POLYLINE) as w:
        w.field("line_id", "C", size=50)
        w.field("corridor", "C", size=50)

        # Line 1
        line1 = [
            [77.5850, 12.9650],
            [77.5920, 12.9710],
            [77.5980, 12.9790],
            [77.6050, 12.9850],
        ]
        w.line([line1])
        w.record("FLIGHT-01", "North-South Transmission")

        # Line 2
        line2 = [
            [77.6150, 12.9700],
            [77.6200, 12.9700],
            [77.6200, 12.9750],
        ]
        w.line([line2])
        w.record("FLIGHT-02", "East Feeder")

    prj_file = temp_dir / f"{base_name}.prj"
    with open(prj_file, "w", encoding="utf-8") as f:
        f.write(wgs84_prj)

    zip_path = SAMPLE_DIR / "sample_flight_lines_shapefile.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for ext in [".shp", ".shx", ".dbf", ".prj"]:
            file_to_add = temp_dir / f"{base_name}{ext}"
            if file_to_add.exists():
                z.write(file_to_add, arcname=f"{base_name}{ext}")
                file_to_add.unlink()

    try:
        temp_dir.rmdir()
    except Exception:
        pass

    print(f"Generated sample LineString Shapefile ZIP at: {zip_path}")


if __name__ == "__main__":
    generate_kml()
    generate_polygon_shapefile_zip()
    generate_lines_shapefile_zip()
