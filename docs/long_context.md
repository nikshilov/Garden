# Long-Context Management Strategy

> **Goal:** enable effectively unbounded chats while keeping the active prompt small (<4 k tokens) and predictable in cost.

---

## 1. Context Layers
Layer | Typical Size | Description
----- | ------------ | -----------
Short-term window | last 10–20 raw turns | Verbatim recent dialogue needed for local coherence.
Episodic memory | ≤500 tokens per episode | Auto-generated TL;DR of batches that have scrolled out of the short-term window.
Semantic memory | vector store, ∞ | Facts, user profile, outstanding promises. Queried by embedding similarity + freshness weight.
Persona / System | ≤500 tokens | Character instructions & style.

Only a subset of layers is sent in every request: `prompt = persona + short-term + top-K(episodic+semantic)`.

---

## 2. Sliding Window → Episodic Summaries
1. Append each user/assistant message to the short-term list.
2. When `len(short_term) > WINDOW_SIZE` (_default = 20_), pop the oldest N messages (e.g. 8).
3. Run **Summarizer** LLM (small/local) and produce 1–2 sentence TL;DR (max 120 tokens).
4. Persist TL;DR as `EpisodicRecord(id, text, token_count, created_at)` in `episodic_store`.

Recursive summarization: every `DEPTH_FACTOR` episodes (e.g. 8) trigger second-level summary to keep store compact (tree structure).

---

## 3. Retrieval
Before calling the character LLM:
```
short_term = last 10–20 raw turns
candidates = episodic_store.vector_search(query_embedding, top=8)
semantic = memory_manager.top_k(character_id, k=5)
context = short_term + rerank(candidates+semantic, k_final=8)
```
Rerank uses weighted score: `0.6×similarity + 0.4×recency_boost`.

---

## 4. Cost Control
* Only the short-term window and a handful of summaries are sent → hard ceiling on prompt length.
* Summaries are produced by an inexpensive LLM (`phi3-mini`) or batch-processed nightly.
* **CostTracker** already measures usage; add budget alerts (`warn ≥$X/day`).

---

## 5. Module Interfaces
### Summarizer (`garden_graph/summarizer.py`)
```python
class Summarizer:
    def summarize(messages: list[dict[str,str]]) -> str: ...  # returns TL;DR
```

### EpisodicStore (`garden_graph/memory/episodic.py`)
```python
class EpisodicStore:
    def add(summary: str) -> EpisodicRecord: ...
    def search(query: str, k: int = 8) -> list[EpisodicRecord]: ...
    def recursive_compact() -> None: ...
```
Backed by JSON + optional FAISS/Chroma for vectors.

### DialogManager Updates
```python
# inside on_user_message()
if window_full:
    tl_dr = Summarizer.summarize(popped_msgs)
    episodic_store.add(tl_dr)
```

---

## 6. Background Tasks (Scheduler)
* Nightly job: `episodic_store.recursive_compact()`
* Weekly: decay semantic memory weights (already implemented).

---

## 7. Testing Checklist
- [ ] Short-term overflow triggers summarizer & store entry.
- [ ] Prompt length never exceeds budget.
- [ ] Retrieval returns relevant episodic summaries.
- [ ] End-to-end long chat (≥1 000 turns) stays coherent.

---
*(Last updated: 2025-06-05)*
