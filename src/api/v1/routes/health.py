from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
import subprocess
import shutil
import time
import psutil

from src.infrastructure.db.session import get_db
from src.core.logger import get_logger
from src.core.config import settings
from src.schemas.common import APIResponse

router = APIRouter()
logger = get_logger(__name__)
health_start_time = time.time()


def format_uptime(seconds: int) -> str:
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}D")
    if hours > 0 or days > 0:
        parts.append(f"{hours}H")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}M")
    parts.append(f"{seconds}S")
    return " ".join(parts)


def _dependency_checks(db: Session) -> dict:
    result = {
        "database": "unhealthy",
        "redis": "unhealthy",
        "ffmpeg": "unhealthy",
        "storage": "unhealthy",
        "queue": {},
    }

    try:
        db.execute(text("SELECT 1"))
        result["database"] = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    try:
        from src.infrastructure.queue.redis_client import redis_client

        result["redis"] = "healthy" if redis_client.ping() else "unhealthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")

    try:
        if not shutil.which("ffmpeg"):
            raise Exception("FFmpeg not found in PATH")
        proc = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )
        if proc.returncode != 0:
            raise Exception(proc.stderr)
        result["ffmpeg"] = "healthy"
    except Exception as e:
        logger.error(f"FFmpeg health check failed: {e}")

    try:
        from src.infrastructure.storage import get_storage

        result["storage"] = "healthy" if get_storage().health_check() else "unhealthy"
        result["storage_backend"] = settings.STORAGE_BACKEND
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")

    try:
        from src.infrastructure.queue.job_queue import job_queue

        result["queue"] = job_queue.get_queue_stats()
    except Exception as e:
        logger.error(f"Queue stats failed: {e}")
        result["queue"] = {"error": str(e)}

    return result


@router.get("/health", response_model=APIResponse)
def health_check(request: Request, db: Session = Depends(get_db)):
    deps = _dependency_checks(db)
    critical = [deps["database"], deps["storage"]]
    overall = (
        "healthy"
        if all(s == "healthy" for s in critical)
        else "degraded"
        if deps["database"] == "healthy"
        else "unhealthy"
    )
    payload = {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **deps,
    }
    return APIResponse(
        data=payload,
        request_id=request.state.request_id,
        timestamp=datetime.now(timezone.utc),
        message="Health check completed",
    )


@router.get("/health/live", response_model=APIResponse)
def liveness_check(request: Request):
    uptime_seconds = int(time.time() - health_start_time)
    return APIResponse(
        data={
            "status": "alive",
            "uptime": format_uptime(uptime_seconds),
            "memory_mb": round(psutil.virtual_memory().used / 1024**2, 2),
            "cpu_percent": psutil.cpu_percent(interval=None),
        },
        request_id=request.state.request_id,
        timestamp=datetime.now(timezone.utc),
        message="Application is alive",
    )


@router.get("/health/ready", response_model=APIResponse)
def readiness_check(request: Request, db: Session = Depends(get_db)):
    deps = _dependency_checks(db)
    ready = deps["database"] == "healthy" and deps["storage"] == "healthy"
    if ready:
        return APIResponse(
            data={"status": "ready", **deps},
            request_id=request.state.request_id,
            timestamp=datetime.now(timezone.utc),
            message="Application is ready to serve requests",
        )
    return APIResponse(
        success=False,
        data={"status": "not ready", **deps},
        request_id=request.state.request_id,
        timestamp=datetime.now(timezone.utc),
        message="Application is not ready",
    )
