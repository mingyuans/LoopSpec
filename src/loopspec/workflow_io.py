"""有界读取和基于目录描述符的安全写入；不跟随符号链接。"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from .errors import WorkflowError
from .workflow_yaml import parse_yaml

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_BUNDLE_BYTES = 16 * 1024 * 1024
_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
ModelT = TypeVar("ModelT", bound=BaseModel)


def relative_path(value: str, *, glob: bool = False) -> str:
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise WorkflowError("unsafe_path", "路径必须是安全相对路径")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise WorkflowError("unsafe_path", "路径包含非法目录分量")
    if not glob and any(c in value for c in "*?["):
        raise WorkflowError("unsafe_path", "此路径不能使用通配符")
    return PurePosixPath(value).as_posix()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def byte_hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _open_absolute(root: Path) -> int:
    path = Path(os.path.abspath(root))
    current = os.open("/", _DIRECTORY)
    try:
        for part in path.parts[1:]:
            following = os.open(part, _DIRECTORY, dir_fd=current)
            os.close(current)
            current = following
        return current
    except OSError:
        os.close(current)
        raise


def _walk(root: Path, parts: list[str], create: bool = False) -> int:
    current = _open_absolute(root)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=current)
                except FileExistsError:
                    pass
            following = os.open(part, _DIRECTORY, dir_fd=current)
            os.close(current)
            current = following
        return current
    except OSError:
        os.close(current)
        raise


def _identity(fd: int) -> tuple[int, int]:
    info = os.fstat(fd)
    return info.st_dev, info.st_ino


@contextmanager
def directory(
    root: Path, path: str = "", *, create: bool = False, relocated_root: Path | None = None
) -> Iterator[int]:
    parts = relative_path(path).split("/") if path else []
    fd = -1
    try:
        fd = _walk(root, parts, create)
        yield fd
        try:
            check = _walk(root, parts)
        except FileNotFoundError:
            if relocated_root is None:
                raise
            check = _walk(relocated_root, parts)
        try:
            if _identity(fd) != _identity(check):
                raise WorkflowError("concurrent_path_change", "操作期间目录身份变化")
        finally:
            os.close(check)
    except OSError as exc:
        raise WorkflowError("unsafe_path", "路径不存在、不可访问或包含符号链接") from exc
    finally:
        if fd >= 0:
            os.close(fd)


def read_bytes(root: Path, path: str, *, limit: int = MAX_FILE_BYTES) -> bytes:
    parts = relative_path(path).split("/")
    with directory(root, "/".join(parts[:-1])) as parent:
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
                raise WorkflowError("resource_limit", "输入不是普通文件或超过读取限额")
            data = bytearray()
            while len(data) <= limit:
                piece = os.read(fd, min(65536, limit + 1 - len(data)))
                if not piece:
                    break
                data.extend(piece)
            after = os.fstat(fd)
            linked = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
            attrs = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
            if any(getattr(before, a) != getattr(after, a) for a in attrs):
                raise WorkflowError("concurrent_source_change", "读取期间文件内容变化")
            if (linked.st_dev, linked.st_ino) != (after.st_dev, after.st_ino):
                raise WorkflowError("concurrent_path_change", "读取期间文件身份变化")
            if len(data) > limit:
                raise WorkflowError("resource_limit", "输入超过读取限额")
            return bytes(data)
        finally:
            os.close(fd)


def exists(root: Path, path: str) -> bool:
    parts = relative_path(path).split("/")
    try:
        with directory(root, "/".join(parts[:-1])) as parent:
            info = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                raise WorkflowError("unsafe_path", "产物必须是普通文件")
        return True
    except WorkflowError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            return False
        raise


def atomic_write(root: Path, path: str, data: bytes, *, exclusive: bool = False) -> None:
    parts = relative_path(path).split("/")
    with directory(root, "/".join(parts[:-1]), create=True) as parent:
        temporary = ".write-" + uuid.uuid4().hex
        fd = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if exclusive:
                os.link(
                    temporary,
                    parts[-1],
                    src_dir_fd=parent,
                    dst_dir_fd=parent,
                    follow_symlinks=False,
                )
            else:
                os.replace(temporary, parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)
        finally:
            try:
                os.unlink(temporary, dir_fd=parent)
            except FileNotFoundError:
                pass


def write_json(root: Path, path: str, value: Any, *, exclusive: bool = False) -> None:
    atomic_write(root, path, canonical(value) + b"\n", exclusive=exclusive)


def write_yaml(root: Path, path: str, value: Any, *, exclusive: bool = False) -> None:
    text = yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=1000)
    atomic_write(root, path, text.encode("utf-8"), exclusive=exclusive)


def unlink_file(root: Path, path: str) -> None:
    parts = relative_path(path).split("/")
    with directory(root, "/".join(parts[:-1])) as fd:
        info = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError("unsafe_path", "只允许删除明确的普通控制文件")
        os.unlink(parts[-1], dir_fd=fd)
        os.fsync(fd)


def archive_file(root: Path, source: str, destination: str) -> None:
    src, dst = relative_path(source).split("/"), relative_path(destination).split("/")
    with directory(root, "/".join(src[:-1])) as srcfd:
        with directory(root, "/".join(dst[:-1]), create=True) as dstfd:
            try:
                os.stat(dst[-1], dir_fd=dstfd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise WorkflowError("archive_conflict", "归档目标已存在，不能覆盖")
            if not stat.S_ISREG(os.stat(src[-1], dir_fd=srcfd, follow_symlinks=False).st_mode):
                raise WorkflowError("unsafe_path", "归档源必须是普通文件")
            os.rename(src[-1], dst[-1], src_dir_fd=srcfd, dst_dir_fd=dstfd)
            os.fsync(srcfd)
            os.fsync(dstfd)


@contextmanager
def write_lock(root: Path, *, relocated_root: Path | None = None) -> Iterator[None]:
    # The lock lives under plans/, which the Git diff already excludes as a control directory.
    with directory(root, "plans", create=True, relocated_root=relocated_root) as parent:
        fd = os.open(".write.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise WorkflowError("unsafe_path", "写锁不是普通文件")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        except BlockingIOError as exc:
            raise WorkflowError("concurrent_write", "该需求正在执行其他写操作") from exc
        finally:
            os.close(fd)


class ResourceBundle:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.files: dict[str, bytes] = {}
        self.total = 0

    def read(self, path: str) -> bytes:
        path = relative_path(path)
        if path not in self.files:
            value = read_bytes(self.root, path)
            self.total += len(value)
            if self.total > MAX_BUNDLE_BYTES or len(self.files) >= 2048:
                raise WorkflowError("resource_limit", "编译资源超过累计限额")
            self.files[path] = value
        return self.files[path]

    def model(self, path: str, model: type[ModelT]) -> ModelT:
        try:
            return model.model_validate(parse_yaml(self.read(path)))
        except (ValueError, ValidationError, UnicodeError) as exc:
            raise WorkflowError("workflow_invalid", "工作流文档结构不合法") from exc
