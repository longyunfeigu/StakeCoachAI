"""
Shared business codes used across layers (Domain/Core/API).

This package exposes BusinessCode at `shared.codes`.
"""

from enum import IntEnum


class BusinessCode(IntEnum):
    """Unified business status codes (single source of truth)."""

    # Success
    SUCCESS = 0

    # Parameter errors (1xxxx)
    PARAM_ERROR = 10000
    PARAM_MISSING = 10001
    PARAM_TYPE_ERROR = 10002
    PARAM_VALIDATION_ERROR = 10003

    # Business errors (2xxxx)
    BUSINESS_ERROR = 20000
    USER_NOT_FOUND = 20001
    USER_ALREADY_EXISTS = 20002
    PASSWORD_ERROR = 20003
    NOT_FOUND = 20004  # Generic resource not found

    # Authorization errors (3xxxx)
    PERMISSION_ERROR = 30000
    UNAUTHORIZED = 30001
    FORBIDDEN = 30002

    # System errors (4xxxx)
    SYSTEM_ERROR = 40000
    DATABASE_ERROR = 40001
    NETWORK_ERROR = 40002
    SERVICE_UNAVAILABLE = 40003

    # Rate limiting (5xxxx)
    RATE_LIMIT_ERROR = 50000
    TOO_MANY_REQUESTS = 50001

    # Agent / AI (6xxxx)
    CONVERSATION_NOT_FOUND = 60001
    CONVERSATION_ARCHIVED = 60002
    RUN_NOT_FOUND = 60003
    RUN_ALREADY_COMPLETED = 60004
    AGENT_CONFIG_NOT_FOUND = 60005
    AGENT_CONFIG_NAME_EXISTS = 60006
    LLM_PROVIDER_ERROR = 60010
    LLM_TIMEOUT = 60011

    # Stakeholder Chat (7xxxx)
    CHATROOM_NOT_FOUND = 70001
    SCENARIO_NOT_FOUND = 70002
    ANALYSIS_PARSE_ERROR = 70003
    ANALYSIS_NO_MESSAGES = 70004
    ANALYSIS_REPORT_NOT_FOUND = 70005
    COACHING_SESSION_NOT_FOUND = 70006


__all__ = ["BusinessCode"]
