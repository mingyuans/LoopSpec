## 背景

main 上 Release 工作流在 #19、#21 合并后失败：`tests/test_text_reports.py::test_every_rendered_command_takes_json` 在 `--help` 文本中查找 `--json`；CI 中 rich 输出带 ANSI 颜色码，把 `--json` 拆成 `-` 与 `-json`。阻塞发布 v1.3.0。

## 用户场景

维护者发版时 main 的 CI 必须通过。

## 范围

- 测试改为检查 click 命令对象的选项列表，不依赖帮助文本渲染。

## 非目标

- 不改产品代码与帮助文本。

## 验收条件

- [ ] `FORCE_COLOR=1` 下该测试修复前失败、修复后通过。
- [ ] 全量测试通过；合入后 main 的 CI 通过。

## 风险

- 无。
