# TokenWatch — REST API Reference

Two auth types are used:
- 🔒 **JWT** — short-lived access token for web app sessions (`Authorization: Bearer <jwt>`)
- 🗝️ **SDK Token** — long-lived write-only token for SDK data ingestion (`Authorization: Bearer tw-...`)

All web app endpoints are prefixed with `/api/v1`.

---

## Auth

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
**Response `201`**
```json
{
  "user": { "id": "...", "email": "...", "full_name": "..." },
  "access_token": "...",
  "refresh_token": "..."
}
```

---

### `POST /api/v1/auth/login`
Authenticate and receive tokens.

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
  "expires_in": 900
}
```

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

---

### `POST /api/v1/auth/logout`
Invalidate the current refresh token. 🔒 JWT

**Request**
```json
{ "refresh_token": "..." }
```
**Response `204`** — No content.

---

## Users

### `GET /api/v1/users/me`
Get the authenticated user's profile. 🔒 JWT

**Response `200`**
```json
{
  "id": "...",
  "email": "...",
  "full_name": "...",
  "created_at": "2026-03-07T00:00:00Z"
}
```

---

### `PATCH /api/v1/users/me`
Update the authenticated user's profile. 🔒 JWT

**Request** *(all fields optional)*
```json
{
  "full_name": "Jane Doe",
  "phone": "+1..."
}
```
**Response `200`** — Updated user object.

---

## SDK Tokens

### `POST /api/v1/sdk-tokens`
Generate a new long-lived SDK token. Raw value returned once only — not stored in plaintext. 🔒 JWT

**Request**
```json
{
  "name": "production"
}
```
**Response `201`**
```json
{
  "id": "...",
  "name": "production",
  "token": "tw-abc123...",
  "created_at": "..."
}
```
> ⚠️ `token` is only returned here. Copy it now — it cannot be retrieved again.

---

### `GET /api/v1/sdk-tokens`
List all SDK tokens for the authenticated user. Raw tokens never returned. 🔒 JWT

**Response `200`**
```json
[
  {
    "id": "...",
    "name": "production",
    "created_at": "...",
    "last_used_at": "..."
  }
]
```

---

### `DELETE /api/v1/sdk-tokens/{token_id}`
Revoke an SDK token immediately. Any SDK using it will stop being able to ingest data. 🔒 JWT

**Response `204`** — No content.

---

## Usage Ingestion (SDK → TokenWatch)

### `POST /usage`
Ingest a single usage record from the SDK. 🗝️ SDK Token

This endpoint is called automatically by the SDK after every API response. Not intended for direct use.

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
**Response `200`**
```json
{
  "id": "...",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "tokens_in": 512,
  "tokens_out": 128,
  "cost_usd": 0.000102,
  "latency_ms": 340,
  "timestamp": "..."
}
```

---

## Usage (Dashboard Queries)

### `GET /usage`
Query raw usage records. 🔒 JWT

**Query params**
| Param | Type | Description |
|-------|------|-------------|
| `start` | ISO datetime | Start of date range |
| `end` | ISO datetime | End of date range |
| `provider` | string | Filter by provider |
| `model` | string | Filter by model |
| `app_tag` | string | Filter by app tag |
| `limit` | int | Max records (default 100) |
| `skip` | int | Pagination offset |

**Response `200`**
```json
[
  {
    "id": "...",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "tokens_in": 512,
    "tokens_out": 128,
    "cost_usd": 0.000102,
    "latency_ms": 340,
    "app_tag": "my-app",
    "timestamp": "..."
  }
]
```

---

### `GET /usage/summary`
Aggregated totals grouped by provider + model. 🔒 JWT

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

## Webhooks *(Post-MVP)*

### `POST /api/v1/webhooks`
Register a webhook to receive usage events. 🔒 JWT

**Request**
```json
{ "url": "https://my-app.com/hooks/tokenwatch" }
```
**Response `201`**
```json
{ "id": "...", "url": "...", "created_at": "..." }
```

---

### `GET /api/v1/webhooks`
List registered webhooks. 🔒 JWT

---

### `DELETE /api/v1/webhooks/{webhook_id}`
Remove a webhook. 🔒 JWT — **Response `204`**

---

**Webhook payload** (POST'd to registered URLs after every usage event ingested):
```json
{
  "user_id": "...",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "tokens_in": 512,
  "tokens_out": 128,
  "cost_usd": 0.000102,
  "app_tag": "my-app",
  "timestamp": "..."
}
```

---

## Alerts *(Post-MVP)*

### `GET /api/v1/alerts`
List triggered alerts. 🔒 JWT

**Response `200`**
```json
[
  {
    "id": "...",
    "type": "quota_80",
    "triggered_at": "...",
    "acknowledged": false
  }
]
```
Alert types: `quota_80` | `quota_100` | `spike_detected`

---

### `PATCH /api/v1/alerts/{alert_id}/acknowledge`
Acknowledge an alert. 🔒 JWT — **Response `200`** — Updated alert object.

---

## Optimizer *(Post-MVP)*

### `GET /api/v1/optimizer/suggestions`
Model suggestions with potential savings. 🔒 JWT

**Response `200`**
```json
{
  "potential_savings_usd": 3.42,
  "suggestions": [
    {
      "model_used": "gpt-4o",
      "optimal_model": "gpt-4o-mini",
      "request_count": 80,
      "savings_usd": 2.10,
      "complexity_avg": 2.4
    }
  ]
}
```
