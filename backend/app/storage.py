import json
from pathlib import Path
from threading import Lock
from typing import Any
from .config import settings


class Store:
    """Firestore in production, durable JSON locally for zero-cost development."""

    def __init__(self):
        self._lock = Lock()
        self.client = None
        try:
            if settings.google_cloud_project:
                from google.cloud import firestore
                self.client = firestore.Client(project=settings.google_cloud_project, database=settings.firestore_database)
        except Exception:
            self.client = None
        self.path = Path(settings.local_data_file)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({}), encoding="utf-8")

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def list(self, collection: str) -> list[dict[str, Any]]:
        if self.client:
            return [doc.to_dict() | {"id": doc.id} for doc in self.client.collection(collection).stream()]
        with self._lock:
            return list(self._read().get(collection, {}).values())

    def get(self, collection: str, item_id: str) -> dict[str, Any] | None:
        if self.client:
            doc = self.client.collection(collection).document(item_id).get()
            return doc.to_dict() | {"id": doc.id} if doc.exists else None
        with self._lock:
            return self._read().get(collection, {}).get(item_id)

    def upsert(self, collection: str, item_id: str, value: dict[str, Any]) -> dict[str, Any]:
        value = value | {"id": item_id}
        if self.client:
            self.client.collection(collection).document(item_id).set(value, merge=True)
            return value
        with self._lock:
            data = self._read()
            data.setdefault(collection, {})[item_id] = value
            self.path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            return value

    def add(self, collection: str, value: dict[str, Any], item_id: str) -> dict[str, Any]:
        return self.upsert(collection, item_id, value)


store = Store()

