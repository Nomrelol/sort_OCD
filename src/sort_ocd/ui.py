"""
ui.py — All Rich/Questionary UI components for sort_OCD.

Principles:
- Premium, branded look with consistent color palette
- Progressive disclosure: simple questions first, advanced options on demand
- Every interactive prompt has a sane default
- Never crashes on KeyboardInterrupt
"""

import os
from typing import Any, Dict, List, Optional, Tuple

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.columns import Columns
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich.layout import Layout
    from rich.align import Align
    from rich import box
    import questionary
    from questionary import Style
except ImportError:
    raise ImportError(
        "Missing UI dependencies. Run: pip install rich questionary"
    )

# ─── Color Palette ────────────────────────────────────────────────────────────

ACCENT   = "bright_cyan"
BRAND    = "bold bright_cyan"
SUCCESS  = "bold bright_green"
WARNING  = "bold yellow"
ERROR    = "bold red"
MUTED    = "dim white"
HEADER   = "bold magenta"

# ─── Questionary Style ────────────────────────────────────────────────────────

Q_STYLE = Style([
    ("qmark",       "fg:#00d7ff bold"),
    ("question",    "bold white"),
    ("answer",      "fg:#00d7ff bold"),
    ("pointer",     "fg:#00d7ff bold"),
    ("highlighted", "fg:#00d7ff bold"),
    ("selected",    "fg:#ffffff bold"),
    ("separator",   "fg:#555555"),
    ("instruction", "fg:#888888"),
])

console = Console()


# ─── Banner ───────────────────────────────────────────────────────────────────

def print_banner(version: str = "2.0.0") -> None:
    """Print the branded sort_OCD welcome banner."""
    banner_text = Text()
    banner_text.append("⚡ ", style="bold yellow")
    banner_text.append("sort_OCD", style="bold bright_cyan")
    banner_text.append(f"  v{version}", style="dim white")
    banner_text.append("\n")
    banner_text.append("  AI-Powered File Organizer", style="dim white")

    console.print(
        Panel(
            Align.center(banner_text),
            border_style="bright_cyan",
            padding=(0, 4),
            expand=False,
        )
    )
    console.print()


# ─── Action Plan Display ──────────────────────────────────────────────────────

# Icons for folder categories
CATEGORY_ICONS = {
    "Images": "🖼 ",  "Videos": "🎬 ", "Audio": "🎵 ",
    "Documents": "📄 ", "Spreadsheets": "📊 ", "Presentations": "📑 ",
    "Archives": "📦 ", "Code": "💻 ", "Data": "🗄 ",
    "Design": "🎨 ", "3D-Models": "🧊 ", "Fonts": "🔤 ",
    "eBooks": "📚 ", "Executables": "⚙️ ", "Disk-Images": "💿 ",
    "Torrents": "🌊 ", "Configs": "🔧 ", "Misc": "📁 ",
    "Uncategorized": "❓ ", "AI_Error": "⚠️ ",
}

# Cycling colors for destination folders
FOLDER_COLORS = ["cyan", "green", "yellow", "magenta", "blue", "red",
                 "bright_cyan", "bright_green", "bright_yellow"]


