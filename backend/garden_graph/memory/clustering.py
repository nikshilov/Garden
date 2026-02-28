"""Memory clustering — finds thematic groups in episodic memories.

During heartbeat, clusters related memories together so that reflections
can synthesize meaning from groups of related experiences rather than
individual events.

"These 5 memories are all about your relationship with your sister."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

logger = logging.getLogger("garden.memory.clustering")


@dataclass
class MemoryCluster:
    """A group of related episodic memories."""
    label: str  # human-readable theme label
    record_ids: List[str]  # IDs of EpisodicRecords in this cluster
    centroid: List[float]  # average embedding vector
    coherence: float  # average pairwise similarity within cluster (0-1)


def cluster_memories(
    embeddings: np.ndarray,
    record_ids: List[str],
    summaries: List[str],
    min_cluster_size: int = 3,
    similarity_threshold: float = 0.5,
) -> List[MemoryCluster]:
    """Cluster memories by embedding similarity using agglomerative approach.

    Uses a simple greedy agglomerative algorithm rather than pulling in
    sklearn — keeps dependencies light for a personal project.

    Args:
        embeddings: (N, D) array of embedding vectors
        record_ids: parallel list of record IDs
        summaries: parallel list of summary texts (for labeling)
        min_cluster_size: minimum memories to form a cluster
        similarity_threshold: cosine similarity threshold to merge

    Returns:
        List of MemoryCluster objects
    """
    n = len(record_ids)
    if n < min_cluster_size:
        return []

    # Normalize embeddings for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    normed = embeddings / norms

    # Compute full similarity matrix
    sim_matrix = normed @ normed.T

    # Greedy agglomerative clustering
    # Start with each memory in its own cluster
    clusters: List[List[int]] = [[i] for i in range(n)]
    active = set(range(n))

    while len(active) > 1:
        best_sim = -1.0
        best_pair = (-1, -1)

        active_list = sorted(active)
        for i_idx in range(len(active_list)):
            for j_idx in range(i_idx + 1, len(active_list)):
                ci, cj = active_list[i_idx], active_list[j_idx]
                # Average linkage
                total_sim = 0.0
                count = 0
                for a in clusters[ci]:
                    for b in clusters[cj]:
                        total_sim += sim_matrix[a, b]
                        count += 1
                avg_sim = total_sim / count if count else 0
                if avg_sim > best_sim:
                    best_sim = avg_sim
                    best_pair = (ci, cj)

        if best_sim < similarity_threshold:
            break

        # Merge best pair
        ci, cj = best_pair
        clusters[ci] = clusters[ci] + clusters[cj]
        clusters[cj] = []
        active.discard(cj)

    # Filter to clusters meeting minimum size
    results = []
    for cluster_indices in clusters:
        if len(cluster_indices) < min_cluster_size:
            continue

        ids = [record_ids[i] for i in cluster_indices]
        vecs = embeddings[cluster_indices]
        centroid = vecs.mean(axis=0)

        # Compute coherence (average pairwise similarity)
        cluster_normed = normed[cluster_indices]
        if len(cluster_indices) > 1:
            pairwise = cluster_normed @ cluster_normed.T
            # Extract upper triangle (exclude diagonal)
            mask = np.triu(np.ones_like(pairwise, dtype=bool), k=1)
            coherence = float(pairwise[mask].mean())
        else:
            coherence = 1.0

        # Label from the summary closest to centroid
        centroid_normed = centroid / (np.linalg.norm(centroid) + 1e-8)
        sims_to_centroid = cluster_normed @ centroid_normed
        closest_idx = cluster_indices[int(np.argmax(sims_to_centroid))]
        label = summaries[closest_idx][:80]

        results.append(MemoryCluster(
            label=label,
            record_ids=ids,
            centroid=centroid.tolist(),
            coherence=coherence,
        ))

    logger.debug(f"Clustered {n} memories into {len(results)} clusters")
    return results
