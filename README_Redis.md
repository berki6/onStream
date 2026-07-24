# Video Processing with Redis Job Queue & Reliability Features

This FastAPI application uses Redis for asynchronous video processing job queuing with advanced reliability features, enabling scalable and fault-tolerant video transcoding with HLS streaming and thumbnail generation.

## Architecture

### Components

1. **FastAPI Web Server**: Handles video uploads and API requests
2. **Redis Queue with Reliability Layer**: Stores video processing jobs with connection pooling, retry logic, and circuit breaker protection
3. **Database Fallback System**: Persists jobs when Redis is unavailable with automatic recovery
4. **Video Worker**: Consumes jobs from Redis/database and processes videos using FFmpeg

### Workflow

1. User uploads video via `POST /videos/` endpoint
2. Video metadata is saved to database with a unique `upload_id`
3. `VideoJob` record is created in database for tracking processing status
4. `upload_id` is pushed to Redis queue `video_jobs_queue` using `LPUSH` (with retry logic)
5. If Redis is unavailable, job is stored in database `QueuedJob` table
6. Worker consumes job from Redis using `BLPOP` (blocking pop) and processes video
7. If Redis recovers, jobs are automatically migrated from database to Redis
8. Progress is updated in database via `VideoJob` status fields
9. Processed video (HLS segments + thumbnail) becomes available for streaming

## 🔧 Reliability & Resilience Features

### Connection Pooling & Retry Logic

The platform implements robust Redis connection management:

- **Connection Pool**: Configurable pool size (default: 10 connections) with automatic cleanup
- **Socket Timeouts**: 5-second connection and read timeouts to prevent hanging operations
- **Retry Mechanism**: Up to 3 retry attempts with exponential backoff (1s, 2s, 4s delays)
- **Error Handling**: Graceful handling of `ConnectionError`, `TimeoutError`, and `OSError`

### Circuit Breaker Pattern

Implements a three-state circuit breaker for Redis operations:

- **CLOSED State**: Normal operation, all requests pass through
- **OPEN State**: Failure threshold exceeded (5 failures), requests fail fast
- **HALF_OPEN State**: Testing recovery after timeout period (60 seconds)

**Benefits**:

- Prevents cascading failures during Redis outages
- Reduces system load during service degradation
- Enables faster recovery when services are restored
- Provides monitoring and alerting capabilities

### Job Persistence Fallback

When Redis is unavailable, the system automatically falls back to database storage:

- **Primary Storage**: Redis queue for optimal performance
- **Fallback Storage**: Database `QueuedJob` table for persistence
- **Recovery Process**: Automatic migration of jobs from database to Redis when service restores
- **Status Tracking**: Complete job lifecycle tracking (pending → processing → completed/failed)

**Key Features**:

- Zero job loss during Redis outages
- Automatic recovery with configurable batch sizes (max 100 jobs)
- Retry limits to prevent infinite processing loops
- Comprehensive monitoring and statistics

## Setup

### Prerequisites

- Redis server running (default: `localhost:6379`)
- FFmpeg installed for video processing
- Python dependencies installed (see `requirements.txt`)

### Installation

Redis client is included in dependencies:

```bash
pip install -r requirements.txt
```

### Configuration

Redis URL can be configured via environment variable:

```bash
export REDIS_URL=redis://localhost:6379/1
```

Default: `redis://localhost:6379/1`

Other Redis-related settings:

- `CELERY_BROKER_URL`: `redis://localhost:6379/0` (for Celery, if enabled)
- `CELERY_RESULT_BACKEND`: `redis://localhost:6379/0` (for Celery results)

## Running the Application

### Start the Web Server

```bash
python -m uvicorn src.main:app --reload
```

### Start the Video Worker

```bash
python start_worker.py
```

Or run multiple workers for scalability:

```bash
python start_worker.py &
python start_worker.py &
python start_worker.py &
```

## API Endpoints

### Upload Video

```http
POST /videos/
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <video_file>
title: <optional_title>
```

**Response**: Video object with `upload_id` for tracking.

**Process**:

- Validates file type, size, and duration using FFmpeg
- Creates database records for video and job tracking
- Pushes `upload_id` to Redis queue for processing (with retry logic and fallback)
- If Redis is unavailable, job is stored in database for later recovery
- Returns immediately (processing happens asynchronously)

### Check Job Status

```http
GET /videos/{upload_id}/job
Authorization: Bearer <token>
```

**Response**: Job status with progress information.

## Job Status Values

The `VideoJob` model tracks processing status:

- `pending`: Job queued in Redis, waiting for worker
- `processing`: Worker actively processing (with progress percentage)
- `ready`: Processing completed successfully, video ready for streaming
- `error`: Processing failed (error message in `message` field)

### Job Progress Tracking

```python
class VideoJob(Base):
    upload_id: str  # Primary key, 8-character unique identifier
    status: str     # Current status (pending/processing/ready/error)
    progress: int   # Progress percentage (0-100)
    eta: str        # Estimated time remaining (HH:MM:SS format)
    message: str    # Status message or error details
```

## Video Processing Details

### FFmpeg Operations

The worker performs these FFmpeg operations:

1. **HLS Transcoding**: Converts video to HLS format with multiple quality variants

   ```bash
   ffmpeg -i input.mp4 -c:v libx264 -c:a aac -hls_time 10 -hls_playlist_type vod output.m3u8
   ```

2. **Thumbnail Generation**: Extracts frame at 1-second mark

   ```bash
   ffmpeg -i input.mp4 -ss 00:00:01 -vframes 1 -q:v 2 thumbnail.jpg
   ```

