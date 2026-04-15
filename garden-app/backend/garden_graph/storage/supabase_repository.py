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

from garden_graph.storage.repository import MemoryRepository, EventRepository, GraphRepository

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


class SupabaseGraphRepo(GraphRepository):
    ENTITIES_TABLE = "memory_graph_entities"
    EDGES_TABLE = "memory_graph_edges"

    def load_graph(self, character_id: str) -> dict:
        entities_data = (
            _client.table(self.ENTITIES_TABLE)
            .select("*")
            .eq("character_id", character_id)
            .execute()
            .data
            or []
        )
        edges_data = (
            _client.table(self.EDGES_TABLE)
            .select("*")
            .eq("character_id", character_id)
            .execute()
            .data
            or []
        )

        entities = {}
        for row in entities_data:
            entities[row["name"]] = {
                "name": row["name"],
                "entity_type": row["entity_type"],
                "memory_ids": row.get("memory_ids") or [],
                "aliases": row.get("aliases") or [],
            }

        edges = []
        for row in edges_data:
            edges.append({
                "source_id": row["source_memory_id"],
                "target_id": row["target_memory_id"],
                "edge_type": row["edge_type"],
                "confidence": float(row.get("confidence", 0.5)),
                "created_at": row.get("created_at", ""),
            })

        return {"entities": entities, "edges": edges}

    def save_graph(self, character_id: str, data: dict) -> None:
        # Clear existing data for this character
        _client.table(self.ENTITIES_TABLE).delete().eq("character_id", character_id).execute()
        _client.table(self.EDGES_TABLE).delete().eq("character_id", character_id).execute()

        # Insert entities
        for name, ent in data.get("entities", {}).items():
            self.add_entity(character_id, ent)

        # Insert edges
        for edge in data.get("edges", []):
            self.add_edge(character_id, edge)

    def add_entity(self, character_id: str, entity: dict) -> None:
        row = {
            "character_id": character_id,
            "name": entity["name"],
            "entity_type": entity.get("entity_type", "concept"),
            "memory_ids": entity.get("memory_ids", []),
            "aliases": entity.get("aliases", []),
            "metadata": entity.get("metadata", {}),
        }
        _client.table(self.ENTITIES_TABLE).upsert(
            row, on_conflict="character_id,name"
        ).execute()

    def add_edge(self, character_id: str, edge: dict) -> None:
        row = {
            "character_id": character_id,
            "source_memory_id": edge.get("source_id", ""),
            "target_memory_id": edge.get("target_id", ""),
            "edge_type": edge.get("edge_type", "amplifies"),
            "confidence": float(edge.get("confidence", 0.5)),
            "metadata": edge.get("metadata", {}),
        }
        _client.table(self.EDGES_TABLE).insert(row).execute()

    def remove_entity(self, character_id: str, entity_name: str) -> None:
        _client.table(self.ENTITIES_TABLE).delete().eq(
            "character_id", character_id
        ).eq("name", entity_name).execute()

    def remove_edges_for_memory(self, character_id: str, memory_id: str) -> None:
        # Delete edges where memory is source
        _client.table(self.EDGES_TABLE).delete().eq(
            "character_id", character_id
        ).eq("source_memory_id", memory_id).execute()
        # Delete edges where memory is target
        _client.table(self.EDGES_TABLE).delete().eq(
            "character_id", character_id
        ).eq("target_memory_id", memory_id).execute()
