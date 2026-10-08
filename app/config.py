import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "measurements.db"

# Create required directories
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Application Settings
APP_NAME = "Geospatial File Measurement API"
APP_VERSION = "1.0.0"
DESCRIPTION = (
    "Production-grade FastAPI service that accepts Shapefile (.zip) and KML geospatial files, "
    "processes spatial features, dynamically transforms geographic coordinates to optimal projected CRS (UTM), "
    "and returns precise geometric measurements (Polygon Area, LineString Length)."
)

# Supported extensions
ALLOWED_EXTENSIONS = {".zip", ".kml"}
DEFAULT_GEOGRAPHIC_CRS = "EPSG:4326"
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
