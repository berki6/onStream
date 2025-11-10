from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.core.database import get_db
from src.core.logger import get_logger
from datetime import datetime, timezone

router = APIRouter()

logger = get_logger(__name__)


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint that verifies:
    - Application is running
    - Database connection is working
    """
    try:
        # Test database connection by making a simple query
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_status = "unhealthy"

    health_status = {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        f"Health check performed: status={health_status['status']}, database={db_status}"
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
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        return {"status": "not ready", "error": str(e)}
