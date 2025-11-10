from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import subprocess
from contextlib import asynccontextmanager

from src.schema import models
from src.core.database import engine
from src.core.logger import get_logger
from src.routers import auth, videos, stream

# Load environment variables
load_dotenv()

# Get logger
logger = get_logger(__name__)

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(videos.router, prefix="/videos", tags=["videos"])
app.include_router(stream.router, prefix="/stream", tags=["stream"])


@app.get("/")
def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Custom Video Player Backend"}
