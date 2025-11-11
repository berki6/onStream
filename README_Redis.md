# Video Processing with Redis Job Queue

This FastAPI application uses Redis for asynchronous video processing job queuing, enabling scalable and reliable video transcoding with HLS streaming and thumbnail generation.

## Architecture

### Components

1. **FastAPI Web Server**: Handles video uploads and API requests
2. **Redis Queue**: Stores video processing jobs using a simple list structure
3. **Video Worker**: Consumes jobs from Redis and processes videos using FFmpeg

### Workflow

1. User uploads video via `POST /videos/upload` endpoint
2. Video metadata is saved to database with a unique `upload_id`
3. `VideoJob` record is created in database for tracking processing status
4. `upload_id` is pushed to Redis queue `video_jobs_queue` using `LPUSH`
5. Worker consumes job from Redis using `BLPOP` (blocking pop) and processes video
6. Progress is updated in database via `VideoJob` status fields
7. Processed video (HLS segments + thumbnail) becomes available for streaming

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
POST /videos/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <video_file>
title: <optional_title>
```

**Response**: Video object with `upload_id` for tracking.

**Process**:

- Validates file type, size, and duration using FFmpeg
- Creates database records for video and job tracking
- Pushes `upload_id` to Redis queue for processing
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

### Database Job Status

Query job status directly from database:

```python
from sqlalchemy.orm import Session
from src.schema.models import VideoJob

def get_job_status(db: Session, upload_id: str):
    job = db.query(VideoJob).filter(VideoJob.upload_id == upload_id).first()
    if job:
        return {
            "status": job.status,
            "progress": job.progress,
            "eta": job.eta,
            "message": job.message
        }
```

### Worker Logs

Workers log progress using the application logger. Monitor logs for:

- Job consumption: `"Consuming job: {upload_id}"`
- Processing start: `"Processing video: {upload_id}"`
- Progress updates: `"Job {upload_id}: {progress}% complete"`
- Completion: `"Job {upload_id} completed successfully"`
- Errors: `"Job {upload_id} failed: {error_message}"`

## Benefits

1. **Decoupling**: Upload and processing are separate concerns
2. **Scalability**: Multiple workers can process jobs concurrently
3. **Reliability**: Jobs persist in Redis even if workers restart
4. **Efficiency**: Workers block on Redis BLPOP, no polling overhead
5. **Monitoring**: Real-time job status tracking via database
6. **Fault Tolerance**: Failed jobs don't block the queue

## Troubleshooting

### Common Issues

1. **Worker not processing jobs**: Check Redis connection and queue name
2. **Jobs stuck in pending**: Ensure workers are running and can connect to Redis
3. **FFmpeg errors**: Verify FFmpeg installation and video file integrity
4. **Database connection issues**: Check database URL and connectivity

### Debug Commands

```bash
# Check Redis connectivity
redis-cli -u redis://localhost:6379/1 ping

# Monitor Redis commands
redis-cli -u redis://localhost:6379/1 monitor

# Check worker logs
tail -f python.log | grep -i video
```
