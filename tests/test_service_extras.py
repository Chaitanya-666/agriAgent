"""Coverage-driven tests for the Field Service lines the Lab 4 tests missed (Lab 5). IDs: CT-S-xx.

The first coverage run left: the `python -m service` launcher (0%), the NumPy-to-JSON helper,
the environment-variable settings reader and the "no web folder" branch of create_app.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from fastapi.testclient import TestClient

from service import __main__ as launcher
from service import analysis, config
from service.config import Settings, load_settings
from service.main import create_app


class LauncherTests(unittest.TestCase):
    def test_defaults_and_flags_reach_uvicorn(self):  # CT-S-01
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"AGRIAGENT_DB": str(Path(tmp) / "l.db")}), \
                mock.patch.object(launcher.uvicorn, "run") as run:
            for argv, host, port in ((["service"], "127.0.0.1", 8000),
                                     (["service", "--host", "0.0.0.0", "--port", "9001"], "0.0.0.0", 9001)):
                with self.subTest(argv=argv), mock.patch.object(sys, "argv", argv):
                    launcher.main()
                    kwargs = run.call_args.kwargs
                    self.assertEqual((kwargs["host"], kwargs["port"]), (host, port))
                    self.assertEqual(run.call_args.args[0].title, "AgriAgent Field Service")

    def test_bad_port_is_refused_by_argparse(self):  # CT-S-02
        with mock.patch.object(sys, "argv", ["service", "--port", "eighty"]), \
                mock.patch.object(launcher.uvicorn, "run") as run, \
                mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                launcher.main()
        run.assert_not_called()


class SettingsTests(unittest.TestCase):
    def test_defaults(self):  # CT-S-03
        with mock.patch.dict(os.environ, {}, clear=True):
            s = load_settings()
        self.assertEqual(s.db_path, config.DEFAULT_DB_PATH)
        self.assertFalse(s.allow_real_mode)

    def test_environment_overrides(self):  # CT-S-04
        with mock.patch.dict(os.environ, {"AGRIAGENT_DB": "/tmp/x.db", "AGRIAGENT_ALLOW_REAL": "1"}):
            s = load_settings()
        self.assertEqual((s.db_path, s.allow_real_mode), (Path("/tmp/x.db"), True))

    def test_only_the_exact_value_1_switches_real_mode_on(self):  # CT-S-05
        for value in ("true", "yes", "0", "", " 1"):
            with self.subTest(value=value), mock.patch.dict(os.environ, {"AGRIAGENT_ALLOW_REAL": value}):
                self.assertFalse(load_settings().allow_real_mode)


class JsonDefaultTests(unittest.TestCase):
    def test_numpy_values_become_plain_python(self):  # CT-S-06
        self.assertEqual(analysis._json_default(np.float64(84.88)), 84.88)
        self.assertIsInstance(analysis._json_default(np.int64(3)), int)
        self.assertIs(analysis._json_default(np.bool_(True)), True)
        self.assertEqual(analysis._json_default(np.array([[1, 2], [3, 4]])), [[1, 2], [3, 4]])

    def test_other_objects_are_refused(self):  # CT-S-07
        with self.assertRaises(TypeError):
            analysis._json_default(object())


class NoWebFolderTests(unittest.TestCase):
    def test_api_still_works_without_the_web_page(self):  # CT-S-08
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(config, "WEB_DIR", Path(tmp) / "missing"):
            client = TestClient(create_app(Settings(db_path=Path(tmp) / "w.db")))
            self.assertEqual(client.get("/api/health").status_code, 200)
            r = client.get("/")
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (404, "not_found"))
            client.close()


if __name__ == "__main__":
    unittest.main()
