"""
SuperCopy: A high-performance file copy and unpack utility for Windows.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional, Sequence, Tuple

from tqdm import tqdm

# py7zr is used for .7z; imported lazily in UnpackEngine when needed.

ProgressCallback = Callable[[str, object], None]
FileEntry = Tuple[str, str, str, int]  # source_path, rel_dir, name, size


# --- HELPER FUNCTIONS ---


def get_version_from_package_json() -> str:
    """Reads the version of the application from the package.json file."""
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates = [
            os.path.join(exe_dir, "..", "package.json"),
            os.path.join(exe_dir, "package.json"),
        ]
    else:
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "package.json")
        ]

    for package_json_path in candidates:
        try:
            with open(package_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("version", "Unknown Version")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
    return "Unknown Version"


def safe_print(*args, file=None, **kwargs) -> None:
    """Print text safely on Windows consoles that cannot encode emoji."""
    target = file or sys.stdout
    try:
        print(*args, file=target, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        text = text.encode(target.encoding or "ascii", errors="replace").decode(
            target.encoding or "ascii", errors="replace"
        )
        print(text, file=target, **kwargs)


def to_long_path(path: str) -> str:
    """Prefix a Windows path with \\\\?\\ when needed for long-path support."""
    if os.name != "nt":
        return path
    path = os.path.abspath(path)
    if path.startswith("\\\\?\\"):
        return path
    if path.startswith("\\\\"):
        # UNC: \\server\share -> \\?\UNC\server\share
        return "\\\\?\\UNC\\" + path[2:]
    return "\\\\?\\" + path


def strip_long_path(path: str) -> str:
    if path.startswith("\\\\?\\UNC\\"):
        return "\\" + path[7:]
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


def path_matches_any(rel_path: str, patterns: Sequence[str]) -> bool:
    """Match a relative path against glob patterns (basename and full path)."""
    if not patterns:
        return False
    norm = rel_path.replace("\\", "/")
    base = os.path.basename(norm)
    for pattern in patterns:
        pat = pattern.replace("\\", "/")
        if fnmatch.fnmatch(norm, pat) or fnmatch.fnmatch(base, pat):
            return True
        if "/" not in pat.rstrip("/") and fnmatch.fnmatch(base, pat):
            return True
    return False


def should_include_path(
    rel_path: str, include: Sequence[str], exclude: Sequence[str]
) -> bool:
    if exclude and path_matches_any(rel_path, exclude):
        return False
    if include:
        return path_matches_any(rel_path, include)
    return True


def retry_call(
    fn: Callable,
    retries: int,
    retry_wait: float,
    *args,
    **kwargs,
):
    """Call fn with retries on OSError / IOError."""
    attempt = 0
    while True:
        try:
            return fn(*args, **kwargs)
        except (OSError, IOError):
            attempt += 1
            if attempt > retries:
                raise
            time.sleep(retry_wait)


def validate_buffer_size(buffer_size: int) -> int:
    if buffer_size is None or buffer_size < 1:
        raise ValueError(
            f"Buffer size must be >= 1 byte (got {buffer_size}). "
            "Use -b/--buffer with a positive integer."
        )
    return buffer_size


# --- CORE ENGINE ---


class CopyEngine:
    """Encapsulates the core logic for high-performance file copying."""

    def get_file_list(
        self,
        source_dir: str,
        include: Optional[Sequence[str]] = None,
        exclude: Optional[Sequence[str]] = None,
        collect_empty_dirs: bool = True,
    ):
        """Generates a list of all files (and optional empty dirs) under source_dir."""
        include = include or []
        exclude = exclude or []
        file_list: List[FileEntry] = []
        empty_dirs: List[str] = []
        total_size = 0
        scan_errors: List[Tuple[str, str]] = []

        source_dir_long = to_long_path(source_dir)

        for root, dirs, files in os.walk(source_dir_long):
            rel_root = os.path.relpath(strip_long_path(root), source_dir)
            if rel_root == ".":
                rel_root = ""

            # Prune explicitly excluded directories early (still walk for includes)
            dirs[:] = [
                d
                for d in dirs
                if not (
                    exclude
                    and path_matches_any(
                        os.path.join(rel_root, d) if rel_root else d, exclude
                    )
                )
            ]

            if collect_empty_dirs and not files and not dirs:
                if rel_root and should_include_path(rel_root, include, exclude):
                    empty_dirs.append(rel_root)

            for file in files:
                rel_file = os.path.join(rel_root, file) if rel_root else file
                if not should_include_path(rel_file, include, exclude):
                    continue
                source_path = os.path.join(strip_long_path(root), file)
                try:
                    file_size = os.path.getsize(to_long_path(source_path))
                    total_size += file_size
                    file_list.append((source_path, rel_root or ".", file, file_size))
                except OSError as e:
                    scan_errors.append((source_path, str(e)))

        return file_list, total_size, empty_dirs, scan_errors

    def _should_skip_conflict(
        self, source_path: str, dest_path: str, on_conflict: str
    ) -> bool:
        if on_conflict == "overwrite":
            return False
        if not os.path.exists(to_long_path(dest_path)):
            return False
        if on_conflict == "skip":
            return True
        if on_conflict == "update":
            try:
                src_stat = os.stat(to_long_path(source_path))
                dst_stat = os.stat(to_long_path(dest_path))
                if (
                    src_stat.st_mtime <= dst_stat.st_mtime
                    and src_stat.st_size == dst_stat.st_size
                ):
                    return True
            except OSError:
                return False
        return False

    def _copy_bytes(
        self, source_path: str, dest_path: str, buffer_size: int
    ) -> None:
        src = to_long_path(source_path)
        dst = to_long_path(dest_path)
        parent = os.path.dirname(strip_long_path(dst))
        if parent:
            os.makedirs(to_long_path(parent), exist_ok=True)
        with open(src, "rb") as fsrc, open(dst, "wb") as fdest:
            while True:
                chunk = fsrc.read(buffer_size)
                if not chunk:
                    break
                fdest.write(chunk)

    def _preserve_metadata(self, source_path: str, dest_path: str) -> None:
        try:
            shutil.copystat(to_long_path(source_path), to_long_path(dest_path), follow_symlinks=True)
        except OSError:
            pass

    def _verify_checksum(
        self, file_path: str, original_checksum: str, buffer_size: int
    ) -> bool:
        sha256 = hashlib.sha256()
        try:
            with open(to_long_path(file_path), "rb") as f:
                while True:
                    chunk = f.read(buffer_size)
                    if not chunk:
                        break
                    sha256.update(chunk)
            return sha256.hexdigest() == original_checksum
        except Exception:
            return False

    def _hash_file(self, file_path: str, buffer_size: int) -> str:
        sha256 = hashlib.sha256()
        with open(to_long_path(file_path), "rb") as f:
            while True:
                chunk = f.read(buffer_size)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    def _copy_file_task(
        self,
        source_path: str,
        dest_path: str,
        buffer_size: int,
        verify: bool,
        progress_callback: ProgressCallback,
        on_conflict: str = "overwrite",
        dry_run: bool = False,
        preserve_metadata: bool = True,
        retries: int = 0,
        retry_wait: float = 1.0,
        move: bool = False,
    ):
        """The actual file copy operation performed by a worker thread."""
        try:
            if self._should_skip_conflict(source_path, dest_path, on_conflict):
                progress_callback("skip", os.path.getsize(to_long_path(source_path)))
                return (source_path, None, "skipped")

            if dry_run:
                size = os.path.getsize(to_long_path(source_path))
                progress_callback("file", size)
                return (source_path, None, "dry-run")

            def do_copy():
                original_checksum = None
                if verify:
                    original_checksum = self._hash_file(source_path, buffer_size)

                self._copy_bytes(source_path, dest_path, buffer_size)

                if preserve_metadata:
                    self._preserve_metadata(source_path, dest_path)

                if verify and original_checksum:
                    if not self._verify_checksum(
                        dest_path, original_checksum, buffer_size
                    ):
                        raise Exception("Checksum mismatch")

                if move:
                    try:
                        os.remove(to_long_path(source_path))
                    except OSError as e:
                        raise Exception(f"Copied but failed to remove source: {e}")

            retry_call(do_copy, retries, retry_wait)

            file_size = os.path.getsize(to_long_path(dest_path))
            progress_callback("file", file_size)
            return (source_path, None, "copied")
        except Exception as e:
            progress_callback("file", 0)
            return (source_path, str(e), "error")

    def _mirror_delete_extras(
        self,
        dest_dir: str,
        kept_rel_files: set,
        kept_rel_dirs: set,
        dry_run: bool,
        progress_callback: ProgressCallback,
    ) -> List[Tuple[str, str]]:
        """Delete files/dirs under dest_dir that are not in the source set."""
        errors: List[Tuple[str, str]] = []
        dest_dir = os.path.abspath(dest_dir)
        if not os.path.isdir(to_long_path(dest_dir)):
            return errors

        # Collect dest files
        to_delete_files: List[str] = []
        to_delete_dirs: List[str] = []
        for root, dirs, files in os.walk(to_long_path(dest_dir), topdown=False):
            rel_root = os.path.relpath(strip_long_path(root), dest_dir)
            if rel_root == ".":
                rel_root = ""
            for file in files:
                rel_file = os.path.join(rel_root, file) if rel_root else file
                rel_norm = rel_file.replace("\\", "/")
                kept_norm = {p.replace("\\", "/") for p in kept_rel_files}
                if rel_norm not in kept_norm and rel_file not in kept_rel_files:
                    to_delete_files.append(os.path.join(strip_long_path(root), file))
            for d in dirs:
                rel_d = os.path.join(rel_root, d) if rel_root else d
                # Keep if any kept file lives under it or it is an empty dir we kept
                prefix = rel_d.replace("\\", "/") + "/"
                kept = any(
                    p.replace("\\", "/").startswith(prefix)
                    or p.replace("\\", "/") == rel_d.replace("\\", "/")
                    for p in kept_rel_files
                ) or any(
                    p.replace("\\", "/") == rel_d.replace("\\", "/")
                    for p in kept_rel_dirs
                )
                if not kept:
                    to_delete_dirs.append(os.path.join(strip_long_path(root), d))

        for path in to_delete_files:
            try:
                if dry_run:
                    progress_callback("mirror-delete", path)
                else:
                    os.remove(to_long_path(path))
                    progress_callback("mirror-delete", path)
            except OSError as e:
                errors.append((path, str(e)))

        for path in to_delete_dirs:
            try:
                if dry_run:
                    progress_callback("mirror-delete", path)
                else:
                    os.rmdir(to_long_path(path))
                    progress_callback("mirror-delete", path)
            except OSError:
                # Non-empty or already gone — ignore
                pass

        return errors

    def run_copy(
        self,
        source: str,
        destination: str,
        workers: int,
        buffer_size: int,
        verify: bool,
        progress_callback: ProgressCallback,
        on_conflict: str = "overwrite",
        dry_run: bool = False,
        include: Optional[Sequence[str]] = None,
        exclude: Optional[Sequence[str]] = None,
        preserve_metadata: bool = True,
        retries: int = 0,
        retry_wait: float = 1.0,
        mirror: bool = False,
        move: bool = False,
        copy_empty_dirs: bool = True,
    ):
        """Executes the copy operation for a source file or directory."""
        buffer_size = validate_buffer_size(buffer_size)
        errors: List[Tuple[str, str]] = []
        stats = {
            "copied": 0,
            "skipped": 0,
            "errors": 0,
            "bytes": 0,
            "dry_run": dry_run,
        }

        source = os.path.abspath(source)
        destination = os.path.abspath(destination)

        if not os.path.exists(to_long_path(source)):
            raise FileNotFoundError(f"Source path '{source}' does not exist.")

        # Guard: refuse copying a path onto itself
        if os.path.normcase(source) == os.path.normcase(destination):
            raise ValueError("Source and destination are the same path.")

        if os.path.isdir(to_long_path(source)):
            if os.path.exists(to_long_path(destination)) and not os.path.isdir(
                to_long_path(destination)
            ):
                raise ValueError(f"Cannot copy a directory to a file '{destination}'.")

            # Refuse destination inside source (overlap)
            src_norm = os.path.normcase(source) + os.sep
            dst_norm = os.path.normcase(destination)
            if dst_norm == os.path.normcase(source) or dst_norm.startswith(src_norm):
                raise ValueError(
                    "Destination is inside the source directory; refusing to copy."
                )

            dest_dir = (
                os.path.join(destination, os.path.basename(source))
                if os.path.isdir(to_long_path(destination))
                and os.path.basename(source) != ""
                else destination
            )

            file_list, total_size, empty_dirs, scan_errors = self.get_file_list(
                source, include=include, exclude=exclude, collect_empty_dirs=copy_empty_dirs
            )
            errors.extend(scan_errors)

            if not file_list and not empty_dirs:
                progress_callback("finish", stats)
                return errors, stats

            progress_callback(
                "start",
                {"files": max(len(file_list), 1) if file_list else 0, "bytes": total_size},
            )

            if not dry_run:
                required_dirs = {
                    os.path.join(dest_dir, rel_path if rel_path != "." else "")
                    for _, rel_path, _, _ in file_list
                }
                for d in empty_dirs:
                    required_dirs.add(os.path.join(dest_dir, d))
                for d in required_dirs:
                    d_clean = d.rstrip("\\/") or dest_dir
                    os.makedirs(to_long_path(d_clean), exist_ok=True)

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        self._copy_file_task,
                        src_path,
                        os.path.join(
                            dest_dir,
                            "" if rel_path == "." else rel_path,
                            file_name,
                        ),
                        buffer_size,
                        verify,
                        progress_callback,
                        on_conflict,
                        dry_run,
                        preserve_metadata,
                        retries,
                        retry_wait,
                        move,
                    ): (src_path, rel_path, file_name)
                    for src_path, rel_path, file_name, _ in file_list
                }

                for future in as_completed(futures):
                    path, error, status = future.result()
                    if error:
                        errors.append((path, error))
                        stats["errors"] += 1
                    elif status == "skipped":
                        stats["skipped"] += 1
                    else:
                        stats["copied"] += 1
                        try:
                            stats["bytes"] += os.path.getsize(to_long_path(path))
                        except OSError:
                            pass

            if mirror:
                kept_files = set()
                for _, rel_path, file_name, _ in file_list:
                    if rel_path == ".":
                        kept_files.add(file_name)
                    else:
                        kept_files.add(os.path.join(rel_path, file_name))
                kept_dirs = set(empty_dirs)
                mirror_errors = self._mirror_delete_extras(
                    dest_dir, kept_files, kept_dirs, dry_run, progress_callback
                )
                errors.extend(mirror_errors)
                stats["errors"] += len(mirror_errors)

            if move and not dry_run and not errors:
                # Remove emptied source tree (best effort)
                try:
                    shutil.rmtree(to_long_path(source), ignore_errors=True)
                except OSError:
                    pass
        else:
            # Single file
            if include or exclude:
                name = os.path.basename(source)
                if not should_include_path(name, include or [], exclude or []):
                    progress_callback("start", {"files": 0, "bytes": 0})
                    progress_callback("finish", stats)
                    return errors, stats

            if os.path.isdir(to_long_path(destination)):
                dest_file = os.path.join(destination, os.path.basename(source))
            else:
                dest_file = destination
            parent = os.path.dirname(dest_file)
            if parent and not dry_run:
                os.makedirs(to_long_path(parent), exist_ok=True)

            file_size = os.path.getsize(to_long_path(source))
            progress_callback("start", {"files": 1, "bytes": file_size})

            path, error, status = self._copy_file_task(
                source,
                dest_file,
                buffer_size,
                verify,
                progress_callback,
                on_conflict,
                dry_run,
                preserve_metadata,
                retries,
                retry_wait,
                move,
            )
            if error:
                errors = [(source, error)]
                stats["errors"] = 1
            elif status == "skipped":
                stats["skipped"] = 1
            else:
                stats["copied"] = 1
                stats["bytes"] = file_size

        progress_callback("finish", stats)
        return errors, stats


class UnpackEngine:
    """Encapsulates the logic for unpacking various archive formats."""

    SUPPORTED_EXTS = {".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".bz2", ".xz"}

    def _detect_format(self, archive_path: str) -> str:
        name = archive_path.lower()
        if name.endswith(".tar.gz") or name.endswith(".tgz"):
            return "tar.gz"
        if name.endswith(".tar.bz2") or name.endswith(".tbz2"):
            return "tar.bz2"
        if name.endswith(".tar.xz") or name.endswith(".txz"):
            return "tar.xz"
        if name.endswith(".tar"):
            return "tar"
        _, ext = os.path.splitext(archive_path)
        ext = ext.lower()
        if ext in {".zip", ".7z", ".rar"}:
            return ext.lstrip(".")
        raise ValueError(f"Unsupported archive format: {ext or '(none)'}")

    def list_archive(self, archive_path: str, password: Optional[str] = None) -> List[dict]:
        archive_path = os.path.abspath(archive_path)
        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Archive path '{archive_path}' does not exist.")
        fmt = self._detect_format(archive_path)
        entries: List[dict] = []

        if fmt == "zip":
            with zipfile.ZipFile(archive_path, "r") as zf:
                if password:
                    zf.setpassword(password.encode("utf-8"))
                for info in zf.infolist():
                    entries.append(
                        {
                            "name": info.filename,
                            "size": info.file_size,
                            "is_dir": info.is_dir(),
                        }
                    )
        elif fmt == "7z":
            import py7zr

            pwd = password.encode("utf-8") if password else None
            with py7zr.SevenZipFile(archive_path, mode="r", password=pwd) as z:
                for f in z.list():
                    entries.append(
                        {
                            "name": f.filename,
                            "size": f.uncompressed or 0,
                            "is_dir": f.is_directory,
                        }
                    )
        elif fmt == "rar":
            tool = self._find_7z()
            result = subprocess.run(
                [tool, "l", "-slt", archive_path],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise Exception(f"7-Zip failed to list archive: {result.stderr}")
            current: dict = {}
            for line in result.stdout.splitlines():
                if line.startswith("Path = "):
                    if current.get("name"):
                        entries.append(current)
                    current = {"name": line[7:], "size": 0, "is_dir": False}
                elif line.startswith("Size = ") and current:
                    try:
                        current["size"] = int(line[7:].strip())
                    except ValueError:
                        pass
                elif line.startswith("Attributes = ") and current:
                    current["is_dir"] = "D" in line
            if current.get("name"):
                entries.append(current)
        elif fmt.startswith("tar"):
            mode = {
                "tar": "r:",
                "tar.gz": "r:gz",
                "tar.bz2": "r:bz2",
                "tar.xz": "r:xz",
            }[fmt]
            with tarfile.open(archive_path, mode) as tf:
                for m in tf.getmembers():
                    entries.append(
                        {"name": m.name, "size": m.size, "is_dir": m.isdir()}
                    )
        return entries

    def _find_7z(self) -> str:
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
        else:
            exe_dir = os.path.dirname(os.path.abspath(__file__))
        local = os.path.join(exe_dir, "7z.exe")
        if os.path.exists(local):
            return local
        return "7z"

    def run_unpack(
        self,
        archive_path: str,
        destination_path: str,
        progress_callback: ProgressCallback,
        password: Optional[str] = None,
        dry_run: bool = False,
    ):
        archive_path = os.path.abspath(archive_path)
        destination_path = os.path.abspath(destination_path)

        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Archive path '{archive_path}' does not exist.")

        if not dry_run:
            os.makedirs(destination_path, exist_ok=True)

        fmt = self._detect_format(archive_path)

        if dry_run:
            entries = self.list_archive(archive_path, password=password)
            files = [e for e in entries if not e.get("is_dir")]
            total = sum(e.get("size", 0) for e in files)
            progress_callback("start", {"files": len(files), "bytes": total})
            for e in files:
                progress_callback("file", e.get("size", 0))
            progress_callback("finish", 0)
            return

        if fmt == "zip":
            self._unpack_zip(archive_path, destination_path, progress_callback, password)
        elif fmt == "7z":
            self._unpack_7z(archive_path, destination_path, progress_callback, password)
        elif fmt == "rar":
            self._unpack_rar(archive_path, destination_path, progress_callback, password)
        elif fmt.startswith("tar"):
            self._unpack_tar(archive_path, destination_path, progress_callback, fmt)
        else:
            raise ValueError(f"Unsupported archive format: {fmt}")

        progress_callback("finish", 0)

    def _unpack_zip(self, archive_path, dest_path, callback, password=None):
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            if password:
                zip_ref.setpassword(password.encode("utf-8"))
            members = [m for m in zip_ref.infolist() if not m.is_dir()]
            total_size = sum(f.file_size for f in members)
            callback("start", {"files": len(members), "bytes": total_size})
            for member in zip_ref.infolist():
                zip_ref.extract(member, dest_path)
                if not member.is_dir():
                    callback("file", member.file_size)

    def _unpack_7z(self, archive_path, dest_path, callback, password=None):
        import py7zr

        pwd = password.encode("utf-8") if password else None
        with py7zr.SevenZipFile(archive_path, mode="r", password=pwd) as z:
            members = z.list()
            file_members = [f for f in members if not f.is_directory]
            total_size = sum(f.uncompressed or 0 for f in file_members)
            callback("start", {"files": len(file_members), "bytes": total_size})
            z.extractall(path=dest_path)
            for f in file_members:
                callback("file", f.uncompressed or 0)

    def _unpack_rar(self, archive_path, dest_path, callback, password=None):
        tool = self._find_7z()
        # Estimate via list for progress totals
        try:
            entries = self.list_archive(archive_path)
            files = [e for e in entries if not e.get("is_dir")]
            total_files = max(len(files), 1)
            total_size = max(sum(e.get("size", 0) for e in files), 1)
        except Exception:
            total_files, total_size = 1, 1

        callback("start", {"files": total_files, "bytes": total_size})

        command = [tool, "x", archive_path, f"-o{dest_path}", "-y", "-bsp1"]
        if password:
            command.append(f"-p{password}")
        else:
            command.append("-p-")

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                check=False,
            )
        except FileNotFoundError:
            raise Exception(
                "7z.exe not found. Ensure 7-Zip is installed and in your PATH."
            )

        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            raise Exception(
                f"7-Zip failed to unpack {archive_path} "
                f"(exit {result.returncode}): {err}"
            )

        callback("file", total_size)

    def _unpack_tar(self, archive_path, dest_path, callback, fmt):
        mode = {
            "tar": "r:",
            "tar.gz": "r:gz",
            "tar.bz2": "r:bz2",
            "tar.xz": "r:xz",
        }[fmt]
        with tarfile.open(archive_path, mode) as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            total_size = sum(m.size for m in members)
            callback("start", {"files": len(members), "bytes": total_size})
            tf.extractall(path=dest_path)
            for m in members:
                callback("file", m.size)


# --- GUI (lazy-loaded) ---


def main_gui():
    """Launches the graphical user interface (imports GUI deps only when needed)."""
    import threading

    try:
        import customtkinter as ctk
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as e:
        safe_print(
            "GUI dependencies are not available in this build.\n"
            f"Details: {e}\n"
            "Use CLI mode: supercopy <source> <destination> [options]",
            file=sys.stderr,
        )
        sys.exit(1)

    class SuperCopyApp(ctk.CTk):
        def __init__(self):
            super().__init__()

            self.title("SuperCopy - High Performance File Operations")
            self.geometry("750x650")
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")

            self.grid_columnconfigure(0, weight=1)
            self.grid_columnconfigure(1, weight=3)
            self.grid_columnconfigure(2, weight=1)

            self.source_path = tk.StringVar()
            self.dest_path = tk.StringVar()
            self.verify_files = tk.BooleanVar()
            self.is_unpack_mode = False
            self.is_running = False

            self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.main_frame.grid(
                row=0, column=0, columnspan=3, padx=20, pady=20, sticky="nsew"
            )
            self.main_frame.grid_columnconfigure(1, weight=1)

            self.header_frame = ctk.CTkFrame(
                self.main_frame, height=100, corner_radius=15
            )
            self.header_frame.grid(
                row=0, column=0, columnspan=3, padx=0, pady=(0, 20), sticky="ew"
            )
            self.header_frame.grid_propagate(False)

            self.title_label = ctk.CTkLabel(
                self.header_frame,
                text=" SuperCopy",
                font=ctk.CTkFont(size=32, weight="bold"),
            )
            self.title_label.pack(pady=(20, 5))

            self.subtitle_label = ctk.CTkLabel(
                self.header_frame,
                text="High-Performance File Copying & Archive Unpacking",
                font=ctk.CTkFont(size=14),
                text_color="lightgray",
            )
            self.subtitle_label.pack()

            version = get_version_from_package_json()
            self.version_label = ctk.CTkLabel(
                self.header_frame,
                text=f"Version {version}",
                font=ctk.CTkFont(size=12),
                text_color="gray",
            )
            self.version_label.pack()

            self.source_card = ctk.CTkFrame(self.main_frame)
            self.source_card.grid(
                row=1, column=0, columnspan=3, padx=0, pady=(0, 15), sticky="ew"
            )
            self.source_title = ctk.CTkLabel(
                self.source_card,
                text="Source Location",
                font=ctk.CTkFont(size=16, weight="bold"),
            )
            self.source_title.pack(pady=(15, 10))

            source_inner_frame = ctk.CTkFrame(self.source_card, fg_color="transparent")
            source_inner_frame.pack(fill="x", padx=20, pady=(0, 15))
            source_inner_frame.grid_columnconfigure(1, weight=1)

            self.source_entry = ctk.CTkEntry(
                source_inner_frame,
                textvariable=self.source_path,
                placeholder_text="Select source file or folder...",
            )
            self.source_entry.grid(row=0, column=1, padx=(10, 5), pady=5, sticky="ew")
            self.source_button = ctk.CTkButton(
                source_inner_frame, text="Browse", command=self.browse_source, width=80
            )
            self.source_button.grid(row=0, column=2, padx=5, pady=5)

            self.dest_card = ctk.CTkFrame(self.main_frame)
            self.dest_card.grid(
                row=2, column=0, columnspan=3, padx=0, pady=(0, 15), sticky="ew"
            )
            self.dest_title = ctk.CTkLabel(
                self.dest_card,
                text="Destination Location",
                font=ctk.CTkFont(size=16, weight="bold"),
            )
            self.dest_title.pack(pady=(15, 10))

            dest_inner_frame = ctk.CTkFrame(self.dest_card, fg_color="transparent")
            dest_inner_frame.pack(fill="x", padx=20, pady=(0, 15))
            dest_inner_frame.grid_columnconfigure(1, weight=1)

            self.dest_entry = ctk.CTkEntry(
                dest_inner_frame,
                textvariable=self.dest_path,
                placeholder_text="Select destination folder...",
            )
            self.dest_entry.grid(row=0, column=1, padx=(10, 5), pady=5, sticky="ew")
            self.dest_button = ctk.CTkButton(
                dest_inner_frame,
                text="Browse",
                command=self.browse_destination,
                width=80,
            )
            self.dest_button.grid(row=0, column=2, padx=5, pady=5)

            self.options_card = ctk.CTkFrame(self.main_frame)
            self.options_card.grid(
                row=3, column=0, columnspan=3, padx=0, pady=(0, 20), sticky="ew"
            )
            self.options_title = ctk.CTkLabel(
                self.options_card,
                text="Options",
                font=ctk.CTkFont(size=16, weight="bold"),
            )
            self.options_title.pack(pady=(15, 10))

            self.options_inner_frame = ctk.CTkFrame(
                self.options_card, fg_color="transparent"
            )
            self.options_inner_frame.pack(fill="x", padx=20, pady=(0, 15))

            self.verify_checkbox = ctk.CTkCheckBox(
                self.options_inner_frame,
                text="Verify files after copy (slower but more secure)",
                variable=self.verify_files,
                font=ctk.CTkFont(size=14),
            )
            self.verify_checkbox.pack(anchor="w", pady=5)

            self.action_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
            self.action_frame.grid(
                row=4, column=0, columnspan=3, padx=0, pady=(0, 20), sticky="ew"
            )
            self.action_button = ctk.CTkButton(
                self.action_frame,
                text="Start Operation",
                command=self.start_operation,
                height=50,
                font=ctk.CTkFont(size=16, weight="bold"),
            )
            self.action_button.pack(fill="x", pady=10)

            self.progress_card = ctk.CTkFrame(self.main_frame)
            self.progress_card.grid(
                row=5, column=0, columnspan=3, padx=0, pady=(0, 10), sticky="ew"
            )
            self.progress_title = ctk.CTkLabel(
                self.progress_card,
                text="Progress",
                font=ctk.CTkFont(size=16, weight="bold"),
            )
            self.progress_title.pack(pady=(15, 10))

            self.status_label = ctk.CTkLabel(
                self.progress_card,
                text="Ready to start",
                font=ctk.CTkFont(size=14),
                anchor="w",
            )
            self.status_label.pack(fill="x", padx=20, pady=(0, 10))

            self.files_frame = ctk.CTkFrame(self.progress_card, fg_color="transparent")
            self.files_frame.pack(fill="x", padx=20, pady=(0, 5))
            self.pbar_files_label = ctk.CTkLabel(
                self.files_frame, text="Files Progress:", anchor="w"
            )
            self.pbar_files_label.pack(anchor="w")
            self.pbar_files = ctk.CTkProgressBar(self.progress_card, height=20)
            self.pbar_files.pack(fill="x", padx=20, pady=(0, 10))
            self.pbar_files.set(0)

            self.size_frame = ctk.CTkFrame(self.progress_card, fg_color="transparent")
            self.size_frame.pack(fill="x", padx=20, pady=(0, 5))
            self.pbar_bytes_label = ctk.CTkLabel(
                self.size_frame, text="Data Progress:", anchor="w"
            )
            self.pbar_bytes_label.pack(anchor="w")
            self.pbar_bytes = ctk.CTkProgressBar(self.progress_card, height=20)
            self.pbar_bytes.pack(fill="x", padx=20, pady=(0, 15))
            self.pbar_bytes.set(0)

            self.grid_rowconfigure(0, weight=1)
            self.source_path.trace_add("write", self.update_ui_mode)
            self.bind("<Control-o>", lambda e: self.browse_source())
            self.bind("<Control-d>", lambda e: self.browse_destination())
            self.bind(
                "<Return>",
                lambda e: self.start_operation() if not self.is_running else None,
            )

            self.update_idletasks()
            width = self.winfo_width()
            height = self.winfo_height()
            x = (self.winfo_screenwidth() // 2) - (width // 2)
            y = (self.winfo_screenheight() // 2) - (height // 2)
            self.geometry(f"{width}x{height}+{x}+{y}")
            self.minsize(650, 600)

        def update_ui_mode(self, *args):
            source = self.source_path.get()
            is_archive = any(
                source.lower().endswith(ext)
                for ext in [".zip", ".rar", ".7z", ".tar", ".tgz", ".tar.gz"]
            )
            if is_archive:
                self.is_unpack_mode = True
                self.action_button.configure(text="Unpack Archive")
                self.verify_checkbox.configure(state="disabled")
                self.source_title.configure(text="Archive File")
                self.progress_title.configure(text="Unpacking Progress")
            else:
                self.is_unpack_mode = False
                self.action_button.configure(text="Start Copy")
                self.verify_checkbox.configure(state="normal")
                self.source_title.configure(text="Source Location")
                self.progress_title.configure(text="Progress")

        def set_ui_state(self, is_running):
            state = "disabled" if is_running else "normal"
            self.is_running = is_running
            self.source_entry.configure(state=state)
            self.dest_entry.configure(state=state)
            self.source_button.configure(state=state)
            self.dest_button.configure(state=state)
            self.verify_checkbox.configure(
                state=state if not self.is_unpack_mode else "disabled"
            )
            self.action_button.configure(state=state)
            if is_running:
                self.action_button.configure(text="Processing...")
            else:
                self.update_ui_mode()

        def gui_progress_callback(self, event_type, data):
            if event_type == "start":
                self.total_files = data["files"]
                self.total_bytes = data["bytes"]
                self.copied_files = 0
                self.copied_bytes = 0
                self.pbar_files.set(0)
                self.pbar_bytes.set(0)
                if self.is_unpack_mode:
                    status_text = f"Starting unpacking... Found {self.total_files} items"
                else:
                    status_text = f"Starting copy... Found {self.total_files} files"
                if self.total_bytes > 0:
                    size_mb = self.total_bytes / (1024 * 1024)
                    if size_mb > 1024:
                        size_text = f" ({size_mb / 1024:.1f} GB)"
                    else:
                        size_text = f" ({size_mb:.1f} MB)"
                    status_text += size_text
                self.status_label.configure(text=status_text)
            elif event_type in ("file", "skip"):
                self.copied_files += 1
                self.copied_bytes += data if isinstance(data, (int, float)) else 0
                file_progress = (
                    self.copied_files / self.total_files if self.total_files > 0 else 0
                )
                byte_progress = (
                    self.copied_bytes / self.total_bytes if self.total_bytes > 0 else 0
                )
                self.pbar_files.set(file_progress)
                self.pbar_bytes.set(byte_progress)
                elapsed_time = time.time() - getattr(self, "start_time", time.time())
                eta_text = ""
                if elapsed_time > 0 and self.copied_bytes > 0:
                    bytes_per_second = self.copied_bytes / elapsed_time
                    if bytes_per_second > 0:
                        remaining_bytes = self.total_bytes - self.copied_bytes
                        eta_seconds = remaining_bytes / bytes_per_second
                        if eta_seconds < 60:
                            eta_text = f" - ETA: {eta_seconds:.0f}s"
                        elif eta_seconds < 3600:
                            eta_text = f" - ETA: {eta_seconds / 60:.0f}m"
                        else:
                            eta_text = f" - ETA: {eta_seconds / 3600:.1f}h"
                if self.is_unpack_mode:
                    status_text = (
                        f"Extracted: {self.copied_files}/{self.total_files} files{eta_text}"
                    )
                else:
                    status_text = (
                        f"Copied: {self.copied_files}/{self.total_files} files{eta_text}"
                    )
                self.status_label.configure(text=status_text)
            elif event_type == "finish":
                if self.is_unpack_mode:
                    self.status_label.configure(
                        text="Archive unpacking completed successfully!"
                    )
                else:
                    self.status_label.configure(
                        text="File copying completed successfully!"
                    )
                self.set_ui_state(False)

        def start_operation(self):
            source = self.source_path.get()
            dest = self.dest_path.get()
            if not source or not dest:
                self.status_label.configure(
                    text="Error: Please select both source and destination paths."
                )
                return
            if not os.path.exists(source):
                self.status_label.configure(
                    text=f"Error: Source path does not exist: {source}"
                )
                return
            dest_dir = os.path.dirname(dest) if os.path.isfile(dest) else dest
            if dest_dir and not os.path.exists(dest_dir):
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                except Exception as e:
                    self.status_label.configure(
                        text=f"Error: Cannot create destination directory: {e}"
                    )
                    return

            self.start_time = time.time()
            self.set_ui_state(True)

            if self.is_unpack_mode:
                thread = threading.Thread(
                    target=self._safe_run_unpack,
                    args=(source, dest, self.gui_progress_callback),
                )
            else:
                thread = threading.Thread(
                    target=self._safe_run_copy,
                    args=(
                        source,
                        dest,
                        os.cpu_count() or 4,
                        1048576,
                        self.verify_files.get(),
                        self.gui_progress_callback,
                    ),
                )
            thread.daemon = True
            thread.start()

        def _safe_run_copy(self, source, dest, workers, buffer_size, verify, callback):
            try:
                engine = CopyEngine()
                errors, _stats = engine.run_copy(
                    source, dest, workers, buffer_size, verify, callback
                )
                if errors:
                    self.after(0, lambda: self._show_errors(errors))
            except Exception as e:
                self.after(0, lambda: self._show_operation_error(str(e)))

        def _safe_run_unpack(self, source, dest, callback):
            try:
                engine = UnpackEngine()
                engine.run_unpack(source, dest, callback)
            except Exception as e:
                self.after(0, lambda: self._show_operation_error(str(e)))

        def _show_errors(self, errors):
            self.set_ui_state(False)
            error_count = len(errors)
            self.status_label.configure(
                text=f"Operation completed with {error_count} errors. Check console for details."
            )
            safe_print(f"\nCopy Operation completed with {error_count} errors:")
            for path, msg in errors:
                safe_print(f"  - {path}: {msg}")
            safe_print("-" * 50)

        def _show_operation_error(self, error_msg):
            self.set_ui_state(False)
            self.status_label.configure(text=f"Operation failed: {error_msg}")
            safe_print(f"\nOperation failed: {error_msg}")

        def browse_source(self):
            current_path = self.source_path.get()
            try:
                is_file = os.path.isfile(current_path)
            except Exception:
                is_file = False
            if is_file or any(
                current_path.lower().endswith(ext)
                for ext in [".zip", ".rar", ".7z", ".tar", ".tgz", ".gz"]
            ):
                path = filedialog.askopenfilename(
                    title="Select a source file",
                    filetypes=[
                        ("All Files", "*.*"),
                        ("ZIP Archive", "*.zip"),
                        ("7-Zip Archive", "*.7z"),
                        ("RAR Archive", "*.rar"),
                        ("TAR Archives", "*.tar;*.tar.gz;*.tgz;*.tar.bz2;*.tar.xz"),
                    ],
                )
            else:
                path = filedialog.askdirectory(title="Select a source folder")
            if path:
                self.source_path.set(path)

        def browse_destination(self):
            path = filedialog.askdirectory(title="Select destination folder")
            if path:
                self.dest_path.set(path)

    app = SuperCopyApp()
    app.mainloop()


# --- CLI ---


def get_parser():
    """Defines and returns the ArgumentParser for CLI mode."""
    current_version = get_version_from_package_json()
    parser = argparse.ArgumentParser(
        prog="supercopy",
        description="A high-performance file copy and unpack tool.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Commands:\n"
            "  completion [bash|zsh|powershell]  Generate shell completion scripts.\n"
            "\n"
            "Examples:\n"
            "  supercopy C:\\src D:\\dst\n"
            "  supercopy C:\\src D:\\dst --on-conflict skip --exclude '*.tmp'\n"
            "  supercopy archive.zip D:\\out --unpack\n"
            "  supercopy archive.zip --list\n"
        ),
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {current_version}",
        help="Show program's version number and exit.",
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="Source file/directory, or archive path (or 'completion').",
    )
    parser.add_argument(
        "destination",
        nargs="?",
        help="Destination file or directory.",
    )
    parser.add_argument(
        "--unpack",
        action="store_true",
        help="Unpack mode: extract archive to destination.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List archive contents (no extraction). Source must be an archive.",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=os.cpu_count() or 4,
        help="Concurrent copy threads (copy mode only).",
    )
    parser.add_argument(
        "-b",
        "--buffer",
        type=int,
        default=1048576,
        help="I/O buffer size in bytes (copy mode; must be >= 1).",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="SHA-256 verify after each file copy (copy mode only).",
    )
    parser.add_argument(
        "--on-conflict",
        choices=["overwrite", "skip", "update"],
        default="overwrite",
        help="When destination exists: overwrite, skip, or update if newer/different size.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing files.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="Exclude paths matching GLOB (repeatable).",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="GLOB",
        help="Only include paths matching GLOB (repeatable).",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress bars and non-error output.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print a JSON summary to stdout when finished.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=0,
        help="Retry count for locked/transient I/O errors (default: 0).",
    )
    parser.add_argument(
        "--retry-wait",
        type=float,
        default=1.0,
        help="Seconds to wait between retries (default: 1.0).",
    )
    parser.add_argument(
        "--mirror",
        action="store_true",
        help="After copy, delete destination files not present in source (dangerous).",
    )
    parser.add_argument(
        "--move",
        action="store_true",
        help="Move files (copy then remove source).",
    )
    parser.add_argument(
        "--no-empty-dirs",
        action="store_true",
        help="Do not recreate empty directories from the source tree.",
    )
    parser.add_argument(
        "--no-preserve-metadata",
        action="store_true",
        help="Do not copy mtime/attributes after writing file bytes.",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Password for encrypted archives (unpack/list).",
    )
    return parser


def _one_line_help(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.replace("\n", " ").split())


def generate_completion(parser, shell):
    """Generates shell completion scripts for supercopy and scpy."""
    options = []
    for action in parser._actions:
        options.extend(action.option_strings)
    options = sorted(set(opt for opt in options if opt.startswith("-")))
    commands = ["supercopy", "SuperCopy", "scpy"]

    if shell == "powershell":
        options_str = "@('" + "', '".join(options) + "')"
        cmds = ", ".join(f"'{c}'" for c in commands)
        print(
            f"""
