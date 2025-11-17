from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.core.database import get_db
from src.core.logger import get_logger
from src.core.config import settings
from datetime import datetime, timezone
import redis
import subprocess
import shutil

router = APIRouter()

logger = get_logger(__name__)


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Comprehensive health check endpoint that verifies:
    - Application is running
    - Database connection is working
    - Redis connection is working
    - FFmpeg is available for video processing
    """
    health_status = {
        "status": "healthy",
        "database": "healthy",
        "redis": "healthy",
        "ffmpeg": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Check database connection
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_status = "unhealthy"
        health_status["status"] = "unhealthy"

    # Check Redis connection
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.ping()  # Simple ping to test connectivity
        redis_status = "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        redis_status = "unhealthy"
        health_status["status"] = "unhealthy"

    # Check FFmpeg availability
    try:
        # First check if ffmpeg is in PATH
        if not shutil.which("ffmpeg"):
            raise Exception("FFmpeg not found in PATH")

        # Test FFmpeg by running version command
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            raise Exception(f"FFmpeg version check failed: {result.stderr}")

        ffmpeg_status = "healthy"
    except Exception as e:
        logger.error(f"FFmpeg health check failed: {str(e)}")
        ffmpeg_status = "unhealthy"
        health_status["status"] = "unhealthy"

    health_status.update(
        {
            "database": db_status,
            "redis": redis_status,
            "ffmpeg": ffmpeg_status,
        }
    )

    logger.info(
        f"Health check performed: status={health_status['status']}, "
        f"database={db_status}, redis={redis_status}, ffmpeg={ffmpeg_status}"
    )
    return health_status


@router.get("/health/live")
def liveness_check():
    """
    Liveness probe - checks if the application is running
    """
    return {"status": "alive"}


@router.get("/health/ready")
def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness probe - checks if the application is ready to serve requests
    Verifies all critical dependencies: database, Redis, and FFmpeg
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))

        # Test Redis connection
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.ping()

        # Test FFmpeg availability
        if not shutil.which("ffmpeg"):
            raise Exception("FFmpeg not found in PATH")

        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            raise Exception("FFmpeg version check failed")

        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        return {"status": "not ready", "error": str(e)}
