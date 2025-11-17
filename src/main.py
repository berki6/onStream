from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import subprocess
from contextlib import asynccontextmanager
import uuid
import time

from src.schema import models
from src.core.database import engine
from src.core.logger import get_logger, request_id_context
from src.routers import auth, videos, stream, health, playlists

# Load environment variables
load_dotenv()

# Get logger
logger = get_logger(__name__)

logger.info("Main application module loaded")

# Models base
models.Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup: Check if FFmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        logger.info("FFmpeg is available.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("FFmpeg not found. Install it for video processing.")
    yield
    # Shutdown: Add any cleanup logic here if needed
    pass


# App
app = FastAPI(title="Custom Video Player Backend", version="0.1.0", lifespan=lifespan)

# Global start time for uptime tracking
app_start_time = time.time()

logger.info("'Custom Video Player Backend' v0.1.0 Loaded 🎉")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("CORS middleware configured")


# Request ID middleware for tracking
@app.middleware("http")
async def add_request_id(request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Set request ID in logging context
    request_id_context.set(request_id)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


logger.info("Request ID middleware configured")


# Custom validation error handler for cleaner error responses
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = []
    for error in exc.errors():
        # Extract field name from location
        field = "unknown"
        if error.get("loc") and len(error["loc"]) > 1:
            field = error["loc"][1]  # e.g., ["body", "password"] -> "password"

        # Clean up the error message
        msg = error.get("msg", "Validation error")
        if msg.startswith("Value error, "):
            msg = msg.replace("Value error, ", "")

        errors.append({"field": field, "message": msg})

    return JSONResponse(
        status_code=422, content={"error": "Validation failed", "details": errors}
    )


logger.info("Custom validation error handler configured")

# Include routers with organized logging
router_configs = [
    {"router": auth.router, "prefix": "/auth", "tags": ["auth"]},
    {"router": videos.router, "prefix": "/videos", "tags": ["videos"]},
    {"router": stream.router, "prefix": "/stream", "tags": ["stream"]},
    {"router": health.router, "prefix": "", "tags": ["health"]},
    {"router": playlists.router, "prefix": "/playlists", "tags": ["playlists"]},
]

for config in router_configs:
    app.include_router(**config)

loaded_routes = [
    f"{config['tags'][0]}({config['prefix'] or 'root'})" for config in router_configs
]
logger.info(f"All routes loaded: {', '.join(loaded_routes)}")


@app.get("/")
def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Custom Video Player Backend"}
