"""Local filesystem repository for uploaded IFC files and derived state."""

from pathlib import Path
from uuid import uuid4
import json

from app.models.ifc import IfcRecord
from app.settings import get_settings


class IfcRecordNotFoundError(LookupError):
    """Raised when an IFC record cannot be found."""


class IfcRepository:
    """Persist IFC uploads and derived metadata in a local directory."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or get_settings().IFC_STORAGE_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def create_ifc_id(self) -> str:
        """Create an opaque IFC identifier."""

        return uuid4().hex

    def save_ifc_bytes(self, ifc_id: str, filename: str, content: bytes) -> Path:
        """Persist the uploaded IFC bytes."""

        record_dir = self._record_dir(ifc_id)
        record_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename).suffix or ".ifc"
        ifc_path = record_dir / f"model{suffix}"
        ifc_path.write_bytes(content)
        return ifc_path

    def save_record(self, record: IfcRecord) -> None:
        """Persist a complete IFC record."""

        record_dir = self._record_dir(record.ifc_id)
        record_dir.mkdir(parents=True, exist_ok=True)
        payload = record.model_dump(mode="json")
        self._record_path(record.ifc_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_record(self, ifc_id: str) -> IfcRecord:
        """Load a stored IFC record."""

        record_path = self._record_path(ifc_id)
        if not record_path.exists():
            raise IfcRecordNotFoundError(f"IFC id not found: {ifc_id}")
        payload = json.loads(record_path.read_text(encoding="utf-8"))
        return IfcRecord.model_validate(payload)

    def _record_dir(self, ifc_id: str) -> Path:
        return self.storage_dir / ifc_id

    def _record_path(self, ifc_id: str) -> Path:
        return self._record_dir(ifc_id) / "record.json"
