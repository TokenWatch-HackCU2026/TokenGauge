# TokenWatch — REST API Reference

All endpoints are prefixed with `/api/v1`. Protected routes require `Authorization: Bearer <access_token>`.

---

## Auth

### `POST /auth/register`
Register a new user and create an organization.

**Request**
```json
{
  "email": "user@example.com",
  "password": "...",
  "org_name": "My Company"
}
```
**Response `201`**
```json
{
  "user": { "id": "...", "email": "...", "org_id": "..." },
  "access_token": "...",
  "refresh_token": "..."
}
```

---

### `POST /auth/login`
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

### `POST /auth/refresh`
Exchange a refresh token for a new access token.

**Request**
```json
{
  "refresh_token": "..."
}
```
**Response `200`**
```json
{
  "access_token": "...",
  "expires_in": 900
}
```

---

### `POST /auth/logout`
Invalidate the current refresh token. 🔒 Protected.

**Request**
```json
{
  "refresh_token": "..."
}
```
**Response `204`** — No content.

---

## Users

### `GET /users/me`
Get the authenticated user's profile. 🔒 Protected.

**Response `200`**
```json
{
  "id": "...",
  "email": "...",
  "org_id": "...",
  "phone": "+1...",
  "created_at": "2026-03-07T00:00:00Z"
}
```

---

### `PATCH /users/me`
Update the authenticated user's profile. 🔒 Protected.

**Request** *(all fields optional)*
```json
{
  "phone": "+1..."
}
```
**Response `200`** — Updated user object.

---

## Organizations

### `GET /orgs/me`
Get the authenticated user's organization. 🔒 Protected.

**Response `200`**
```json
{
  "id": "...",
  "name": "My Company",
  "plan": "free",
  "owner_id": "...",
  "created_at": "..."
}
```

---

### `PATCH /orgs/me`
Update the organization name. 🔒 Protected.

**Request**
```json
{
  "name": "New Org Name"
}
```
**Response `200`** — Updated org object.

---

## API Key Vault

### `POST /keys`
Register an AI provider key. Key is encrypted at rest via AWS KMS. 🔒 Protected.

**Request**
```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-..."
}
```
**Response `201`**
```json
{
  "id": "...",
  "provider": "anthropic",
  "key_hint": "a1b2",
  "created_at": "..."
}
```

---

### `GET /keys`
List all registered keys for the authenticated user. Raw keys are never returned. 🔒 Protected.

**Response `200`**
```json
[
  {
    "id": "...",
    "provider": "anthropic",
    "key_hint": "a1b2",
    "created_at": "..."
  }
]
```

---

### `DELETE /keys/{key_id}`
Delete a registered key. 🔒 Protected.

**Response `204`** — No content.

---

## Proxy

### `POST /proxy/{provider}/{model}`
Forward an AI request through the TokenWatch gateway. The gateway authenticates the user, enforces rate limits, decrypts the provider key in-memory, forwards the request, logs usage, and returns the provider's response unmodified. 🔒 Protected.

**Path params**
- `provider` — `anthropic` | `openai` | `google` | `mistral`
- `model` — e.g. `claude-3-5-sonnet`, `gpt-4o`, `gemini-1.5-flash`, `mistral-large`

**Headers** *(optional)*
- `X-App-Tag: my-app` — tag this request for per-application tracking

**Request** *(mirrors provider API shape)*
```json
{
  "messages": [
    { "role": "user", "content": "Hello" }
  ],
  "max_tokens": 1024,
  "temperature": 0.7
}
```
**Response `200`** — Raw provider response, unmodified.

