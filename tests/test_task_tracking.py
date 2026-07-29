from pathlib import Path

from loopspec.task_tracking import (
    parse_tasks,
    progress_detail,
    progress_summary,
    read_task_progress,
    tracked_work_complete,
)

MIXED = """## 1. Setup

- [x] 1.1 Create module
- [x] 1.2 Add dependency
- [ ] 1.3 Wire it up

## 2. Core

- [x] 2.1 Implement parser
- [ ] 2.2 Add CLI flag
"""


def test_mixed_checkbox_counts(tmp_path: Path):
    (tmp_path / "tasks.md").write_text(MIXED, encoding="utf-8")
    progress = read_task_progress(tmp_path, "tasks.md")
    assert (progress.total, progress.complete, progress.remaining) == (5, 3, 2)


def test_task_ids_follow_document_order():
    tasks = parse_tasks(MIXED)
    assert [task.id for task in tasks] == [1, 2, 3, 4, 5]
    assert tasks[0].description == "1.1 Create module"
    assert tasks[2].description == "1.3 Wire it up"
    assert [task.done for task in tasks] == [True, True, False, True, False]


def test_uppercase_x_counts_as_done():
    tasks = parse_tasks("- [X] done already")
    assert tasks[0].done is True


def test_asterisk_bullets_recognized():
    tasks = parse_tasks("* [ ] pending\n* [x] finished")
    assert [(task.description, task.done) for task in tasks] == [
        ("pending", False),
        ("finished", True),
    ]


def test_non_checkbox_lines_ignored():
    text = "## 1. Group\n\nSome prose about the work.\n\n- a plain bullet\n- [ ] real task\n"
    tasks = parse_tasks(text)
    assert len(tasks) == 1
    assert tasks[0].description == "real task"


def test_missing_file_yields_zero_progress(tmp_path: Path):
    progress = read_task_progress(tmp_path, "tasks.md")
    assert (progress.total, progress.complete, progress.remaining) == (0, 0, 0)
    assert progress.tasks == []
    assert progress.resolved_path == (tmp_path / "tasks.md").resolve()


def test_tracked_work_complete_requires_at_least_one_task(tmp_path: Path):
    (tmp_path / "empty.md").write_text("## No tasks here\n", encoding="utf-8")
    assert tracked_work_complete(read_task_progress(tmp_path, "empty.md")) is False
    assert tracked_work_complete(read_task_progress(tmp_path, "absent.md")) is False


def test_tracked_work_complete_when_all_ticked(tmp_path: Path):
    (tmp_path / "tasks.md").write_text("- [x] one\n- [X] two\n", encoding="utf-8")
    assert tracked_work_complete(read_task_progress(tmp_path, "tasks.md")) is True


def test_tracked_work_incomplete_with_pending_task(tmp_path: Path):
    (tmp_path / "tasks.md").write_text("- [x] one\n- [ ] two\n", encoding="utf-8")
    assert tracked_work_complete(read_task_progress(tmp_path, "tasks.md")) is False


def test_summary_has_no_task_list_but_detail_does(tmp_path: Path):
    (tmp_path / "tasks.md").write_text("- [x] one\n- [ ] two\n", encoding="utf-8")
    progress = read_task_progress(tmp_path, "tasks.md")

    summary = progress_summary(progress)
    assert "tasks" not in summary
    assert summary["path"] == "tasks.md"
    assert summary["total"] == 2 and summary["complete"] == 1 and summary["remaining"] == 1

    detail = progress_detail(progress)
    assert detail["tasks"] == [
        {"id": 1, "description": "one", "done": True},
        {"id": 2, "description": "two", "done": False},
    ]
