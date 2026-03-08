# TokenGauge — Project Memory

This file stores persistent context, decisions, and conventions for the TokenGauge project.

---

## Project Identity
- **Name**: TokenGauge
- **Type**: Multi-tenant SaaS AI Gateway & Usage Intelligence Platform
- **Repo**: https://github.com/TokenGauge-HackCU2026/TokenGauge
- **Project Board**: https://github.com/orgs/TokenGauge-HackCU2026/projects/1
- **Event**: HackCU 2026

---

## Architecture Decisions

### Why a proxy architecture?
All traffic routes through TokenGauge so that usage logging, key security, rate limiting, and model optimization all happen at a single, centralized layer. Users never call AI providers directly.

### AWS KMS for key encryption
Envelope encryption: a data key (AES-256) encrypts the raw provider key; the data key itself is encrypted by a KMS CMK. The database only stores the encrypted blob. Raw keys exist only in-memory during a single proxy request. This ensures that even if the database is compromised, no API keys are exposed.

### Redis sliding window rate limiting
Chosen over fixed windows to prevent burst exploitation at window boundaries. Counter key: `ratelimit:{userId}` (sorted set, scored by timestamp). Lua script for atomic check-and-increment.

### Redis Pub/Sub for live dashboard
After every proxy request completes, the gateway publishes a usage event to the `new_api_call` channel. The dashboard backend subscribes and pushes updates to connected clients via WebSockets — making the dashboard feel live without polling.

### Redis prompt response caching
Identical prompts (same model + parameters) are cached by `hash(prompt + params)` with a configurable TTL. Prevents paying a provider twice for the same question.

### Redis API key validation
Valid TokenGauge API keys are stored in a Redis Set (`valid_keys`). `SISMEMBER valid_keys {key}` is O(1) — avoids a database round-trip on every request.

### arq for async jobs
All side effects (alerts, webhooks, usage summaries, spike detection) are handled async via arq queues backed by Redis. This keeps the proxy request path fast and ensures usage logging failure doesn't affect the user.

### Fire-and-forget usage logging
The proxy logs usage asynchronously after returning the response to the client. If the log fails, the user's request still succeeds. This keeps proxy latency overhead minimal (target: < 50ms p99 added latency).

---

## Technology Conventions

### Backend
- Language: TypeScript (strict mode)
- Framework: Express.js
- MongoDB ODM: Mongoose
- Redis client: ioredis
- HTTP client for provider forwarding: axios
- JWT: jsonwebtoken
- Password hashing: bcrypt (cost 12)
- Validation: zod

### Frontend
- Framework: Next.js 14 (App Router)
- Styling: Tailwind CSS
- Charts: Recharts
- State: React Query (TanStack Query) for server state
- Forms: react-hook-form + zod

### Infrastructure
- Container: Docker + docker-compose
- MongoDB: Atlas (prod) / local docker (dev)
- Redis: Upstash (prod) / local docker (dev)
- Key Management: AWS KMS

---

## Environment Variables Required

```
# App
NODE_ENV=development
PORT=3001
JWT_SECRET=...
JWT_REFRESH_SECRET=...

# Database
MONGODB_URI=mongodb://localhost:27017/tokengauge
REDIS_URL=redis://localhost:6379

# AWS KMS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
KMS_KEY_ID=...

# Twilio (post-MVP)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=...
```

---

## MVP Scope (Build First)
1. Project setup (monorepo, Docker, TypeScript config)
2. MongoDB + Redis infrastructure
3. JWT auth (register, login, refresh, middleware)
4. API key vault (KMS encryption, CRUD endpoints)
5. AI proxy gateway (forward to Anthropic, OpenAI, Google, Mistral)
6. Usage logging (log every api_call record)
7. Rate limiting (Redis sliding window)
8. Dashboard backend (aggregation query endpoints)
9. Dashboard frontend (charts, cost breakdown, filters)

## Post-MVP Scope
- Query classifier + model optimizer
- Model suggester + usage summarizer
- SMS alerts via Twilio
- Webhook delivery system

---

## Pricing Table (per 1M tokens, input/output)

| Model | Input ($) | Output ($) |
|-------|-----------|------------|
| claude-3-haiku | 0.25 | 1.25 |
| claude-3-5-sonnet | 3.00 | 15.00 |
| gpt-4o-mini | 0.15 | 0.60 |
| gpt-4o | 5.00 | 15.00 |
| gemini-1.5-flash | 0.075 | 0.30 |
| gemini-1.5-pro | 3.50 | 10.50 |
| mistral-small | 1.00 | 3.00 |
| mistral-large | 8.00 | 24.00 |

---

## Key Invariants (Never Break These)
- Raw API keys are NEVER stored in any database or log file
- Every KMS decryption must be audit-logged
- Rate limit check happens BEFORE key decryption
- Usage logging is async (never blocks proxy response)
- All MongoDB queries on api_calls must use indexes (userId, timestamp, provider, model)
