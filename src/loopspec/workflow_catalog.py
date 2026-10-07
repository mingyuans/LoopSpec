"""Fragment/Profile 安全目录发现；Fragment 为自包含目录，一次操作共享有界资源缓存。"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

from .errors import WorkflowError
from .models import KEBAB_RE
from .workflow_io import ResourceBundle, directory, relative_path
from .workflow_models import Fragment, Profile


class WorkflowCatalog:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.bundle = ResourceBundle(home)

    def _path(self, kind: str, name: str) -> str:
        if not re.fullmatch(KEBAB_RE, name):
            raise WorkflowError("workflow_invalid", "定义名称必须是 kebab-case")
        if kind == "fragments":
            return f"fragments/{name}/fragment.yaml"
        return f"{kind}/{name}.yaml"

    def fragment(self, name: str) -> Fragment:
        value = self.bundle.model(self._path("fragments", name), Fragment)
        if value.name != name:
            raise WorkflowError("workflow_invalid", "Fragment 名称与目录名不一致")
        return value

    def profile(self, name: str) -> Profile:
        value = self.bundle.model(self._path("profiles", name), Profile)
        if value.name != name:
            raise WorkflowError("workflow_invalid", "Profile 名称与文件名不一致")
        return value

    def entries(self, kind: str) -> list[Fragment] | list[Profile]:
        if kind not in {"fragments", "profiles"}:
            raise WorkflowError("workflow_invalid", "未知工作流目录类型")
        with directory(self.home, kind) as parent:
            names = os.listdir(parent)
            if len(names) > 4096:
                raise WorkflowError("resource_limit", "定义目录超过条目限制")
            if kind == "fragments":
                selected = sorted(name for name in names if self._fragment_dir(parent, name))
                return [self.fragment(name) for name in selected]
            selected = sorted(name[:-5] for name in names if name.endswith(".yaml"))
            for name in selected:
                info = os.stat(name + ".yaml", dir_fd=parent, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    raise WorkflowError("unsafe_path", "定义不能是链接或特殊文件")
        return [self.profile(name) for name in selected]

    @staticmethod
    def _fragment_dir(parent: int, name: str) -> bool:
        """A Fragment is a sub-directory holding ``fragment.yaml``; other entries are ignored."""
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode):
            raise WorkflowError("unsafe_path", "Fragment 目录不能是链接")
        if not stat.S_ISDIR(info.st_mode):
            return False
        try:
            definition = os.stat(name + "/fragment.yaml", dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return False
        if not stat.S_ISREG(definition.st_mode):
            raise WorkflowError("unsafe_path", "定义不能是链接或特殊文件")
        return True

    def resource(self, fragment: str, path: str) -> str:
        """Resolve a resource inside the owning Fragment's own directory."""
        if not re.fullmatch(KEBAB_RE, fragment):
            raise WorkflowError("workflow_invalid", "定义名称必须是 kebab-case")
        source = f"fragments/{fragment}/" + relative_path(path)
        self.bundle.read(source)
        return source
