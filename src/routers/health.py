from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.core.database import get_db
from src.core.logger import get_logger
from src.core.config import settings
from datetime import datetime, timezone
import redis
import subprocess
import shutil
from src.schema.schemas import APIResponse
import time
import psutil

router = APIRouter()

logger = get_logger(__name__)

# Track application start time for uptime calculation
health_start_time = time.time()


def format_uptime(seconds: int) -> str:
    """Format seconds into human readable time (e.g., '1D 2H 30M 45S')"""
    days, remainder = divmod(seconds, 86400)  # 86400 seconds in a day
    hours, remainder = divmod(remainder, 3600)  # 3600 seconds in an hour
    minutes, seconds = divmod(remainder, 60)  # 60 seconds in a minute

    parts = []
    if days > 0:
        parts.append(f"{days}D")
    if hours > 0 or days > 0:  # Show hours if there are days or hours
        parts.append(f"{hours}H")
    if minutes > 0 or hours > 0 or days > 0:  # Show minutes if there are larger units
        parts.append(f"{minutes}M")
    parts.append(f"{seconds}S")

    return " ".join(parts)


@router.get("/health", response_model=APIResponse)
def health_check(request: Request, db: Session = Depends(get_db)):
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

    return APIResponse(
        data=health_status,
        request_id=request.state.request_id,
        timestamp=datetime.now(timezone.utc),
        message="Health check completed",
    )


@router.get("/health/live", response_model=APIResponse)
def liveness_check(request: Request):
    """
    Liveness probe - checks if the application is running
    Includes uptime and basic system metrics
    """
    uptime_seconds = int(time.time() - health_start_time)
    uptime_formatted = format_uptime(uptime_seconds)

    return APIResponse(
        data={
            "status": "alive",
            # "uptime_seconds": uptime_seconds,
            "uptime": uptime_formatted,
            "memory_mb": round(psutil.virtual_memory().used / 1024**2, 2),
            "cpu_percent": psutil.cpu_percent(interval=None),
        },
        request_id=request.state.request_id,
        timestamp=datetime.now(timezone.utc),
        message="Application is alive",
    )


@router.get("/health/ready", response_model=APIResponse)
def readiness_check(request: Request, db: Session = Depends(get_db)):
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

        return APIResponse(
            data={"status": "ready"},
            request_id=request.state.request_id,
            timestamp=datetime.now(timezone.utc),
            message="Application is ready to serve requests",
        )
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        return APIResponse(
            success=False,
            data={"status": "not ready", "error": str(e)},
            request_id=request.state.request_id,
            timestamp=datetime.now(timezone.utc),
            message="Application is not ready",
        )
