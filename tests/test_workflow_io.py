import os
from pathlib import Path

import pytest

from loopspec.errors import WorkflowError
from loopspec.workflow_io import ResourceBundle, atomic_write, read_bytes, relative_path, write_lock


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
