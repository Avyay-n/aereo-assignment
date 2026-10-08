import io
import logging
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

import pyproj
import shapefile
from shapely.geometry import shape, mapping
from shapely.geometry.base import BaseGeometry

from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)


class ParsedFeature:
    """Internal representation of a parsed geospatial feature."""

    def __init__(
        self,
        feature_index: int,
        feature_id: Optional[str],
        geometry_type: str,
        geometry_geojson: Dict[str, Any],
        shapely_geometry: BaseGeometry,
        crs: str,
        properties: Dict[str, Any],
    ):
        self.feature_index = feature_index
        self.feature_id = feature_id
        self.geometry_type = geometry_type
        self.geometry_geojson = geometry_geojson
        self.shapely_geometry = shapely_geometry
        self.crs = crs
        self.properties = properties


class GeospatialParser:
    """
    Parser service for Shapefiles (.zip) and KML files (.kml).
    Extracts features, coordinates, geometry types, attributes, and CRS.
    """

    @classmethod
    def parse(cls, file_path: Path, filename: str) -> Tuple[List[ParsedFeature], str]:
        """
        Main entry point for parsing uploaded geospatial files.
        Returns:
            (List of ParsedFeature, detected_crs_string)
        """
        lower_name = filename.lower()
        if lower_name.endswith(".zip"):
            return cls.parse_shapefile_zip(file_path)
        elif lower_name.endswith(".kml"):
            return cls.parse_kml(file_path)
        else:
            raise ValueError(f"Unsupported file format '{filename}'. Expected .zip or .kml.")

    @classmethod
    def parse_shapefile_zip(cls, zip_path: Path) -> Tuple[List[ParsedFeature], str]:
        """
        Extracts and parses ESRI Shapefile(s) contained within a .zip archive.
        Supports single or multiple shapefiles inside the zip.
        """
        if not zipfile.is_zipfile(zip_path):
            raise ValueError("The uploaded file is not a valid ZIP archive.")

        features: List[ParsedFeature] = []
        detected_crs = "EPSG:4326"

        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            shp_files = [n for n in names if n.lower().endswith(".shp") and not n.startswith("__MACOSX")]

            if not shp_files:
                raise ValueError("No .shp file found inside the provided ZIP archive.")

            # Search for .prj file to detect CRS
            prj_files = [n for n in names if n.lower().endswith(".prj") and not n.startswith("__MACOSX")]
            if prj_files:
                try:
                    prj_bytes = z.read(prj_files[0])
                    prj_text = prj_bytes.decode("utf-8", errors="ignore").strip()
                    if prj_text:
                        parsed_crs = CRSService.parse_crs(prj_text)
                        detected_crs = (
                            f"EPSG:{parsed_crs.to_epsg()}"
                            if parsed_crs.to_epsg()
                            else parsed_crs.to_string()
                        )
                except Exception as e:
                    logger.warning(f"Could not parse .prj file in zip: {e}")

            # Read all shapefiles present in the zip
            global_index = 0
            for shp_name in shp_files:
                base_name = shp_name[:-4]

                # Check for corresponding required files (.shx and .dbf)
                has_shx = any(n.lower() == f"{base_name.lower()}.shx" for n in names)
                has_dbf = any(n.lower() == f"{base_name.lower()}.dbf" for n in names)

                if not (has_shx and has_dbf):
                    logger.warning(
                        f"Shapefile '{shp_name}' is missing accompanying .shx or .dbf file. Attempting partial read."
                    )

                shp_entry = next((n for n in names if n.lower() == f"{base_name.lower()}.shp"), None)
                shx_entry = next((n for n in names if n.lower() == f"{base_name.lower()}.shx"), None)
                dbf_entry = next((n for n in names if n.lower() == f"{base_name.lower()}.dbf"), None)

                shp_io = io.BytesIO(z.read(shp_entry)) if shp_entry else None
                shx_io = io.BytesIO(z.read(shx_entry)) if shx_entry else None
                dbf_io = io.BytesIO(z.read(dbf_entry)) if dbf_entry else None

                try:
                    reader = shapefile.Reader(shp=shp_io, shx=shx_io, dbf=dbf_io, encoding="utf-8", encodingErrors="replace")
                except Exception as e:
                    logger.error(f"Error opening shapefile '{shp_name}': {e}")
                    raise ValueError(f"Failed to read shapefile '{shp_name}': {e}")

                shape_records = reader.shapeRecords()
                for sr in shape_records:
                    shp = sr.shape
                    rec = sr.record

                    # Convert to GeoJSON geometry dictionary
                    try:
                        geojson_geom = shp.__geo_interface__
                        shapely_geom = shape(geojson_geom)
                    except Exception as e:
                        logger.warning(f"Failed to convert shape to geometry at index {global_index}: {e}")
                        continue

                    # Attributes
                    props = rec.as_dict() if hasattr(rec, "as_dict") else {}
                    # Clean binary or non-serializable property values
                    clean_props = {}
                    for k, v in props.items():
                        if isinstance(v, (str, int, float, bool)) or v is None:
                            clean_props[k] = v
                        else:
                            clean_props[k] = str(v)

                    feat_id = (
                        clean_props.get("id")
                        or clean_props.get("ID")
                        or clean_props.get("name")
                        or clean_props.get("FID")
                        or f"shp_feature_{global_index + 1}"
                    )

                    features.append(
                        ParsedFeature(
                            feature_index=global_index,
                            feature_id=str(feat_id),
                            geometry_type=shapely_geom.geom_type,
                            geometry_geojson=geojson_geom,
                            shapely_geometry=shapely_geom,
                            crs=detected_crs,
                            properties=clean_props,
                        )
                    )
                    global_index += 1

        return features, detected_crs

    @classmethod
    def parse_kml(cls, kml_path: Path) -> Tuple[List[ParsedFeature], str]:
        """
        Parses a KML file into features, geometries, and properties.
        Standard KML CRS is WGS84 (EPSG:4326).
        """
        detected_crs = "EPSG:4326"
        features: List[ParsedFeature] = []

        try:
            tree = ET.parse(kml_path)
            root = tree.getroot()
        except Exception as e:
            raise ValueError(f"Failed to parse KML file as valid XML: {e}")

        # Find all Placemark elements regardless of XML namespace
        placemarks = root.findall(".//{*}Placemark")
        if not placemarks:
            # Check if root itself is a placemark or if elements without Placemark tag exist
            placemarks = root.findall(".//Placemark")

        global_index = 0
        for pm in placemarks:
            # Extract name and description
            name_el = pm.find("{*}name")
            desc_el = pm.find("{*}description")
            feature_name = name_el.text.strip() if (name_el is not None and name_el.text) else None
            feature_desc = desc_el.text.strip() if (desc_el is not None and desc_el.text) else None

            # Extract ExtendedData properties
            properties: Dict[str, Any] = {}
            if feature_name:
                properties["name"] = feature_name
            if feature_desc:
                properties["description"] = feature_desc

            # Process SimpleData
            for sd in pm.findall(".//{*}SimpleData"):
                attr_name = sd.attrib.get("name")
                if attr_name and sd.text:
                    properties[attr_name] = sd.text.strip()

            # Process Data
            for d in pm.findall(".//{*}Data"):
                attr_name = d.attrib.get("name")
                val_el = d.find("{*}value")
                if attr_name and val_el is not None and val_el.text:
                    properties[attr_name] = val_el.text.strip()

            # Extract geometries from placemark
            parsed_geoms = cls._extract_kml_geometries(pm)

            for geom_dict in parsed_geoms:
                try:
                    shapely_geom = shape(geom_dict)
                except Exception as e:
                    logger.warning(f"Invalid geometry in placemark: {e}")
                    continue

                feat_id = (
                    feature_name
                    or pm.attrib.get("id")
                    or f"kml_feature_{global_index + 1}"
                )

                features.append(
                    ParsedFeature(
                        feature_index=global_index,
                        feature_id=str(feat_id),
                        geometry_type=shapely_geom.geom_type,
                        geometry_geojson=geom_dict,
                        shapely_geometry=shapely_geom,
                        crs=detected_crs,
                        properties=properties,
                    )
                )
                global_index += 1

        return features, detected_crs

    @classmethod
    def _parse_coordinates(cls, coord_str: str) -> List[Tuple[float, float]]:
        """
        Parses a KML coordinates string:
        'lon,lat,alt lon,lat,alt ...' into a list of (lon, lat) tuples.
        """
        coords: List[Tuple[float, float]] = []
        if not coord_str:
            return coords

        tokens = re.split(r"[\s\n\r\t]+", coord_str.strip())
        for token in tokens:
            if not token:
                continue
            parts = token.split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    coords.append((lon, lat))
                except ValueError:
                    continue
        return coords

    @classmethod
    def _extract_kml_geometries(cls, element: ET.Element) -> List[Dict[str, Any]]:
        """
        Extracts GeoJSON geometry representations from a KML element (Placemark or MultiGeometry).
        Supports Polygon, LineString, Point, and MultiGeometry nesting.
        """
        geometries: List[Dict[str, Any]] = []

        # 1. Polygon
        for poly_el in element.findall(".//{*}Polygon"):
            outer_ring_coords: List[Tuple[float, float]] = []
            inner_rings: List[List[Tuple[float, float]]] = []

            outer_el = poly_el.find(".//{*}outerBoundaryIs//{*}coordinates")
            if outer_el is not None and outer_el.text:
                outer_ring_coords = cls._parse_coordinates(outer_el.text)

            if not outer_ring_coords:
                continue

            # Ensure polygon ring is closed
            if outer_ring_coords[0] != outer_ring_coords[-1]:
                outer_ring_coords.append(outer_ring_coords[0])

            # Inner rings (holes)
            for inner_el in poly_el.findall(".//{*}innerBoundaryIs//{*}coordinates"):
                if inner_el.text:
                    ring = cls._parse_coordinates(inner_el.text)
                    if ring:
                        if ring[0] != ring[-1]:
                            ring.append(ring[0])
                        inner_rings.append(ring)

            poly_geojson = {
                "type": "Polygon",
                "coordinates": [outer_ring_coords, *inner_rings],
            }
            geometries.append(poly_geojson)

        # 2. LineString (exclude if inside Polygon)
        for line_el in element.findall(".//{*}LineString"):
            coord_el = line_el.find("{*}coordinates")
            if coord_el is not None and coord_el.text:
                coords = cls._parse_coordinates(coord_el.text)
                if len(coords) >= 2:
                    geometries.append({
                        "type": "LineString",
                        "coordinates": coords,
                    })

        # 3. Point (exclude if part of other element)
        for pt_el in element.findall(".//{*}Point"):
            coord_el = pt_el.find("{*}coordinates")
            if coord_el is not None and coord_el.text:
                coords = cls._parse_coordinates(coord_el.text)
                if coords:
                    geometries.append({
                        "type": "Point",
                        "coordinates": list(coords[0]),
                    })

        return geometries
