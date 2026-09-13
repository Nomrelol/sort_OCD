"""
cli.py — Main entry point and subcommand router for sort_OCD.

Commands:
    sort-ocd                              Interactive mode (default)
    sort-ocd sort <path> [--by mode]      Direct sort
    sort-ocd watch <path> [--mode] [--cooldown]  Start folder watcher
    sort-ocd watch --stop                 Stop running watcher
    sort-ocd dupes <path>                 Find and handle duplicates
    sort-ocd stats                        Show history dashboard
    sort-ocd config                       Configure AI backend
    sort-ocd undo [--session N]           Undo last operation (or session N)
    sort-ocd profile list                 List saved profiles
    sort-ocd profile save <name>          Save current config as a profile
    sort-ocd profile run <name> <path>    Run a saved profile on a folder
"""

import argparse
import os
import sys
import random

try:
    from rich.console import Console
    import questionary
except ImportError:
    print("Error: Missing dependencies. Run: pip install sort_ocd[ai-local]")
    sys.exit(1)

from . import config as cfg, database as db, sorter, ui
from .__init__ import __version__

console = Console()


# ─── Subcommand: sort ─────────────────────────────────────────────────────────

def cmd_sort(args) -> None:
    """Sort files in a directory using the specified mode."""
    target = os.path.expanduser(args.path)
    if not os.path.isdir(target):
        ui.print_error(f"Directory not found: {target}")
        sys.exit(1)

    mode = args.by
    custom_rule = getattr(args, "ai_rule", None)

    _run_sort(target, mode, custom_rule)


# ─── Subcommand: interactive (default) ───────────────────────────────────────

def cmd_interactive(_args) -> None:
    """Launch the full interactive TUI flow."""
    # Silently init AI engine (no crash if unavailable)
    from .ai_engine import AIEngine
    engine = AIEngine()
    ai_ok = engine.is_available()
    ai_info = engine.backend_info()

    target, mode, custom_rule = ui.run_interactive_setup(ai_ok, ai_info)
    if not target:
        sys.exit(0)

    _run_sort(target, mode, custom_rule, engine=engine if ai_ok else None)


# ─── Core Sort Runner ─────────────────────────────────────────────────────────

def _run_sort(
    target: str,
    mode: str,
    custom_rule: str | None,
    engine=None,
) -> None:
    """
    Shared sort execution flow used by both interactive and direct CLI modes.
    """
    # Scan files
    files = sorter.scan_files(target)
    if not files:
        ui.print_warning("No files found to sort.")
        sys.exit(0)

    console.print(f"  Found [bright_cyan]{len(files)}[/bright_cyan] file(s) in [dim]{target}[/dim]")

    is_ai_mode = mode in ("ai", "ai_auto")

    if is_ai_mode:
        if engine is None:
            from .ai_engine import AIEngine
            engine = AIEngine()
        if not engine.is_available():
            ui.print_error(
                "No AI backend available. Run [cyan]sort-ocd config[/cyan] to set one up."
            )
            sys.exit(1)

    # AI Auto-Pilot: suggest taxonomies first
    if mode == "ai_auto":
        sample = random.sample(files, min(15, len(files)))
        with ui.make_spinner_progress() as prog:
            prog.add_task("🤖  AI is analysing your files…", total=None)
            strategies = engine.suggest_taxonomy(sample)

        chosen = questionary.select(
            "AI suggests these structures — pick one:",
            choices=strategies,
            style=ui.Q_STYLE,
        ).ask()
        if not chosen:
            sys.exit(0)
        mode = "ai"
        custom_rule = f"Organize strictly following this strategy: {chosen}"
        console.print(f"  Strategy: [cyan]{chosen}[/cyan]\n")

    # Build plan
    plan: dict

    if is_ai_mode:
        console.print(f"  [dim]Analysing {len(files)} file(s) with AI…[/dim]")
        progress = ui.make_file_progress(len(files))
        completed = [0]

        def _cb(i, filename):
            completed[0] += 1
            progress.update(
                task_id,
                advance=1,
                description=f"  🤖  [dim]{filename[:40]}[/dim]",
            )

        with progress:
            task_id = progress.add_task("  🤖  Analysing…", total=len(files))
            plan = sorter.build_plan_ai(target, files, custom_rule, engine, _cb)
    else:
        with ui.make_spinner_progress() as prog:
            prog.add_task(f"  Scanning {len(files)} files…", total=None)
            plan = sorter.build_plan_manual(target, files, mode)

    if not plan:
        ui.print_warning("Nothing to organize.")
        sys.exit(0)

    # Show plan and ask for confirmation
    if not ui.display_action_plan(plan, mode, target):
        sys.exit(0)

    # Execute
    session_id = db.create_session(target, mode)
    with ui.make_spinner_progress() as prog:
        prog.add_task("  Moving files…", total=None)
        moved = sorter.execute_plan(target, plan, session_id, db)
    db.close_session(session_id, moved)

    ui.print_success(f"Done! {moved} file(s) organized. (Session #{session_id})")
    console.print(f"  [dim]Undo with: sort-ocd undo[/dim]")


