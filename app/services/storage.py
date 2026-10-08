import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import DB_PATH

_lock = threading.Lock()


class StorageService:
    """
    Thread-safe SQLite storage for geospatial file metadata,
    extracted features, and computed measurements.
    """

    @classmethod
    def get_connection(cls) -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls):
        """Initializes tables if they do not exist."""
        with _lock:
            conn = cls.get_connection()
            cursor = conn.cursor()

            # Files table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_format TEXT NOT NULL,
                    feature_count INTEGER NOT NULL DEFAULT 0,
                    crs TEXT NOT NULL,
                    projected_crs TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    summary TEXT
                );
                """
            )

            # Features and measurements table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    feature_index INTEGER NOT NULL,
                    feature_id TEXT,
                    geometry_type TEXT NOT NULL,
                    geometry TEXT NOT NULL,
                    crs TEXT NOT NULL,
                    projected_crs TEXT,
                    properties TEXT NOT NULL,
                    measurement TEXT,
                    FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
                );
                """
            )

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_features_file_id ON features (file_id);")
            conn.commit()
            conn.close()

    @classmethod
    def save_file_record(
        cls,
        file_id: str,
        filename: str,
        file_format: str,
        feature_count: int,
        crs: str,
        projected_crs: Optional[str],
        status: str,
        created_at: Optional[str] = None,
        error_message: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
    ):
        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()

        summary_json = json.dumps(summary or {})

        with _lock:
            conn = cls.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO files (
                    id, filename, file_format, feature_count, crs, projected_crs, status, error_message, created_at, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    file_id,
                    filename,
                    file_format,
                    feature_count,
                    crs,
                    projected_crs,
                    status,
                    error_message,
                    created_at,
                    summary_json,
                ),
            )
            conn.commit()
            conn.close()

    @classmethod
    def save_features(cls, file_id: str, features_data: List[Dict[str, Any]]):
        """Batch saves features for a file."""
        with _lock:
            conn = cls.get_connection()
            cursor = conn.cursor()

            records = [
                (
                    file_id,
                    f["feature_index"],
                    f.get("feature_id"),
                    f["geometry_type"],
                    json.dumps(f["geometry"]),
                    f["crs"],
                    f.get("projected_crs"),
                    json.dumps(f.get("properties", {})),
                    json.dumps(f.get("measurement")) if f.get("measurement") else None,
                )
                for f in features_data
            ]

            cursor.executemany(
                """
                INSERT INTO features (
                    file_id, feature_index, feature_id, geometry_type, geometry, crs, projected_crs, properties, measurement
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                records,
            )
            conn.commit()
            conn.close()

    @classmethod
    def get_file(cls, file_id: str) -> Optional[Dict[str, Any]]:
        with _lock:
            conn = cls.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files WHERE id = ?;", (file_id,))
            row = cursor.fetchone()
            conn.close()

        if not row:
            return None

        result = dict(row)
        if result.get("summary"):
            try:
                result["summary"] = json.loads(result["summary"])
            except Exception:
                pass
        return result

    @classmethod
    def list_files(cls) -> List[Dict[str, Any]]:
        with _lock:
            conn = cls.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files ORDER BY created_at DESC;")
            rows = cursor.fetchall()
            conn.close()

        results = []
        for row in rows:
            d = dict(row)
            if d.get("summary"):
                try:
                    d["summary"] = json.loads(d["summary"])
                except Exception:
                    pass
            results.append(d)
        return results

    @classmethod
    def get_file_measurements(cls, file_id: str) -> Optional[Dict[str, Any]]:
        file_record = cls.get_file(file_id)
        if not file_record:
            return None

        with _lock:
            conn = cls.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM features WHERE file_id = ? ORDER BY feature_index ASC;",
                (file_id,),
            )
            rows = cursor.fetchall()
            conn.close()

        features = []
        for r in rows:
            feat_dict = dict(r)
            feat_dict["geometry"] = json.loads(feat_dict["geometry"])
            feat_dict["properties"] = json.loads(feat_dict["properties"])
            feat_dict["measurement"] = (
                json.loads(feat_dict["measurement"]) if feat_dict.get("measurement") else None
            )
            features.append(feat_dict)

        summary = file_record.get("summary") or {}

        return {
            "id": file_record["id"],
            "filename": file_record["filename"],
            "crs": file_record["crs"],
            "projected_crs": file_record.get("projected_crs"),
            "status": file_record["status"],
            "feature_count": file_record["feature_count"],
            "features": features,
            "summary": summary,
        }

    @classmethod
    def delete_file(cls, file_id: str) -> bool:
        with _lock:
            conn = cls.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM features WHERE file_id = ?;", (file_id,))
            cursor.execute("DELETE FROM files WHERE id = ?;", (file_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
        return deleted
