# input: 无外部依赖
# output: BuildTimeoutError, BuildError — PersonaBuilderService 专用异常
# owner: wanhua.gu
# pos: 应用层 - persona 构建流程异常（Story 2.4）；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
"""Exceptions raised by PersonaBuilderService.

Kept distinct from ``domain.common.exceptions.BusinessException`` because
these are application-level orchestration failures (timeout, missing agent
artifacts, structured parse failure) rather than domain invariants.
"""

from __future__ import annotations

from typing import Optional


class BuildError(Exception):
    """Raised when persona build fails at any non-timeout stage."""

    def __init__(self, message: str, *, error_code: str = "BUILD_FAILED") -> None:
        super().__init__(message)
        self.error_code = error_code


class BuildTimeoutError(BuildError):
    """Raised when persona build exceeds its total wall-clock budget."""

    def __init__(
        self,
        *,
        total_timeout_s: int,
        elapsed_s: float,
        error_code: str = "BUILD_TIMEOUT",
        stage: Optional[str] = None,
    ) -> None:
        detail = f" (stage={stage})" if stage else ""
        super().__init__(
            f"Persona build timed out after {elapsed_s:.1f}s (limit={total_timeout_s}s){detail}",
            error_code=error_code,
        )
        self.total_timeout_s = total_timeout_s
        self.elapsed_s = elapsed_s
        self.stage = stage


__all__ = ["BuildError", "BuildTimeoutError"]
