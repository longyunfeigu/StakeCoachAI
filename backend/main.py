"""
FastAPI应用主入口
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from starlette.responses import HTMLResponse

from api.middleware import LoggingMiddleware, RequestIDMiddleware, PrometheusMiddleware
from api.middleware.locale import LocaleMiddleware
from api.routes import chat as chat_routes
from api.routes import conversations as conversations_routes
from api.routes import files as files_routes
from api.routes import health as health_routes
from api.routes import metrics as metrics_routes
from api.routes import stakeholder as stakeholder_routes
from api.routes import storage as storage_routes
from core.config import settings
from core.exceptions import register_exception_handlers
from core.i18n import t
from core.logging_config import configure_logging, get_logger
from core.observability import tracing as tracing_obs
from core.response import success_response
from infrastructure.database import create_tables, upgrade_schema_to_head
from infrastructure.external.cache import init_redis_client, shutdown_redis_client
from infrastructure.external.llm import (
    init_llm_client,
    shutdown_llm_client,
    init_anthropic_client,
    shutdown_anthropic_client,
)
from infrastructure.external.storage import (
    get_storage_config,
    init_storage_client,
    shutdown_storage_client,
)

# 初始化日志：在入口处显式配置，避免模块导入时的副作用
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    if settings.tracing.enabled:
        try:
            tracing_obs.setup_tracing(
                service_name=settings.PROJECT_NAME,
                exporter=settings.tracing.exporter,
                otlp_endpoint=settings.tracing.otlp_endpoint,
                sample_rate=settings.tracing.sample_rate,
            )
            tracing_obs.instrument_app(app)
            logger.info("tracing_initialized", exporter=settings.tracing.exporter)
        except Exception as exc:
            logger.warning("tracing_init_failed", error=str(exc))
    # 可配置的启动迁移策略：优先自动执行 Alembic 迁移
    if settings.AUTO_RUN_MIGRATIONS:
        await upgrade_schema_to_head()
        logger.info("database_migrated", message="Alembic upgraded to head at startup")
    elif settings.DEBUG:
        await create_tables()
        logger.info("database_initialized", message="Database tables created (development)")
    else:
        logger.info(
            "database_migrations_required",
            message="Auto migration is disabled in production, run Alembic before startup",
        )
    if settings.redis.url:
        try:
            await init_redis_client()
            logger.info("redis_cache_initialized", message="Redis cache initialized")
        except Exception as exc:
            logger.error("redis_cache_init_failed", error=str(exc))

    # 初始化存储服务（根据配置自动选择 provider；本地为默认）
    try:
        await init_storage_client()
        config = get_storage_config()
        logger.info(
            "storage_initialized",
            message="Storage service initialized",
            provider=config.type,
            bucket=config.bucket,
        )
        # 执行健康检查
        from infrastructure.external.storage import get_storage_client

        storage = get_storage_client()
        if storage and await storage.health_check():
            logger.info("storage_health_check_passed", message="Storage health check passed")
    except Exception as exc:
        logger.error(
            "storage_init_failed",
            error=str(exc),
        )

    # 初始化 LLM 客户端
    try:
        await init_llm_client()
    except Exception as exc:
        logger.error("llm_init_failed", error=str(exc))

    # 初始化 Anthropic 客户端（Stakeholder Chat）
    try:
        await init_anthropic_client()
    except Exception as exc:
        logger.error("anthropic_init_failed", error=str(exc))

    yield
    # 关闭时的清理工作
    await shutdown_anthropic_client()
    logger.info("anthropic_shutdown", message="Anthropic client shutdown")
    await shutdown_llm_client()
    logger.info("llm_shutdown", message="LLM client shutdown")
    if settings.redis.url:
        await shutdown_redis_client()
        logger.info("redis_cache_shutdown", message="Redis cache shutdown")

    # 关闭存储服务
    await shutdown_storage_client()
    logger.info("storage_shutdown", message="Storage service shutdown")
    if settings.tracing.enabled:
        tracing_obs.shutdown_tracing()
    logger.info("application_shutdown", message="Application shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    description="基于DDD架构的Fastapi骨架",
    docs_url=None,  # 使用自定义 Swagger UI 以支持国际化
    redoc_url="/redoc",
)

# 添加中间件（注意顺序：从下往上执行）
# 1. Request ID中间件（最先执行，为后续中间件提供request_id）
app.add_middleware(RequestIDMiddleware)

# 2. 日志中间件（依赖request_id）
app.add_middleware(LoggingMiddleware)

# 2.5 语言中间件（解析 locale）
app.add_middleware(LocaleMiddleware)

# 3. CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# 4. Prometheus metrics middleware (optional)
if settings.metrics.enabled:
    app.add_middleware(PrometheusMiddleware)

# 注册全局异常处理器
register_exception_handlers(app)


# 注册路由
app.include_router(storage_routes.router, prefix="/api/v1")
app.include_router(files_routes.router, prefix="/api/v1")
app.include_router(conversations_routes.router, prefix="/api/v1")
app.include_router(chat_routes.router, prefix="/api/v1")
app.include_router(stakeholder_routes.router, prefix="/api/v1")
app.include_router(health_routes.router)
app.include_router(metrics_routes.router)


# 根路径
@app.get("/", tags=["Root"])
async def root():
    """API根路径"""
    return success_response(
        data={
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs": "/docs",
            "redoc": "/redoc",
        },
        message=t("welcome"),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        workers=1 if settings.RELOAD else settings.WORKERS,
        log_level="debug" if settings.DEBUG else "info",
    )


# 自定义 Swagger UI（支持国际化）
def _map_locale_to_swagger_lang(locale: str) -> str:
    """将后端 locale 映射为 Swagger UI 支持的语言代码。"""
    if not locale:
        return "en"
    tag = locale.replace("_", "-").lower()
    # 常见映射（根据 Swagger UI 语言包）
    if tag in {"zh", "zh-cn", "zh-hans"}:
        return "zh-CN"
    if tag in {"zh-tw", "zh-hant"}:
        return "zh-TW"
    if tag in {"en", "en-us", "en-gb"}:
        return "en"
    # 其他语言可按需扩展
    return "en"


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html(request: Request) -> HTMLResponse:
    # 由 LocaleMiddleware 解析的语言，或从查询参数获取
    try:
        current = getattr(request.state, "locale", None)
    except Exception:
        current = None
    lang = _map_locale_to_swagger_lang(str(current or "en"))

    base = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{settings.PROJECT_NAME} - API Docs",
        swagger_ui_parameters={
            # 关键：传入语言
            "lang": lang,
            # 常用增强参数（可按需调整）
            "persistAuthorization": True,
            "displayRequestDuration": True,
        },
    )
    # 注入 requestInterceptor：为“Try it out”请求附带语言信息
    try:
        content = base.body.decode("utf-8")
    except Exception:
        content = str(base.body)
    injection = (
        "requestInterceptor: function(req){\n"
        "  try {\n"
        "    const url = new URL(req.url, window.location.origin);\n"
        "    const params = new URLSearchParams(window.location.search);\n"
        "    const lang = params.get('lang') || localStorage.getItem('docs_lang') || '%s';\n"
        "    if (lang) {\n"
        "      req.headers = req.headers || {};\n"
        "      req.headers['X-Lang'] = lang;\n"
        "      url.searchParams.set('lang', lang);\n"
        "      req.url = url.toString();\n"
        "    }\n"
        "  } catch (e) {}\n"
        "  return req;\n"
        "},"
    ) % (lang,)
    content = content.replace("SwaggerUIBundle({", "SwaggerUIBundle({\n  " + injection, 1)
    # 记住当前语言（刷新仍能保留）
    remember_lang_script = (
        "<script>\n"
        "(function(){\n"
        "  try {\n"
        "    var p = new URLSearchParams(window.location.search);\n"
        "    var l = p.get('lang');\n"
        "    if (l) localStorage.setItem('docs_lang', l);\n"
        "  } catch (e) {}\n"
        "})();\n"
        "</script>"
    )
    content = content.replace("</body>", remember_lang_script + "\n</body>")
    # 返回新的 HTMLResponse，避免沿用旧的 Content-Length 头
    return HTMLResponse(content=content, status_code=base.status_code)
