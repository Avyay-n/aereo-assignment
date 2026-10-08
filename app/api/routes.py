import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.config import ALLOWED_EXTENSIONS, UPLOAD_DIR
from app.models.schemas import (
    ErrorResponse,
    FileMeasurementsResponse,
    FileUploadResponse,
)
from app.services.processor import FileProcessingService
from app.services.storage import StorageService

router = APIRouter(prefix="/api", tags=["Geospatial Files & Measurements"])


@router.post(
    "/files/",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a geospatial file",
    description="Upload a .zip containing an ESRI Shapefile or a .kml file. Extracts features and computes projected measurements.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file format or corrupted contents"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def upload_geospatial_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing.",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Only .zip (Shapefile) and .kml files are accepted.",
        )

    # Save to disk
    temp_target = UPLOAD_DIR / f"upload_{file.filename}"
    try:
        with open(temp_target, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(e)}",
        )
    finally:
        await file.close()

    try:
        result = FileProcessingService.process_file(temp_target, file.filename)
        return result
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing file: {str(e)}",
        )
    finally:
        # Clean up temporary upload if desired or keep
        pass


@router.get(
    "/files/{file_id}/",
    response_model=FileUploadResponse,
    summary="Get file information",
    description="Retrieve high-level metadata, feature count, CRS, and status for an uploaded file.",
    responses={404: {"model": ErrorResponse, "description": "File not found"}},
)
async def get_file_info(file_id: str):
    file_record = StorageService.get_file(file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Geospatial file with ID '{file_id}' not found.",
        )

    return FileUploadResponse(
        id=file_record["id"],
        filename=file_record["filename"],
        feature_count=file_record["feature_count"],
        crs=file_record["crs"],
        status=file_record["status"],
        projected_crs=file_record.get("projected_crs"),
        created_at=file_record.get("created_at"),
    )


@router.get(
    "/files/{file_id}/measurements/",
    response_model=FileMeasurementsResponse,
    summary="Get measurements for features in the file",
    description="Retrieve feature-by-feature geometric measurements (Polygon area, LineString length) and dataset summary.",
    responses={404: {"model": ErrorResponse, "description": "File not found"}},
)
async def get_file_measurements(file_id: str):
    measurements_data = StorageService.get_file_measurements(file_id)
    if not measurements_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Measurements for file ID '{file_id}' not found.",
        )

    return FileMeasurementsResponse(**measurements_data)


@router.get(
    "/files/",
    response_model=List[FileUploadResponse],
    summary="List all uploaded files",
    description="List all previously processed files with their status and metadata.",
)
async def list_files():
    records = StorageService.list_files()
    return [
        FileUploadResponse(
            id=r["id"],
            filename=r["filename"],
            feature_count=r["feature_count"],
            crs=r["crs"],
            status=r["status"],
            projected_crs=r.get("projected_crs"),
            created_at=r.get("created_at"),
        )
        for r in records
    ]


@router.delete(
    "/files/{file_id}/",
    summary="Delete a file",
    description="Deletes a file, its features, and associated measurement records.",
    responses={404: {"model": ErrorResponse, "description": "File not found"}},
)
async def delete_file(file_id: str):
    deleted = StorageService.delete_file(file_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found.",
        )
    return {"message": f"File '{file_id}' and all associated measurements successfully deleted."}


@router.get(
    "/sample/{filename}",
    summary="Download sample test file",
    description="Retrieve one of the pre-generated sample geospatial files for testing.",
)
async def get_sample_file(filename: str):
    from fastapi.responses import FileResponse
    sample_file = Path(__file__).resolve().parent.parent.parent / "sample_data" / filename
    if not sample_file.exists():
        raise HTTPException(status_code=404, detail="Sample file not found.")
    return FileResponse(
        path=sample_file,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get(
    "/health/",
    summary="Service health check",
    tags=["Health"],
)
async def health_check():
    return {
        "status": "healthy",
        "service": "Geospatial File Measurement API",
        "version": "1.0.0",
    }