def display_action_plan(
    plan: Dict[str, List[dict]],
    mode: str,
    target_folder: str,
) -> bool:
    """
    Display a rich action plan table. Returns True if user confirms, False to cancel.
    """
    from . import sorter

    total_files = sum(len(v) for v in plan.values())
    total_bytes = 0
    for items in plan.values():
        for item in items:
            try:
                total_bytes += os.path.getsize(item["src"])
            except OSError:
                pass

    # Summary line
    console.print(
        f"\n  [bold]Destination:[/bold] [cyan]{target_folder}[/cyan]"
    )
    console.print(
        f"  [bold]Files:[/bold] [{ACCENT}]{total_files}[/{ACCENT}]  "
        f"[bold]Folders:[/bold] [{ACCENT}]{len(plan)}[/{ACCENT}]  "
        f"[bold]Total Size:[/bold] [{ACCENT}]{sorter.format_bytes(total_bytes)}[/{ACCENT}]"
    )
    console.print()

    is_ai = mode in ("ai", "ai_auto")

    table = Table(
        show_header=True,
        header_style=HEADER,
        box=box.ROUNDED,
        border_style="dim cyan",
        padding=(0, 1),
        expand=False,
    )
    table.add_column("Folder", style="bold", min_width=16)
    table.add_column("Original File", style=MUTED, max_width=30)
    if is_ai:
        table.add_column("→ New Name", style="bright_green", max_width=30)
        table.add_column("AI Reason", style="dim yellow", max_width=35)
    table.add_column("Size", justify="right", style=MUTED)

    for idx, (folder, items) in enumerate(plan.items()):
        color = FOLDER_COLORS[idx % len(FOLDER_COLORS)]
        icon = CATEGORY_ICONS.get(folder, "📁 ")
        folder_label = f"[{color}]{icon}{folder}[/{color}]"
        first = True
        for item in items:
            try:
                size = sorter.format_bytes(os.path.getsize(item["src"]))
            except OSError:
                size = "?"
            src_name = os.path.basename(item["src"])
            if is_ai:
                rationale = (item.get("rationale") or "")[:50]
                table.add_row(
                    folder_label if first else "",
                    src_name,
                    item.get("dest_name", src_name),
                    rationale,
                    size,
                )
            else:
                table.add_row(
                    folder_label if first else "",
                    src_name,
                    size,
                )
            first = False

    console.print(table)
    console.print()

    try:
        return questionary.confirm(
            "Proceed with this plan?",
            default=True,
            style=Q_STYLE,
        ).ask() or False
    except KeyboardInterrupt:
        console.print(f"\n  [{ERROR}]Cancelled.[/{ERROR}]")
        return False


# ─── Interactive Mode (Main Flow) ─────────────────────────────────────────────

def run_interactive_setup(ai_available: bool, ai_backend_info: str) -> Optional[Tuple]:
    """
    Zero-friction interactive mode. Simple choices first, advanced on demand.

    Returns: (target_folder, mode, custom_rule) or (None, None, None) on cancel.
    """
    print_banner()

    # AI status hint
    if ai_available:
        console.print(
            f"  [{SUCCESS}]✓[/{SUCCESS}] AI ready: [dim]{ai_backend_info}[/dim]\n"
        )
    else:
        console.print(
            f"  [{WARNING}]⚠[/{WARNING}]  No AI backend detected. "
            f"AI modes will be skipped. (Run [cyan]sort-ocd config[/cyan] to set up)\n"
        )

    try:
        # Step 1: Folder
        target_folder = questionary.path(
            "📂  Which folder do you want to organize?",
            style=Q_STYLE,
            only_directories=True,
        ).ask()

        if not target_folder:
            return None, None, None

        target_folder = os.path.expanduser(target_folder)
        if not os.path.isdir(target_folder):
            console.print(f"  [{ERROR}]✗  Folder not found.[/{ERROR}]")
            return None, None, None

        # Step 2: How to sort — simple choices
        mode_choices = [
            questionary.Choice("📁  By File Type  (Images, Videos, Code…)", value="ext"),
            questionary.Choice("📅  By Date  (Year / Month / Day)", value="date_sub"),
            questionary.Choice("📏  By Size  (Tiny → Huge)", value="size"),
            questionary.Choice("🔤  Alphabetically  (A → Z)", value="alpha"),
        ]
        if ai_available:
            mode_choices.insert(1, questionary.Choice(
                "🤖  AI Auto-Pilot  (AI suggests best structure)", value="ai_auto"
            ))
            mode_choices.insert(2, questionary.Choice(
                "💬  AI Custom Rule  (describe what you want)", value="ai"
            ))

        choice = questionary.select(
            "How would you like to sort?",
            choices=mode_choices,
            style=Q_STYLE,
        ).ask()

        if not choice:
            return None, None, None

        mode = choice
        custom_rule = None

        # Step 3: Sub-choices (only shown when relevant)
        if choice == "date_sub":
            date_choice = questionary.select(
                "Group by:",
                choices=[
                    questionary.Choice("Year  (2024, 2025…)", value="year"),
                    questionary.Choice("Month  (2025-09 September)", value="month"),
                    questionary.Choice("Day  (2025-09-13 Saturday)", value="day"),
                ],
                style=Q_STYLE,
            ).ask()
            mode = date_choice or "year"

        elif choice == "ai":
            custom_rule = questionary.text(
                "💬  Describe your rule:",
                placeholder='e.g. "Put receipts in Finance, code in Projects"',
                style=Q_STYLE,
            ).ask()

        return target_folder, mode, custom_rule

    except KeyboardInterrupt:
        console.print(f"\n  [{ERROR}]Cancelled.[/{ERROR}]")
        return None, None, None


