"""Tests for CostTracker - P3 requirements verification."""
import os
import tempfile
import pytest
from garden_graph.cost_tracker import CostTracker, CostRecord, DEFAULT_PRICING


class TestCostRecord:
    """Tests for individual cost records."""

    def test_create_record(self):
        """Test creating a cost record calculates USD correctly."""
        record = CostRecord(
            model_id="gpt-4o",
            prompt_tokens=1000,
            completion_tokens=500,
            message_id="msg_123",
            category="general"
        )

        # Verify pricing calculation
        pricing = DEFAULT_PRICING["gpt-4o"]
        expected_usd = (1000 / 1000) * pricing["prompt"] + (500 / 1000) * pricing["completion"]

        assert record.prompt_tokens == 1000
        assert record.completion_tokens == 500
        assert record.model_id == "gpt-4o"
        assert record.message_id == "msg_123"
        assert abs(record.usd - expected_usd) < 0.0001

    def test_record_to_dict(self):
        """Test serialization to dictionary."""
        record = CostRecord(
            model_id="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            category="router"
        )

        d = record.to_dict()
        assert "id" in d
        assert d["model_id"] == "gpt-4o"
        assert d["prompt_tokens"] == 100
        assert d["completion_tokens"] == 50
        assert d["category"] == "router"
        assert "created_at" in d
        assert "usd" in d


class TestCostTracker:
    """Tests for CostTracker functionality."""

    def test_record_and_total(self):
        """Test recording calls and getting total."""
        tracker = CostTracker()

        # Record several calls
        tracker.record("gpt-4o", 1000, 500, "msg_1")
        tracker.record("gpt-4o", 2000, 1000, "msg_2")

        total = tracker.get_total_usd()
        assert total > 0
        assert len(tracker.records) == 2

    def test_model_breakdown(self):
        """Test breakdown by model."""
        tracker = CostTracker()

        tracker.record("gpt-4o", 1000, 500, "msg_1")
        tracker.record("gpt-3.5-turbo", 1000, 500, "msg_2")
        tracker.record("gpt-4o", 500, 250, "msg_3")

        breakdown = tracker.get_model_breakdown()
        assert "gpt-4o" in breakdown
        assert "gpt-3.5-turbo" in breakdown
        assert len(breakdown) == 2

    def test_category_breakdown(self):
        """Test breakdown by category."""
        tracker = CostTracker()

        tracker.record("gpt-4o", 1000, 500, "msg_1", category="router")
        tracker.record("gpt-4o", 1000, 500, "msg_2", category="character")
        tracker.record("gpt-4o", 1000, 500, "msg_3", category="character")

        breakdown = tracker.get_category_breakdown()
        assert "router" in breakdown
        assert "character" in breakdown
        # Character should be roughly 2x router
        assert breakdown["character"] > breakdown["router"]

    def test_budget_alert(self, capsys):
        """Test budget alert fires when limit exceeded."""
        tracker = CostTracker()
        tracker.set_budget_limit(0.001)  # Very low limit

        # Record a call that should exceed the budget
        tracker.record("gpt-4o", 10000, 5000, "msg_1")

        # Check that warning was printed
        captured = capsys.readouterr()
        assert "WARNING" in captured.out or tracker.session_usd > tracker.budget_limit

    def test_csv_export(self):
        """Test CSV export functionality."""
        tracker = CostTracker()

        # Record several calls
        tracker.record("gpt-4o", 1000, 500, "msg_1", "router")
        tracker.record("gpt-3.5-turbo", 2000, 1000, "msg_2", "character")

        # Export to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name

        try:
            tracker.export_csv(temp_path)

            # Verify file exists and has content
            assert os.path.exists(temp_path)

            with open(temp_path, 'r') as f:
                lines = f.readlines()

            # Header + 2 records
            assert len(lines) == 3

            # Check header
            header = lines[0].strip()
            assert "Model" in header
            assert "USD" in header
            assert "Category" in header

            # Check data rows contain expected info
            assert "gpt-4o" in lines[1]
            assert "gpt-3.5-turbo" in lines[2]
        finally:
            os.unlink(temp_path)

    def test_reset(self):
        """Test reset clears all records."""
        tracker = CostTracker()

        tracker.record("gpt-4o", 1000, 500)
        tracker.record("gpt-4o", 1000, 500)

        assert len(tracker.records) == 2
        assert tracker.session_usd > 0

        tracker.reset()

        assert len(tracker.records) == 0
        assert tracker.session_usd == 0.0

    def test_disabled_tracking(self):
        """Test that disabled tracking returns empty records."""
        tracker = CostTracker()
        tracker.disabled = True

        record = tracker.record("gpt-4o", 1000, 500)

        # Should return empty record
        assert record.prompt_tokens == 0
        assert record.completion_tokens == 0

    def test_unknown_model_pricing(self):
        """Test handling of unknown model with zero pricing."""
        tracker = CostTracker()

        record = tracker.record("unknown-model-xyz", 1000, 500)

        # Should still record but with zero USD
        assert record.prompt_tokens == 1000
        assert record.completion_tokens == 500
        assert record.usd == 0.0
