from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import subprocess
from contextlib import asynccontextmanager

from src.schema import models
from src.core.database import engine
from src.core.logger import get_logger
from src.routers import auth, videos, stream, health

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

logger.info("'Custom Video Player Backend' v0.1.0 Loaded 🎉")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("CORS middleware configured")

# Include routers with organized logging
router_configs = [
    {"router": auth.router, "prefix": "/auth", "tags": ["auth"]},
    {"router": videos.router, "prefix": "/videos", "tags": ["videos"]},
    {"router": stream.router, "prefix": "/stream", "tags": ["stream"]},
    {"router": health.router, "prefix": "", "tags": ["health"]},
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