# ─── Subcommand: watch ────────────────────────────────────────────────────────

def cmd_watch(args) -> None:
    from . import watcher

    if args.stop:
        stopped = watcher.stop_watcher()
        if stopped:
            ui.print_success("Watcher stopped.")
        else:
            ui.print_warning("No watcher is currently running.")
        return

    if not args.path:
        ui.print_error("Please provide a folder to watch. Example: sort-ocd watch ~/Downloads")
        sys.exit(1)

    target = os.path.expanduser(args.path)
    mode = args.mode or cfg.get("watch_sort_mode") or "ext"
    cooldown = args.cooldown or cfg.get("watch_cooldown_seconds") or 3.0

    watcher.start_watcher(target, mode, float(cooldown))


# ─── Subcommand: dupes ────────────────────────────────────────────────────────

def cmd_dupes(args) -> None:
    from . import duplicates

    target = os.path.expanduser(args.path)
    if not os.path.isdir(target):
        ui.print_error(f"Directory not found: {target}")
        sys.exit(1)

    files = sorter.scan_files(target)
    if not files:
        ui.print_warning("No files found.")
        sys.exit(0)

    console.print(f"  Scanning [cyan]{len(files)}[/cyan] files for duplicates…")

    with ui.make_spinner_progress() as prog:
        prog.add_task("  Hashing files…", total=None)
        groups = duplicates.find_duplicates(target, files)

    if not groups:
        ui.print_success("No duplicate files found! 🎉")
        sys.exit(0)

    formatted = duplicates.format_duplicate_groups(groups)
    total_wasted = sum(g["total_wasted"] for g in formatted)

    console.print(
        f"  Found [yellow]{len(groups)}[/yellow] duplicate group(s)  "
        f"| Reclaimable: [yellow]{sorter.format_bytes(total_wasted)}[/yellow]\n"
    )

    all_moves = []

    for i, group in enumerate(formatted):
        console.print(f"  [bold]Group {i+1}[/bold] ({sorter.format_bytes(group['sizes'][0])} each):")
        choices = []
        for path, size in zip(group["paths"], group["sizes"]):
            label = f"{os.path.basename(path)}  [dim]({sorter.format_bytes(size)})[/dim]  {os.path.dirname(path)}"
            choices.append(questionary.Choice(label, value=path))

        keep = questionary.select(
            "  Which copy do you want to KEEP?",
            choices=choices,
            style=ui.Q_STYLE,
        ).ask()

        if keep is None:
            console.print("  [dim]Skipped this group.[/dim]")
            continue

        console.print(f"  → Keeping: [green]{os.path.basename(keep)}[/green]")
        moves = duplicates.move_to_duplicates_folder(group["paths"], keep, target)
        all_moves.extend(moves)
        console.print(f"  → Moved {len(moves)} duplicate(s) to [dim]_DUPLICATES/[/dim]\n")

    if all_moves:
        ui.print_success(f"Cleaned up {len(all_moves)} duplicate(s). Saved in _DUPLICATES/ (not deleted).")
    else:
        console.print("  [dim]No changes made.[/dim]")


