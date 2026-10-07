"""仅补齐缺失的四层模型内置资源，不覆盖项目路径映射或自定义内容。"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .builtin_resources import builtin_root
from .errors import WorkflowError
from .workflow_io import ResourceBundle, atomic_write, directory, exists, relative_path


def install_resources(home: Path) -> list[str]:
    source = builtin_root()
    bundle = ResourceBundle(source)
    copied = []
    count = 0

    def visit(path: str, depth: int) -> None:
        nonlocal count
        if depth > 32:
            raise WorkflowError("resource_limit", "内置资源目录过深")
        with directory(source, path) as fd:
            for name in sorted(os.listdir(fd)):
                count += 1
                if count > 4096:
                    raise WorkflowError("resource_limit", "内置资源过多")
                target = relative_path(path + "/" + name)
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    visit(target, depth + 1)
                elif stat.S_ISREG(info.st_mode):
                    if not exists(home, target):
                        atomic_write(home, target, bundle.read(target), exclusive=True)
                        copied.append(target)
                else:
                    raise WorkflowError("unsafe_path", "内置资源不能包含链接或特殊文件")

    for kind in ("fragments", "profiles"):
        with directory(home, kind, create=True):
            pass
        visit(kind, 0)
    return copied
