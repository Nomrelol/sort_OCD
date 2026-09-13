"""
sorter.py — Core file sorting logic for sort_OCD.

8 sorting modes, 20+ file type categories.
Completely decoupled from UI and AI — clean, testable, reusable.
"""

import datetime
import hashlib
import os
from typing import Dict, List, Optional, Tuple

# ─── Extension → Category Map (20+ categories) ───────────────────────────────

EXT_MAP: Dict[str, str] = {
    # Images
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images", ".gif": "Images",
    ".bmp": "Images", ".svg": "Images", ".webp": "Images", ".tiff": "Images",
    ".tif": "Images", ".ico": "Images", ".heic": "Images", ".heif": "Images",
    ".raw": "Images", ".cr2": "Images", ".nef": "Images", ".arw": "Images",

    # Videos
    ".mp4": "Videos", ".mkv": "Videos", ".mov": "Videos", ".avi": "Videos",
    ".webm": "Videos", ".flv": "Videos", ".wmv": "Videos", ".m4v": "Videos",
    ".3gp": "Videos", ".ts": "Videos", ".vob": "Videos",

    # Audio
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio", ".aac": "Audio",
    ".ogg": "Audio", ".m4a": "Audio", ".wma": "Audio", ".opus": "Audio",
    ".aiff": "Audio", ".alac": "Audio",

    # Documents
    ".pdf": "Documents", ".docx": "Documents", ".doc": "Documents",
    ".txt": "Documents", ".md": "Documents", ".rtf": "Documents",
    ".odt": "Documents", ".pages": "Documents", ".tex": "Documents",

    # Spreadsheets
    ".xlsx": "Spreadsheets", ".xls": "Spreadsheets", ".csv": "Spreadsheets",
    ".numbers": "Spreadsheets", ".ods": "Spreadsheets", ".tsv": "Spreadsheets",

    # Presentations
    ".pptx": "Presentations", ".ppt": "Presentations", ".key": "Presentations",
    ".odp": "Presentations",

    # Archives
    ".zip": "Archives", ".rar": "Archives", ".tar": "Archives",
    ".gz": "Archives", ".7z": "Archives", ".bz2": "Archives",
    ".xz": "Archives", ".tgz": "Archives", ".zst": "Archives",

    # Code
    ".py": "Code", ".js": "Code", ".ts": "Code", ".java": "Code",
    ".html": "Code", ".css": "Code", ".json": "Code", ".xml": "Code",
    ".yaml": "Code", ".yml": "Code", ".toml": "Code", ".sh": "Code",
    ".bash": "Code", ".zsh": "Code", ".rs": "Code", ".go": "Code",
    ".cpp": "Code", ".c": "Code", ".h": "Code", ".rb": "Code",
    ".php": "Code", ".swift": "Code", ".kt": "Code", ".r": "Code",
    ".sql": "Code", ".lua": "Code", ".pl": "Code", ".scala": "Code",

    # Data
    ".db": "Data", ".sqlite": "Data", ".sqlite3": "Data",
    ".parquet": "Data", ".arrow": "Data", ".hdf5": "Data",

    # Design
    ".psd": "Design", ".ai": "Design", ".sketch": "Design",
    ".fig": "Design", ".xd": "Design", ".afdesign": "Design",
    ".indd": "Design",

    # 3D Models
    ".obj": "3D-Models", ".fbx": "3D-Models", ".stl": "3D-Models",
    ".blend": "3D-Models", ".dae": "3D-Models", ".3ds": "3D-Models",
    ".gltf": "3D-Models", ".glb": "3D-Models",

    # Fonts
    ".ttf": "Fonts", ".otf": "Fonts", ".woff": "Fonts",
    ".woff2": "Fonts", ".eot": "Fonts",

    # eBooks
    ".epub": "eBooks", ".mobi": "eBooks", ".azw": "eBooks",
    ".azw3": "eBooks", ".lit": "eBooks",

    # Executables & Apps
    ".exe": "Executables", ".dmg": "Executables", ".pkg": "Executables",
    ".app": "Executables", ".deb": "Executables", ".rpm": "Executables",
    ".msi": "Executables", ".appimage": "Executables",

    # Disk Images
    ".iso": "Disk-Images", ".img": "Disk-Images", ".vmdk": "Disk-Images",
    ".vhd": "Disk-Images", ".vdi": "Disk-Images",

    # Torrents & Downloads
    ".torrent": "Torrents",

    # Configs & Dotfiles
    ".env": "Configs", ".ini": "Configs", ".cfg": "Configs",
    ".conf": "Configs", ".config": "Configs",
}

# Size buckets for --by size mode
SIZE_BUCKETS: List[Tuple[int, str]] = [
    (50 * 1024,          "Tiny (< 50KB)"),
    (10 * 1024 * 1024,   "Small (< 10MB)"),
    (500 * 1024 * 1024,  "Medium (< 500MB)"),
    (5 * 1024 ** 3,      "Large (< 5GB)"),
]
SIZE_BUCKET_OVERFLOW = "Huge (5GB+)"

SKIP_FILES = {".ds_store", "thumbs.db", "desktop.ini", ".localized"}


# ─── Core Sort Functions ──────────────────────────────────────────────────────

def get_dest_ext(filename: str) -> Optional[str]:
    """Map a filename to its category by extension."""
    ext = os.path.splitext(filename)[1].lower()
    return EXT_MAP.get(ext)


