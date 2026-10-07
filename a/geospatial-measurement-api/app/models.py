from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

@dataclass
class FileRecord:
    id: str
    filename: str
    stored_path: str
    feature_count: int
    crs: str | None
    status: str
    created_at: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
