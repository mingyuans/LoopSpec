from loopspec.errors import WorkflowError


def test_error_envelope():
    error = WorkflowError("plan_invalid", "计划无效", "重新校验")
    assert error.to_dict() == {"error": "plan_invalid", "message": "计划无效", "fix": "重新校验"}