def get_dest_date(file_path: str, mode: str) -> Optional[str]:
    """
    Return a date-based folder name.
    mode: 'year' | 'month' | 'day'
    """
    try:
        ts = os.path.getmtime(file_path)
        dt = datetime.datetime.fromtimestamp(ts)
        if mode == "year":
            return dt.strftime("%Y")
        elif mode == "month":
            return dt.strftime("%Y-%m %B")       # e.g. "2025-09 September"
        elif mode == "day":
            return dt.strftime("%Y-%m-%d %A")    # e.g. "2025-09-13 Saturday"
    except OSError:
        pass
    return None


def get_dest_size(file_path: str) -> str:
    """Return a size-bucket folder name."""
    try:
        size = os.path.getsize(file_path)
        for threshold, label in SIZE_BUCKETS:
            if size < threshold:
                return label
        return SIZE_BUCKET_OVERFLOW
    except OSError:
        return SIZE_BUCKET_OVERFLOW


def get_dest_alpha(filename: str) -> str:
    """Return an alphabetical folder name (A-Z or #)."""
    first = filename[0].upper() if filename else "#"
    return first if first.isalpha() else "#"


def should_skip(filename: str) -> bool:
    """Return True if this file should be ignored (system files, etc.)."""
    return filename.lower() in SKIP_FILES or filename.startswith(".")


def get_safe_dest_path(directory: str, filename: str) -> str:
    """
    Return a safe path inside `directory` for `filename`.
    If the path already exists, appends (1), (2), etc.
    """
    dest = os.path.join(directory, filename)
    if not os.path.exists(dest):
        return dest
    name, ext = os.path.splitext(filename)
    counter = 1
    while True:
        candidate = os.path.join(directory, f"{name} ({counter}){ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def format_bytes(n: Optional[int]) -> str:
    """Format integer bytes as human-readable string."""
    if not n:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ─── Plan Builder ─────────────────────────────────────────────────────────────

def build_plan_manual(
    target_folder: str,
    files: List[str],
    mode: str,
) -> Dict[str, List[dict]]:
    """
    Build a move plan for non-AI modes.

    Returns: {folder_name: [{"src": path, "dest_name": name}, ...], ...}
    """
    plan: Dict[str, List[dict]] = {}

    for filename in files:
        if should_skip(filename):
            continue

        file_path = os.path.join(target_folder, filename)
        dest_dir = None

        if mode == "ext":
            dest_dir = get_dest_ext(filename) or "Misc"
        elif mode in ("year", "month", "day"):
            dest_dir = get_dest_date(file_path, mode) or "Unknown-Date"
        elif mode == "size":
            dest_dir = get_dest_size(file_path)
        elif mode == "alpha":
            dest_dir = get_dest_alpha(filename)

        if dest_dir:
            plan.setdefault(dest_dir, []).append({
                "src": file_path,
                "dest_name": filename,
                "summary": None,
                "rationale": None,
            })

    return plan


def build_plan_ai(
    target_folder: str,
    files: List[str],
    custom_rule: Optional[str],
    ai_engine,  # AIEngine instance
    progress_callback=None,
) -> Dict[str, List[dict]]:
    """
    Build a move plan using AI for categorization.

    progress_callback(i, filename): called after each file is processed.
    Returns: {folder_name: [{"src", "dest_name", "summary", "rationale"}, ...], ...}
    """
    plan: Dict[str, List[dict]] = {}

    for i, filename in enumerate(files):
        if should_skip(filename):
            if progress_callback:
                progress_callback(i, filename)
            continue

        file_path = os.path.join(target_folder, filename)
        meta = ai_engine.categorize(file_path, custom_rule)

        dest_dir = meta.get("folder", "Uncategorized")
        new_name = meta.get("filename", filename)

        # Ensure extension is preserved
        orig_ext = os.path.splitext(filename)[1]
        if orig_ext and not new_name.lower().endswith(orig_ext.lower()):
            new_name = os.path.splitext(new_name)[0] + orig_ext

        plan.setdefault(dest_dir, []).append({
            "src": file_path,
            "dest_name": new_name,
            "summary": meta.get("summary", ""),
            "rationale": meta.get("rationale", ""),
        })

        if progress_callback:
            progress_callback(i, filename)

    return plan


# ─── Execution ────────────────────────────────────────────────────────────────

def execute_plan(
    target_folder: str,
    plan: Dict[str, List[dict]],
    session_id: int,
    db,  # database module
) -> int:
    """
    Execute a move plan. Creates destination folders, moves files,
    logs every move to the database. Returns count of files moved.
    """
    moved = 0

    for dest_dir_name, items in plan.items():
        dest_dir_path = os.path.join(target_folder, dest_dir_name)
        os.makedirs(dest_dir_path, exist_ok=True)

        for item in items:
            src = item["src"]
            safe_dest = get_safe_dest_path(dest_dir_path, item["dest_name"])

            try:
                os.rename(src, safe_dest)
                db.log_move(session_id, src, safe_dest)

                # Write an INDEX.md summary file if AI generated a summary
                if item.get("summary"):
                    index_path = os.path.join(dest_dir_path, "INDEX.md")
                    with open(index_path, "a", encoding="utf-8") as f:
                        basename = os.path.basename(safe_dest)
                        f.write(f"- **{basename}**: {item['summary']}\n")

                moved += 1
            except OSError:
                pass  # Skip files that can't be moved (permissions, etc.)

    return moved


def scan_files(target_folder: str) -> List[str]:
    """
    Return a list of filenames (not paths) in target_folder.
    Excludes directories, hidden files, and system files.
    """
    try:
        return [
            f for f in os.listdir(target_folder)
            if os.path.isfile(os.path.join(target_folder, f))
            and not should_skip(f)
        ]
    except PermissionError:
        return []
