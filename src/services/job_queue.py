"""
Job queue service with database persistence fallback.

This service provides a robust job queue that uses Redis as primary storage
but falls back to database persistence when Redis is unavailable. It also
handles job recovery when Redis comes back online.
"""

from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.core.database import get_db
from src.core.redis_client import redis_client, CircuitBreakerOpenException
from src.schema import models
from src.core.logger import get_logger

logger = get_logger(__name__)


class JobQueueService:
    """Service for managing job queues with Redis primary and database fallback."""

    def __init__(self):
        self.redis_client = redis_client
        self.queue_name = "video_jobs_queue"
        self.max_recovery_batch_size = 100

    def enqueue_job(self, upload_id: str, db: Session) -> bool:
        """
        Enqueue a job, trying Redis first, then falling back to database.

        Returns True if successfully queued, False otherwise.
        """
        # Try Redis first
        try:
            self.redis_client.lpush(self.queue_name, upload_id)
            logger.info(f"Job {upload_id} queued in Redis")
            return True
        except (CircuitBreakerOpenException, Exception) as e:
            logger.warning(
                f"Redis unavailable for job {upload_id}, falling back to database: {e}"
            )

            # Fall back to database storage
            try:
                # Check if job already exists in database queue
                existing_job = (
                    db.query(models.QueuedJob)
                    .filter_by(upload_id=upload_id, status="pending")
                    .first()
                )

                if not existing_job:
                    queued_job = models.QueuedJob(
                        upload_id=upload_id,
                        queue_name=self.queue_name,
                        status="pending",
                        retry_count=0,
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(queued_job)
                    db.commit()
                    logger.info(f"Job {upload_id} queued in database fallback")
                    return True
                else:
                    logger.info(f"Job {upload_id} already queued in database")
                    return True

            except Exception as db_error:
                logger.error(
                    f"Failed to queue job {upload_id} in database fallback: {db_error}"
                )
                return False

    def dequeue_job(self, timeout: int = 1) -> Optional[str]:
        """
        Dequeue a job from Redis, or recover from database if Redis is available.

        Returns upload_id if job found, None otherwise.
        """
        # Try Redis first
        try:
            result = self.redis_client.blpop(self.queue_name, timeout=timeout)
            if result:
                _, upload_id_bytes = result
                upload_id = (
                    upload_id_bytes.decode("utf-8")
                    if isinstance(upload_id_bytes, bytes)
                    else upload_id_bytes
                )
                logger.info(f"Job {upload_id} dequeued from Redis")
                return upload_id
        except (CircuitBreakerOpenException, Exception) as e:
            logger.warning(
                f"Redis unavailable for dequeue, checking database recovery: {e}"
            )

        # If Redis is down, try to recover jobs from database
        return self._recover_job_from_database()

    def _recover_job_from_database(self) -> Optional[str]:
        """Recover a pending job from database storage."""
        db = next(get_db())
        try:
            # Get oldest pending job
            queued_job = (
                db.query(models.QueuedJob)
                .filter(
                    and_(
                        models.QueuedJob.status == "pending",
                        models.QueuedJob.queue_name == self.queue_name,
                    )
                )
                .order_by(models.QueuedJob.created_at.asc())
                .first()
            )

            if queued_job:
                # Mark as processing to prevent duplicate processing
                queued_job.status = "processing"
                queued_job.retry_count += 1
                db.commit()

                logger.info(
                    f"Recovered job {queued_job.upload_id} from database (retry #{queued_job.retry_count})"
                )
                return queued_job.upload_id

        except Exception as e:
            logger.error(f"Failed to recover job from database: {e}")
        finally:
            db.close()

        return None

    def mark_job_completed(self, upload_id: str):
        """Mark a job as completed in database (for cleanup)."""
        db = next(get_db())
        try:
            queued_job = (
                db.query(models.QueuedJob)
                .filter_by(upload_id=upload_id, status="processing")
                .first()
            )

            if queued_job:
                queued_job.status = "completed"
                db.commit()
                logger.info(f"Job {upload_id} marked as completed in database")
        except Exception as e:
            logger.error(f"Failed to mark job {upload_id} as completed: {e}")
        finally:
            db.close()

    def mark_job_failed(self, upload_id: str, error_message: Optional[str] = None):
        """Mark a job as failed in database."""
        db = next(get_db())
        try:
            queued_job = (
                db.query(models.QueuedJob)
                .filter_by(upload_id=upload_id, status="processing")
                .first()
            )

            if queued_job:
                queued_job.status = "failed"
                if error_message:
                    queued_job.error_message = error_message
                queued_job.retry_count += 1
                db.commit()
                logger.warning(f"Job {upload_id} marked as failed: {error_message}")
        except Exception as e:
            logger.error(f"Failed to mark job {upload_id} as failed: {e}")
        finally:
            db.close()

    def recover_jobs_to_redis(self) -> int:
        """
        Recover pending jobs from database to Redis when Redis becomes available.

        Returns number of jobs recovered.
        """
        recovered_count = 0
        db = next(get_db())

        try:
            # Get pending jobs that haven't been retried too many times
            pending_jobs = (
                db.query(models.QueuedJob)
                .filter(
                    and_(
                        models.QueuedJob.status == "pending",
                        models.QueuedJob.queue_name == self.queue_name,
                        models.QueuedJob.retry_count < 3,  # Max retries
                    )
                )
                .order_by(models.QueuedJob.created_at.asc())
                .limit(self.max_recovery_batch_size)
                .all()
            )

            for job in pending_jobs:
                try:
                    # Try to push to Redis
                    self.redis_client.lpush(self.queue_name, job.upload_id)

                    # Mark as recovered in database
                    job.status = "recovered"
                    recovered_count += 1

                    logger.info(f"Recovered job {job.upload_id} to Redis")

                except (CircuitBreakerOpenException, Exception) as e:
                    logger.warning(
                        f"Failed to recover job {job.upload_id} to Redis: {e}"
                    )
                    break  # Stop if Redis is still unavailable

            db.commit()

        except Exception as e:
            logger.error(f"Failed to recover jobs to Redis: {e}")
        finally:
            db.close()

        if recovered_count > 0:
            logger.info(f"Successfully recovered {recovered_count} jobs to Redis")

        return recovered_count

    def get_queue_stats(self) -> dict:
        """Get queue statistics for monitoring."""
        stats = {
            "redis_available": False,
            "redis_queue_length": 0,
            "database_pending_jobs": 0,
            "database_failed_jobs": 0,
            "circuit_breaker_status": self.redis_client.get_circuit_breaker_status(),
        }

        # Check Redis status
        try:
            stats["redis_available"] = self.redis_client.ping()
            if stats["redis_available"]:
                stats["redis_queue_length"] = self.redis_client.llen(self.queue_name)
        except Exception:
            pass

        # Get database stats
        db = next(get_db())
        try:
            stats["database_pending_jobs"] = (
                db.query(models.QueuedJob)
                .filter(
                    and_(
                        models.QueuedJob.status == "pending",
                        models.QueuedJob.queue_name == self.queue_name,
                    )
                )
                .count()
            )

            stats["database_failed_jobs"] = (
                db.query(models.QueuedJob)
                .filter(
                    and_(
                        models.QueuedJob.status == "failed",
                        models.QueuedJob.queue_name == self.queue_name,
                    )
                )
                .count()
            )
        except Exception as e:
            logger.error(f"Failed to get database queue stats: {e}")
        finally:
            db.close()

        return stats

    def cleanup_old_jobs(self, days_old: int = 30):
        """Clean up old completed/failed jobs from database."""
        from datetime import timedelta

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        db = next(get_db())

        try:
            deleted_count = (
                db.query(models.QueuedJob)
                .filter(
                    and_(
                        or_(
                            models.QueuedJob.status == "completed",
                            models.QueuedJob.status == "recovered",
                        ),
                        models.QueuedJob.created_at < cutoff_date,
                    )
                )
                .delete()
            )

            db.commit()
            logger.info(f"Cleaned up {deleted_count} old jobs from database")

        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
        finally:
            db.close()


# Global job queue service instance
job_queue = JobQueueService()
