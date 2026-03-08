# TokenGauge — REST API Reference

Base URL: `http://localhost:3001`

## Authentication

Two auth mechanisms:
- **JWT** — short-lived access token (15 min) for web app sessions (`Authorization: Bearer <jwt>`)
- **SDK Token** — long-lived token (1 year) for SDK data ingestion (`Authorization: Bearer <sdk-jwt>`)

Both are validated by the same `get_current_user` dependency. Any endpoint marked 🔒 requires a valid Bearer token.

---

## Health

### `GET /health`
Returns API health status. No authentication required.

**Response `200`**
```json
{ "status": "ok" }
```

---

## Auth (`/api/v1/auth`)

### `POST /api/v1/auth/register`
Register a new user account.

**Request**
```json
{
  "email": "user@example.com",
  "password": "...",
  "full_name": "Jane Doe"
}
```
- `full_name` is optional.

**Response `201`**
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "user": {
    "id": "...",
    "email": "...",
    "full_name": "...",
    "avatar_url": null,
    "phone": null,
    "created_at": "2026-03-07T00:00:00Z"
  }
}
```

**Errors:** `409` email already registered, `422` validation error.

---

### `POST /api/v1/auth/login`
Authenticate with email/password and receive tokens.

**Request**
```json
{
  "email": "user@example.com",
  "password": "..."
}
```

**Response `200`**
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 900,
  "user": { ... }
}
```

**Errors:** `401` invalid credentials, `422` validation error.

---

### `POST /api/v1/auth/refresh`
Exchange a refresh token for a new access token.

**Request**
```json
{ "refresh_token": "..." }
```

**Response `200`**
```json
{
  "access_token": "...",
  "expires_in": 900
}
```

**Errors:** `401` invalid/expired refresh token, `422` validation error.

---

### `POST /api/v1/auth/logout`
Invalidate the current refresh token. Idempotent — garbage tokens return 204.

**Request**
```json
{ "refresh_token": "..." }
```

**Response `204`** — No content.

**Errors:** `422` missing body.

---

### `GET /api/v1/auth/google`
Get the Google OAuth redirect URL. Requires `GOOGLE_CLIENT_ID` and `GOOGLE_REDIRECT_URI` env vars.

**Response `200`**
```json
{ "url": "https://accounts.google.com/o/oauth2/v2/auth?..." }
```

---

### `GET /api/v1/auth/google/callback`
Google OAuth callback. Exchanges the authorization code for tokens, creates or links user account.

**Query params:** `code` (string, required)