$scriptBlock = {{
    param($wordToComplete, $commandAst, $cursorPosition)
    $choices = {options_str}
    $matches = $choices | Where-Object {{ $_ -like "$wordToComplete*" }}
    if ($matches) {{
        $matches | ForEach-Object {{
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterName', $_)
        }}
    }} else {{
        # Fall back to path completion when no flag matches
        Get-ChildItem -Path "$wordToComplete*" -ErrorAction SilentlyContinue | ForEach-Object {{
            $name = $_.FullName
            if ($_.PSIsContainer) {{ $name += [IO.Path]::DirectorySeparatorChar }}
            [System.Management.Automation.CompletionResult]::new($name, $_.Name, 'ProviderItem', $name)
        }}
    }}
}}
foreach ($cmd in @({cmds})) {{
    Register-ArgumentCompleter -Native -CommandName $cmd -ScriptBlock $scriptBlock
}}
"""
        )
    elif shell == "bash":
        options_str = " ".join(options)
        cmd_list = " ".join(commands)
        print(
            f"""
_supercopy_completion() {{
    local cur opts
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    opts="{options_str}"
    if [[ "$cur" == -* ]]; then
        COMPREPLY=( $(compgen -W "${{opts}}" -- ${{cur}}) )
    else
        COMPREPLY=( $(compgen -f -- ${{cur}}) )
    fi
    return 0
}}
for cmd in {cmd_list}; do
    complete -o filenames -F _supercopy_completion "$cmd"
