from ..models import now_iso
from ..storage import store


class MemoryBank:
    def recall(self, entity: str | None) -> dict | None:
        if not entity or not str(entity).strip():
            return None
        return store.get("memories", str(entity).strip())

    def remember(self, entity: str | None, previous_analysis: str, decisions: list[str], workflow_id: str) -> dict:
        if not entity or not str(entity).strip():
            return {}
        clean_entity = str(entity).strip()
        return store.upsert("memories", clean_entity, {
            "entity": clean_entity,
            "previous_analysis": previous_analysis,
            "previous_decisions": decisions,
            "last_updated": now_iso(),
            "workflow_id": workflow_id
        })


memory_bank = MemoryBank()
