"""Tests for the embedding engine (Phase 2)."""
import json
import unittest
from unittest.mock import patch, MagicMock
import numpy as np


class TestEmbedder(unittest.TestCase):
    """Test the Embedder singleton and its operations."""

    def test_get_embedder_returns_instance(self):
        from garden_graph.memory.embedder import get_embedder
        emb = get_embedder()
        # sentence-transformers is installed, so this should work
        self.assertIsNotNone(emb)

    def test_singleton(self):
        from garden_graph.memory.embedder import get_embedder
        a = get_embedder()
        b = get_embedder()
        self.assertIs(a, b)

    def test_encode_returns_384_dim(self):
        from garden_graph.memory.embedder import get_embedder
        emb = get_embedder()
        vec = emb.encode("hello world")
        self.assertEqual(vec.shape, (384,))
        self.assertEqual(vec.dtype, np.float32)

    def test_encode_batch(self):
        from garden_graph.memory.embedder import get_embedder
        emb = get_embedder()
        vecs = emb.encode_batch(["hello", "world", "test"])
        self.assertEqual(vecs.shape, (3, 384))

    def test_cosine_similarity_identical(self):
        from garden_graph.memory.embedder import get_embedder
        emb = get_embedder()
        vec = emb.encode("the cat sat on the mat")
        sim = emb.cosine_similarity(vec, vec)
        self.assertAlmostEqual(sim, 1.0, places=5)

    def test_cosine_similarity_different(self):
        from garden_graph.memory.embedder import get_embedder
        emb = get_embedder()
        v1 = emb.encode("I feel lonely tonight")
        v2 = emb.encode("quantum mechanics equations")
        sim = emb.cosine_similarity(v1, v2)
        self.assertLess(sim, 0.5)

    def test_semantic_similarity_captures_meaning(self):
        """The whole point: 'I feel alone' should match 'loneliness' better than 'quantum physics'."""
        from garden_graph.memory.embedder import get_embedder
        emb = get_embedder()
        query = emb.encode("I feel alone tonight")
        close = emb.encode("We talked about loneliness and connection")
        far = emb.encode("The stock market crashed yesterday")

        sim_close = emb.cosine_similarity(query, close)
        sim_far = emb.cosine_similarity(query, far)
        self.assertGreater(sim_close, sim_far,
                           f"Semantic match failed: close={sim_close:.3f} should be > far={sim_far:.3f}")

    def test_search_returns_top_k(self):
        from garden_graph.memory.embedder import get_embedder
        emb = get_embedder()
        corpus = [
            "We discussed feelings of loneliness",
            "Had a conversation about quantum physics",
            "Talked about missing someone special",
            "Reviewed the stock market performance",
            "Shared memories of childhood friends",
        ]
        corpus_vecs = emb.encode_batch(corpus)
        query_vec = emb.encode("I miss my old friends")
        results = emb.search(query_vec, corpus_vecs, top_k=2)
        self.assertEqual(len(results), 2)
        # Results should be (index, score) tuples
        idx, score = results[0]
        self.assertIsInstance(idx, int)
        self.assertIsInstance(score, float)
        # Top result should be about missing someone or childhood friends
        self.assertIn(idx, [2, 4])


class TestClustering(unittest.TestCase):
    """Test memory clustering."""

    def test_cluster_similar_memories(self):
        from garden_graph.memory.embedder import get_embedder
        from garden_graph.memory.clustering import cluster_memories
        emb = get_embedder()

        summaries = [
            # Cluster 1: loneliness theme
            "Talked about feeling lonely at night",
            "Discussed missing close friends",
            "Shared feelings of isolation",
            # Cluster 2: work theme
            "Discussed the new project deadline",
            "Talked about workplace stress",
            "Shared frustration about the boss",
            # Outlier
            "Random thought about cooking pasta",
        ]
        record_ids = [f"rec_{i}" for i in range(len(summaries))]
        embeddings = emb.encode_batch(summaries)

        clusters = cluster_memories(
            embeddings, record_ids, summaries,
            min_cluster_size=2, similarity_threshold=0.4,
        )
        # Should find at least 1 cluster
        self.assertGreaterEqual(len(clusters), 1)
        # Each cluster should have a label and coherence
        for c in clusters:
            self.assertTrue(len(c.label) > 0)
            self.assertGreater(c.coherence, 0)
            self.assertGreaterEqual(len(c.record_ids), 2)

    def test_no_clusters_for_small_input(self):
        from garden_graph.memory.clustering import cluster_memories
        # Less than min_cluster_size
        embeddings = np.random.randn(2, 384).astype(np.float32)
        clusters = cluster_memories(embeddings, ["a", "b"], ["s1", "s2"], min_cluster_size=3)
        self.assertEqual(clusters, [])

    def test_no_clusters_for_dissimilar(self):
        from garden_graph.memory.clustering import cluster_memories
        # Very different topics shouldn't cluster at high threshold
        rng = np.random.RandomState(42)
        embeddings = rng.randn(5, 384).astype(np.float32)
        clusters = cluster_memories(
            embeddings, [f"r{i}" for i in range(5)], [f"s{i}" for i in range(5)],
            min_cluster_size=2, similarity_threshold=0.99,
        )
        self.assertEqual(clusters, [])