done
"""
        )
    elif shell == "zsh":
        opts_with_help = []
        for action in parser._actions:
            if action.option_strings:
                help_text = _one_line_help(action.help)
                help_text = (
                    help_text.replace("'", "'\\''")
                    .replace("[", "\\[")
                    .replace("]", "\\]")
                )
                for opt in action.option_strings:
                    opts_with_help.append(f"'{opt}[{help_text}]'")
        opts_str = " \\\n        ".join(opts_with_help)
        print(
            f"""
#compdef supercopy SuperCopy scpy

_supercopy() {{
    _arguments \\
        {opts_str} \\
        '*:file:_files'
}}

compdef _supercopy supercopy SuperCopy scpy
"""
        )
    else:
        raise ValueError(f"Unsupported shell: {shell}")


def main_cli(argv: Optional[Sequence[str]] = None):
    """Function to run the tool in command-line mode."""
    parser = get_parser()
    argv = list(argv) if argv is not None else sys.argv[1:]

    if len(argv) > 0 and argv[0] == "completion":
        shell = argv[1] if len(argv) > 1 else "powershell"
        if shell not in ["bash", "zsh", "powershell"]:
            safe_print(
                f"Error: Invalid shell '{shell}'. Choices are bash, zsh, powershell.",
                file=sys.stderr,
            )
            return 1
        generate_completion(parser, shell)
        return 0

    args = parser.parse_args(argv)

    if args.list:
        if not args.source:
            parser.print_help()
            return 1
        try:
            engine = UnpackEngine()
            entries = engine.list_archive(args.source, password=args.password)
            if args.json_output:
                print(json.dumps({"archive": args.source, "entries": entries}, indent=2))
            else:
                for e in entries:
                    kind = "DIR " if e.get("is_dir") else "FILE"
                    safe_print(f"{kind}  {e.get('size', 0):>12}  {e.get('name')}")
            return 0
        except Exception as e:
            safe_print(f"Error: {e}", file=sys.stderr)
            return 1

    if not args.source or not args.destination:
        parser.print_help()
        safe_print("\nCommands:")
        safe_print(
            "  completion [bash|zsh|powershell]  Generate shell completion scripts."
        )
        return 1

    # Validate buffer early for copy mode
    if not args.unpack:
        try:
            validate_buffer_size(args.buffer)
        except ValueError as e:
            safe_print(f"Error: {e}", file=sys.stderr)
            return 2

    # Warn / refuse copy-only flags with unpack
    if args.unpack:
        unused = []
        if args.verify:
            unused.append("--verify")
        if args.workers != (os.cpu_count() or 4):
            unused.append("--workers")
        if args.buffer != 1048576:
            unused.append("--buffer")
        if args.on_conflict != "overwrite":
            unused.append("--on-conflict")
        if args.mirror:
            unused.append("--mirror")
        if args.move:
            unused.append("--move")
        if unused and not args.quiet:
            safe_print(
                f"Warning: ignored in unpack mode: {', '.join(unused)}",
                file=sys.stderr,
            )

    if args.mirror and not args.dry_run and not args.quiet:
        safe_print(
            "Warning: --mirror will delete destination files not in source.",
            file=sys.stderr,
        )

    quiet = args.quiet or args.json_output
    pbar_files = None
    pbar_bytes = None
    start_time = time.time()
    mirror_deletes: List[str] = []

    def cli_progress_callback(event_type, data):
        nonlocal pbar_files, pbar_bytes
        if quiet:
            if event_type == "mirror-delete":
                mirror_deletes.append(str(data))
            return
        if event_type == "start":
            pbar_files = tqdm(total=data["files"], unit="file", desc="Files")
            pbar_bytes = tqdm(
                total=data["bytes"],
                unit="B",
                desc="Size ",
                unit_scale=True,
                unit_divisor=1024,
            )
        elif event_type in ("file", "skip"):
            if pbar_files:
                pbar_files.update(1)
            if pbar_bytes and isinstance(data, (int, float)) and data > 0:
                pbar_bytes.update(data)
        elif event_type == "mirror-delete":
            mirror_deletes.append(str(data))
            if not quiet:
                safe_print(f"mirror delete: {data}", file=sys.stderr)
        elif event_type == "finish":
            if pbar_files:
                pbar_files.close()
            if pbar_bytes:
                pbar_bytes.close()

    try:
        if args.unpack:
            if not quiet:
                safe_print(f"Unpacking {args.source} to {args.destination}...")
            engine = UnpackEngine()
            engine.run_unpack(
                args.source,
                args.destination,
                cli_progress_callback,
                password=args.password,
                dry_run=args.dry_run,
            )
            elapsed = time.time() - start_time
            summary = {
                "ok": True,
                "mode": "unpack",
                "source": args.source,
                "destination": args.destination,
                "dry_run": args.dry_run,
                "elapsed_sec": round(elapsed, 3),
            }
            if args.json_output:
                print(json.dumps(summary))
            elif not quiet:
                safe_print("\nUnpacking completed successfully!")
            return 0

        if not quiet:
            verb = "Moving" if args.move else "Copying"
            if args.dry_run:
                verb = f"[dry-run] {verb}"
            safe_print(f"{verb} {args.source} to {args.destination}...")

        engine = CopyEngine()
        errors, stats = engine.run_copy(
            args.source,
            args.destination,
            args.workers,
            args.buffer,
            args.verify,
            cli_progress_callback,
            on_conflict=args.on_conflict,
            dry_run=args.dry_run,
            include=args.include,
            exclude=args.exclude,
            preserve_metadata=not args.no_preserve_metadata,
            retries=args.retries,
            retry_wait=args.retry_wait,
            mirror=args.mirror,
            move=args.move,
            copy_empty_dirs=not args.no_empty_dirs,
        )

        elapsed = time.time() - start_time
        summary = {
            "ok": len(errors) == 0,
            "mode": "move" if args.move else "copy",
            "source": args.source,
            "destination": args.destination,
            "copied": stats.get("copied", 0),
            "skipped": stats.get("skipped", 0),
            "errors": len(errors),
            "bytes": stats.get("bytes", 0),
            "elapsed_sec": round(elapsed, 3),
            "dry_run": args.dry_run,
            "mirror_deletes": len(mirror_deletes),
            "error_details": [{"path": p, "message": m} for p, m in errors],
        }

        if args.json_output:
            print(json.dumps(summary))
        elif not quiet:
            safe_print("\n----- Copy Operation Summary -----")
            if not errors:
                safe_print(
                    f"OK: copied={stats.get('copied', 0)} "
                    f"skipped={stats.get('skipped', 0)} "
                    f"bytes={stats.get('bytes', 0)} "
                    f"elapsed={elapsed:.2f}s"
                )
            else:
                safe_print(f"Completed with {len(errors)} errors.", file=sys.stderr)
                for path, msg in errors:
                    safe_print(f"  - {path}: {msg}", file=sys.stderr)
            safe_print("------------------------------------")

        return 1 if errors else 0

    except Exception as e:
        if args.json_output:
            print(json.dumps({"ok": False, "error": str(e)}))
        else:
            safe_print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    is_cli_mode = len(sys.argv) > 1

    if is_cli_mode:
        sys.exit(main_cli())
    else:
        try:
            import ctypes

            console_window = ctypes.windll.kernel32.GetConsoleWindow()
            if console_window != 0:
                ctypes.windll.user32.ShowWindow(console_window, 0)
        except Exception:
            pass
        main_gui()