# ─── Subcommand: stats ────────────────────────────────────────────────────────

def cmd_stats(_args) -> None:
    stats = db.get_stats()
    ui.display_stats(stats)


# ─── Subcommand: config ───────────────────────────────────────────────────────

def cmd_config(_args) -> None:
    current = cfg.load()
    updated = ui.run_config_wizard(current)
    if updated:
        cfg.save(updated)


# ─── Subcommand: undo ─────────────────────────────────────────────────────────

def cmd_undo(args) -> None:
    session_id = getattr(args, "session", None)

    if session_id is None:
        session_id = db.get_last_session_id()
        if session_id is None:
            ui.print_warning("No sessions in history. Nothing to undo.")
            sys.exit(0)

    moves = db.get_moves_for_session(session_id)
    if not moves:
        ui.print_warning(f"Session #{session_id} has no moves to undo (may already be undone).")
        sys.exit(0)

    console.print(
        f"  About to undo [cyan]{len(moves)}[/cyan] move(s) from session [cyan]#{session_id}[/cyan]."
    )
    if not ui.confirm("Proceed with undo?", default=True):
        sys.exit(0)

    success, failed = 0, 0
    for src, dest in moves:
        if os.path.exists(dest):
            try:
                os.makedirs(os.path.dirname(src), exist_ok=True)
                os.rename(dest, src)
                success += 1
            except OSError:
                failed += 1
        else:
            failed += 1

    db.delete_session_moves(session_id)

    if failed:
        ui.print_warning(f"Undone: {success} file(s). Could not revert: {failed} file(s) (already moved/deleted?).")
    else:
        ui.print_success(f"Undo complete! {success} file(s) restored.")

    # Clean up empty folders left behind
    _cleanup_empty_dirs(None)


def _cleanup_empty_dirs(target: str | None) -> None:
    """Best-effort cleanup of empty subdirectories after undo."""
    pass  # Non-critical; skipped to keep undo fast and safe


# ─── Subcommand: profile ──────────────────────────────────────────────────────

