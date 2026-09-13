"""
watcher.py — Background folder watching daemon for sort_OCD.

Usage:
    sort-ocd watch ~/Downloads         Start watching
    sort-ocd watch --stop              Stop daemon

Design:
- Uses watchdog (pure Python, cross-platform)
- 3-second cooldown after last file event before sorting (avoids sorting mid-download)
- PID stored at ~/.sort_ocd_watch.pid for reliable start/stop
- All auto-moves logged to SQLite via database module
- Runs in foreground with clean Ctrl+C handling (or background via & in shell)
"""

import os
import sys
import time
import signal
import threading
from typing import Optional

PID_FILE = os.path.expanduser("~/.sort_ocd_watch.pid")


def _write_pid() -> None:
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def _clear_pid() -> None:
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass


def get_running_pid() -> Optional[int]:
    """Return the PID of the running watcher, or None if not running."""
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        # Verify the process is actually alive
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        _clear_pid()
        return None


def stop_watcher() -> bool:
    """
    Send SIGTERM to the running watcher process.
    Returns True if successfully stopped, False if no watcher was running.
    """
    pid = get_running_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        # Wait briefly for process to clean up
        for _ in range(10):
            time.sleep(0.3)
            if get_running_pid() is None:
                return True
        return True  # Assume stopped even if PID lingers
    except ProcessLookupError:
        _clear_pid()
        return True
    except PermissionError:
        return False


class _SortHandler:
    """
    Watches a folder and auto-sorts files after a cooldown period.
    Thread-safe: uses a timer that resets on rapid file events.
    """

    def __init__(
        self,
        target_folder: str,
        sort_mode: str,
        cooldown: float,
        console,
    ):
        self.target_folder = target_folder
        self.sort_mode = sort_mode
        self.cooldown = cooldown
        self.console = console
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def on_file_event(self, event_path: str) -> None:
        """Called when a file event fires. Resets cooldown timer."""
        # Ignore hidden files and system files
        fname = os.path.basename(event_path)
        if fname.startswith(".") or fname.lower() in {"thumbs.db", "desktop.ini"}:
            return
        # Ignore if it's already in a subfolder we created
        rel = os.path.relpath(event_path, self.target_folder)
        if os.sep in rel:
            return

        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.cooldown, self._do_sort)
            self._timer.daemon = True
            self._timer.start()

    def _do_sort(self) -> None:
        """Execute the sort after cooldown expires."""
        from . import sorter, database

        files = sorter.scan_files(self.target_folder)
        if not files:
            return

        self.console.print(
            f"\n  [cyan]⚡ Watcher:[/cyan] Found {len(files)} file(s) — auto-sorting ({self.sort_mode})…"
        )

        session_id = database.create_session(
            self.target_folder, self.sort_mode, source="watcher"
        )
        plan = sorter.build_plan_manual(self.target_folder, files, self.sort_mode)
        moved = sorter.execute_plan(self.target_folder, plan, session_id, database)
        database.close_session(session_id, moved)

        self.console.print(
            f"  [bright_green]✓[/bright_green] Auto-sorted [cyan]{moved}[/cyan] file(s)."
        )


def start_watcher(
    target_folder: str,
    sort_mode: str = "ext",
    cooldown: float = 3.0,
) -> None:
    """
    Start watching target_folder in the foreground.
    Ctrl+C or SIGTERM will stop cleanly.
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print(
            "Error: 'watchdog' is required for folder watching.\n"
            "Install it with: pip install watchdog"
        )
        sys.exit(1)

    try:
        from rich.console import Console
        console = Console()
    except ImportError:
        class _FallbackConsole:
            def print(self, msg, *a, **k):
                import re
                print(re.sub(r"\[/?[^\]]+\]", "", str(msg)))
        console = _FallbackConsole()

    if not os.path.isdir(target_folder):
        console.print(f"  [bold red]✗  Folder not found: {target_folder}[/bold red]")
        sys.exit(1)

    existing = get_running_pid()
    if existing:
        console.print(
            f"  [yellow]⚠  A watcher is already running (PID {existing}).[/yellow]\n"
            f"  Stop it first with: [cyan]sort-ocd watch --stop[/cyan]"
        )
        sys.exit(1)

    handler_state = _SortHandler(target_folder, sort_mode, cooldown, console)

    class _WatchdogBridge(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory:
                handler_state.on_file_event(event.src_path)

        def on_moved(self, event):
            if not event.is_directory:
                handler_state.on_file_event(event.dest_path)

    observer = Observer()
    observer.schedule(_WatchdogBridge(), target_folder, recursive=False)

    _write_pid()

    def _shutdown(signum=None, frame=None):
        observer.stop()
        _clear_pid()
        console.print("\n  [dim]Watcher stopped.[/dim]")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)

    console.print(
        f"  [bold bright_cyan]⚡ Watching:[/bold bright_cyan] {target_folder}\n"
        f"  Mode: [cyan]{sort_mode}[/cyan]  |  Cooldown: [cyan]{cooldown}s[/cyan]\n"
        f"  Press [dim]Ctrl+C[/dim] or run [dim]sort-ocd watch --stop[/dim] to exit.\n"
    )

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown()
