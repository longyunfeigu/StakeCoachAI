# input: application.services.stakeholder.exceptions
# output: Story 2.4 BuildError / BuildTimeoutError 契约测试
# owner: wanhua.gu
# pos: 测试层 - Story 2.4 异常类型单元测试；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Tests for Story 2.4 exceptions."""

from __future__ import annotations

import pytest

from application.services.stakeholder.exceptions import BuildError, BuildTimeoutError


def test_build_error_carries_error_code_default():
    exc = BuildError("something went wrong")
    assert exc.error_code == "BUILD_FAILED"
    assert "something went wrong" in str(exc)


def test_build_error_custom_error_code():
    exc = BuildError("parse broke", error_code="STRUCTURED_PARSE_FAILED")
    assert exc.error_code == "STRUCTURED_PARSE_FAILED"


def test_build_timeout_error_is_subclass_of_build_error():
    exc = BuildTimeoutError(total_timeout_s=240, elapsed_s=245.3, stage="agent")
    assert isinstance(exc, BuildError)
    assert exc.error_code == "BUILD_TIMEOUT"
    assert exc.total_timeout_s == 240
    assert exc.elapsed_s == 245.3
    assert exc.stage == "agent"
    assert "245.3s" in str(exc)
    assert "240s" in str(exc)


def test_build_timeout_error_without_stage():
    exc = BuildTimeoutError(total_timeout_s=60, elapsed_s=61.0)
    assert exc.stage is None


def test_build_error_is_raisable():
    with pytest.raises(BuildError):
        raise BuildError("boom")
