"""CLI-focused tests for SuperCopy (no GUI / no frozen exe required)."""

from __future__ import annotations

import json
import os
import sys
import time
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import supercopy  # noqa: E402


def _write(p: Path, data: bytes = b"hello") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def test_buffer_rejects_zero():
    with pytest.raises(ValueError, match="Buffer size must be >= 1"):
        supercopy.validate_buffer_size(0)


def test_buffer_rejects_negative():
    with pytest.raises(ValueError, match="Buffer size must be >= 1"):
        supercopy.validate_buffer_size(-1)


def test_cli_buffer_zero_exits_2(tmp_path: Path):
    src = _write(tmp_path / "a.txt")
    dst = tmp_path / "out.txt"
    code = supercopy.main_cli(
        [str(src), str(dst), "-b", "0", "--quiet"]
    )
    assert code == 2
    assert not dst.exists()


def test_copy_success_exit_0(tmp_path: Path):
    src = _write(tmp_path / "a.txt", b"abc")
    dst = tmp_path / "b.txt"
    code = supercopy.main_cli([str(src), str(dst), "--quiet"])
    assert code == 0
    assert dst.read_bytes() == b"abc"


def test_copy_errors_exit_nonzero(tmp_path: Path, monkeypatch):
    src = _write(tmp_path / "a.txt", b"abc")
    dst = tmp_path / "b.txt"

    def boom(*_a, **_k):
        raise OSError("simulated failure")

    monkeypatch.setattr(supercopy.CopyEngine, "_copy_bytes", boom)
    code = supercopy.main_cli([str(src), str(dst), "--quiet"])
    assert code == 1


def test_on_conflict_skip(tmp_path: Path):
    src = _write(tmp_path / "src" / "f.txt", b"new")
    dst_dir = tmp_path / "dst"
    dest_file = _write(dst_dir / "src" / "f.txt", b"old")
    # Destination already exists as directory named differently —
    # copy into dst creates dst/src/f.txt when dst exists.
    code = supercopy.main_cli(
        [str(tmp_path / "src"), str(dst_dir), "--on-conflict", "skip", "--quiet"]
    )
    assert code == 0
    # When dst_dir exists, engine nests into dst_dir/src
    nested = dst_dir / "src" / "f.txt"
    assert nested.read_bytes() == b"old"


def test_on_conflict_update_skips_same(tmp_path: Path):
    src_file = _write(tmp_path / "src" / "f.txt", b"same")
    dst_root = tmp_path / "dst"
    nested = _write(dst_root / "src" / "f.txt", b"same")
    # Align mtimes so update treats as unchanged
    mtime = time.time() - 10
    os.utime(src_file, (mtime, mtime))
    os.utime(nested, (mtime, mtime))

    code = supercopy.main_cli(
        [str(tmp_path / "src"), str(dst_root), "--on-conflict", "update", "--quiet"]
    )
    assert code == 0
    assert nested.read_bytes() == b"same"


def test_dry_run_does_not_write(tmp_path: Path):
    src = _write(tmp_path / "a.txt", b"data")
    dst = tmp_path / "b.txt"
    code = supercopy.main_cli([str(src), str(dst), "--dry-run", "--quiet"])
    assert code == 0
    assert not dst.exists()


def test_exclude_glob(tmp_path: Path):
    _write(tmp_path / "src" / "keep.txt", b"1")
    _write(tmp_path / "src" / "skip.tmp", b"2")
    dst = tmp_path / "dst"
    dst.mkdir()
    code = supercopy.main_cli(
        [str(tmp_path / "src"), str(dst), "--exclude", "*.tmp", "--quiet"]
    )
    assert code == 0
    assert (dst / "src" / "keep.txt").exists()
    assert not (dst / "src" / "skip.tmp").exists()


def test_empty_dirs_copied(tmp_path: Path):
    empty = tmp_path / "src" / "empty"
    empty.mkdir(parents=True)
    _write(tmp_path / "src" / "f.txt", b"x")
    dst = tmp_path / "dst"
    dst.mkdir()
    code = supercopy.main_cli([str(tmp_path / "src"), str(dst), "--quiet"])
    assert code == 0
    assert (dst / "src" / "empty").is_dir()


def test_json_summary(tmp_path: Path, capsys):
    src = _write(tmp_path / "a.txt", b"xyz")
    dst = tmp_path / "b.txt"
    code = supercopy.main_cli([str(src), str(dst), "--json"])
    assert code == 0
    out = capsys.readouterr().out.strip()
    data = json.loads(out)
    assert data["ok"] is True
    assert data["copied"] == 1
    assert data["bytes"] == 3


def test_preserve_mtime(tmp_path: Path):
    src = _write(tmp_path / "a.txt", b"abc")
    past = time.time() - 3600
    os.utime(src, (past, past))
    dst = tmp_path / "b.txt"
    code = supercopy.main_cli([str(src), str(dst), "--quiet"])
    assert code == 0
    assert abs(os.path.getmtime(dst) - past) < 2


def test_list_zip(tmp_path: Path, capsys):
    zpath = tmp_path / "a.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("inside.txt", "hi")
    code = supercopy.main_cli([str(zpath), "--list", "--quiet"])
    assert code == 0
    out = capsys.readouterr().out
    assert "inside.txt" in out


def test_completion_powershell_includes_scpy(capsys):
    code = supercopy.main_cli(["completion", "powershell"])
    assert code == 0
    out = capsys.readouterr().out
    assert "scpy" in out
    assert "--on-conflict" in out or "--dry-run" in out


def test_completion_zsh_no_raw_newlines_in_help(capsys):
    code = supercopy.main_cli(["completion", "zsh"])
    assert code == 0
    out = capsys.readouterr().out
    # Help text inside option brackets should be single-line fragments
    for line in out.splitlines():
        if line.strip().startswith("'--"):
            # Bracket content should not contain unescaped newlines
            assert "\n" not in line or line.endswith("\\")


def test_path_matches_and_filters():
    assert supercopy.path_matches_any("foo/bar.tmp", ["*.tmp"])
    assert supercopy.should_include_path("a.txt", [], ["*.tmp"])
    assert not supercopy.should_include_path("a.tmp", [], ["*.tmp"])
    assert supercopy.should_include_path("a.txt", ["*.txt"], [])
    assert not supercopy.should_include_path("a.tmp", ["*.txt"], [])


def test_mirror_deletes_extra(tmp_path: Path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write(src / "keep.txt", b"1")
    dst.mkdir()
    # After copy, dest nests as dst/src/
    _write(dst / "src" / "keep.txt", b"1")
    _write(dst / "src" / "extra.txt", b"gone")
    code = supercopy.main_cli(
        [str(src), str(dst), "--mirror", "--quiet"]
    )
    assert code == 0
    assert (dst / "src" / "keep.txt").exists()
    assert not (dst / "src" / "extra.txt").exists()
