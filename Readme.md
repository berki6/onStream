# OnStream - Video Streaming Platform

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.121.1-green.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-passing-green.svg)](tests/)

A modern, scalable video streaming platform built with FastAPI, featuring asynchronous video processing, HLS streaming, and Redis-based job queuing.

## 🚀 Features

### Core Functionality

- **User Authentication**: JWT-based authentication with secure password hashing
- **Video Upload & Processing**: Asynchronous video transcoding with FFmpeg
- **HLS Streaming**: HTTP Live Streaming for adaptive bitrate video playback
- **Thumbnail Generation**: Automatic thumbnail extraction from video frames
- **Job Queue**: Redis-powered background processing for video transcoding
- **Playlists**: User-created video playlists with custom ordering
- **Analytics**: Video view tracking and analytics (optional)

### Technical Features

- **RESTful API**: Well-documented REST API with OpenAPI/Swagger
- **Database**: SQLAlchemy ORM with support for SQLite, PostgreSQL, and MySQL
- **Migrations**: Alembic for database schema versioning
- **Background Jobs**: Redis-based job queue with worker processes
- **File Storage**: Organized file storage with configurable directories
- **Logging**: Structured logging with configurable levels
- **Health Checks**: Comprehensive health monitoring endpoints
- **CORS Support**: Cross-origin resource sharing configuration

## 📁 Project Structure

```
onstream/
├── src/
│   ├── core/                 # Core application components
│   │   ├── auth.py          # JWT authentication utilities
│   │   ├── config.py        # Application configuration
│   │   ├── database.py      # Database connection and session management
│   │   └── logger.py        # Logging configuration
│   ├── routers/             # API route handlers
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── videos.py        # Video management endpoints
│   │   ├── stream.py        # Video streaming endpoints
│   │   ├── health.py        # Health check endpoints
│   │   └── playlists.py     # Playlist management endpoints
│   ├── schema/              # Data models and schemas
│   │   ├── models.py        # SQLAlchemy database models
│   │   └── schemas.py       # Pydantic API schemas
│   ├── services/            # Business logic services
│   │   └── crud.py          # Database CRUD operations
│   ├── tasks/               # Background job processors
│   │   └── video_worker.py  # Video processing worker
│   ├── utils/               # Utility functions
│   │   └── upload_id.py     # Upload ID generation utilities
│   └── main.py              # FastAPI application entry point
├── tests/                   # Test suite
│   ├── conftest.py          # Test configuration and fixtures
│   ├── test_*.py            # Individual test modules
│   └── sample.mp4           # Test video file
├── alembic/                 # Database migrations
│   └── versions/            # Migration files
├── data/                    # File storage directories
│   ├── uploads/             # Uploaded video files
│   ├── videos/              # Processed video files
│   ├── hls/                 # HLS streaming segments
│   └── thumbnails/          # Generated thumbnails
├── docs/                    # Documentation
├── requirements.txt         # Python dependencies
├── pytest.ini              # Test configuration
├── alembic.ini             # Migration configuration
├── start_worker.py         # Worker process entry point
├── README_Redis.md         # Redis job queue documentation
└── CHANGELOG               # Project changelog
```

## 🛠️ Installation

### Prerequisites

- **Python**: 3.8 or higher
- **FFmpeg**: For video processing and thumbnail generation
- **Redis**: For job queuing (optional, defaults to local Redis instance)

### Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd onstream
   ```

2. **Create virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment configuration**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Database setup**

   ```bash
   # Run database migrations
   alembic upgrade head
   ```

6. **Start Redis server** (if using Redis features)

   ```bash
   redis-server
   ```

## 🚀 Running the Application

### Development Server

```bash
# Start the FastAPI server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: [http://localhost:8000](http://localhost:8000)

- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI)
- **Alternative Docs**: [http://localhost:8000/redoc](http://localhost:8000/redoc) (ReDoc)

### Background Worker

For video processing, start the worker process:

```bash
# Start video processing worker
python start_worker.py
```

For production deployment, run multiple workers:

```bash
# Terminal 1
python start_worker.py

# Terminal 2
python start_worker.py

# Terminal 3
python start_worker.py
```

## 🔧 Configuration

The application uses environment variables for configuration. Copy `.env.example` to `.env` and modify as needed.

### Key Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | - | JWT signing key (required for production) |
| `ENV` | `development` | Environment mode (`development` or `production`) |
| `DATABASE_URL` | `sqlite:///./onstream.db` | Database connection string |
| `REDIS_URL` | `redis://localhost:6379/1` | Redis connection for job queue |
| `MAX_UPLOAD_SIZE` | `104857600` | Maximum video upload size (bytes) |
| `MAX_VIDEO_DURATION_SECONDS` | `3600` | Maximum video duration (seconds) |
| `VIDEO_STORAGE_BASE` | `data` | Base directory for video storage |
| `VIDEO_UPLOAD_SUBDIR` | `uploads` | Upload subdirectory (relative to base) |
| `VIDEO_HLS_SUBDIR` | `hls` | HLS segments subdirectory (relative to base) |
| `VIDEO_THUMBNAIL_SUBDIR` | `thumbnails` | Thumbnails subdirectory (relative to base) |
| `LOG_LEVEL` | `INFO` | Logging level |

### Environment-Specific Path Configuration

The application automatically configures file paths based on the environment:

**Development Mode** (`ENV=development`):

- Base paths are resolved relative to the project root
- Example: `data/uploads` → `/full/path/to/project/data/uploads`

**Production Mode** (`ENV=production`):

- Base paths are treated as absolute (container-friendly)
- Example: `data` → `/app/data` (when running in Docker)

This ensures consistent file handling across development and production environments without manual path manipulation.

## 📚 API Endpoints

### Authentication

- `POST /auth/register` - Register new user
  - **Body**: `{"username": "string", "email": "string", "password": "string"}`
  - **Response**: `201 Created` - User object
  - **Errors**: `400 Bad Request` - Username/email already exists, invalid data
- `POST /auth/login` - User login
  - **Body**: `{"username": "string", "password": "string"}`
  - **Response**: `200 OK` - `{"access_token": "string", "token_type": "bearer"}`
  - **Errors**: `401 Unauthorized` - Invalid credentials

### Videos

- `POST /videos/` - Upload video
  - **Auth**: Bearer token required
  - **Content-Type**: `multipart/form-data`
  - **Body**: `file` (video file), `title` (optional)
  - **Response**: `201 Created` - Video object with `upload_id`
  - **Errors**: `400 Bad Request` - Invalid file type/size, `413 Payload Too Large` - File too large
- `GET /videos/` - List user videos
  - **Auth**: Bearer token required
  - **Query**: `skip` (int, default 0), `limit` (int, default 100, max 100)
  - **Response**: `200 OK` - Array of video objects
- `GET /videos/{upload_id}` - Get video details
  - **Auth**: Bearer token required
  - **Path**: `upload_id` (8-character string)
  - **Response**: `200 OK` - Video object
  - **Errors**: `404 Not Found` - Video not found, `403 Forbidden` - Access denied
- `GET /videos/{upload_id}/job` - Get processing status
  - **Auth**: Bearer token required
  - **Path**: `upload_id` (8-character string)
  - **Response**: `200 OK` - Job status with progress
  - **Errors**: `404 Not Found` - Job not found
- `DELETE /videos/{upload_id}` - Delete video
  - **Auth**: Bearer token required
  - **Path**: `upload_id` (8-character string)
  - **Response**: `204 No Content`
  - **Errors**: `404 Not Found` - Video not found, `403 Forbidden` - Access denied

### Streaming

- `GET /stream/{upload_id}/playlist.m3u8` - Get HLS playlist
  - **Auth**: Bearer token required
  - **Path**: `upload_id` (8-character string)
  - **Response**: `200 OK` - M3U8 playlist file
  - **Errors**: `404 Not Found` - Video not found/ready, `403 Forbidden` - Access denied
- `GET /stream/{upload_id}/{segment}.ts` - Get HLS video segment
  - **Auth**: Bearer token required
  - **Path**: `upload_id` (8-character string), `segment` (filename)
  - **Response**: `200 OK` - TS video segment
  - **Errors**: `404 Not Found` - Segment not found, `403 Forbidden` - Access denied

### Playlists

- `POST /playlists/` - Create playlist
  - **Auth**: Bearer token required
  - **Body**: `{"name": "string"}`
  - **Response**: `201 Created` - Playlist object
  - **Errors**: `400 Bad Request` - Invalid name or duplicate name
- `GET /playlists/` - List user's playlists
  - **Auth**: Bearer token required
  - **Query**: `skip` (int, default 0), `limit` (int, default 100, max 100)
  - **Response**: `200 OK` - Array of playlist objects
- `GET /playlists/{playlist_id}` - Get specific playlist
  - **Auth**: Bearer token required
  - **Path**: `playlist_id` (integer)
  - **Response**: `200 OK` - Playlist object with videos
  - **Errors**: `404 Not Found` - Playlist not found, `403 Forbidden` - Access denied
- `DELETE /playlists/{playlist_id}` - Delete playlist
  - **Auth**: Bearer token required
  - **Path**: `playlist_id` (integer)
  - **Response**: `204 No Content`
  - **Errors**: `404 Not Found` - Playlist not found, `403 Forbidden` - Access denied
- `POST /playlists/{playlist_id}/videos/{upload_id}` - Add video to playlist
  - **Auth**: Bearer token required
  - **Path**: `playlist_id` (integer), `upload_id` (8-character string)
  - **Body**: `{"position": int}` (optional, defaults to end)
  - **Response**: `201 Created`
  - **Errors**: `404 Not Found` - Playlist/video not found, `403 Forbidden` - Access denied
- `DELETE /playlists/{playlist_id}/videos/{upload_id}` - Remove video from playlist
  - **Auth**: Bearer token required
  - **Path**: `playlist_id` (integer), `upload_id` (8-character string)
  - **Response**: `204 No Content`
  - **Errors**: `404 Not Found` - Playlist/video not found, `403 Forbidden` - Access denied
- `GET /playlists/{playlist_id}/videos` - List videos in playlist
  - **Auth**: Bearer token required
  - **Path**: `playlist_id` (integer)
  - **Response**: `200 OK` - Array of video objects with positions
  - **Errors**: `404 Not Found` - Playlist not found, `403 Forbidden` - Access denied
- `PUT /playlists/{playlist_id}/videos/{upload_id}` - Update video position
  - **Auth**: Bearer token required
  - **Path**: `playlist_id` (integer), `upload_id` (8-character string)
  - **Body**: `{"position": int}` (required)
  - **Response**: `200 OK`
  - **Errors**: `404 Not Found` - Playlist/video not found, `403 Forbidden` - Access denied

### Health

- `GET /health` - Application health check
  - **Response**: `200 OK` - `{"status": "healthy", "database": "healthy", "timestamp": "ISO datetime"}`
  - **Errors**: `503 Service Unavailable` - Database unhealthy
- `GET /health/live` - Liveness probe
  - **Response**: `200 OK` - `{"status": "alive"}`
- `GET /health/ready` - Readiness probe
  - **Response**: `200 OK` - `{"status": "ready"}`
  - **Errors**: `503 Service Unavailable` - Database connection failed

## 🧪 Testing

[![Tests](https://img.shields.io/badge/tests-123%20passed-green.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-80.61%25-brightgreen.svg)](tests/)

**Current Test Status**: ✅ **123 tests passed** with **80.61% code coverage** (237 uncovered lines out of 1222 total)

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_videos_extended.py

# Run tests with verbose output
pytest -v
```

### Test Structure

- **Unit Tests**: Individual component testing
- **Integration Tests**: API endpoint testing with database
- **E2E Tests**: Complete workflow testing
- **Fixtures**: Pre-configured test data and database sessions

### Coverage Report

```bash
TOTAL                        1222    237    81%
Required test coverage of 80% reached. Total coverage: 80.61%
================================================ 123 passed in 46.63s ================================================
```

### Test Files

- `test_auth.py` - Authentication endpoints
- `test_crud.py` - Database operations
- `test_models.py` - Data models and schemas
- `test_videos_extended.py` - Video management (extended)
- `test_video_job.py` - Background job processing
- `test_video_worker.py` - Video processing worker
- `test_playlists_extended.py` - Playlist management
- `test_stream.py` - Video streaming endpoints
- `test_e2e.py` - End-to-end workflows

## 🗄️ Database Schema

### Core Tables

- **users**: User accounts and authentication
- **videos**: Video metadata and file references
- **video_jobs**: Background processing job tracking
- **playlists**: User-created video collections
- **playlist_videos**: Many-to-many playlist-video relationships
- **video_views**: Analytics and view tracking

### Schema Documentation

For detailed database schema documentation with Mermaid diagrams, see: **[docs/SCHEMA.md](docs/SCHEMA.md)**

This document includes:

- Entity Relationship Diagrams (ERD)
- Class diagrams for all models
- Pydantic schema documentation
- Field constraints and validation rules
- Database indexes and relationships
- Data flow diagrams

### Migrations

Database schema changes are managed through Alembic:

```bash
# Create new migration
alembic revision --autogenerate -m "migration description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## 🔄 Video Processing Pipeline

1. **Upload**: Video file uploaded via API endpoint
2. **Validation**: File type, size, and duration validation
3. **Queue**: Job added to Redis queue for processing
4. **Processing**: Worker processes video with FFmpeg:
   - HLS segment generation
   - Thumbnail extraction
   - Metadata updates
5. **Completion**: Video marked as ready for streaming

## 📊 Monitoring & Observability

### Logging

Structured logging with configurable levels:

- Console and file output
- Request/response logging
- Error tracking with stack traces

### Health Checks

Comprehensive health monitoring:

- Application status
- Database connectivity
- Redis connectivity
- Background worker status

### Metrics (Optional)

Prometheus metrics support for:

- Request counts and latency
- Database query performance
- Queue processing metrics
- Error rates

## 🚀 Deployment

### Production Considerations

1. **Environment Variables**: Set all required production variables
2. **Database**: Use PostgreSQL or MySQL for production
3. **Redis**: Configure Redis cluster for high availability
4. **File Storage**: Use cloud storage (S3, GCS) for scalability
5. **Reverse Proxy**: Nginx or similar for load balancing
6. **SSL/TLS**: Enable HTTPS in production
7. **Monitoring**: Set up logging and metrics collection

### Docker Deployment

```dockerfile
# Example Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN alembic upgrade head

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 📝 License

Pending.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [SQLAlchemy](https://sqlalchemy.org/) - Python SQL toolkit
- [FFmpeg](https://ffmpeg.org/) - Multimedia processing
- [Redis](https://redis.io/) - In-memory data structure store
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