class TestAPIEmbedder(unittest.TestCase):
    """Test the API-based embedding backend (LM Studio / OpenAI / OpenRouter)."""

    def _make_api_response(self, texts, dim=384):
        """Create a mock OpenAI-compatible embeddings response."""
        data = []
        for i, _ in enumerate(texts):
            # Deterministic fake embedding based on text hash
            rng = np.random.RandomState(hash(texts[i]) % 2**31)
            vec = rng.randn(dim).astype(np.float32).tolist()
            data.append({"index": i, "embedding": vec})
        return {"data": data, "model": "test-model", "usage": {"total_tokens": 10}}

    @patch("httpx.post")
    def test_api_embedder_encode(self, mock_post):
        from garden_graph.memory.embedder import APIEmbedder

        mock_response = MagicMock()
        mock_response.json.return_value = self._make_api_response(["hello"], dim=768)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        emb = APIEmbedder(
            base_url="http://192.168.1.100:1234",
            model="nomic-embed-text",
            dim=768,
        )
        vec = emb.encode("hello")
        self.assertEqual(vec.shape, (768,))
        self.assertEqual(vec.dtype, np.float32)

        # Verify correct URL called
        mock_post.assert_called_once()
        call_url = mock_post.call_args[1].get("url") or mock_post.call_args[0][0]
        self.assertIn("/v1/embeddings", call_url)

    @patch("httpx.post")
    def test_api_embedder_batch(self, mock_post):
        from garden_graph.memory.embedder import APIEmbedder

        texts = ["hello", "world", "test"]
        mock_response = MagicMock()
        mock_response.json.return_value = self._make_api_response(texts, dim=512)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        emb = APIEmbedder(base_url="http://localhost:1234", model="test", dim=512)
        vecs = emb.encode_batch(texts)
        self.assertEqual(vecs.shape, (3, 512))

    @patch("httpx.post")
    def test_api_embedder_auth_header(self, mock_post):
        from garden_graph.memory.embedder import APIEmbedder

        mock_response = MagicMock()
        mock_response.json.return_value = self._make_api_response(["hi"])
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        emb = APIEmbedder(
            base_url="https://api.openai.com",
            api_key="sk-test-key",
            model="text-embedding-3-small",
        )
        emb.encode("hi")

        headers = mock_post.call_args[1].get("headers", {})
        self.assertEqual(headers.get("Authorization"), "Bearer sk-test-key")

    @patch("httpx.post")
    def test_api_embedder_dim_autodetect(self, mock_post):
        from garden_graph.memory.embedder import APIEmbedder

        mock_response = MagicMock()
        mock_response.json.return_value = self._make_api_response(["probe"], dim=1024)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        emb = APIEmbedder(base_url="http://localhost:1234", model="big-model")
        # dim not set, should auto-detect on first call
        self.assertEqual(emb.dim, 1024)

    def test_embedder_backend_selection_local(self):
        """Default backend should be local."""
        from garden_graph.memory.embedder import Embedder, LocalEmbedder
        with patch.dict("os.environ", {"EMBEDDING_BACKEND": "local"}, clear=False):
            emb = Embedder()
            self.assertIsInstance(emb._backend, LocalEmbedder)

    def test_embedder_backend_selection_lmstudio(self):
        from garden_graph.memory.embedder import Embedder, APIEmbedder
        env = {
            "EMBEDDING_BACKEND": "lmstudio",
            "EMBEDDING_API_URL": "http://100.64.0.1:1234",
        }
        with patch.dict("os.environ", env, clear=False):
            emb = Embedder()
            self.assertIsInstance(emb._backend, APIEmbedder)
            self.assertIn("100.64.0.1", emb._backend._base_url)

    def test_embedder_backend_selection_openai(self):
        from garden_graph.memory.embedder import Embedder, APIEmbedder
        env = {
            "EMBEDDING_BACKEND": "openai",
            "EMBEDDING_API_KEY": "sk-test",
        }
        with patch.dict("os.environ", env, clear=False):
            emb = Embedder()
            self.assertIsInstance(emb._backend, APIEmbedder)
            self.assertIn("openai.com", emb._backend._base_url)


if __name__ == "__main__":
    unittest.main()
