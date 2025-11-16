# Database Schema & Models Documentation

This document provides a comprehensive overview of the OnStream video streaming platform's database schema and Pydantic models, including entity relationships and data structures.

## 📊 Database Schema Overview

### Entity Relationship Diagram (ERD)

```mermaid
erDiagram
    User ||--o{ Video : owns
    User ||--o{ Playlist : creates
    User ||--o{ VideoView : views

    Video ||--o{ VideoView : "has views"
    Video ||--o{ PlaylistVideo : "in playlists"
    Video ||--|| VideoJob : "has job"

    Playlist ||--o{ PlaylistVideo : contains
    PlaylistVideo }o--|| Video : references

    User {
        integer id PK
        string username UK
        string email UK
        string hashed_password
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    Video {
        integer id PK
        string upload_id UK
        integer user_id FK
        string title
        text description
        float duration
        string file_path
        string hls_path
        string thumbnail_path
        enum status
        boolean is_public
        datetime created_at
        datetime updated_at
    }

    VideoView {
        integer id PK
        integer user_id FK
        integer video_id FK
        datetime viewed_at
        float watch_time
        string device_info
    }

    Playlist {
        integer id PK
        integer user_id FK
        string name
        boolean is_public
        datetime created_at
    }

    PlaylistVideo {
        integer id PK
        integer playlist_id FK
        integer video_id FK
        integer position
    }

    VideoJob {
        string upload_id PK
        string status
        integer progress
        integer eta
        text message
        datetime created_at
        datetime updated_at
    }
```

## 🏗️ Database Tables

### Users Table

```mermaid
classDiagram
    class User {
        +integer id (PK)
        +string username (UK, 50)
        +string email (UK, 100)
        +string hashed_password (255)
        +boolean is_active
        +datetime created_at
        +datetime updated_at
        --
        +videos: Video[]
        +playlists: Playlist[]
        +video_views: VideoView[]
    }
```

**Relationships:**

- One-to-many with Video (owns videos)
- One-to-many with Playlist (creates playlists)
- One-to-many with VideoView (views videos)

### Videos Table

```mermaid
classDiagram
    class Video {
        +integer id (PK)
        +string upload_id (UK, 12)
        +integer user_id (FK)
        +string title (200)
        +text description
        +float duration
        +string file_path (500)
        +string hls_path (500)
        +string thumbnail_path (500)
        +VideoStatus status
        +boolean is_public
        +datetime created_at
        +datetime updated_at
        --
        +owner: User
        +views: VideoView[]
    }
```

**Relationships:**

- Many-to-one with User (belongs to owner)
- One-to-many with VideoView (has views)
- One-to-one with VideoJob (processing job)
- Many-to-many with Playlist (through PlaylistVideo)

### Video Jobs Table

```mermaid
classDiagram
    class VideoJob {
        +string upload_id (PK)
        +string status
        +integer progress
        +integer eta
        +text message
        +datetime created_at
        +datetime updated_at
    }
```

**Purpose:** Tracks background video processing jobs with progress and status.

### Video Views Table (Analytics)

```mermaid
classDiagram
    class VideoView {
        +integer id (PK)
        +integer user_id (FK, nullable)
        +integer video_id (FK)
        +datetime viewed_at
        +float watch_time
        +string device_info (200)
        --
        +viewer: User?
        +video: Video
    }
```

**Purpose:** Analytics table for tracking video views and watch time.

### Playlists Table

```mermaid
classDiagram
    class Playlist {
        +integer id (PK)
        +integer user_id (FK)
        +string name (100)
        +boolean is_public
        +datetime created_at
        --
        +owner: User
        +videos: PlaylistVideo[]
    }
```

**Relationships:**

- Many-to-one with User (belongs to creator)
- One-to-many with PlaylistVideo (contains videos)

### Playlist Videos Table (Junction)

```mermaid
classDiagram
    class PlaylistVideo {
        +integer id (PK)
        +integer playlist_id (FK)
        +integer video_id (FK)
        +integer position
        --
        +playlist: Playlist
        +video: Video
    }
```

**Purpose:** Junction table for many-to-many relationship between Playlists and Videos, with ordering support.

## 📋 Pydantic Models

### Authentication Models

