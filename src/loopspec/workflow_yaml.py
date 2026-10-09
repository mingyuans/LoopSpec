"""有界 YAML 解析，不接受重复键、别名或任意对象构造。"""

from __future__ import annotations

from typing import Any

import yaml

MAX_DOCUMENT_BYTES = 1024 * 1024


class StrictLoader(yaml.SafeLoader):
    def __init__(self, stream: str) -> None:
        super().__init__(stream)
        self._depth = 0
        self._count = 0

    def compose_node(self, parent: Any, index: Any) -> Any:
        self._depth += 1
        self._count += 1
        try:
            if self._depth > 64 or self._count > 16384:
                raise ValueError("YAML 超过深度或条目限制")
            if self.check_event(yaml.AliasEvent):
                raise ValueError("YAML 不接受别名")
            return super().compose_node(parent, index)
        finally:
            self._depth -= 1

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[Any, Any]:
        result: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError("YAML 键必须是唯一字符串")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def parse_yaml(data: bytes | str) -> dict[str, Any]:
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="strict")
    if len(data.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise ValueError("YAML 超过文件大小限制")
    try:
        result = yaml.load(data, Loader=StrictLoader)
    except (yaml.YAMLError, RecursionError) as exc:
        # 不将原始输入（可能含敏感值）写入错误信息。
        raise ValueError("YAML 格式不合法") from exc
    if not isinstance(result, dict):
        raise ValueError("YAML 顶层必须是映射")
    return result
