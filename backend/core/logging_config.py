"""
Structlog 日志配置模块
"""

import logging
import json
import structlog
from logging.handlers import RotatingFileHandler
from structlog.processors import TimeStamper, add_log_level, JSONRenderer
from structlog.dev import ConsoleRenderer
from structlog.contextvars import merge_contextvars
from structlog.stdlib import ProcessorFormatter
from typing import Any, List

from core.config import settings


def get_renderer() -> Any:
    """根据环境选择渲染器 (Console in DEBUG, JSON otherwise).
    注意：structlog 会向 serializer 传入 default/sort_keys 等参数，需要适配。
    """
    if settings.DEBUG:
        return ConsoleRenderer(colors=True)

    # 定义 serializer，兼容 structlog 传入的关键字参数
    def _dumps(obj, default=None, **kwargs):
        return json.dumps(obj, ensure_ascii=False, default=default, **kwargs)

    return JSONRenderer(serializer=_dumps)


def _add_trace_context(logger, method_name, event_dict):
    try:
        from core.observability.tracing import get_current_span_id, get_current_trace_id

        trace_id = get_current_trace_id()
        span_id = get_current_span_id()
        if trace_id:
            event_dict["trace_id"] = trace_id
        if span_id:
            event_dict["span_id"] = span_id
    except Exception:
        pass
    return event_dict


def configure_logging() -> None:
    """配置 structlog 并桥接标准库 logging 到同一处理链。"""
    timestamper = TimeStamper(fmt="iso")

    # 预处理链（同时用于 stdlib ProcessorFormatter 和 structlog.configure）
    shared_pre_chain: List[Any] = [
        merge_contextvars,
        _add_trace_context,
        add_log_level,
        timestamper,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # 配置 structlog —— 交由 ProcessorFormatter 渲染
    structlog.configure(
        processors=[
            *shared_pre_chain,
            ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 标准库 logging 使用 ProcessorFormatter，把 stdlib 日志也纳入 structlog 渲染
    renderer = get_renderer()
    formatter = ProcessorFormatter(
        foreign_pre_chain=shared_pre_chain,
        processors=[
            ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # 设置日志级别
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # 配置处理器
    handlers = []

    # 控制台处理器 - 始终启用
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    handlers.append(console_handler)

    # 文件处理器 - 如果配置了 LOG_FILE
    if settings.LOG_FILE:
        # 生产环境使用 JSON 格式，开发环境可以使用带颜色的控制台格式
        file_formatter = formatter
        if settings.DEBUG:
            # 开发环境下文件也使用 JSON 格式，避免颜色代码污染日志文件
            def _file_dumps(obj, default=None, **kwargs):
                return json.dumps(obj, ensure_ascii=False, default=default, **kwargs)

            file_formatter = ProcessorFormatter(
                foreign_pre_chain=shared_pre_chain,
                processors=[
                    ProcessorFormatter.remove_processors_meta,
                    JSONRenderer(serializer=_file_dumps),
                ],
            )

        # 使用 RotatingFileHandler 进行日志轮转
        file_handler = RotatingFileHandler(
            filename=settings.LOG_FILE,
            maxBytes=settings.LOG_MAX_BYTES,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    # 配置根日志记录器
    root = logging.getLogger()
    root.handlers.clear()
    for handler in handlers:
        root.addHandler(handler)

    # 设置根日志记录器级别
    root.setLevel(log_level)


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """获取 structlog logger 实例。"""
    return structlog.get_logger(name)


# Note: do not auto-configure on import to avoid side effects in
# libraries and test collection. Call `configure_logging()` from the
# application entrypoints (e.g., `main.py`, `grpc_main.py`).
