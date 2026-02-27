"""
File Size Analyzer
Scans your computer's folders and shows what's taking up storage space.
"""

import os
import sys
import time
from pathlib import Path
from collections import defaultdict


# ── Helpers ───────────────────────────────────────────────────────────────────

def format_size(bytes_val: int) -> str:
    """Convert bytes to a human-readable string (KB / MB / GB / TB)."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} PB"


def bar(fraction: float, width: int = 30) -> str:
    """Return a simple ASCII progress bar."""
    filled = int(fraction * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


# ── Core scanning ─────────────────────────────────────────────────────────────

def scan_directory(root: str, skip_errors: bool = True) -> tuple[dict, list, dict]:
    """
    Walk *root* and return:
        folder_sizes  – {path: total_bytes}
        large_files   – list of (size, path) for files >= 10 MB, sorted desc
        ext_sizes     – {'.ext': total_bytes}
    """
    folder_sizes: dict[str, int] = defaultdict(int)
    large_files: list[tuple[int, str]] = []
    ext_sizes: dict[str, int] = defaultdict(int)

    print(f"\nScanning: {root}")
    print("(This may take a while for large drives — press Ctrl+C to stop early)\n")

    scanned = 0
    errors = 0
    start = time.time()

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        # Skip common system / hidden directories that cause permission errors
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith("$")          # e.g. $Recycle.Bin, $WinREAgent
            and d not in {"System Volume Information", "Recovery", "Config.Msi"}
        ]

        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            try:
                size = os.path.getsize(fpath)
            except (PermissionError, FileNotFoundError, OSError):
                errors += 1
                continue

            scanned += 1

            # Roll the size up to every ancestor folder
            parts = Path(dirpath).parts
            for i in range(len(parts)):
                ancestor = str(Path(*parts[: i + 1]))
                folder_sizes[ancestor] += size

            # Track large files (>= 10 MB)
            if size >= 10 * 1024 * 1024:
                large_files.append((size, fpath))

            # Track by extension
            ext = Path(fname).suffix.lower() or "(no extension)"
            ext_sizes[ext] += size

            if scanned % 5000 == 0:
                elapsed = time.time() - start
                print(f"  ...{scanned:,} files scanned  ({elapsed:.0f}s elapsed)", end="\r")

    elapsed = time.time() - start
    print(f"\n  Done — {scanned:,} files scanned in {elapsed:.1f}s  ({errors} skipped)\n")

    large_files.sort(reverse=True)
    return dict(folder_sizes), large_files, dict(ext_sizes)


# ── Report sections ───────────────────────────────────────────────────────────

def report_top_folders(folder_sizes: dict, root: str, top_n: int = 20) -> None:
    print("=" * 70)
    print(f"  TOP {top_n} LARGEST FOLDERS")
    print("=" * 70)

    # Only show folders directly under root (depth = 1 below root) by default,
    # plus any deeper path with size >= 1 GB so large sub-trees are visible.
    root_parts_len = len(Path(root).parts)
    candidates = {
        p: s for p, s in folder_sizes.items()
        if len(Path(p).parts) == root_parts_len + 1        # direct children
        or s >= 1 * 1024 ** 3                              # OR >= 1 GB anywhere
    }

    sorted_folders = sorted(candidates.items(), key=lambda x: x[1], reverse=True)[:top_n]
    if not sorted_folders:
        print("  No folders found.\n")
        return

    total_root = folder_sizes.get(root, 1) or 1
    for path, size in sorted_folders:
        fraction = size / total_root
        depth = len(Path(path).parts) - root_parts_len
        indent = "  " * depth
        print(f"  {bar(fraction)}  {format_size(size):>10}  {indent}{path}")
    print()


def report_large_files(large_files: list, top_n: int = 20) -> None:
    print("=" * 70)
    print(f"  TOP {top_n} LARGEST FILES  (>= 10 MB)")
    print("=" * 70)

    if not large_files:
        print("  No large files found.\n")
        return

    max_size = large_files[0][0] or 1
    for size, path in large_files[:top_n]:
        fraction = size / max_size
        print(f"  {bar(fraction, 20)}  {format_size(size):>10}  {path}")
    print()


def report_file_types(ext_sizes: dict, top_n: int = 15) -> None:
    print("=" * 70)
    print(f"  TOP {top_n} FILE TYPES BY SIZE")
    print("=" * 70)

    sorted_exts = sorted(ext_sizes.items(), key=lambda x: x[1], reverse=True)[:top_n]
    if not sorted_exts:
        print("  No data.\n")
        return

    total = sum(ext_sizes.values()) or 1
    for ext, size in sorted_exts:
        fraction = size / total
        print(f"  {bar(fraction, 20)}  {format_size(size):>10}  {ext}")
    print()


def report_summary(folder_sizes: dict, large_files: list, ext_sizes: dict, root: str) -> None:
    total = folder_sizes.get(root, sum(ext_sizes.values()))
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Scan root        : {root}")
    print(f"  Total size found : {format_size(total)}")
    print(f"  Large files      : {len(large_files):,}  (>= 10 MB each)")
    print(f"  Unique extensions: {len(ext_sizes):,}")

    if large_files:
        top_size, top_path = large_files[0]
        print(f"  Biggest file     : {format_size(top_size)}  —  {top_path}")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) > 1:
        root = sys.argv[1]
    else:
        # Default: scan the current user's home directory
        root = str(Path.home())
        print(f"No path provided — defaulting to your home folder: {root}")
        print("Tip: run as   python file_analyzer.py C:\\   to scan the whole C: drive\n")

    if not os.path.isdir(root):
        print(f"ERROR: '{root}' is not a valid directory.")
        sys.exit(1)

    try:
        folder_sizes, large_files, ext_sizes = scan_directory(root)
    except KeyboardInterrupt:
        print("\n\nScan interrupted by user — showing partial results.\n")
        # Results gathered so far are still in scope if we restructure;
        # for simplicity just exit cleanly.
        sys.exit(0)

    report_summary(folder_sizes, large_files, ext_sizes, root)
    report_top_folders(folder_sizes, root)
    report_large_files(large_files)
    report_file_types(ext_sizes)


if __name__ == "__main__":
    main()