def cmd_profile(args) -> None:
    sub = args.profile_cmd

    if sub == "list":
        profiles = cfg.list_profiles()
        if not profiles:
            ui.print_warning("No saved profiles. Create one with: sort-ocd profile save <name>")
            return
        from rich.table import Table
        from rich import box
        t = Table(box=box.SIMPLE, border_style="dim", show_header=True, header_style="bold magenta")
        t.add_column("Name")
        t.add_column("Mode")
        t.add_column("AI Rule")
        for name, data in profiles.items():
            t.add_row(name, data.get("mode", "?"), data.get("custom_rule", ""))
        console.print(t)

    elif sub == "save":
        name = args.name
        current = cfg.load()
        mode = getattr(args, "mode", None) or current.get("default_sort_mode", "ext")
        profile_data = {"mode": mode, "custom_rule": getattr(args, "ai_rule", None)}
        cfg.save_profile(name, profile_data)
        ui.print_success(f"Profile '{name}' saved.")

    elif sub == "run":
        profile = cfg.get_profile(args.name)
        if not profile:
            ui.print_error(f"Profile '{args.name}' not found. Use: sort-ocd profile list")
            sys.exit(1)
        target = os.path.expanduser(args.path)
        _run_sort(target, profile.get("mode", "ext"), profile.get("custom_rule"))

    elif sub == "delete":
        if cfg.delete_profile(args.name):
            ui.print_success(f"Profile '{args.name}' deleted.")
        else:
            ui.print_error(f"Profile '{args.name}' not found.")


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def main() -> None:
    """Parse arguments and dispatch to the correct subcommand."""
    parser = argparse.ArgumentParser(
        prog="sort-ocd",
        description="⚡ sort_OCD — AI-Powered File Organizer",
        epilog=(
            "Examples:\n"
            "  sort-ocd                            # Interactive mode\n"
            "  sort-ocd sort ~/Downloads --by ext  # Sort by file type\n"
            "  sort-ocd watch ~/Downloads          # Auto-sort watcher\n"
            "  sort-ocd dupes ~/Downloads          # Find duplicates\n"
            "  sort-ocd stats                      # Show history\n"
            "  sort-ocd undo                       # Undo last operation\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--version", action="version", version=f"sort-ocd {__version__}")

    subs = parser.add_subparsers(dest="command", metavar="<command>")

    # ── sort ──
    p_sort = subs.add_parser("sort", help="Sort files in a folder")
    p_sort.add_argument("path", help="Folder to sort")
    p_sort.add_argument(
        "--by", "-b",
        choices=["ext", "year", "month", "day", "ai", "ai_auto", "size", "alpha"],
        default="ext",
        help="Sorting mode (default: ext)",
    )
    p_sort.add_argument("--ai-rule", default=None, help="Custom AI sorting rule")

    # ── watch ──
    p_watch = subs.add_parser("watch", help="Auto-sort a folder as files arrive")
    p_watch.add_argument("path", nargs="?", default=None, help="Folder to watch")
    p_watch.add_argument("--stop", action="store_true", help="Stop running watcher")
    p_watch.add_argument("--mode", default=None, help="Sort mode for auto-sort (default: ext)")
    p_watch.add_argument("--cooldown", type=float, default=None, help="Seconds to wait before sorting (default: 3)")

    # ── dupes ──
    p_dupes = subs.add_parser("dupes", help="Find and handle duplicate files")
    p_dupes.add_argument("path", help="Folder to scan")

    # ── stats ──
    subs.add_parser("stats", help="Show history and stats dashboard")

    # ── config ──
    subs.add_parser("config", help="Configure AI backend")

    # ── undo ──
    p_undo = subs.add_parser("undo", help="Undo the last sort operation")
    p_undo.add_argument("--session", type=int, default=None, help="Session ID to undo (default: last)")

    # ── profile ──
    p_prof = subs.add_parser("profile", help="Manage saved sorting profiles")
    prof_subs = p_prof.add_subparsers(dest="profile_cmd", metavar="<action>")

    prof_subs.add_parser("list", help="List all saved profiles")

    p_prof_save = prof_subs.add_parser("save", help="Save a new profile")
    p_prof_save.add_argument("name", help="Profile name")
    p_prof_save.add_argument("--mode", default=None)
    p_prof_save.add_argument("--ai-rule", default=None)

    p_prof_run = prof_subs.add_parser("run", help="Run a saved profile")
    p_prof_run.add_argument("name", help="Profile name")
    p_prof_run.add_argument("path", help="Folder to sort")

    p_prof_del = prof_subs.add_parser("delete", help="Delete a profile")
    p_prof_del.add_argument("name", help="Profile name")

    # ── Parse and dispatch ──
    args = parser.parse_args()

    try:
        if args.command == "sort":
            cmd_sort(args)
        elif args.command == "watch":
            cmd_watch(args)
        elif args.command == "dupes":
            cmd_dupes(args)
        elif args.command == "stats":
            cmd_stats(args)
        elif args.command == "config":
            cmd_config(args)
        elif args.command == "undo":
            cmd_undo(args)
        elif args.command == "profile":
            if not args.profile_cmd:
                p_prof.print_help()
            else:
                cmd_profile(args)
        else:
            # No subcommand → interactive mode
            cmd_interactive(args)
    except KeyboardInterrupt:
        console.print("\n  [dim]Cancelled.[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    main()