```mermaid
classDiagram
    class UserBase {
        +string username*
        +string email*
        --
        +validate_username_format()
        +validate_email_format()
    }

    class UserCreate {
        +string username*
        +string email*
        +string password*
        --
        +validate_password_strength()
    }

    class User {
        +string username
        +string email
        +integer id
        +datetime created_at
    }

    class Token {
        +string access_token
        +string token_type
    }

    class TokenData {
        +string username?
    }

    UserBase <|-- UserCreate
    UserBase <|-- User
```

### Video Models

```mermaid
classDiagram
    class VideoStatus {
        <<enumeration>>
        PENDING
        PROCESSING
        READY
        ERROR
        DELETED
    }

    class VideoBase {
        +string title*
        +string description?
        +float duration?
        --
        +validate_title_content()
        +validate_description()
        +validate_duration()
    }

    class VideoCreate {
        +string title*
        +string description?
        +float duration?
        +string file_path*
        --
        +validate_file_path()
    }

    class Video {
        +string title
        +string description?
        +float duration?
        +string upload_id
        +integer user_id
        +string file_path
        +string hls_path?
        +string thumbnail_path?
        +VideoStatus status
        +boolean is_public
        +datetime created_at
        +datetime updated_at
        --
        +validate_upload_id()
    }

    class VideoResponse {
        // Same as Video
    }

    VideoBase <|-- VideoCreate
    VideoBase <|-- Video
    Video <|-- VideoResponse
```

### Job Processing Models

```mermaid
classDiagram
    class VideoJobBase {
        +string upload_id*
        +string status
        +integer progress
        +integer eta
        +string message?
    }

    class VideoJobCreate {
        // Same as VideoJobBase
    }

    class VideoJob {
        +string upload_id
        +string status
        +integer progress
        +integer eta
        +string message?
        +datetime created_at
        +datetime updated_at
    }

    class VideoJobResponse {
        // Same as VideoJob
    }

    VideoJobBase <|-- VideoJobCreate
    VideoJobBase <|-- VideoJob
    VideoJob <|-- VideoJobResponse
```

### Playlist Models

```mermaid
classDiagram
    class PlaylistBase {
        +string name*
        --
        +validate_playlist_name()
    }

    class PlaylistCreate {
        // Same as PlaylistBase
    }

    class Playlist {
        +string name
        +integer id
        +integer user_id
        +boolean is_public
        +datetime created_at
    }

    class PlaylistResponse {
        +string name
        +integer id
        +integer user_id
        +boolean is_public
        +datetime created_at
        +Video[] videos?
    }

    class PlaylistVideoBase {
        +integer position*
    }

    class PlaylistVideoCreate {
        // Same as PlaylistVideoBase
    }

    class PlaylistVideo {
        +integer position
        +integer id
        +integer playlist_id
        +integer video_id
    }

    PlaylistBase <|-- PlaylistCreate
    PlaylistBase <|-- Playlist
    Playlist <|-- PlaylistResponse
    PlaylistVideoBase <|-- PlaylistVideoCreate
    PlaylistVideoBase <|-- PlaylistVideo
```

## 🔄 Data Flow & Relationships

### Video Upload & Processing Flow

```mermaid
flowchart TD
    A[User Uploads Video] --> B[VideoCreate Schema]
    B --> C[Video Model Created]
    C --> D[VideoJob Created]
    D --> E[Job Queued in Redis]
    E --> F[Worker Processes Video]
    F --> G[FFmpeg Transcoding]
    G --> H[HLS Segments Generated]
    H --> I[Thumbnail Created]
    I --> J[Video Status: READY]

    K[Error Occurs] --> L[Video Status: ERROR]
    M[Job Fails] --> N[VideoJob Status: error]

    C --> O[Database: videos table]
    D --> P[Database: video_jobs table]
    J --> Q[Update video record]
    L --> R[Update video record]
    N --> S[Update job record]
```

### User Authentication Flow

```mermaid
flowchart TD
    A[User Registration] --> B[UserCreate Schema]
    B --> C[Validate Password Strength]
    C --> D[Hash Password]
    D --> E[Create User Record]
    E --> F[JWT Token Generated]

    G[User Login] --> H[Verify Credentials]
    H --> I[Generate Access Token]
    I --> J[Return Token]

    K[API Request] --> L[Validate JWT Token]
    L --> M[Extract User Info]
    M --> N[Authorize Request]

    E --> O[Database: users table]
    F --> P[Return Token Response]
    J --> Q[Return Token Response]
```

## 📏 Field Constraints & Validation

### String Length Limits

