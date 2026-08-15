"""Create a distributable initial data snapshot without credentials or model settings."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path


def copy_tree_if_present(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination)


def clear_sensitive_configuration(database_path: Path) -> None:
    if not database_path.is_file():
        return
    with sqlite3.connect(database_path) as database:
        # A provider record can disclose the selected model, endpoint, key, and routing policy.
        database.execute("DELETE FROM ai_provider_configs")

        # Browser request headers can contain a Cookie or Authorization value. They are not
        # needed for the initial experience and must never be handed to another user.
        row = database.execute("SELECT id, value FROM app_settings WHERE key = ?", ("browser_defaults",)).fetchone()
        if row is not None:
            try:
                value = json.loads(row[1])
            except (TypeError, json.JSONDecodeError):
                value = {}
            if isinstance(value, dict):
                value["headers"] = {}
                database.execute("UPDATE app_settings SET value = ? WHERE id = ?", (json.dumps(value, ensure_ascii=False), row[0]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    arguments = parser.parse_args()

    source_data = arguments.project_root / "data"
    source_reports = arguments.project_root / "reports"
    destination = arguments.destination
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    copy_tree_if_present(source_data, destination / "data")
    copy_tree_if_present(source_reports, destination / "reports")
    clear_sensitive_configuration(destination / "data" / "app.db")


if __name__ == "__main__":
    main()
