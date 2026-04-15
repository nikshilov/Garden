"""Tests for Phase 6: Soil — Sense of Place (Garden World)."""
import os
import json
import tempfile
import unittest
from datetime import datetime, timezone

from garden_graph.garden_world import (
    GardenWorld, GardenState, CharacterPresence, Artifact,
    LOCATIONS, ARTIFACT_TYPES,
    _season_from_month, _time_of_day_from_hour, _pick_weather, _pick_ambiance,
)


class TestSeasonAndTime(unittest.TestCase):
    """Test calendar-derived season and time-of-day logic."""

    def test_winter_months(self):
        for m in (12, 1, 2):
            self.assertEqual(_season_from_month(m), "winter")

    def test_spring_months(self):
        for m in (3, 4, 5):
            self.assertEqual(_season_from_month(m), "spring")

    def test_summer_months(self):
        for m in (6, 7, 8):
            self.assertEqual(_season_from_month(m), "summer")

    def test_autumn_months(self):
        for m in (9, 10, 11):
            self.assertEqual(_season_from_month(m), "autumn")

    def test_dawn(self):
        self.assertEqual(_time_of_day_from_hour(5), "dawn")
        self.assertEqual(_time_of_day_from_hour(6), "dawn")

    def test_morning(self):
        self.assertEqual(_time_of_day_from_hour(7), "morning")
        self.assertEqual(_time_of_day_from_hour(11), "morning")

    def test_afternoon(self):
        self.assertEqual(_time_of_day_from_hour(12), "afternoon")
        self.assertEqual(_time_of_day_from_hour(16), "afternoon")

    def test_evening(self):
        self.assertEqual(_time_of_day_from_hour(17), "evening")
        self.assertEqual(_time_of_day_from_hour(19), "evening")

    def test_night(self):
        self.assertEqual(_time_of_day_from_hour(20), "night")
        self.assertEqual(_time_of_day_from_hour(22), "night")

    def test_late_night(self):
        self.assertEqual(_time_of_day_from_hour(23), "late_night")
        self.assertEqual(_time_of_day_from_hour(0), "late_night")
        self.assertEqual(_time_of_day_from_hour(3), "late_night")


class TestWeatherAndAmbiance(unittest.TestCase):
    """Test weather and ambiance generation."""

    def test_pick_weather_returns_valid(self):
        for season in ("spring", "summer", "autumn", "winter"):
            weather = _pick_weather(season)
            self.assertIsInstance(weather, str)
            self.assertTrue(len(weather) > 0)

    def test_pick_ambiance_returns_string(self):
        for season in ("spring", "summer", "autumn", "winter"):
            for tod in ("dawn", "morning", "afternoon", "evening", "night", "late_night"):
                ambiance = _pick_ambiance(season, tod)
                self.assertIsInstance(ambiance, str)
                self.assertTrue(len(ambiance) > 10)