**Response `200`**
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "user": { ... }
}
```

**Errors:** `400` token exchange or userinfo fetch failed.

---

### `GET /api/v1/auth/sdk-token` 🔒
Get or regenerate the user's persistent SDK token (valid 1 year).

**Query params:** `regenerate` (bool, optional, default `false`)

**Response `200`**
```json
{ "sdk_token": "..." }
```

Calling without `regenerate` returns the same token. Pass `?regenerate=true` to rotate.

---

## Usage (`/usage`) 🔒

All usage endpoints require authentication.

### `POST /usage/`
Log a new API call usage record.

**Request**
```json
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "tokens_in": 512,
  "tokens_out": 128,
  "cost_usd": 0.000102,
  "latency_ms": 340,
  "app_tag": "my-app"
}
```
- `app_tag` is optional.

**Response `200`**
```json
{
  "id": "...",
  "user_id": "...",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "tokens_in": 512,
  "tokens_out": 128,
  "cost_usd": 0.000102,
  "latency_ms": 340,
  "app_tag": "my-app",
  "timestamp": "..."
}
```

**Errors:** `401` unauthenticated, `422` validation error.

---

### `GET /usage/`
List raw usage records (paginated, sorted newest-first). Users only see their own records.

**Query params**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 100 | Max records to return |
| `skip` | int | 0 | Pagination offset |

**Response `200`** — Array of usage record objects.

---

### `GET /usage/summary`
Aggregated totals grouped by provider + model. No date filtering — covers all records.

**Response `200`**
```json
[
  {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "total_tokens_in": 50000,
    "total_tokens_out": 25000,
    "total_cost_usd": 0.525,
    "request_count": 42
  }
]
```

---

### `DELETE /usage/{record_id}`
Delete a specific usage record. Owner-only.

**Response `200`**
```json
{ "ok": true }
```

**Errors:** `403` not your record, `404` record not found, `422` invalid ID format.

---

## Dashboard (`/dashboard`) 🔒

All dashboard endpoints require authentication. Responses are cached in Redis (60s TTL). Default date range is the last 7 days if `start_date`/`end_date` are not provided.

### `GET /dashboard/summary`
Aggregated stats across all usage within a date window.

**Query params**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `start_date` | ISO datetime | 7 days ago | Start of range |
| `end_date` | ISO datetime | now | End of range |
| `provider` | string | — | Filter by provider |
| `model` | string | — | Filter by model |
| `app_tag` | string | — | Filter by app tag |

**Response `200`**
```json
{
  "total_tokens_in": 50000,
  "total_tokens_out": 25000,
  "total_cost_usd": 1.23,
  "request_count": 150,
  "avg_latency_ms": 420.5
}
```

Returns zeroes for all fields if no data matches the filters.

---

### `GET /dashboard/timeseries`
Time-series data grouped by day or hour.

**Query params**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `start_date` | ISO datetime | 7 days ago | Start of range |
| `end_date` | ISO datetime | now | End of range |
| `group_by` | `"day"` \| `"hour"` | `"day"` | Grouping interval |
| `provider` | string | — | Filter by provider |
| `model` | string | — | Filter by model |

**Response `200`**
```json
[
  {
    "date": "2026-03-07",
    "tokens_in": 5000,
    "tokens_out": 2500,
    "cost_usd": 0.12,
    "request_count": 15
  }
]
```

Date format: `YYYY-MM-DD` for day, `YYYY-MM-DDTHH:00:00Z` for hour. Sorted ascending.

---

### `GET /dashboard/breakdown`
Provider/model breakdown sorted by cost descending.

**Query params**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `start_date` | ISO datetime | 7 days ago | Start of range |
| `end_date` | ISO datetime | now | End of range |

**Response `200`**
```json
[
  {
    "provider": "openai",
    "model": "gpt-4o",
    "tokens_in": 10000,
    "tokens_out": 5000,
    "cost_usd": 0.85,
    "request_count": 20
  }
]
```

---

### `GET /dashboard/quota`
Daily token quota status. Uses Redis sorted sets for tracking.

**Response `200`**
```json
{
  "limit": 1000000,
  "used": 42000,
  "remaining": 958000,
  "reset_at": 1709856000000,
  "window_ms": 86400000
}
```

- `limit`: 1,000,000 tokens/day
- `window_ms`: 24-hour sliding window (86,400,000 ms)
- `reset_at`: Unix timestamp in ms when the window resets
- Fail-open: if Redis is unavailable, `used` returns 0

---

## Endpoint Summary

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | Health check |
| POST | `/api/v1/auth/register` | — | Register |
| POST | `/api/v1/auth/login` | — | Login |
| POST | `/api/v1/auth/refresh` | — | Refresh access token |
| POST | `/api/v1/auth/logout` | — | Logout |
| GET | `/api/v1/auth/google` | — | Google OAuth URL |
| GET | `/api/v1/auth/google/callback` | — | Google OAuth callback |
| GET | `/api/v1/auth/sdk-token` | 🔒 | Get/regenerate SDK token |
| POST | `/usage/` | 🔒 | Log usage record |
| GET | `/usage/` | 🔒 | List usage records |
| GET | `/usage/summary` | 🔒 | Usage summary by provider+model |
| DELETE | `/usage/{record_id}` | 🔒 | Delete usage record |
| GET | `/dashboard/summary` | 🔒 | Aggregated stats |
| GET | `/dashboard/timeseries` | 🔒 | Time-series data |
| GET | `/dashboard/breakdown` | 🔒 | Provider/model breakdown |
| GET | `/dashboard/quota` | 🔒 | Daily quota status |

**Total: 16 endpoints** (6 public, 10 authenticated)
