# TokenWatch — System Architecture

## Overview

TokenWatch is a multi-tenant SaaS AI gateway and usage intelligence platform. All AI provider traffic routes through the TokenWatch proxy, enabling unified logging, cost tracking, key security, rate limiting, and model optimization.

```
User App → TokenWatch Proxy → AI Provider (Anthropic / OpenAI / Google / Mistral)
                 ↓
         Usage Logger → MongoDB (api_calls)
                 ↓
         Redis (rate limits, cache)
                 ↓
         Dashboard API → Frontend
```

---

## System Components

### 1. AI Gateway / Proxy
- Intercepts all incoming AI requests
- Authenticates the calling user via JWT or TokenWatch API key
- Looks up the user's stored provider API key (decrypts via AWS KMS in-memory only)
- Forwards the request to the target AI provider
- Captures response, measures latency, calculates token cost
- Logs usage to MongoDB `api_calls` collection
- Enforces rate limits via Redis sliding window
- Raw provider keys never touch the database — decrypted in memory, used once, discarded

### 2. Auth System
- JWT-based authentication (access token + refresh token)
- User registration, login, logout endpoints
- Organization (multi-tenant) support — users belong to orgs
- Middleware validates JWT on all protected routes

### 3. API Key Vault
- Users register their AI provider API keys via the vault API
- Keys encrypted using AWS KMS envelope encryption (AES-256 data key, wrapped by KMS CMK)
- MongoDB stores only: `{ encryptedBlob, keyHint (last 4 chars), provider, userId }`
- Raw keys exist only in-memory during a proxy request lifecycle
- Every decryption event is audit-logged: `{ userId, keyId, timestamp, requestId }`

### 4. Usage Database (MongoDB)
Collections:
- `users` — id, email, passwordHash, orgId, createdAt
- `orgs` — id, name, plan, ownerId, createdAt
- `api_keys` — id, userId, provider, encryptedBlob, keyHint, createdAt
- `api_calls` — id, userId, orgId, provider, model, tokensIn, tokensOut, costUsd, latencyMs, appTag, timestamp
- `usage_summaries` — aggregated daily/weekly rollups per user/org
- `alerts` — id, userId, type (limit/spike), threshold, triggeredAt, acknowledged
- `spike_events` — id, userId, detectedAt, baselineTokens, actualTokens, multiplier

### 5. Redis
- Rate limit counters: `ratelimit:{userId}` sliding window (tokens per minute/hour/day)
- Session cache: JWT validation cache (TTL 300s)
- Dashboard cache: usage query results (TTL 60s)
- BullMQ job queues: async alert processing, spike detection, webhook delivery

### 6. Dashboard
- Real-time usage charts (tokens over time, cost over time)
- Cost breakdown by provider and model
- Filterable by: date range, provider, model, app tag
- Rate limit status and quota remaining
- Key vault management UI

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API Server | Python + FastAPI |
| Frontend | React + Vite + Tailwind CSS |
| Primary DB | MongoDB (Atlas or self-hosted) |
| Cache / Queue | Redis + arq |
| Key Management | AWS KMS (envelope encryption) |
| Auth | JWT (python-jose) + passlib[bcrypt] |
| Proxy | httpx (async) for provider forwarding |
| Containerization | Docker + docker-compose |
| Cost Calculation | Static pricing table per provider/model |

---

## Request Flow (Proxy)

1. Client sends POST `/proxy/{provider}/{model}` with `Authorization: Bearer <tokenwatch-jwt>`
2. Gateway middleware validates JWT → extracts userId
3. Redis rate limiter checks sliding window → reject if over quota
4. Key vault retrieves encrypted blob for this user+provider → KMS decrypts → raw key in memory
5. Request forwarded to provider with raw key in `Authorization` header
6. Provider response received → raw key discarded from memory
7. Tokens, latency, cost calculated from response metadata
8. Usage record inserted into MongoDB `api_calls`
9. Redis counters incremented (rate limit + dashboard cache invalidated)
10. Response returned to client

---

## Security Model

- **Keys at rest**: AES-256 encrypted blobs only; KMS holds the master key
- **Keys in transit**: Raw keys exist only in-memory during a single request lifecycle
- **Audit log**: Every KMS decryption event logged with userId + timestamp
- **TLS**: All external traffic over TLS 1.3
- **Auth**: JWT with short expiry (15m access token, 7d refresh token)
- **Rate limiting**: Redis sliding window prevents abuse and enforces quotas

---

## Post-MVP Components

### Model Optimizer
- Analyzes query complexity (1–10 score) and type (code, creative, analysis, chat)
- Routes to cheapest model capable of handling that complexity tier
- Simple queries → Haiku / Flash; complex → Sonnet / GPT-4o

### Query Classifier
- Scores every prompt at proxy time: complexity 1–10, type label
- Feeds the optimizer and usage summarizer

### Model Suggester
- Weekly job: compares model used vs optimal for each request
- Calculates potential savings, surfaces recommendations in dashboard

### Usage Summarizer
- Categorizes all LLM inputs by type and model
- Generates report: "for these X requests, model Y would have been optimal, saving $Z"

### SMS Alerts (Twilio)
- BullMQ job checks usage against thresholds at 80% and 100% of quota
- Spike detection: if current 24h usage > 2x 7-day baseline → alert
- Sends SMS via Twilio to user's registered phone

### Webhooks
- Users define endpoint URLs in dashboard
- On each API call: BullMQ enqueues a POST to all registered webhooks
- Payload: `{ userId, provider, model, tokensIn, tokensOut, costUsd, timestamp }`