class TestGardenWorld(unittest.TestCase):
    """Test the GardenWorld manager."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gw = GardenWorld(data_dir=self.tmpdir)

    def test_update_creates_state(self):
        now = datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc)
        state = self.gw.update(now)
        self.assertEqual(state.season, "summer")
        self.assertEqual(state.time_of_day, "morning")
        self.assertIn(state.weather, ["clear", "cloudy", "rainy", "stormy"])

    def test_get_state_lazy_init(self):
        state = self.gw.get_state()
        self.assertIsNotNone(state)
        self.assertIsInstance(state, GardenState)

    def test_presence_defaults(self):
        presence = self.gw.get_presence("eve")
        self.assertEqual(presence.char_id, "eve")
        self.assertEqual(presence.location, "rose_garden")
        self.assertIn(presence.activity, ["tending roses"])

    def test_presence_unknown_character(self):
        presence = self.gw.get_presence("unknown_char")
        self.assertEqual(presence.char_id, "unknown_char")
        self.assertEqual(presence.location, "oak_tree")  # default fallback

    def test_all_presences(self):
        presences = self.gw.get_all_presences()
        char_ids = {p.char_id for p in presences}
        self.assertIn("eve", char_ids)
        self.assertIn("atlas", char_ids)
        self.assertIn("adam", char_ids)
        self.assertIn("lilith", char_ids)
        self.assertIn("sophia", char_ids)

    def test_energy_tracks_time(self):
        # Morning should have higher energy than late night
        # Use separate GardenWorld instances to avoid drift affecting results
        gw_morning = GardenWorld(data_dir=tempfile.mkdtemp())
        morning = datetime(2026, 6, 15, 9, 0, 0, tzinfo=timezone.utc)
        gw_morning.update(morning)
        # get_presence syncs energy with current time_of_day
        presence_morning = gw_morning.get_presence("eve")

        gw_night = GardenWorld(data_dir=tempfile.mkdtemp())
        late_night = datetime(2026, 6, 15, 2, 0, 0, tzinfo=timezone.utc)
        gw_night.update(late_night)
        presence_night = gw_night.get_presence("eve")

        self.assertGreater(presence_morning.energy, presence_night.energy)

    def test_persistence_round_trip(self):
        now = datetime(2026, 3, 20, 14, 0, 0, tzinfo=timezone.utc)
        self.gw.update(now)

        # Create a new instance from the same data dir
        gw2 = GardenWorld(data_dir=self.tmpdir)
        state2 = gw2.get_state()
        self.assertEqual(state2.season, "spring")
        self.assertEqual(state2.time_of_day, "afternoon")


class TestArtifacts(unittest.TestCase):
    """Test artifact creation and retrieval."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gw = GardenWorld(data_dir=self.tmpdir)

    def test_add_and_get_artifact(self):
        art = self.gw.add_artifact("eve", "poem", "Morning Song", "The roses wake...")
        self.assertEqual(art.creator_id, "eve")
        self.assertEqual(art.artifact_type, "poem")
        self.assertTrue(art.id.startswith("art_"))

        retrieved = self.gw.get_artifacts()
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0].title, "Morning Song")

    def test_filter_by_creator(self):
        self.gw.add_artifact("eve", "poem", "Song", "words")
        self.gw.add_artifact("atlas", "theory", "Theorem", "proof")

        eve_arts = self.gw.get_artifacts(creator_id="eve")
        self.assertEqual(len(eve_arts), 1)
        self.assertEqual(eve_arts[0].creator_id, "eve")

    def test_artifact_persistence(self):
        self.gw.add_artifact("lilith", "sketch", "Midnight", "dark lines")

        gw2 = GardenWorld(data_dir=self.tmpdir)
        arts = gw2.get_artifacts()
        self.assertEqual(len(arts), 1)
        self.assertEqual(arts[0].title, "Midnight")

    def test_newest_first(self):
        self.gw.add_artifact("eve", "poem", "First", "a")
        self.gw.add_artifact("eve", "poem", "Second", "b")
        self.gw.add_artifact("eve", "poem", "Third", "c")

        arts = self.gw.get_artifacts()
        self.assertEqual(arts[0].title, "Third")
        self.assertEqual(arts[2].title, "First")


class TestPromptHelpers(unittest.TestCase):
    """Test world_context and character_context prompt generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gw = GardenWorld(data_dir=self.tmpdir)
        self.gw.update(datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc))

    def test_world_context_contains_key_info(self):
        ctx = self.gw.world_context()
        self.assertIn("THE GARDEN RIGHT NOW:", ctx)
        self.assertIn("winter", ctx)

    def test_character_context_contains_location(self):
        # Use a fresh instance to avoid drift from update()
        gw = GardenWorld(data_dir=tempfile.mkdtemp())
        ctx = gw.character_context("eve")
        self.assertIn("rose garden", ctx)

    def test_character_context_contains_energy(self):
        ctx = self.gw.character_context("atlas")
        # Morning at 10am should be alert
        self.assertIn("alert", ctx.lower())

    def test_world_context_lists_all_characters(self):
        ctx = self.gw.world_context()
        self.assertIn("Eve", ctx)
        self.assertIn("Atlas", ctx)


class TestDataclassSerialization(unittest.TestCase):
    """Test to_dict / from_dict round trips."""

    def test_garden_state_round_trip(self):
        state = GardenState(
            season="autumn", time_of_day="evening", weather="rainy",
            ambiance="Rain falls softly.", last_updated="2026-01-01T00:00:00+00:00",
        )
        d = state.to_dict()
        restored = GardenState.from_dict(d)
        self.assertEqual(restored.season, "autumn")
        self.assertEqual(restored.weather, "rainy")

    def test_character_presence_round_trip(self):
        p = CharacterPresence(char_id="eve", location="stream", activity="meditating", energy=0.6)
        d = p.to_dict()
        restored = CharacterPresence.from_dict(d)
        self.assertEqual(restored.char_id, "eve")
        self.assertEqual(restored.energy, 0.6)

    def test_artifact_round_trip(self):
        a = Artifact(
            id="art_abc123", creator_id="atlas", artifact_type="theory",
            title="On Roots", content="Roots grow down before branches grow up.",
            created_at="2026-01-01T00:00:00+00:00",
        )
        d = a.to_dict()
        restored = Artifact.from_dict(d)
        self.assertEqual(restored.title, "On Roots")
        self.assertEqual(restored.creator_id, "atlas")


if __name__ == "__main__":
    unittest.main()
