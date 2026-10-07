# Geospatial File Measurement API

A production-oriented FastAPI service for uploading KML files or ZIP archives containing a Shapefile, extracting feature information, and calculating CRS-safe measurements.

## Features

- FastAPI REST API with automatic OpenAPI/Swagger documentation.
- Accepts `.kml` and `.zip` containing one Shapefile.
- Extracts feature ID/index, geometry type, geometry, CRS and properties.
- Polygon → area in square metres (`m²`).
- LineString → length in metres (`m`).
- Point → no measurement required.
- Unsupported geometry types are returned with `UNSUPPORTED` status instead of crashing the request.
- Geographic CRS such as EPSG:4326 is never measured directly in degrees.
- Uses a local UTM CRS for normal geographic datasets and keeps an already-metric projected CRS when appropriate.
- ZIP path traversal protection and upload-size limit.
- JSON-backed metadata repository keeps the example easy to run; it can be replaced by PostgreSQL/SQLAlchemy for production scale.
- Docker and docker-compose support.
- Automated tests for API validation and CRS-safe measurements.

## Tech Stack

- Python 3.12
- FastAPI
- GeoPandas
- Shapely
- PyProj
- Fiona/GDAL
- Pytest

## Project Structure

```text
geospatial-measurement-api/
├── app/
│   ├── api/routes.py          # HTTP endpoints and request handling
│   ├── services/geospatial.py # file parsing, CRS selection and measurements
│   ├── config.py              # paths and configuration
│   ├── models.py              # file metadata model
│   ├── repository.py          # lightweight persistent metadata repository
│   ├── schemas.py             # API response schemas
│   └── main.py                # FastAPI application
├── storage/
│   ├── uploads/               # uploaded source files (gitignored)
│   └── processed/             # processed JSON results (gitignored)
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Setup

### Option 1 — Local Python

Python 3.12 is recommended.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the API:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

- `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

### Option 2 — Docker

```bash
docker compose up --build
```

Then open `http://127.0.0.1:8000/docs`.

## API Documentation

### 1. Upload and process a file

`POST /api/files/`

Multipart form field:

- `file`: `.kml` or `.zip` containing a Shapefile

Example using curl:

```bash
curl -X POST "http://127.0.0.1:8000/api/files/" \
  -F "file=@survey.kml"
```

Example response:

```json
{
  "id": "8b0f0c3c0b9342d9a0b9b6e2c5b0d8c1",
  "filename": "survey.kml",
  "feature_count": 120,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "created_at": "2026-10-07T10:00:00+00:00",
  "error": null
}
```

### 2. File information

`GET /api/files/{id}/`

Example:

```bash
curl "http://127.0.0.1:8000/api/files/8b0f0c3c0b9342d9a0b9b6e2c5b0d8c1/"
```

Returns the uploaded filename, feature count, source CRS and processing status.

### 3. Measurements

`GET /api/files/{id}/measurements/`

Example:

```bash
curl "http://127.0.0.1:8000/api/files/8b0f0c3c0b9342d9a0b9b6e2c5b0d8c1/measurements/"
```

Example response shape:

```json
{
  "file_id": "8b0f0c3c0b9342d9a0b9b6e2c5b0d8c1",
  "filename": "survey.kml",
  "source_crs": "EPSG:4326",
  "measurement_crs": "EPSG:32643",
  "features": [
    {
      "feature_id": 0,
      "geometry_type": "Polygon",
      "geometry": {
        "type": "Polygon",
        "coordinates": []
      },
      "crs": "EPSG:4326",
      "properties": {
        "name": "Plot A"
      },
      "measurement": {
        "type": "area",
        "value": 12345.67,
        "unit": "m²"
      },
      "measurement_status": "COMPLETED",
      "message": null
    }
  ]
}
```

For a LineString, the measurement is:

```json
{
  "type": "length",
  "value": 1250.42,
  "unit": "m"
}
```

For a Point, `measurement` is `null` and `measurement_status` is `NOT_REQUIRED`.

