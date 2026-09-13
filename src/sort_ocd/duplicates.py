"""
duplicates.py — SHA-256 based duplicate file detection for sort_OCD.

Design:
- Exact duplicates only (byte-for-byte via SHA-256 hash)
- Safe: moves to _DUPLICATES/ subfolder, NEVER hard-deletes
- Interactive: user picks which copy to keep per group
- Shows sizes so user can make informed decisions
"""

import hashlib
import os
from typing import Dict, List, Optional, Tuple


def _sha256(file_path: str, chunk_size: int = 65536) -> Optional[str]:
    """
    Compute SHA-256 hash of a file. Returns None on any read error.
    Uses chunked reading to handle large files without memory issues.
    """
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


def find_duplicates(
    target_folder: str,
    filenames: List[str],
    progress_callback=None,
) -> List[List[str]]:
    """
    Scan files and group exact duplicates by SHA-256 hash.

    Args:
        target_folder: Directory containing files.
        filenames: List of filenames (not full paths) to scan.
        progress_callback(i, filename): Called after each file is hashed.

    Returns:
        List of groups, each group is a list of full paths that are identical.
        Only returns groups with 2+ files (actual duplicates).
    """
    hash_map: Dict[str, List[str]] = {}

    for i, filename in enumerate(filenames):
        file_path = os.path.join(target_folder, filename)
        digest = _sha256(file_path)
        if digest:
            hash_map.setdefault(digest, []).append(file_path)
        if progress_callback:
            progress_callback(i, filename)

    # Only return groups with actual duplicates
    return [paths for paths in hash_map.values() if len(paths) >= 2]


def move_to_duplicates_folder(
    paths: List[str],
    keep_path: str,
    target_folder: str,
) -> List[Tuple[str, str]]:
    """
    Move all files EXCEPT keep_path into a _DUPLICATES subfolder.

    Returns list of (original_path, new_path) for every moved file.
    """
    dup_folder = os.path.join(target_folder, "_DUPLICATES")
    os.makedirs(dup_folder, exist_ok=True)
    moved = []

    for path in paths:
        if path == keep_path:
            continue
        filename = os.path.basename(path)
        dest = _safe_path(dup_folder, filename)
        try:
            os.rename(path, dest)
            moved.append((path, dest))
        except OSError:
            pass

    return moved


def _safe_path(directory: str, filename: str) -> str:
    """Return a collision-safe path in directory."""
    dest = os.path.join(directory, filename)
    if not os.path.exists(dest):
        return dest
    name, ext = os.path.splitext(filename)
    i = 1
    while True:
        candidate = os.path.join(directory, f"{name} ({i}){ext}")
        if not os.path.exists(candidate):
            return candidate
        i += 1


def format_duplicate_groups(
    groups: List[List[str]],
) -> List[Dict]:
    """
    Prepare groups for display. Adds size and filename info per path.
    Returns list of {paths: [...], sizes: [...], total_wasted: int}
    """
    result = []
    for group in groups:
        sizes = []
        for p in group:
            try:
                sizes.append(os.path.getsize(p))
            except OSError:
                sizes.append(0)

        total_wasted = sum(sizes) - max(sizes) if sizes else 0
        result.append({
            "paths": group,
            "sizes": sizes,
            "total_wasted": total_wasted,
        })

    # Sort by wasted space (most wasteful first)
    result.sort(key=lambda x: x["total_wasted"], reverse=True)
    return result