**Response `429`** — Rate limit exceeded.
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 42
}
```

---

## Usage

### `GET /usage`
Query raw usage records from `api_calls`. 🔒 Protected.

**Query params**
| Param | Type | Description |
|-------|------|-------------|
| `start` | ISO datetime | Start of date range |
| `end` | ISO datetime | End of date range |
| `provider` | string | Filter by provider |
| `model` | string | Filter by model |
| `app_tag` | string | Filter by app tag |
| `limit` | int | Max records (default 100) |
| `offset` | int | Pagination offset |

**Response `200`**
```json
{
  "total": 1200,
  "records": [
    {
      "id": "...",
      "provider": "anthropic",
      "model": "claude-3-5-sonnet",
      "tokens_in": 512,
      "tokens_out": 256,
      "cost_usd": 0.0054,
      "latency_ms": 340,
      "app_tag": "my-app",
      "timestamp": "..."
    }
  ]
}
```

---

### `GET /usage/summary`
Aggregated token and cost totals grouped by time bucket. 🔒 Protected.

**Query params**
| Param | Type | Description |
|-------|------|-------------|
| `start` | ISO datetime | Start of date range |
| `end` | ISO datetime | End of date range |
| `group_by` | `hour` \| `day` | Time bucket size (default `day`) |
| `provider` | string | Optional filter |
| `model` | string | Optional filter |
| `app_tag` | string | Optional filter |

**Response `200`**
```json
[
  {
    "date": "2026-03-07",
    "provider": "anthropic",
    "model": "claude-3-5-sonnet",
    "total_tokens_in": 50000,
    "total_tokens_out": 25000,
    "total_cost_usd": 0.525,
    "request_count": 42,
    "avg_latency_ms": 310
  }
]
```

---

### `GET /usage/cost`
Cost breakdown by provider and model for a time range. 🔒 Protected.

**Query params** — `start`, `end` (required)

**Response `200`**
```json
{
  "total_cost_usd": 12.45,
  "by_provider": [
    { "provider": "anthropic", "cost_usd": 8.20, "request_count": 300 }
  ],
  "by_model": [
    { "model": "claude-3-5-sonnet", "cost_usd": 6.10, "request_count": 180 }
  ]
}
```

---

## Rate Limits

### `GET /rate-limits`
Get the authenticated user's current quota usage and limit status. 🔒 Protected.

**Response `200`**
```json
{
  "tokens_per_minute": {
    "limit": 100000,
    "used": 24000,
    "remaining": 76000,
    "reset_at": "2026-03-07T00:01:00Z"
  },
  "tokens_per_day": {
    "limit": 5000000,
    "used": 1200000,
    "remaining": 3800000,
    "reset_at": "2026-03-08T00:00:00Z"
  }
}
```

---

## Webhooks *(Post-MVP)*

### `POST /webhooks`
Register a webhook endpoint to receive usage events after every proxy request. 🔒 Protected.

**Request**
```json
{
  "url": "https://my-app.com/hooks/tokenwatch"
}
```
**Response `201`**
```json
{
  "id": "...",
  "url": "https://my-app.com/hooks/tokenwatch",
  "created_at": "..."
}
```

---

### `GET /webhooks`
List all registered webhook endpoints. 🔒 Protected.

**Response `200`**
```json
[
  { "id": "...", "url": "...", "created_at": "..." }
]
```

---

### `DELETE /webhooks/{webhook_id}`
Remove a webhook endpoint. 🔒 Protected.

**Response `204`** — No content.

---

### `GET /webhooks/{webhook_id}/logs`
View recent delivery attempt logs for a webhook. 🔒 Protected.

**Response `200`**
```json
[
  {
    "id": "...",
    "webhook_id": "...",
    "status": "delivered",
    "attempts": 1,
    "response_status": 200,
    "delivered_at": "..."
  }
]
```

**Webhook payload** (POST'd to registered URLs after every proxy request):
```json
{
  "user_id": "...",
  "provider": "anthropic",
  "model": "claude-3-5-sonnet",
  "tokens_in": 512,
  "tokens_out": 256,
  "cost_usd": 0.0054,
  "app_tag": "my-app",
  "timestamp": "..."
}
```

---

## Alerts *(Post-MVP)*

### `GET /alerts`
List triggered alerts for the authenticated user. 🔒 Protected.

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

### `PATCH /alerts/{alert_id}/acknowledge`
Mark an alert as acknowledged. 🔒 Protected.

**Response `200`** — Updated alert object.

---

## Optimizer *(Post-MVP)*

### `GET /optimizer/suggestions`
Weekly model suggestions — shows what model would have been optimal per request and the potential savings. 🔒 Protected.

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

---

### `GET /optimizer/report`
Usage summary report categorized by prompt type and model. 🔒 Protected.

**Query params** — `start`, `end`

**Response `200`**
```json
{
  "period": { "start": "...", "end": "..." },
  "by_type": [
    {
      "type": "chat",
      "request_count": 200,
      "cost_usd": 1.20,
      "optimal_model": "claude-3-haiku",
      "potential_savings_usd": 0.80
    }
  ]
}
```