### Error Handling

- FFmpeg errors are captured from stderr and stored in job `message`
- Worker continues processing other jobs if one fails
- Failed jobs are marked with `error` status

## Scaling

### Multiple Workers

Run multiple worker processes to handle higher throughput:

```bash
# Terminal 1
python start_worker.py

# Terminal 2
python start_worker.py

# Terminal 3
python start_worker.py
```

Workers use Redis `BLPOP` which blocks until a job is available, making it efficient for multiple workers.

### Redis Clustering

For production deployments:

- Use Redis Cluster for horizontal scaling
- Configure Redis Sentinel for high availability
- Consider Redis persistence for job durability

## Monitoring

### Redis Queue Status

Check queue length and inspect jobs:

```python
import redis
r = redis.from_url('redis://localhost:6379/1')

# Check queue length
queue_length = r.llen('video_jobs_queue')
print(f"Jobs in queue: {queue_length}")

# Peek at next job (without removing)
next_job = r.lindex('video_jobs_queue', -1)  # Redis lists are last-in-first-out
print(f"Next job: {next_job}")
```

### Circuit Breaker & Reliability Monitoring

Monitor the health of Redis connections and reliability features:

```python
from src.infrastructure.queue.redis_client import redis_client

# Check circuit breaker status
circuit_status = redis_client.get_circuit_breaker_status()
print(f"Circuit Breaker State: {circuit_status['state']}")
print(f"Failure Count: {circuit_status['failure_count']}")
print(f"Last Failure Time: {circuit_status['last_failure_time']}")

# Check queue statistics (Redis + Database fallback)
queue_stats = redis_client.get_queue_statistics()
print(f"Redis Queue Length: {queue_stats['redis_queue_length']}")
print(f"Database Queue Length: {queue_stats['db_queue_length']}")
print(f"Jobs Recovered: {queue_stats['jobs_recovered']}")
```

### Database Job Status

Query job status directly from database:

```python
from sqlalchemy.orm import Session
from src.infrastructure.db.models import VideoJob, QueuedJob

def get_job_status(db: Session, upload_id: str):
    # Check active job status
    job = db.query(VideoJob).filter(VideoJob.upload_id == upload_id).first()
    if job:
        return {
            "status": job.status,
            "progress": job.progress,
            "eta": job.eta,
            "message": job.message
        }
    
    # Check if job is in fallback queue
    fallback_job = db.query(QueuedJob).filter(QueuedJob.upload_id == upload_id).first()
    if fallback_job:
        return {
            "status": "queued_fallback",
            "message": "Job queued in database (Redis unavailable)"
        }
    
    return None
```

### Worker Logs

Workers log progress using the application logger. Monitor logs for:

- Job consumption: `"Consuming job: {upload_id}"`
- Processing start: `"Processing video: {upload_id}"`
- Progress updates: `"Job {upload_id}: {progress}% complete"`
- Completion: `"Job {upload_id} completed successfully"`
- Errors: `"Job {upload_id} failed: {error_message}"`
- Reliability events: `"Circuit breaker opened"`, `"Redis recovered, migrating jobs"`, `"Job recovered from database"`

## Benefits

1. **Decoupling**: Upload and processing are separate concerns
2. **Scalability**: Multiple workers can process jobs concurrently
3. **Reliability**: Jobs persist in Redis even if workers restart
4. **Fault Tolerance**: Failed jobs don't block the queue
5. **Resilience**: Connection pooling and retry logic handle temporary Redis issues
6. **High Availability**: Circuit breaker prevents cascade failures during outages
7. **Data Integrity**: Job persistence fallback ensures zero job loss
8. **Automatic Recovery**: System recovers automatically when Redis service is restored
9. **Monitoring**: Real-time job status tracking and reliability metrics
10. **Efficiency**: Workers block on Redis BLPOP, no polling overhead

## Troubleshooting

### Common Issues

1. **Worker not processing jobs**: Check Redis connection and queue name
2. **Jobs stuck in pending**: Ensure workers are running and can connect to Redis
3. **Circuit breaker opened**: Redis is experiencing connectivity issues, check Redis service
4. **Jobs in database fallback**: Redis is unavailable, jobs are safely stored in database
5. **FFmpeg errors**: Verify FFmpeg installation and video file integrity
6. **Database connection issues**: Check database URL and connectivity
7. **High retry counts**: Network issues or Redis performance problems

### Reliability-Specific Issues

1. **Circuit Breaker Frequently Opening**: Check Redis stability and network connectivity
2. **Jobs Accumulating in Database**: Redis service is down, monitor for automatic recovery
3. **Connection Pool Exhausted**: Increase pool size or reduce connection timeout
4. **Recovery Process Slow**: Large number of jobs migrating, monitor progress logs

### Debug Commands

```bash
# Check Redis connectivity
redis-cli -u redis://localhost:6379/1 ping

# Monitor Redis commands
redis-cli -u redis://localhost:6379/1 monitor

# Check worker logs
tail -f python.log | grep -i video

# Check circuit breaker status
curl http://localhost:8000/health | jq '.circuit_breaker'

# Check queue statistics
curl http://localhost:8000/health | jq '.queue_stats'

# Monitor database fallback jobs
python -c "from src.infrastructure.db.session import get_db; from src.infrastructure.db.models import QueuedJob; db = next(get_db()); print(f'Fallback jobs: {db.query(QueuedJob).count()}')"
```
