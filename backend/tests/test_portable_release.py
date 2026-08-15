from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path


def _load_initial_data_preparer():
    script = Path(__file__).resolve().parents[2] / "scripts" / "prepare-initial-data.py"
    specification = importlib.util.spec_from_file_location("prepare_initial_data", script)
    assert specification and specification.loader
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_release_snapshot_removes_model_and_browser_credentials(tmp_path: Path) -> None:
    database_path = tmp_path / "app.db"
    with sqlite3.connect(database_path) as database:
        database.execute("CREATE TABLE ai_provider_configs (id INTEGER PRIMARY KEY, api_key TEXT)")
        database.execute("INSERT INTO ai_provider_configs (api_key) VALUES ('secret-key')")
        database.execute("CREATE TABLE app_settings (id INTEGER PRIMARY KEY, key TEXT, value TEXT)")
        database.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)",
            ("browser_defaults", json.dumps({"mode": "isolated", "headers": {"Cookie": "private"}})),
        )

    _load_initial_data_preparer().clear_sensitive_configuration(database_path)

    with sqlite3.connect(database_path) as database:
        assert database.execute("SELECT COUNT(*) FROM ai_provider_configs").fetchone() == (0,)
        browser_settings = json.loads(database.execute("SELECT value FROM app_settings WHERE key = 'browser_defaults'").fetchone()[0])
        assert browser_settings["mode"] == "isolated"
        assert browser_settings["headers"] == {}
