import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

import app.config as config
from app.main import app
from app.services.storage import StorageService
import scripts.generate_sample_data as sample_gen


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    # Use temporary directories for testing
    temp_dir = Path(tempfile.mkdtemp(prefix="aereo_test_"))
    test_db = temp_dir / "test_measurements.db"
    test_uploads = temp_dir / "uploads"
    test_uploads.mkdir(parents=True, exist_ok=True)

    orig_db = config.DB_PATH
    orig_uploads = config.UPLOAD_DIR

    config.DB_PATH = test_db
    config.UPLOAD_DIR = test_uploads

    # Generate sample files if not already present
    sample_gen.generate_kml()
    sample_gen.generate_polygon_shapefile_zip()
    sample_gen.generate_lines_shapefile_zip()

    StorageService.init_db()

    yield

    # Cleanup
    config.DB_PATH = orig_db
    config.UPLOAD_DIR = orig_uploads
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
