from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from ..config import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE, PROCESSED_DIR, UPLOAD_DIR
from ..models import FileRecord
from ..repository import repository
from ..schemas import FileInfo, MeasurementsResponse
from ..services.geospatial import process_file

router = APIRouter(tags=["files"])


def _get_record_or_404(file_id: str) -> dict:
    record = repository.get(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    return record


@router.post("/files/", response_model=FileInfo, status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...)) -> FileInfo:
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .kml or .zip (Shapefile) files are supported")

    file_id = uuid.uuid4().hex
    stored_path = UPLOAD_DIR / f"{file_id}{suffix}"
    total = 0
    try:
        with stored_path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_SIZE // (1024 * 1024)} MB limit")
                output.write(chunk)

        record = FileRecord(
            id=file_id,
            filename=filename,
            stored_path=str(stored_path.relative_to(UPLOAD_DIR.parent.parent)),
            feature_count=0,
            crs=None,
            status="PROCESSING",
            created_at=FileRecord.now_iso(),
        )
        repository.save(record.to_dict())

        features, source_crs, measurement_crs = process_file(
            stored_path,
            suffix,
            PROCESSED_DIR / file_id,
        )
        result = {
            "file_id": file_id,
            "filename": filename,
            "source_crs": source_crs,
            "measurement_crs": measurement_crs,
            "features": features,
        }
        result_path = PROCESSED_DIR / f"{file_id}.json"
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        record.update({
            "feature_count": len(features),
            "crs": source_crs,
            "status": "COMPLETED",
            "error": None,
        })
        repository.save(record)
        return FileInfo(**record)
    except HTTPException:
        if stored_path.exists():
            stored_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        record = FileRecord(
            id=file_id,
            filename=filename,
            stored_path=str(stored_path.relative_to(UPLOAD_DIR.parent.parent)) if stored_path.exists() else "",
            feature_count=0,
            crs=None,
            status="FAILED",
            created_at=FileRecord.now_iso(),
            error=str(exc),
        )
        repository.save(record.to_dict())
        raise HTTPException(status_code=422, detail=f"Unable to process geospatial file: {exc}") from exc
    finally:
        await file.close()


@router.get("/files/{file_id}/", response_model=FileInfo)
def get_file_info(file_id: str) -> FileInfo:
    return FileInfo(**_get_record_or_404(file_id))


@router.get("/files/{file_id}/measurements/", response_model=MeasurementsResponse)
def get_measurements(file_id: str) -> MeasurementsResponse:
    record = _get_record_or_404(file_id)
    if record["status"] != "COMPLETED":
        raise HTTPException(status_code=409, detail=f"File processing status is {record['status']}")
    result_path = PROCESSED_DIR / f"{file_id}.json"
    if not result_path.exists():
        raise HTTPException(status_code=500, detail="Processed measurement data is missing")
    return MeasurementsResponse(**json.loads(result_path.read_text(encoding="utf-8")))
