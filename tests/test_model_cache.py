"""F26: real models load once per process, one load at a time."""

import threading
import time
import unittest

from src.vision import model_cache


class ModelCacheTests(unittest.TestCase):
    def setUp(self):
        model_cache.clear()

    def tearDown(self):
        model_cache.clear()

    def test_concurrent_callers_share_one_load(self):
        calls = []

        def slow_loader():
            calls.append(1)
            time.sleep(0.05)
            return object()

        results = []
        threads = [
            threading.Thread(target=lambda: results.append(model_cache.load_once("k", slow_loader)))
            for _ in range(5)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(calls), 1)
        self.assertEqual(len({id(r) for r in results}), 1)

    def test_meta_tensor_error_is_retried_once(self):
        attempts = []

        def flaky():
            attempts.append(1)
            if len(attempts) == 1:
                raise NotImplementedError("Cannot copy out of meta tensor; no data!")
            return "model"

        self.assertEqual(model_cache.load_once("k", flaky), "model")
        self.assertEqual(len(attempts), 2)

    def test_other_errors_raise_and_are_not_cached(self):
        def broken():
            raise OSError("weights missing")

        with self.assertRaises(OSError):
            model_cache.load_once("k", broken)
        self.assertEqual(model_cache.load_once("k", lambda: "fixed"), "fixed")

    def test_different_keys_load_separately(self):
        self.assertEqual(model_cache.load_once("a", lambda: 1), 1)
        self.assertEqual(model_cache.load_once("b", lambda: 2), 2)


if __name__ == "__main__":
    unittest.main()
