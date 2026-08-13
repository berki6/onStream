from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
import uuid
import time

from src.api.v1.router import api_router
from src.api.v1.routes import health
from src.application.errors import AppError
from src.core.config import settings
from src.core.logger import bind_context, clear_context, get_logger
from src.utils.paths import PROJECT_ROOT

load_dotenv()

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        logger.info("FFmpeg is available.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("FFmpeg not found. Install it for video processing.")
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="OnStream", version="0.3.0", lifespan=lifespan)

    try:
        from src.core.otel import instrument_fastapi, setup_tracing

        setup_tracing(service_name="onstream-api")
        instrument_fastapi(application)
    except Exception as e:
        logger.warning(f"OTel setup skipped: {e}")

    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration

            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                integrations=[FastApiIntegration()],
                environment=settings.ENV,
                traces_sample_rate=0.1 if settings.ENV == "production" else 0.0,
            )
            logger.info("Sentry initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Sentry: {e}")

    cors_origins = settings.cors_origins_list
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Location", "X-Request-ID"],
    )

    @application.middleware("http")
    async def add_request_id(request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        bind_context(request_id=request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            clear_context()

    if settings.PROMETHEUS_ENABLED:

        @application.middleware("http")
        async def prometheus_middleware(request: Request, call_next):
            from src.core.metrics import REQUEST_COUNT, REQUEST_LATENCY

            start = time.perf_counter()
            response = await call_next(request)
            elapsed = time.perf_counter() - start
            endpoint = request.url.path
            REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(
                elapsed
            )
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                status=str(response.status_code),
            ).inc()
            return response

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        from src.application.error_codes import ErrorCode
        from src.application.error_envelope import (
            error_body,
            validation_detail_code,
        )

        errors = []
        for error in exc.errors():
            field = "unknown"
            loc = error.get("loc") or ()
            if len(loc) > 1:
                field = str(loc[-1])
            msg = error.get("msg", "Validation error")
            if msg.startswith("Value error, "):
                msg = msg.replace("Value error, ", "")
            detail_code = validation_detail_code(field, str(error.get("type") or ""))
            errors.append(
                {
                    "field": field,
                    "message": msg,
                    "code": detail_code.value,
                }
            )

        return JSONResponse(
            status_code=422,
            content=error_body(
                request=request,
                code=ErrorCode.VALIDATION_FAILED,
                message="Validation failed",
                details=errors,
                http_status=422,
            ),
        )

    @application.exception_handler(AppError)
    async def app_error_handler(request, exc: AppError):
        from src.application.error_envelope import error_body

        headers = exc.headers or None
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                request=request,
                code=exc.code,
                message=exc.message,
                details=exc.details,
                http_status=exc.status_code,
            ),
            headers=headers,
        )

    from fastapi import HTTPException

    @application.exception_handler(HTTPException)
    async def http_exception_handler(request, exc: HTTPException):
        from src.application.error_codes import ErrorCode
        from src.application.error_envelope import error_body

        # Prefer structured AppError path; map leftover HTTPException.
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            code = exc.detail.get("code", ErrorCode.INTERNAL_SERVER_ERROR.value)
            message = exc.detail.get("message", str(exc.detail))
            details = exc.detail.get("details")
        else:
            message = (
                exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            )
            if exc.status_code == 401:
                code = ErrorCode.AUTH_UNAUTHORIZED
            elif exc.status_code == 403:
                code = ErrorCode.VIDEO_FORBIDDEN
            elif exc.status_code == 404:
                code = ErrorCode.VIDEO_NOT_FOUND
            elif exc.status_code == 429:
                code = ErrorCode.RATE_LIMIT_EXCEEDED
            elif exc.status_code == 422:
                code = ErrorCode.VALIDATION_FAILED
            elif exc.status_code >= 500:
                code = ErrorCode.INTERNAL_SERVER_ERROR
            else:
                code = ErrorCode.VALIDATION_BAD_REQUEST
            details = None

        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                request=request,
                code=code,
                message=message,
                details=details,
                http_status=exc.status_code,
            ),
            headers=getattr(exc, "headers", None),
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc: Exception):
        from src.application.error_codes import ErrorCode
        from src.application.error_envelope import error_body

        logger.exception("Unhandled exception: %s", exc)
        message = (
            "Internal server error"
            if settings.ENV == "production"
            else str(exc) or "Internal server error"
        )
        return JSONResponse(
            status_code=500,
            content=error_body(
                request=request,
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                message=message,
                http_status=500,
            ),
        )

    application.include_router(api_router, prefix="/v1")
    application.include_router(health.router, prefix="", tags=["health"])

    if settings.DEMO_PLAYER_ENABLED:
        from src.application.demo_whip_proxy import abs_session_url, whip_proxy_allowed

        @application.post("/demo/whip/session")
        async def demo_whip_publish(
            request: Request, target: str = Query(..., min_length=8)
        ):
            if not whip_proxy_allowed(target):
                return JSONResponse(
                    {"error": "WHIP target is not this lab's MediaMTX"},
                    status_code=400,
                )
            import httpx

            sdp = await request.body()
            try:
                async with httpx.AsyncClient(
                    timeout=20.0, follow_redirects=False
                ) as client:
                    res = await client.post(
                        target,
                        content=sdp,
                        headers={"Content-Type": "application/sdp"},
                    )
            except httpx.HTTPError as e:
                return JSONResponse({"error": str(e)}, status_code=502)
            session = abs_session_url(target, res.headers.get("Location"))
            return JSONResponse(
                {"sdp": res.text, "session_url": session},
                status_code=res.status_code if res.status_code < 500 else 502,
            )

        @application.delete("/demo/whip/session")
        async def demo_whip_stop(target: str = Query(..., min_length=8)):
            if not whip_proxy_allowed(target):
                return JSONResponse({"error": "Invalid WHIP session"}, status_code=400)
            import httpx

            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                await client.delete(target)
            return Response(status_code=204)

        demo_dir = PROJECT_ROOT / "static" / "demo"
        if demo_dir.is_dir():
            application.mount(
                "/demo",
                StaticFiles(directory=str(demo_dir), html=True),
                name="demo",
            )
            logger.info("Demo player mounted at /demo/")

    @application.get("/")
    def read_root():
        return {
            "message": "OnStream API",
            "version": "0.3.0",
            "docs": "/docs",
            "scalar": "/scalar",
        }

    @application.get("/scalar", include_in_schema=False)
    async def scalar_api_reference():
        from scalar_fastapi import AgentScalarConfig, get_scalar_api_reference

        return get_scalar_api_reference(
            openapi_url=application.openapi_url,
            title=f"{application.title} API",
            scalar_proxy_url="https://proxy.scalar.com",
            agent=AgentScalarConfig(disabled=True),
        )

    if settings.PROMETHEUS_ENABLED:

        @application.get("/metrics")
        def metrics():
            from src.core.metrics import metrics_payload

            payload, content_type = metrics_payload()
            return Response(content=payload, media_type=content_type)

    logger.info("OnStream v0.3.0 loaded (/v1 only)")
    return application


app = create_app()
app_start_time = time.time()
