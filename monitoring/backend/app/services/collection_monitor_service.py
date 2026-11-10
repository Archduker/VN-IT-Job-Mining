"""Collection entry point: R2 inventory only, without Airflow or local reads."""

from app.services.collection_r2_service import get_collection


class CollectionMonitorService:
    def get_collection(self, days: int = 14):
        return get_collection(days)


collection_monitor_service = CollectionMonitorService()
