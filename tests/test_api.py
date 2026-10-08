from pathlib import Path
from fastapi.testclient import TestClient

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def test_health_check(client: TestClient):
    response = client.get("/api/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_dashboard_endpoint(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "Geospatial File Measurement API" in response.text


def test_sample_file_download(client: TestClient):
    response = client.get("/api/sample/sample_drone_survey.kml")
    assert response.status_code == 200
    assert "xml" in response.headers.get("content-type", "") or len(response.content) > 0


def test_upload_kml_file(client: TestClient):
    kml_path = SAMPLE_DIR / "sample_drone_survey.kml"
    assert kml_path.exists()

    with open(kml_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("sample_drone_survey.kml", f, "application/vnd.google-earth.kml+xml")},
        )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "sample_drone_survey.kml"
    assert data["feature_count"] == 6
    assert data["crs"] == "EPSG:4326"
    assert data["status"] == "COMPLETED"
    assert data["projected_crs"] == "EPSG:32643"

    file_id = data["id"]

    # Test file info endpoint
    info_resp = client.get(f"/api/files/{file_id}/")
    assert info_resp.status_code == 200
    info_data = info_resp.json()
    assert info_data["id"] == file_id
    assert info_data["feature_count"] == 6
    assert info_data["status"] == "COMPLETED"

    # Test measurements endpoint
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["id"] == file_id
    assert meas_data["feature_count"] == 6
    assert len(meas_data["features"]) == 6

    # Verify summary
    summary = meas_data["summary"]
    assert summary["polygon_count"] == 2
    assert summary["linestring_count"] == 2
    assert summary["point_count"] == 2
    assert summary["total_area_sq_meters"] > 0
    assert summary["total_length_meters"] > 0

    # Verify features and measurements
    polygon_feats = [f for f in meas_data["features"] if f["geometry_type"] == "Polygon"]
    assert len(polygon_feats) == 2
    for p in polygon_feats:
        assert p["measurement"]["type"] == "area"
        assert p["measurement"]["value"] > 0
        assert p["measurement"]["unit"] == "sq_meters"
        assert "details" in p["measurement"]
        assert "area_hectares" in p["measurement"]["details"]

    line_feats = [f for f in meas_data["features"] if f["geometry_type"] == "LineString"]
    assert len(line_feats) == 2
    for l in line_feats:
        assert l["measurement"]["type"] == "length"
        assert l["measurement"]["value"] > 0
        assert l["measurement"]["unit"] == "meters"

    point_feats = [f for f in meas_data["features"] if f["geometry_type"] == "Point"]
    assert len(point_feats) == 2
    for pt in point_feats:
        # Per specification: Point has no measurement
        assert pt["measurement"]["value"] is None
        assert pt["measurement"]["type"] == "none"


def test_upload_shapefile_zip(client: TestClient):
    shp_zip = SAMPLE_DIR / "sample_parcels_shapefile.zip"
    assert shp_zip.exists()

    with open(shp_zip, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("sample_parcels_shapefile.zip", f, "application/zip")},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 2

    # Fetch measurements
    meas_resp = client.get(f"/api/files/{data['id']}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["summary"]["polygon_count"] == 2
    assert meas_data["summary"]["total_area_sq_meters"] > 0


def test_invalid_extension(client: TestClient):
    response = client.post(
        "/api/files/",
        files={"file": ("test.pdf", b"fake pdf data", "application/pdf")},
    )
    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


def test_corrupted_zip(client: TestClient):
    response = client.post(
        "/api/files/",
        files={"file": ("corrupted.zip", b"not a zip file", "application/zip")},
    )
    assert response.status_code == 400
    assert "not a valid ZIP" in response.json()["detail"]


def test_file_not_found(client: TestClient):
    response = client.get("/api/files/nonexistent_id/")
    assert response.status_code == 404

    meas_resp = client.get("/api/files/nonexistent_id/measurements/")
    assert meas_resp.status_code == 404


def test_list_and_delete_file(client: TestClient):
    kml_path = SAMPLE_DIR / "sample_drone_survey.kml"
    with open(kml_path, "rb") as f:
        upload_resp = client.post(
            "/api/files/",
            files={"file": ("to_delete.kml", f, "application/vnd.google-earth.kml+xml")},
        )
    file_id = upload_resp.json()["id"]

    # Check listing
    list_resp = client.get("/api/files/")
    assert list_resp.status_code == 200
    file_ids = [item["id"] for item in list_resp.json()]
    assert file_id in file_ids

    # Delete
    del_resp = client.delete(f"/api/files/{file_id}/")
    assert del_resp.status_code == 200

    # Ensure deleted
    get_resp = client.get(f"/api/files/{file_id}/")
    assert get_resp.status_code == 404
