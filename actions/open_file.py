"""
Action: open_file
Opens a file on the computer by just its name, partial name, or full path using
its default system application or an optionally specified application.
Auto-discovered by core/action_loader.py.
"""
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"

# Skip noisy/heavy directories during search
_EXCLUDED_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".cache",
    "appdata", "local settings", "application data", "$recycle.bin",
    "system volume information", "windows", "program files", "program files (x86)",
}


def _get_search_roots(folder_hint: str = "") -> List[Path]:
    """Return an ordered list of search roots based on an optional folder hint."""
    home = Path.home()
    roots: List[Path] = []

    hint = (folder_hint or "").strip().lower()
    if hint in ("desktop", "desk"):
        roots.append(home / "Desktop")
    elif hint in ("downloads", "download", "down"):
        roots.append(home / "Downloads")
    elif hint in ("documents", "document", "docs", "doc"):
        roots.append(home / "Documents")
    elif hint in ("cwd", "workspace", "project", "current"):
        roots.append(Path.cwd())
    elif hint:
        hint_path = Path(folder_hint).expanduser().resolve()
        if hint_path.is_dir():
            roots.append(hint_path)

    # Standard default priority search hierarchy
    defaults = [
        Path.cwd(),
        home / "Desktop",
        home / "Downloads",
        home / "Documents",
        home / "Pictures",
        home / "Videos",
        home / "Music",
        home,
    ]
    for d in defaults:
        if d.exists() and d not in roots:
            roots.append(d)

    return roots


def find_file_by_name(query: str, folder_hint: str = "", max_depth: int = 2) -> Optional[Path]:
    """
    Search for a file matching `query` across priority user directories.
    Handles:
    - Direct absolute or relative paths
    - Exact filename matches (case-insensitive)
    - Stem match without extension (e.g. 'resume' -> 'resume.pdf')
    - Substring matches (e.g. 'q3 report' -> '2026_q3_report_final.xlsx')
    Returns the best matching Path (most recently modified if multiple), or None.
    """
    raw_path = Path(query).expanduser()
    if raw_path.is_file():
        return raw_path.resolve()

    # If query is inside current working directory
    cwd_candidate = Path.cwd() / query
    if cwd_candidate.is_file():
        return cwd_candidate.resolve()

    roots = _get_search_roots(folder_hint)
    clean_q = query.strip().lower()
    has_ext = bool(Path(clean_q).suffix)

    exact_matches: List[Tuple[float, Path]] = []
    stem_matches: List[Tuple[float, Path]] = []
    substring_matches: List[Tuple[float, Path]] = []

    for root in roots:
        if not root.is_dir():
            continue

        try:
            # First pass: check direct children of root (depth 0)
            for entry in os.scandir(root):
                try:
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    name_lower = entry.name.lower()
                    entry_path = Path(entry.path)
                    try:
                        mtime = entry.stat().st_mtime
                    except Exception:
                        mtime = 0.0

                    if name_lower == clean_q:
                        exact_matches.append((mtime, entry_path))
                    elif not has_ext and entry_path.stem.lower() == clean_q:
                        stem_matches.append((mtime, entry_path))
                    elif clean_q in name_lower:
                        substring_matches.append((mtime, entry_path))
                except PermissionError:
                    continue

            # Return immediately if an exact or stem match was found at root level
            if exact_matches:
                exact_matches.sort(key=lambda x: x[0], reverse=True)
                return exact_matches[0][1]
            if stem_matches:
                stem_matches.sort(key=lambda x: x[0], reverse=True)
                return stem_matches[0][1]

            # Second pass: shallow traversal up to max_depth
            if max_depth > 0:
                for cur_root, dirs, files in os.walk(root):
                    cur_path = Path(cur_root)
                    depth = len(cur_path.relative_to(root).parts)
                    if depth > max_depth:
                        dirs.clear()
                        continue

                    # Filter out excluded/system directories in place
                    dirs[:] = [
                        d for d in dirs
                        if not d.startswith(".") and d.lower() not in _EXCLUDED_DIRS
                    ]

                    for f in files:
                        f_lower = f.lower()
                        fp = cur_path / f
                        try:
                            mtime = fp.stat().st_mtime
                        except Exception:
                            mtime = 0.0

                        if f_lower == clean_q:
                            exact_matches.append((mtime, fp))
                        elif not has_ext and Path(f).stem.lower() == clean_q:
                            stem_matches.append((mtime, fp))
                        elif clean_q in f_lower:
                            substring_matches.append((mtime, fp))

        except (PermissionError, OSError):
            continue

    if exact_matches:
        exact_matches.sort(key=lambda x: x[0], reverse=True)
        return exact_matches[0][1]

    if stem_matches:
        stem_matches.sort(key=lambda x: x[0], reverse=True)
        return stem_matches[0][1]

    if substring_matches:
        substring_matches.sort(key=lambda x: x[0], reverse=True)
        return substring_matches[0][1]

    return None


def open_file_native(target: Path, app: str = "") -> Tuple[bool, str]:
    """Launch `target` with system default viewer or `app`."""
    try:
        resolved = str(target.resolve())
        app = (app or "").strip()

        if app:
            # Custom app launcher
            subprocess.Popen([app, resolved], shell=False)
            return True, f"Opened '{target.name}' with '{app}'."

        if _OS == "Windows":
            os.startfile(resolved)
            return True, f"Opened '{target.name}' with default application."
        elif _OS == "Darwin":
            subprocess.Popen(["open", resolved])
            return True, f"Opened '{target.name}' with default application."
        else:
            subprocess.Popen(["xdg-open", resolved])
            return True, f"Opened '{target.name}' with default application."

    except Exception as e:
        return False, f"Could not launch '{target.name}': {e}"


def open_file(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """Action handler called by EchoLive when the user asks to open a file."""
    params = parameters or {}
    name = str(params.get("name", "")).strip()
    folder = str(params.get("folder", "")).strip()
    app = str(params.get("app", "")).strip()

    if not name:
        return "Please specify the name of the file you want to open."

    if player:
        player.write_log(f"[open_file] Searching for '{name}'...")

    target = find_file_by_name(name, folder_hint=folder)

    if not target:
        hint_msg = f" in {folder}" if folder else " across Desktop, Documents, Downloads, and Home"
        return f"Could not find any file matching '{name}'{hint_msg}."

    ok, msg = open_file_native(target, app=app)
    if player:
        player.write_log(f"[open_file] {msg} ({target})")

    if ok:
        parent_name = target.parent.name or str(target.parent)
        return f"Opened '{target.name}' from {parent_name}/."
    else:
        return msg


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "open_file",
    "description": (
        "Opens any file on the user's computer by just its name, partial name, or path "
        "using the default operating system application (e.g. PDF reader, Word, Excel, "
        "text editor, image viewer, media player, VS Code) or an optionally specified application."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {
                "type": "STRING",
                "description": "Name or partial name of the file to open (e.g. 'report.pdf', 'resume', 'budget.xlsx', 'notes', 'invoice') or an absolute/relative path.",
            },
            "folder": {
                "type": "STRING",
                "description": "Optional folder hint to search in: 'desktop', 'downloads', 'documents', 'workspace', 'home', or a custom path.",
            },
            "app": {
                "type": "STRING",
                "description": "Optional specific application executable to open the file with (e.g. 'code', 'notepad', 'vlc', 'chrome'). Leave blank to use system default.",
            },
        },
        "required": ["name"],
    },
    "handler": open_file,
}
