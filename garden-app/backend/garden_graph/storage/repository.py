"""Abstract repository interfaces for persistence layer (Phase P4).

These lightweight protocols allow swapping underlying storage engines
(e.g., JSON, SQLite, Core Data, CloudKit) without changing core logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Protocol

from datetime import datetime

# NOTE: Importing at runtime to avoid circular dependencies
if False:  # type checking only
    from garden_graph.memory.manager import MemoryRecord  # pragma: no cover


class MemoryRepository(Protocol):
    """CRUD operations for MemoryRecord objects."""

    @abstractmethod
    def save(self, record: "MemoryRecord") -> None:  # noqa: D401
        """Insert or update a record."""

    @abstractmethod
    def delete(self, record_id: str) -> None:  # noqa: D401
        """Delete by ID."""

    @abstractmethod
    def load_all(self) -> List["MemoryRecord"]:  # noqa: D401
        """Return all records (could be paged in future)."""

    @abstractmethod
    def get_since(self, since: datetime) -> List["MemoryRecord"]:  # noqa: D401
        """Return records created after *since*."""


class EventRepository(Protocol):
    """CRUD for scheduled events."""

    @abstractmethod
    def save(self, event: dict) -> None:  # noqa: D401
        pass

    @abstractmethod
    def load_all(self) -> List[dict]:  # noqa: D401
        pass

    @abstractmethod
    def delete(self, event_id: str) -> None:  # noqa: D401
        pass


class GraphRepository(Protocol):
    """CRUD for graph topology (entities + edges between memories)."""

    @abstractmethod
    def load_graph(self, character_id: str) -> Dict:  # noqa: D401
        """Return full graph as {"entities": {...}, "edges": [...]}."""

    @abstractmethod
    def save_graph(self, character_id: str, data: Dict) -> None:  # noqa: D401
        """Overwrite entire graph for a character."""

    @abstractmethod
    def add_entity(self, character_id: str, entity: Dict) -> None:  # noqa: D401
        """Upsert a single entity node."""

    @abstractmethod
    def add_edge(self, character_id: str, edge: Dict) -> None:  # noqa: D401
        """Insert a single edge."""

    @abstractmethod
    def remove_entity(self, character_id: str, entity_name: str) -> None:  # noqa: D401
        """Delete an entity by name."""

    @abstractmethod
    def remove_edges_for_memory(self, character_id: str, memory_id: str) -> None:  # noqa: D401
        """Delete all edges that reference a given memory_id (source or target)."""