# ─── Progress Bar Factories ───────────────────────────────────────────────────

def make_spinner_progress() -> Progress:
    """A transient spinner for indeterminate operations."""
    return Progress(
        SpinnerColumn(style=ACCENT),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    )


def make_file_progress(total: int) -> Progress:
    """A progress bar for per-file AI processing."""
    return Progress(
        SpinnerColumn(style=ACCENT),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30, style="cyan", complete_style="bright_cyan"),
        TextColumn(f"[{MUTED}]{{task.completed}}/{total}[/{MUTED}]"),
        TimeElapsedColumn(),
        transient=True,
        console=console,
    )


# ─── Stats Dashboard ──────────────────────────────────────────────────────────

def display_stats(stats: dict) -> None:
    """Render the history/stats dashboard using Rich panels."""
    print_banner()

    # Top summary cards
    cards = [
        Panel(
            Align.center(
                Text(f"{stats['total_sessions']}", style="bold bright_cyan", justify="center") +
                Text("\nTotal Sessions", style="dim white", justify="center")
            ),
            border_style="cyan", padding=(1, 2)
        ),
        Panel(
            Align.center(
                Text(f"{stats['total_files']}", style="bold bright_green", justify="center") +
                Text("\nFiles Organized", style="dim white", justify="center")
            ),
            border_style="green", padding=(1, 2)
        ),
    ]
    console.print(Columns(cards, equal=True))
    console.print()

    # Recent sessions table
    if stats["recent_sessions"]:
        console.print("[bold]📋  Recent Sessions[/bold]")
        t = Table(box=box.SIMPLE, border_style="dim", show_header=True,
                  header_style="bold magenta")
        t.add_column("#", style="dim", width=4)
        t.add_column("Date")
        t.add_column("Folder", max_width=35)
        t.add_column("Mode")
        t.add_column("Files", justify="right")
        t.add_column("Via", style="dim")

        for s in stats["recent_sessions"]:
            date_str = s["started_at"][:16].replace("T", " ")
            t.add_row(
                str(s["id"]),
                date_str,
                os.path.basename(s["target_dir"]) or s["target_dir"],
                s["sort_mode"],
                str(s["total_moved"]),
                s.get("source", "manual"),
            )
        console.print(t)
        console.print()

    # Most used modes
    if stats["top_modes"]:
        console.print("[bold]🏆  Most Used Modes[/bold]")
        t2 = Table(box=box.SIMPLE, border_style="dim", show_header=True,
                   header_style="bold magenta")
        t2.add_column("Mode")
        t2.add_column("Sessions", justify="right")
        for m in stats["top_modes"]:
            t2.add_row(m["sort_mode"], str(m["count"]))
        console.print(t2)


# ─── Config Wizard ────────────────────────────────────────────────────────────

