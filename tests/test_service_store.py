"""Unit tests for service/store.py (SQLite run history). IDs: UT-S-xx.

Each test gets its own temporary database file, so tests never share state.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from service.store import INSERT_COLUMNS, RunStore


def make_run(**overrides):
    run = {
        "created_at": "2026-11-10T10:00:00.000+00:00",
        "filename": "field.png",
        "image_sha256": "a" * 64,
        "width": 640,
        "height": 480,
        "crop": "cotton",
        "mode": "mock",
        "min_confidence": 0.70,
        "safety_action": "ACCEPT",
        "spray_allowed": 1,
        "status": "Selective Spot-Spray Prescription Generated (3 weed patch(es))",
        "weed_count": 3,
        "withheld_count": 0,
        "infestation_pct": 9.43,
        "savings_pct": 84.88,
        "sprayed_px": 100,
        "crop_px": 50,
        "unsure_px": 10,
        "system2_needed": 0,
        "duration_ms": 6.0,
        "geojson": '{"type": "FeatureCollection", "features": []}',
        "overlay_jpeg": b"\xff\xd8\xff\xe0fake",
    }
    run.update(overrides)
    return run


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "nested" / "runs.db"
        self.store = RunStore(self.path)
        self.store.init()

    def tearDown(self):
        self._tmp.cleanup()


class InitTests(StoreTestCase):
    def test_init_creates_folder_file_and_table(self):  # UT-S-01
        self.assertTrue(self.path.exists())
        with sqlite3.connect(self.path) as conn:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("runs", tables)

    def test_init_twice_keeps_data(self):  # UT-S-02 (idempotent)
        self.store.add(make_run())
        self.store.init()
        self.assertEqual(self.store.count(), 1)

    def test_wal_mode_is_on(self):  # UT-S-03
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")

    def test_ping(self):  # UT-S-04
        self.assertTrue(self.store.ping())
        self.assertFalse(RunStore(Path(self._tmp.name)).ping())  # a folder is not a database


class AddGetTests(StoreTestCase):
    def test_add_returns_increasing_ids_and_get_reads_back(self):  # UT-S-05
        first = self.store.add(make_run())
        second = self.store.add(make_run(filename="b.png"))
        self.assertEqual((first, second), (1, 2))
        run = self.store.get(second)
        self.assertEqual(run["filename"], "b.png")
        self.assertIs(run["spray_allowed"], True)  # stored as 0/1, returned as bool
        self.assertIs(run["system2_needed"], False)

    def test_summary_leaves_out_large_columns(self):  # UT-S-06
        run = self.store.get(self.store.add(make_run()))
        self.assertNotIn("overlay_jpeg", run)
        self.assertNotIn("geojson", run)

    def test_get_missing_id(self):  # UT-S-07
        self.assertIsNone(self.store.get(999))

    def test_add_with_missing_field_raises(self):  # UT-S-08
        run = make_run()
        del run["crop"]
        with self.assertRaises(KeyError):
            self.store.add(run)
        self.assertEqual(len(INSERT_COLUMNS), 22)

    def test_text_is_stored_verbatim(self):  # UT-S-09 (parameterised SQL, no injection)
        name = "x'); DROP TABLE runs; --<script>.png"
        run_id = self.store.add(make_run(filename=name))
        self.assertEqual(self.store.get(run_id)["filename"], name)
        self.assertEqual(self.store.count(), 1)


class ConstraintTests(StoreTestCase):
    """The database refuses bad rows even if a caller skips validation (defence in depth)."""

    def test_check_constraints(self):  # UT-S-10
        bad_rows = {
            "min_confidence below 0.70": {"min_confidence": 0.69},
            "min_confidence above 1.00": {"min_confidence": 1.01},
            "unknown mode": {"mode": "fast"},
            "infestation over 100": {"infestation_pct": 100.5},
            "negative savings": {"savings_pct": -1},
            "negative weed count": {"weed_count": -1},
            "spray_allowed not 0/1": {"spray_allowed": 2},
            "short hash": {"image_sha256": "abc"},
            "zero width": {"width": 0},
            "negative duration": {"duration_ms": -0.1},
        }
        for label, override in bad_rows.items():
            with self.subTest(label):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.store.add(make_run(**override))
        self.assertEqual(self.store.count(), 0)

    def test_boundary_values_are_accepted(self):  # UT-S-11
        self.store.add(make_run(min_confidence=0.70, infestation_pct=0, savings_pct=100))
        self.store.add(make_run(min_confidence=1.00, infestation_pct=100, savings_pct=0))
        self.assertEqual(self.store.count(), 2)


class ListTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.ids = [
            self.store.add(make_run(created_at="2026-11-10T10:00:00.000+00:00", crop="cotton")),
            self.store.add(make_run(created_at="2026-11-10T11:00:00.000+00:00", crop="wheat")),
            self.store.add(make_run(created_at="2026-11-10T11:00:00.000+00:00", crop="cotton")),
            self.store.add(make_run(created_at="2026-11-10T09:00:00.000+00:00", crop="rice")),
        ]

    def test_newest_first_with_id_as_tie_break(self):  # UT-S-12
        self.assertEqual([r["id"] for r in self.store.list()], [3, 2, 1, 4])

    def test_limit_and_offset(self):  # UT-S-13
        self.assertEqual([r["id"] for r in self.store.list(limit=2)], [3, 2])
        self.assertEqual([r["id"] for r in self.store.list(limit=2, offset=2)], [1, 4])
        self.assertEqual(self.store.list(limit=2, offset=4), [])

    def test_crop_filter_and_count(self):  # UT-S-14
        self.assertEqual([r["id"] for r in self.store.list(crop="cotton")], [3, 1])
        self.assertEqual(self.store.count("cotton"), 2)
        self.assertEqual(self.store.count("sugar beet"), 0)
        self.assertEqual(self.store.count(), 4)


class BlobAndDeleteTests(StoreTestCase):
    def test_overlay_and_geojson(self):  # UT-S-15
        run_id = self.store.add(make_run())
        self.assertTrue(self.store.overlay(run_id).startswith(b"\xff\xd8"))
        self.assertIn("FeatureCollection", self.store.geojson(run_id))
        self.assertIsNone(self.store.overlay(42))
        self.assertIsNone(self.store.geojson(42))

    def test_delete_once(self):  # UT-S-16
        run_id = self.store.add(make_run())
        self.assertTrue(self.store.delete(run_id))
        self.assertFalse(self.store.delete(run_id))
        self.assertIsNone(self.store.get(run_id))


class StatsTests(StoreTestCase):
    def test_empty_database(self):  # UT-S-17
        s = self.store.stats()
        self.assertEqual(
            {k: s[k] for k in ("total_runs", "total_weeds", "avg_infestation_pct", "suppressed_runs")},
            {"total_runs": 0, "total_weeds": 0, "avg_infestation_pct": 0, "suppressed_runs": 0},
        )
        self.assertEqual((s["by_crop"], s["by_safety_action"]), ([], []))

    def test_totals_and_breakdowns(self):  # UT-S-18
        self.store.add(make_run(crop="cotton", weed_count=3, infestation_pct=10.0, savings_pct=80.0))
        self.store.add(make_run(crop="cotton", weed_count=1, infestation_pct=20.0, savings_pct=60.0))
        self.store.add(make_run(crop="wheat", weed_count=0, infestation_pct=60.0, savings_pct=0.0,
                                spray_allowed=0, safety_action="SUPPRESS_SPRAY", withheld_count=2))
        s = self.store.stats()
        self.assertEqual(s["total_runs"], 3)
        self.assertEqual(s["total_weeds"], 4)
        self.assertEqual(s["total_withheld"], 2)
        self.assertEqual(s["avg_infestation_pct"], 30.0)
        self.assertAlmostEqual(s["avg_savings_pct"], 46.67)
        self.assertEqual(s["suppressed_runs"], 1)
        self.assertEqual(s["by_crop"][0], {"crop": "cotton", "runs": 2, "weeds": 4, "avg_infestation_pct": 15.0})
        self.assertEqual(
            s["by_safety_action"],
            [{"safety_action": "ACCEPT", "runs": 2}, {"safety_action": "SUPPRESS_SPRAY", "runs": 1}],
        )


if __name__ == "__main__":
    unittest.main()