For unsupported geometry types, `measurement_status` is `UNSUPPORTED` and a human-readable `message` is included.

## Processing Flow

1. Validate the file extension.
2. Stream the upload to disk with a configurable size limit.
3. For a ZIP, validate archive paths and require exactly one `.shp` plus its `.shx` and `.dbf` companions.
4. Load the data through GeoPandas/Fiona.
5. Read source CRS and feature attributes.
6. Select a metric measurement CRS.
7. Reproject geometries before calculating area/length.
8. Serialize feature information and measurements to processed JSON.
9. Store lightweight file metadata in the repository.
10. Return the file ID and processing status.

## CRS Handling Design

Calculating area or length directly from EPSG:4326 would produce values based on angular degrees and is therefore incorrect for metric measurements.

The service follows this strategy:

1. If the source CRS is already projected and uses metre/meter units, keep that CRS.
2. Otherwise transform the dataset temporarily to EPSG:4326, find its overall centroid, and select the corresponding UTM zone.
3. Northern hemisphere uses EPSG:326xx; southern hemisphere uses EPSG:327xx.
4. If the centroid is outside normal UTM latitude bounds, EPSG:3857 is used as a fallback.

This is appropriate for a general-purpose coding assignment. High-precision cadastral/survey applications should use a domain-specific authoritative CRS selected from the dataset's jurisdiction and accuracy requirements.

## Design Decisions

### Why FastAPI?

FastAPI provides type-safe request/response schemas, automatic OpenAPI documentation, simple multipart uploads and strong async support with relatively little boilerplate.

### Why GeoPandas/Shapely/PyProj?

They are standard Python geospatial tools and provide reliable geometry handling, CRS transformations and measurements without implementing computational geometry manually.

### Why JSON metadata storage?

The assignment only requires file metadata persistence. A small JSON repository keeps setup simple and makes the submission easy to run. The repository is isolated behind `FileRepository`, so replacing it with PostgreSQL/SQLAlchemy is straightforward.

### Why persist processed measurements?

The upload endpoint performs processing once. The measurements endpoint then reads the persisted result rather than parsing the original geospatial file on every request. This is simpler and faster for repeated reads.

### ZIP security

ZIP entries are checked for absolute paths and `..` path traversal before extraction. Only one Shapefile is accepted, and the standard `.shp`, `.shx` and `.dbf` components are required.

## Testing

Run:

```bash
pytest -q
```

The test suite covers:

- health endpoint
- unsupported upload extension
- missing file handling
- EPSG:4326 polygon area calculation using a projected CRS
- EPSG:4326 LineString length calculation

## Configuration

The default maximum upload size is 100 MB. Override it with an environment variable:

```bash
MAX_UPLOAD_SIZE=52428800 uvicorn app.main:app --reload
```

## Learning

This assignment demonstrates practical backend development around geospatial data: multipart uploads, validation, archive safety, GeoPandas/Fiona integration, CRS transformation, geometry measurement, API schema design, persistence and testing.

## Future Scope

- PostgreSQL + PostGIS for scalable persistence and spatial queries.
- Background processing with Celery/RQ for very large files.
- Object storage such as S3 for uploaded files.
- Authentication, authorization and per-user file ownership.
- Pagination for very large feature collections.
- Streaming/async job status for long-running processing.
- More geometry support such as MultiPolygon and MultiLineString.
- Area/length conversion into hectares, km², feet and miles.
- Better CRS selection using administrative boundaries or user-provided CRS.
- Rate limiting, structured logging, metrics and centralized error tracking.
- Virus/malware scanning and stricter archive/resource quotas for public deployments.

## Submission Checklist

Before sharing the repository:

1. Run `pytest -q`.
2. Start the API and verify `/docs`.
3. Upload one KML and one zipped Shapefile.
4. Verify the file-info and measurements endpoints.
5. Push the project to a public GitHub repository.
6. Share the GitHub URL with the recruiter/interviewer.

## License

This assignment implementation is provided for evaluation and learning purposes.
