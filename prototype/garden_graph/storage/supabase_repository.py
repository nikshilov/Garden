"""Supabase-backed repository implementations.

Requires `supabase-py` package:
    pip install supabase

The module expects the following env variables:
    SUPABASE_URL               - project API URL (https://xyzcompany.supabase.co)
    SUPABASE_SERVICE_ROLE_KEY  - service role key (or anon/public key for R/O)

Set STORAGE_BACKEND=supabase to let core switch to these repositories.
"""
from __future__ import annotations

import os
from typing import List

try:
    from supabase import create_client
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "supabase-py package not installed. Run `pip install supabase` inside your environment."
    ) from exc

from datetime import datetime

from garden_graph.storage.repository import MemoryRepository, EventRepository

if False:  # type checking only
    from garden_graph.memory.manager import MemoryRecord  # pragma: no cover


SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars must be set")

_client = create_client(SUPABASE_URL, SUPABASE_KEY)


class SupabaseMemoryRepo(MemoryRepository):
    TABLE = "memories"

    def _to_serializable(self, obj: dict) -> dict:
        """Convert datetimes to ISO strings so Supabase JSON accepts them."""
        for k, v in list(obj.items()):
            if isinstance(v, datetime):
                obj[k] = v.isoformat()
        return obj

    def save(self, record) -> None:  # noqa: D401
        """Accept MemoryRecord or plain dict."""
        from dataclasses import asdict
        if not isinstance(record, dict):
            record = asdict(record)
        _client.table(self.TABLE).upsert(self._to_serializable(record)).execute()

    def delete(self, record_id: str) -> None:  # noqa: D401
        _client.table(self.TABLE).delete().eq("id", record_id).execute()

    def _row_to_record(self, row: dict):
        """Convert Supabase row to MemoryRecord with proper datetime objects."""
        for ts_field in ("created_at", "last_accessed", "last_touched"):
            if ts_field in row and isinstance(row[ts_field], str):
                try:
                    row[ts_field] = datetime.fromisoformat(row[ts_field])
                except ValueError:
                    pass
        from garden_graph.memory.manager import MemoryRecord  # local import
        return MemoryRecord(**row)

    def load_all(self):  # type: ignore[override]
        data = _client.table(self.TABLE).select("*").execute().data or []
        return [self._row_to_record(row) for row in data]

    def get_since(self, since: datetime):  # type: ignore[override]
        data = (
            _client.table(self.TABLE)
            .select("*")
            .gte("created_at", since.isoformat())
            .execute()
            .data
            or []
        )
        return [self._row_to_record(row) for row in data]


class SupabaseEventRepo(EventRepository):
    TABLE = "events"

    def save(self, event: dict) -> None:  # noqa: D401
        from copy import deepcopy
        _client.table(self.TABLE).upsert(self._serialize_event(deepcopy(event))).execute()

    def _serialize_event(self, event: dict) -> dict:
        from datetime import datetime
        for k, v in list(event.items()):
            if isinstance(v, datetime):
                event[k] = v.isoformat()
        return event

    def load_all(self):  # type: ignore[override]
        return _client.table(self.TABLE).select("*").execute().data or []

    def delete(self, event_id: str) -> None:  # noqa: D401
        _client.table(self.TABLE).delete().eq("id", event_id).execute()
