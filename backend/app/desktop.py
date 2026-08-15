"""Windows desktop entry point for the self-contained TrendScope distribution."""

from __future__ import annotations

import os
import socket
import shutil
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


APPLICATION_NAME = "TrendScope"


def resource_directory() -> Path:
    """Locate files bundled by PyInstaller without relying on the install path."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def runtime_directory() -> Path:
    """Keep mutable user data outside the program directory and future upgrades."""
    local_app_data = os.getenv("LOCALAPPDATA")
    base_directory = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base_directory / APPLICATION_NAME


def configure_runtime() -> tuple[Path, Path]:
    resources = resource_directory()
    runtime = runtime_directory()
    data_directory = runtime / "data"
    reports_directory = runtime / "reports"

    os.environ["TRENDSCOPE_DATA_DIR"] = str(data_directory)
    os.environ["TRENDSCOPE_REPORTS_DIR"] = str(reports_directory)
    os.environ["TRENDSCOPE_DATABASE_PATH"] = str(data_directory / "app.db")
    os.environ["TRENDSCOPE_FRONTEND_DIR"] = str(resources / "frontend")
    # The bundled Chromium is used only by the normal, isolated Playwright adapter.
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(resources / "playwright-browsers")
    return resources, runtime


def copy_initial_state(resources: Path) -> None:
    """Seed a new user's writable directory from the safely prepared release data."""
    source = resources / "initial-state"
    destination = runtime_directory()
    if not source.is_dir():
        return
    for name in ("data", "reports"):
        source_directory = source / name
        destination_directory = destination / name
        if source_directory.is_dir() and not destination_directory.exists():
            shutil.copytree(source_directory, destination_directory)
        elif name == "data" and source_directory.is_dir() and not (destination_directory / "app.db").is_file():
            # A previous interrupted first launch may have created an empty data directory.
            shutil.copytree(source_directory, destination_directory, dirs_exist_ok=True)
    for directory in (destination / "data", destination / "reports", destination / "logs"):
        directory.mkdir(parents=True, exist_ok=True)


def run_migrations(resources: Path) -> None:
    from alembic import command
    from alembic.config import Config

    # Do not load alembic.ini here: it only contains development console logging
    # configuration, which is unnecessary in the windowed PyInstaller process.
    config = Config()
    config.set_main_option("script_location", str(resources / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{Path(os.environ['TRENDSCOPE_DATABASE_PATH']).as_posix()}")
    command.upgrade(config, "head")


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_for_server(url: str, timeout_seconds: int = 20) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1) as response:
                if response.status == 200:
                    return True
        except OSError:
            time.sleep(0.2)
    return False


def show_error(message: str) -> None:
    error_log = runtime_directory() / "logs" / "startup-error.txt"
    error_log.parent.mkdir(parents=True, exist_ok=True)
    error_log.write_text(message, encoding="utf-8")
    import tkinter.messagebox

    tkinter.messagebox.showerror(APPLICATION_NAME, message)


def launch_window(application_url: str) -> None:
    import tkinter as tk
    from tkinter import ttk

    window = tk.Tk()
    window.title(APPLICATION_NAME)
    window.resizable(False, False)
    frame = ttk.Frame(window, padding=24)
    frame.grid()
    ttk.Label(frame, text="TrendScope 正在运行", font=("Microsoft YaHei UI", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 10))
    ttk.Label(frame, text="关闭此窗口即可安全停止本地服务。", wraplength=300).grid(row=1, column=0, columnspan=2, pady=(0, 16))
    ttk.Button(frame, text="打开 TrendScope", command=lambda: webbrowser.open(application_url)).grid(row=2, column=0, padx=(0, 8))
    ttk.Button(frame, text="退出", command=lambda: close_window()).grid(row=2, column=1)

    def close_window() -> None:
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", close_window)
    window.mainloop()


def main() -> None:
    try:
        resources, _ = configure_runtime()
        copy_initial_state(resources)
        run_migrations(resources)

        import uvicorn
        from app.main import app

        port = available_port()
        application_url = f"http://127.0.0.1:{port}"
        # The windowed build has no console. Avoid Uvicorn's console formatter,
        # which also relies on a dynamically loaded module in frozen builds.
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info", log_config=None)
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        if not wait_for_server(application_url):
            server.should_exit = True
            raise RuntimeError("本地服务未能在 20 秒内启动，请查看日志后重试。")

        webbrowser.open(application_url)
        launch_window(application_url)
        server.should_exit = True
        thread.join(timeout=10)
    except Exception as exc:  # pragma: no cover - exercised by the packaged executable
        show_error(f"TrendScope 无法启动：{exc}")


if __name__ == "__main__":
    main()
