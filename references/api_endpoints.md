# TikTok Content Posting API — Endpoint Reference

All endpoints are under `https://open-api.tiktok.com`.

---

## Video Upload to Inbox (Draft)

### Step 1: Initialize Upload

**`POST /v2/post/publish/inbox/video/init/`**

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body:**
```json
{
  "source_info": {
    "source": "FILE_UPLOAD",
    "video_size": 25165824,
    "chunk_size": 10485760,
    "total_chunk_count": 3
  }
}
```

**Response:**
```json
{
  "data": {
    "publish_id": "v_inbox_file~v2.abc123def456",
    "upload_url": "https://upload.tiktok.com/v2/upload/video/..."
  },
  "error": {
    "code": "ok",
    "message": "",
    "log_id": "20260729120000A1B2C3D4"
  }
}
```

### Step 2: Upload Chunks

**`PUT {upload_url}`** (from step 1)

**Headers:**
```
Content-Range: bytes 0-10485759/25165824
Content-Type: video/mp4
```

**Chunking rules:**
- Chunk size: 5–64 MB per chunk (default: 10 MB)
- Chunks must be sequential — TikTok rejects out-of-order chunks
- Content-Range must be exact: `bytes {start}-{end}/{total}`
- The `upload_url` already includes query params — append `&chunk={index}` for each chunk

**Response:** `200 OK` (empty body) on success

### Step 3: Poll Status

**`POST /v2/post/publish/status/fetch/`**

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body:**
```json
{
  "publish_id": "v_inbox_file~v2.abc123def456"
}
```

**Response (processing):**
```json
{
  "data": {
    "status": "PROCESSING"
  }
}
```

**Response (success):**
```json
{
  "data": {
    "status": "SEND_TO_USER_INBOX"
  }
}
```

**Response (failed):**
```json
{
  "data": {
    "status": "FAILED",
    "error": {
      "code": "media_processing_failed",
      "message": "Video format not supported"
    }
  }
}
```

---

## Photo Upload to Inbox (Draft)

### Step 1: Initialize Upload

**`POST /v2/post/publish/content/init/`**

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body:**
```json
{
  "post_mode": "MEDIA_UPLOAD",
  "media_type": "PHOTO",
  "post_info": {
    "title": "Check out this product! ✨",
    "privacy_level": "PUBLIC_TO_EVERYONE",
    "disable_duet": false,
    "disable_stitch": false,
    "disable_comment": false
  },
  "source_info": {
    "source": "FILE_UPLOAD",
    "photo_size": 1048576,
    "chunk_size": 1048576,
    "total_chunk_count": 1
  }
}
```

### Step 2: Upload File

**`PUT {upload_url}`**

**Headers:**
```
Content-Range: bytes 0-{filesize-1}/{filesize}
Content-Type: image/jpeg
```

### Step 3: Poll Status

Same as video — `POST /v2/post/publish/status/fetch/`

---

## Token Refresh

**`POST /v2/oauth/token/`**

**Body (form-urlencoded):**
```
client_key=YOUR_CLIENT_KEY
client_secret=YOUR_CLIENT_SECRET
grant_type=refresh_token
refresh_token=THE_REFRESH_TOKEN
```

**Response:**
```json
{
  "data": {
    "access_token": "clt.new.access.token",
    "expires_in": 86400,
    "refresh_token": "clt.new.refresh.token",
    "refresh_expires_in": 31536000,
    "token_type": "Bearer"
  }
}
```

---

## Error Codes

| Code | Meaning | HTTP Status |
|---|---|---|
| `ok` | Success | 200 |
| `access_token_invalid` | Token expired or invalid | 401 |
| `permission_denied` | Missing API scope | 403 |
| `too_many_requests` | Rate limit exceeded | 429 |
| `spam_risk_too_many_posts` | Daily post limit reached | 429 |
| `media_processing_failed` | File rejected during processing | 400 |
| `invalid_parameter` | Missing or invalid field | 400 |
