from ..models import now_iso
from ..storage import store


class MemoryBank:
    def recall(self, entity: str) -> dict | None:
        return store.get("memories", entity)

    def remember(self, entity: str, previous_analysis: str, decisions: list[str], workflow_id: str) -> dict:
        return store.upsert("memories", entity, {"entity": entity, "previous_analysis": previous_analysis,
            "previous_decisions": decisions, "last_updated": now_iso(), "workflow_id": workflow_id})


memory_bank = MemoryBank()