| Model | Field | Min | Max | Notes |
|-------|-------|-----|-----|-------|
| User | username | 4 | 50 | Alphanumeric + _ - |
| User | email | 5 | 100 | Email format |
| User | password | 8 | - | Strength requirements |
| Video | title | 2 | 200 | XSS prevention |
| Video | description | - | 2000 | XSS prevention |
| Video | upload_id | 8 | 12 | Alphanumeric |
| Playlist | name | 1 | 100 | XSS prevention |

### Numeric Constraints

| Model | Field | Min | Max | Type | Notes |
|-------|-------|-----|-----|------|-------|
| Video | duration | 0 | 43200 | Float | Seconds (max 12 hours) |
| VideoJob | progress | 0 | 100 | Integer | Percentage |
| PlaylistVideo | position | 0 | - | Integer | Ordering in playlist |

### Validation Rules

#### Username Validation

- Only letters, numbers, underscores, hyphens
- Cannot start/end with underscore or hyphen
- No consecutive underscores or hyphens

#### Password Validation

- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

#### Email Validation

- Standard email format regex
- Must contain @ and domain

#### Video Title/Description

- XSS prevention (script tag removal)
- Title cannot be just whitespace
- Description converts empty strings to null

#### File Path Validation

- Prevents directory traversal (..)
- Only specific video extensions allowed
- Special case for "temp" during upload

#### File Path Storage & Environment Configuration

- **Environment-Specific Configuration**: Paths are configured per environment (development/production/container)
- **Base Path**: `VIDEO_STORAGE_BASE` defaults to `"data"` (relative in dev, absolute in production)
- **Computed Properties**: `VIDEO_UPLOAD_DIR`, `VIDEO_HLS_DIR`, `VIDEO_THUMBNAIL_DIR` are computed from base path
- **Storage Format**: Full filesystem paths are stored directly (no normalization)
- **Cross-Platform**: Automatic path resolution using `pathlib.Path`
- **Container-Ready**: Supports absolute paths for Docker/Kubernetes deployments

**Configuration Variables**:

- `VIDEO_STORAGE_BASE`: Base directory for all video storage (default: `"data"`)
- `VIDEO_UPLOAD_SUBDIR`: Upload subdirectory (default: `"uploads"`)
- `VIDEO_HLS_SUBDIR`: HLS subdirectory (default: `"hls"`)
- `VIDEO_THUMBNAIL_SUBDIR`: Thumbnail subdirectory (default: `"thumbnails"`)

**Environment Behavior**:

- **Development**: Relative paths resolved to absolute from project root
- **Production**: Absolute paths (e.g., `/app/data`) for container compatibility

## 🔗 Database Indexes

### Primary Keys

- `users.id`
- `videos.id`
- `video_views.id`
- `playlists.id`
- `playlist_videos.id`
- `video_jobs.upload_id`

### Unique Constraints

- `users.username`
- `users.email`
- `videos.upload_id`
- `playlist_videos(playlist_id, video_id)` - Prevents duplicate videos in playlist

### Performance Indexes

- `users.username` - Login lookups
- `users.email` - Registration checks
- `videos.user_id` - User's videos
- `videos.status` - Status filtering
- `videos.upload_id` - Video lookups
- `video_views.video_id, viewed_at` - Analytics queries
- `playlists.user_id` - User's playlists
- `playlist_videos.playlist_id` - Playlist contents
- `playlist_videos.video_id` - Video playlist membership

## 🏷️ Enums & Constants

### VideoStatus Enum

```python
class VideoStatus(str, Enum):
    PENDING = "PENDING"      # Initial state after upload
    PROCESSING = "PROCESSING"  # Worker is processing
    READY = "READY"         # Ready for streaming
    ERROR = "ERROR"         # Processing failed
    DELETED = "DELETED"     # Soft deleted
```

### Default Values

- `User.is_active = True`
- `Video.status = VideoStatus.PENDING`
- `Video.is_public = False`
- `Playlist.is_public = False`
- `VideoJob.status = "processing"`
- `VideoJob.progress = 0`
- `PlaylistVideo.position = 0`

## 🔄 Migration History

### Alembic Migrations

1. **353315e7c3a7** - Initial schema (users, videos, video_views, playlists, playlist_videos)
2. **4794218915c6** - Add upload_id to video table
3. **6688bdf12b34** - Add video_jobs table for background processing

This schema supports a complete video streaming platform with user management, video upload/processing, playlists, and analytics capabilities.
