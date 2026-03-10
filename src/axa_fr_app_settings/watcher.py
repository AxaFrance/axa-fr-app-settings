"""
File-watching support for automatic configuration reload.

Requires the ``watchdog`` package::

    uv add axa-fr-app-settings[watch]
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

try:
    from watchdog.events import FileModifiedEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    _HAS_WATCHDOG = True
except ImportError:  # pragma: no cover
    FileModifiedEvent = None  # type: ignore[assignment,misc]
    FileSystemEventHandler = object  # type: ignore[assignment,misc]
    Observer = None  # type: ignore[assignment,misc]
    _HAS_WATCHDOG = False

TSettings = TypeVar("TSettings", bound=BaseModel)


def _require_watchdog() -> None:
    if not _HAS_WATCHDOG:
        raise ImportError(
            "watchdog is required for reload support. "
            "Install it with: uv add axa-fr-app-settings[watch]"
        )


class _ReloadHandler(FileSystemEventHandler):  # type: ignore[misc]
    """watchdog handler that triggers a debounced rebuild."""

    def __init__(
        self,
        watched_files: set[str],
        on_trigger: Callable[[], None],
        debounce_seconds: float,
    ) -> None:
        super().__init__()
        self._watched_files = watched_files
        self._on_trigger = on_trigger
        self._debounce_seconds = debounce_seconds
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def on_modified(self, event: FileModifiedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        src = str(Path(event.src_path).resolve())
        if src not in self._watched_files:
            return
        self._schedule_reload()

    def _schedule_reload(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_seconds, self._on_trigger)
            self._timer.daemon = True
            self._timer.start()


class SettingsWatcher(Generic[TSettings]):
    """
    Holds a live reference to the latest settings and notifies subscribers
    whenever a watched file changes on disk.

    Usage::

        watcher = (
            ConfigurationBuilder(MySettings)
            .add_yaml_file("settings.yaml", reload_on_change=True)
            .add_environment_variables()
            .build_watched()
        )

        watcher.on_change(lambda s: print("reloaded!", s))
        watcher.start()

        # watcher.settings always returns the latest version
        print(watcher.settings.debug)

        # stop watching when done
        watcher.stop()

    It can also be used as a context-manager::

        with watcher:
            ...
    """

    def __init__(
        self,
        build_fn: Callable[[], TSettings],
        watched_paths: set[str],
        *,
        debounce_seconds: float = 0.3,
        polling_interval_seconds: float | None = None,
    ) -> None:
        _require_watchdog()
        self._build_fn = build_fn
        self._watched_paths = watched_paths
        self._debounce_seconds = debounce_seconds
        self._polling_interval = polling_interval_seconds
        self._callbacks: list[Callable[[TSettings], Any]] = []
        self._lock = threading.Lock()
        self._settings: TSettings = build_fn()
        self._observer: Observer | None = None  # type: ignore[assignment]
        self._polling_timer: threading.Timer | None = None
        self._stopped = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def settings(self) -> TSettings:
        """Return the latest settings snapshot (thread-safe)."""
        with self._lock:
            return self._settings

    def on_change(self, callback: Callable[[TSettings], Any]) -> None:
        """Register a callback invoked after each successful reload."""
        self._callbacks.append(callback)

    def start(self) -> None:
        """Start watching files for changes and/or polling for custom sources."""
        _require_watchdog()
        self._stopped.clear()

        # --- File-watching (watchdog) ---
        if self._observer is None and self._watched_paths:
            dirs_to_watch: set[str] = set()
            for p in self._watched_paths:
                parent = str(Path(p).resolve().parent)
                dirs_to_watch.add(parent)

            resolved = {str(Path(p).resolve()) for p in self._watched_paths}

            handler = _ReloadHandler(
                watched_files=resolved,
                on_trigger=self._reload,
                debounce_seconds=self._debounce_seconds,
            )

            self._observer = Observer()  # type: ignore[assignment]
            for directory in dirs_to_watch:
                self._observer.schedule(handler, directory, recursive=False)  # type: ignore[union-attr]
            self._observer.start()  # type: ignore[union-attr]

        # --- Periodic polling (for custom sources like Key Vault) ---
        if self._polling_interval is not None and self._polling_interval > 0:
            self._schedule_poll()

    def stop(self) -> None:
        """Stop watching files and polling."""
        self._stopped.set()

        if self._polling_timer is not None:
            self._polling_timer.cancel()
            self._polling_timer = None

        if self._observer is not None:
            self._observer.stop()  # type: ignore[union-attr]
            self._observer.join()  # type: ignore[union-attr]
            self._observer = None

    # Context-manager support ------------------------------------------

    def __enter__(self) -> SettingsWatcher[TSettings]:
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _schedule_poll(self) -> None:
        if self._stopped.is_set():
            return
        self._polling_timer = threading.Timer(
            self._polling_interval,  # type: ignore[arg-type]
            self._poll,
        )
        self._polling_timer.daemon = True
        self._polling_timer.start()

    def _poll(self) -> None:
        self._reload()
        self._schedule_poll()

    def _reload(self) -> None:
        try:
            new_settings = self._build_fn()
        except Exception:
            # If the file is in an intermediate state, skip the reload
            return

        with self._lock:
            self._settings = new_settings

        for cb in self._callbacks:
            with contextlib.suppress(Exception):
                cb(new_settings)

