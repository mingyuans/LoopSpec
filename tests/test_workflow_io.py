import os
from pathlib import Path

import pytest

from loopspec.errors import WorkflowError
from loopspec.workflow_io import (
    ResourceBundle,
    append_text,
    atomic_write,
    read_bytes,
    read_capped,
    relative_path,
    write_lock,
)


@pytest.mark.parametrize("path", ["../x", "/x", "a/../x", "a//x", "a\\x", "a\nx", "."])
def test_unsafe_relative(path):
    with pytest.raises(WorkflowError):
        relative_path(path)


def test_symlink_and_parent_escape(tmp_path: Path):
    (tmp_path / "real").mkdir()
    (tmp_path / "real/a").write_text("safe")
    (tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
    (tmp_path / "file").symlink_to(tmp_path / "real/a")
    for name in ["link/a", "file"]:
        with pytest.raises(WorkflowError):
            read_bytes(tmp_path, name)
    with pytest.raises(WorkflowError):
        atomic_write(tmp_path, "link/a", b"changed")
    assert (tmp_path / "real/a").read_text() == "safe"


def test_bounded_single_read_and_atomic_write(tmp_path: Path):
    atomic_write(tmp_path, "a/b.md", b"first")
    bundle = ResourceBundle(tmp_path)
    assert bundle.read("a/b.md") == b"first"
    atomic_write(tmp_path, "a/b.md", b"second")
    assert bundle.read("a/b.md") == b"first"
    with pytest.raises(WorkflowError):
        read_bytes(tmp_path, "a/b.md", limit=2)
    with pytest.raises(WorkflowError):
        atomic_write(tmp_path, "a/b.md", b"override", exclusive=True)
    assert read_bytes(tmp_path, "a/b.md") == b"second"


def test_lock_is_exclusive(tmp_path: Path):
    with write_lock(tmp_path):
        with pytest.raises(WorkflowError):
            with write_lock(tmp_path):
                pass


def test_replacement_during_read_is_rejected(tmp_path: Path, monkeypatch):
    (tmp_path / "a").write_bytes(b"original")
    (tmp_path / "replacement").write_bytes(b"replacement")
    original_read = os.read
    replaced = False

    def replace_after_read(fd, count):
        nonlocal replaced
        data = original_read(fd, count)
        if not replaced:
            replaced = True
            os.replace(tmp_path / "replacement", tmp_path / "a")
        return data

    monkeypatch.setattr(os, "read", replace_after_read)
    with pytest.raises(WorkflowError, match="变化"):
        read_bytes(tmp_path, "a")


def test_append_creates_keeps_and_separates_lines(tmp_path: Path):
    append_text(tmp_path, "state.md", "- one\n")
    (tmp_path / "state.md").write_bytes(b"- one\nno newline")
    append_text(tmp_path, "state.md", "- two\n")
    assert (tmp_path / "state.md").read_bytes() == b"- one\nno newline\n- two\n"


def test_append_refuses_symlinks_and_directories(tmp_path: Path):
    (tmp_path / "outside.md").write_text("outside\n")
    (tmp_path / "link.md").symlink_to(tmp_path / "outside.md")
    (tmp_path / "dir.md").mkdir()
    for name in ("link.md", "dir.md"):
        with pytest.raises(WorkflowError):
            append_text(tmp_path, name, "- x\n")
    assert (tmp_path / "outside.md").read_text() == "outside\n"


def test_read_capped_returns_head_and_tail(tmp_path: Path):
    assert read_capped(tmp_path, "missing.md", 8) is None
    (tmp_path / "small.md").write_bytes(b"12345678")
    assert read_capped(tmp_path, "small.md", 8) == (b"12345678", b"", 8)
    (tmp_path / "big.md").write_bytes(b"abcd" + b"x" * 10 + b"wxyz")
    assert read_capped(tmp_path, "big.md", 8) == (b"abcd", b"wxyz", 18)
    (tmp_path / "link.md").symlink_to(tmp_path / "small.md")
    with pytest.raises(WorkflowError):
        read_capped(tmp_path, "link.md", 8)


def test_append_and_capped_read_refuse_hard_links(tmp_path: Path):
    (tmp_path / "outside.md").write_text("outside\n")
    os.link(tmp_path / "outside.md", tmp_path / "state.md")
    with pytest.raises(WorkflowError):
        append_text(tmp_path, "state.md", "- x\n")
    with pytest.raises(WorkflowError):
        read_capped(tmp_path, "state.md", 8)
    assert (tmp_path / "outside.md").read_text() == "outside\n"
