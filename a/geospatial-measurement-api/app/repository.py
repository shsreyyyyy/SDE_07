import json
from pathlib import Path
from threading import Lock
from typing import Any

from .config import DB_PATH

class FileRepository:
    """Small JSON-backed repository suitable for the assignment.

    For a larger deployment this can be replaced by PostgreSQL/SQLAlchemy
    without changing the API or processing service.
    """
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self.lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def get(self, file_id: str) -> dict[str, Any] | None:
        with self.lock:
            return self._read().get(file_id)

    def save(self, record: dict[str, Any]) -> None:
        with self.lock:
            data = self._read()
            data[record["id"]] = record
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(self.path)

repository = FileRepository()
