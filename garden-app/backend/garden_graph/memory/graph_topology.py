"""
Graph topology layer for Garden MemoryManager.

Adds entity nodes and edges between memories — connections that flat list
scoring cannot discover.  This is ADDITIVE: Garden's existing salient_memories()
scoring (sentiment + anchors + decay) stays untouched.  The graph provides
expand_related() which walks edges from seed memories to find related ones.

Storage: JSON file (memory_graph.json) alongside memories.json, or Supabase
via optional GraphRepository (tables: memory_graph_entities, memory_graph_edges).
Falls back to JSON-only when no repository is provided.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EntityNode:
    """A named entity extracted from memory text (person, place, concept)."""
    name: str                          # normalized lowercase
    entity_type: str                   # "person" | "place" | "concept" | "organization"
    memory_ids: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> EntityNode:
        return cls(**d)


@dataclass
class MemoryEdge:
    """Directed edge between two MemoryRecords."""
    source_id: str
    target_id: str
    edge_type: str       # "cause_of" | "temporal_before" | "amplifies" | "contradicts"
    confidence: float    # 0.0 – 1.0
    created_at: str = ""  # ISO-8601

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> MemoryEdge:
        return cls(**d)


# ---------------------------------------------------------------------------
# MemoryGraph — the topology container
# ---------------------------------------------------------------------------

class MemoryGraph:
    """In-memory graph over MemoryRecords.  Persisted as JSON or Supabase."""

    def __init__(self, repository=None, character_id: Optional[str] = None) -> None:
        self._entities: dict[str, EntityNode] = {}        # name -> EntityNode
        self._edges: list[MemoryEdge] = []
        # Indexes for fast lookup
        self._mem_to_entities: dict[str, set[str]] = {}   # memory_id -> entity names
        self._mem_to_edges: dict[str, list[int]] = {}     # memory_id -> edge indices
        # Optional Supabase persistence (falls back to JSON if None)
        self._repo = repository
        self._character_id = character_id

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_memory_data(
        self,
        memory_id: str,
        entities: list[dict],
        edges: list[dict],
    ) -> None:
        """Register extracted entities and edges for a newly created memory.

        Args:
            memory_id: UUID of the MemoryRecord.
            entities: list of {"name", "entity_type", "aliases"} dicts.
            edges: list of {"target_id", "edge_type", "confidence"} dicts
                   (source_id is always the new memory).
        """
        now = datetime.now(timezone.utc).isoformat()

        for e in entities:
            name = e["name"].lower().strip()
            if not name:
                continue
            if name not in self._entities:
                self._entities[name] = EntityNode(
                    name=name,
                    entity_type=e.get("entity_type", "concept"),
                    memory_ids=[],
                    aliases=[a.lower().strip() for a in e.get("aliases", [])],
                )
            node = self._entities[name]
            if memory_id not in node.memory_ids:
                node.memory_ids.append(memory_id)
            # Merge new aliases
            for alias in e.get("aliases", []):
                a = alias.lower().strip()
                if a and a not in node.aliases:
                    node.aliases.append(a)
            # Update reverse index
            self._mem_to_entities.setdefault(memory_id, set()).add(name)

        # Persist entities to Supabase (incremental upserts)
        if self._repo and self._character_id:
            for name in self._mem_to_entities.get(memory_id, set()):
                node = self._entities.get(name)
                if node:
                    try:
                        self._repo.add_entity(self._character_id, node.to_dict())
                    except Exception as err:
                        print(f"[MemoryGraph] Supabase entity save error: {err}")

        for ed in edges:
            target = ed.get("target_id", "")
            if not target:
                continue
            edge = MemoryEdge(
                source_id=memory_id,
                target_id=target,
                edge_type=ed.get("edge_type", "amplifies"),
                confidence=float(ed.get("confidence", 0.5)),
                created_at=now,
            )
            idx = len(self._edges)
            self._edges.append(edge)
            self._mem_to_edges.setdefault(memory_id, []).append(idx)
            self._mem_to_edges.setdefault(target, []).append(idx)

            # Persist edge to Supabase
            if self._repo and self._character_id:
                try:
                    self._repo.add_edge(self._character_id, edge.to_dict())
                except Exception as err:
                    print(f"[MemoryGraph] Supabase edge save error: {err}")

    def on_archive(self, memory_id: str) -> None:
        """Clean up entity refs when a memory is archived.

        Edges are preserved (the relationship still existed).
        Entity refs are removed; empty entities are pruned.
        """
        entity_names = self._mem_to_entities.pop(memory_id, set())
        dead_entities = []
        for name in entity_names:
            node = self._entities.get(name)
            if node and memory_id in node.memory_ids:
                node.memory_ids.remove(memory_id)
                if not node.memory_ids:
                    dead_entities.append(name)
        for name in dead_entities:
            del self._entities[name]
            if self._repo and self._character_id:
                try:
                    self._repo.remove_entity(self._character_id, name)
                except Exception as err:
                    print(f"[MemoryGraph] Supabase entity remove error: {err}")

        # Persist updated (non-dead) entities back to Supabase
        if self._repo and self._character_id:
            for name in entity_names - set(dead_entities):
                node = self._entities.get(name)
                if node:
                    try:
                        self._repo.add_entity(self._character_id, node.to_dict())
                    except Exception as err:
                        print(f"[MemoryGraph] Supabase entity update error: {err}")

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def expand_related(
        self,
        seed_ids: list[str],
        active_ids: set[str],
        max_hops: int = 1,
        max_expand: int = 2,
    ) -> list[tuple[str, str]]:
        """Walk edges from seed memories to discover related active memories.

        Returns list of (memory_id, reason) tuples.
        Only returns memories in active_ids and NOT in seed_ids.
        """
        seed_set = set(seed_ids)
        candidates: dict[str, tuple[float, str]] = {}  # id -> (score, reason)

        for sid in seed_ids:
            # --- Edge-based expansion ---
            for edge_idx in self._mem_to_edges.get(sid, []):
                edge = self._edges[edge_idx]
                # Follow edge in both directions
                neighbor = edge.target_id if edge.source_id == sid else edge.source_id
                if neighbor in seed_set or neighbor not in active_ids:
                    continue
                score = edge.confidence + 0.5  # edge bonus
                reason = f"{edge.edge_type} (conf={edge.confidence:.1f})"
                if neighbor not in candidates or candidates[neighbor][0] < score:
                    candidates[neighbor] = (score, reason)

            # --- Entity-based expansion ---
            for entity_name in self._mem_to_entities.get(sid, set()):
                node = self._entities.get(entity_name)
                if not node:
                    continue
                for mid in node.memory_ids:
                    if mid in seed_set or mid not in active_ids:
                        continue
                    # Count how many seed entities this memory shares
                    shared = len(
                        self._mem_to_entities.get(mid, set())
                        & self._mem_to_entities.get(sid, set())
                    )
                    score = 0.3 * shared
                    reason = f"shared entity: {entity_name}"
                    if mid not in candidates or candidates[mid][0] < score:
                        candidates[mid] = (score, reason)

        # Rank by score descending
        ranked = sorted(candidates.items(), key=lambda x: -x[1][0])
        return [(mid, reason) for mid, (_, reason) in ranked[:max_expand]]

    def entity_neighbors(
        self,
        entity_name: str,
        exclude_ids: Optional[set[str]] = None,
    ) -> list[str]:
        """Return memory IDs that reference the given entity."""
        name = entity_name.lower().strip()
        # Check direct name and aliases
        node = self._entities.get(name)
        if not node:
            # Search aliases
            for n, ent in self._entities.items():
                if name in ent.aliases:
                    node = ent
                    break
        if not node:
            return []
        exclude = exclude_ids or set()
        return [mid for mid in node.memory_ids if mid not in exclude]

    def get_entities_for_memory(self, memory_id: str) -> list[EntityNode]:
        """Return all entities linked to a given memory."""
        names = self._mem_to_entities.get(memory_id, set())
        return [self._entities[n] for n in names if n in self._entities]

    def get_edges_for_memory(self, memory_id: str) -> list[MemoryEdge]:
        """Return all edges touching a given memory."""
        indices = self._mem_to_edges.get(memory_id, [])
        return [self._edges[i] for i in indices if i < len(self._edges)]

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    # ------------------------------------------------------------------
    # Persistence (JSON + optional Supabase)
    # ------------------------------------------------------------------

    def save_to_file(self, filepath: str) -> None:
        data = {
            "entities": {k: v.to_dict() for k, v in self._entities.items()},
            "edges": [e.to_dict() for e in self._edges],
        }
        Path(filepath).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # Also persist full snapshot to Supabase if repo is wired
        if self._repo and self._character_id:
            try:
                self._repo.save_graph(self._character_id, data)
            except Exception as err:
                print(f"[MemoryGraph] Supabase full save error: {err}")

    def load_from_file(self, filepath: str) -> None:
        p = Path(filepath)
        if not p.exists():
            return
        self._load_data(json.loads(p.read_text(encoding="utf-8")))

    def load_from_repo(self) -> None:
        """Load graph from Supabase repository.  No-op if repo is not set."""
        if not self._repo or not self._character_id:
            return
        data = self._repo.load_graph(self._character_id)
        if data.get("entities") or data.get("edges"):
            self._load_data(data)

    def _load_data(self, data: dict) -> None:
        """Populate in-memory structures from a {entities, edges} dict."""
        self._entities.clear()
        self._edges.clear()
        self._mem_to_entities.clear()
        self._mem_to_edges.clear()

        for name, d in data.get("entities", {}).items():
            node = EntityNode.from_dict(d)
            self._entities[name] = node
            for mid in node.memory_ids:
                self._mem_to_entities.setdefault(mid, set()).add(name)

        for i, d in enumerate(data.get("edges", [])):
            edge = MemoryEdge.from_dict(d)
            self._edges.append(edge)
            self._mem_to_edges.setdefault(edge.source_id, []).append(i)
            self._mem_to_edges.setdefault(edge.target_id, []).append(i)
