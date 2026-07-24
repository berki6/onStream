from fastapi import FastAPI, Request
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
        errors = []
        for error in exc.errors():
            field = "unknown"
            if error.get("loc") and len(error["loc"]) > 1:
                field = error["loc"][1]
            msg = error.get("msg", "Validation error")
            if msg.startswith("Value error, "):
                msg = msg.replace("Value error, ", "")
            errors.append({"field": field, "message": msg})

        return JSONResponse(
            status_code=422, content={"error": "Validation failed", "details": errors}
        )

    @application.exception_handler(AppError)
    async def app_error_handler(request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    application.include_router(api_router, prefix="/v1")
    application.include_router(health.router, prefix="", tags=["health"])

    if settings.DEMO_PLAYER_ENABLED:
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
        return {"message": "OnStream API", "version": "0.3.0"}

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