def run_config_wizard(current_config: dict) -> Optional[dict]:
    """
    Simple, guided config setup. Non-destructive: only updates what the user changes.
    Returns updated config dict, or None if user cancelled.
    """
    print_banner()
    console.print("[bold]  ⚙  AI Backend Configuration[/bold]\n")

    try:
        backend = questionary.select(
            "Which AI backend do you want to use?",
            choices=[
                questionary.Choice("🤖  Auto-detect  (try Ollama, then OpenAI)", value="auto"),
                questionary.Choice("🏠  Ollama  (local, free, private)", value="ollama"),
                questionary.Choice("☁️   OpenAI  (GPT-4o-mini, etc.)", value="openai"),
                questionary.Choice("🧠  Anthropic  (Claude)", value="anthropic"),
                questionary.Choice("🔗  Custom endpoint  (LM Studio, Jan.ai, Codex CLI)", value="custom"),
            ],
            default=current_config.get("ai_backend", "auto"),
            style=Q_STYLE,
        ).ask()

        if backend is None:
            return None

        updated = dict(current_config)
        updated["ai_backend"] = backend

        if backend == "ollama":
            console.print(
                f"\n  [{MUTED}]Leave blank to auto-detect best model.[/{MUTED}]"
            )
            model = questionary.text(
                "Ollama text model (e.g. llama3, mistral):",
                default=current_config.get("ollama_model", "auto"),
                style=Q_STYLE,
            ).ask()
            vision = questionary.text(
                "Ollama vision model (e.g. llava, moondream):",
                default=current_config.get("ollama_vision_model", "auto"),
                style=Q_STYLE,
            ).ask()
            updated["ollama_model"] = model or "auto"
            updated["ollama_vision_model"] = vision or "auto"

        elif backend == "openai":
            key = questionary.password(
                "OpenAI API key:",
                style=Q_STYLE,
            ).ask()
            if key:
                updated["openai_api_key"] = key
            model = questionary.select(
                "Model:",
                choices=["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
                default=current_config.get("openai_model", "gpt-4o-mini"),
                style=Q_STYLE,
            ).ask()
            updated["openai_model"] = model or "gpt-4o-mini"

        elif backend == "anthropic":
            key = questionary.password(
                "Anthropic API key:",
                style=Q_STYLE,
            ).ask()
            if key:
                updated["anthropic_api_key"] = key
            model = questionary.select(
                "Model:",
                choices=[
                    "claude-3-haiku-20240307",
                    "claude-3-5-sonnet-20241022",
                    "claude-opus-4-5",
                ],
                default=current_config.get("anthropic_model", "claude-3-haiku-20240307"),
                style=Q_STYLE,
            ).ask()
            updated["anthropic_model"] = model or "claude-3-haiku-20240307"

        elif backend == "custom":
            endpoint = questionary.text(
                "Endpoint URL:",
                default=current_config.get("custom_endpoint", "http://localhost:1234/v1"),
                style=Q_STYLE,
            ).ask()
            model_name = questionary.text(
                "Model name:",
                default=current_config.get("custom_model", "local-model"),
                style=Q_STYLE,
            ).ask()
            updated["custom_endpoint"] = endpoint or "http://localhost:1234/v1"
            updated["custom_model"] = model_name or "local-model"

        console.print(f"\n  [{SUCCESS}]✓  Configuration saved to ~/.sort_ocd_config.json[/{SUCCESS}]")
        return updated

    except KeyboardInterrupt:
        console.print(f"\n  [{ERROR}]Config unchanged.[/{ERROR}]")
        return None


# ─── Profile Prompts ──────────────────────────────────────────────────────────

def prompt_profile_name(existing: List[str]) -> Optional[str]:
    """Ask for a profile name to save."""
    try:
        name = questionary.text(
            "Profile name:",
            style=Q_STYLE,
        ).ask()
        return name.strip() if name else None
    except KeyboardInterrupt:
        return None


def prompt_select_profile(profiles: dict) -> Optional[str]:
    """Let user pick a saved profile from a list."""
    if not profiles:
        console.print(f"  [{WARNING}]No saved profiles yet.[/{WARNING}]")
        return None
    try:
        choices = list(profiles.keys())
        return questionary.select(
            "Select profile:",
            choices=choices,
            style=Q_STYLE,
        ).ask()
    except KeyboardInterrupt:
        return None


# ─── Generic Helpers ──────────────────────────────────────────────────────────

def confirm(message: str, default: bool = True) -> bool:
    """Confirmed or cancelled with a default. Safe against KeyboardInterrupt."""
    try:
        result = questionary.confirm(message, default=default, style=Q_STYLE).ask()
        return result if result is not None else False
    except KeyboardInterrupt:
        return False


def print_success(message: str) -> None:
    console.print(f"\n  [{SUCCESS}]✓  {message}[/{SUCCESS}]\n")


def print_error(message: str) -> None:
    console.print(f"\n  [{ERROR}]✗  {message}[/{ERROR}]\n")


def print_warning(message: str) -> None:
    console.print(f"\n  [{WARNING}]⚠  {message}[/{WARNING}]\n")


def print_info(message: str) -> None:
    console.print(f"  [dim]{message}[/dim]")
