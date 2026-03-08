# TokenWatch — System Architecture

## Overview

TokenWatch is an AI usage intelligence platform. Users wrap their existing AI provider clients with the TokenWatch SDK. The SDK captures usage data (tokens, cost, latency) from each API response and forwards it to TokenWatch in the background. TokenWatch never acts as a network proxy and never receives or stores provider API keys.

```
User's App
    │
    ▼
TokenWatch SDK (wraps provider client)
    │                    │
    ▼                    ▼
AI Provider          POST /usage/  →  TokenWatch API  →  MongoDB
(direct call)        (background)          │
                                           ▼
                                       Dashboard
```

---

## System Components

### 1. TokenWatch SDK (Python + JavaScript)
- User installs `pip install tokenwatch` or `npm install tokenwatch`
- User initializes with their long-lived TokenWatch SDK token
- SDK wraps the user's existing provider client (OpenAI, Anthropic, Google, Mistral)
- All API calls go **directly** from the user's app to the provider — TokenWatch is never in the network path
- After each response, SDK extracts: model, tokens_in, tokens_out, latency_ms from response metadata
- SDK calculates cost_usd using the local pricing table
- SDK fires a background POST to `POST /usage/` on TokenWatch (non-blocking, does not delay the user's response)
- If TokenWatch is unreachable, SDK queues the event and retries — user's app is never affected

```python
# Python usage
from tokenwatch import TokenWatch
from openai import OpenAI

tw = TokenWatch(api_key="tw-abc123...")     # long-lived SDK token
client = tw.wrap(OpenAI(api_key="sk-...")) # wraps existing client

# Nothing changes — same API call as before
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "hello"}]
)
# SDK captures usage from response.usage and POSTs to TokenWatch
```

```typescript
// TypeScript usage
import { TokenWatch } from 'tokenwatch'
import OpenAI from 'openai'

const tw = new TokenWatch({ apiKey: 'tw-abc123...' })
const client = tw.wrap(new OpenAI({ apiKey: 'sk-...' }))

const response = await client.chat.completions.create({ ... })
// Usage captured automatically
```

### 2. Auth System
- JWT-based authentication for the TokenWatch web app (login, dashboard)
- User registration, login, logout endpoints
- Google OAuth support for sign-in
- Short-lived access tokens (15m) + refresh tokens (7d) for web session
- **Long-lived SDK tokens** (`tw-...`) issued separately for SDK use — never expire, can be revoked

### 3. SDK Token Management
- Users generate one or more long-lived SDK tokens in their dashboard
- Tokens are scoped to write-only access on `/usage/` — cannot read data or manage account
- Tokens can be named (e.g. "production", "staging") and individually revoked
- Stored as hashed values in MongoDB — raw token shown once at creation, never again

### 4. Usage Database (MongoDB)
Collections:
- `users` — id, email, passwordHash, fullName, avatarUrl, googleId, createdAt
- `sdk_tokens` — id, userId, name, tokenHash, createdAt, lastUsedAt, revokedAt
- `api_calls` — id, userId, provider, model, tokensIn, tokensOut, costUsd, latencyMs, appTag, timestamp
- `usage_summaries` — aggregated daily/weekly rollups per user
- `alerts` — id, userId, type (limit/spike), threshold, triggeredAt, acknowledged
- `spike_events` — id, userId, detectedAt, baselineTokens, actualTokens, multiplier

### 5. Redis
- Dashboard cache: usage query results (TTL 60s)
- SDK event queue: buffer for retry when TokenWatch API is temporarily unreachable
- Rate limit counters: prevent SDK token abuse (e.g. max 1000 events/min per token)

### 6. Dashboard
- Real-time usage charts (tokens over time, cost over time)
- Cost breakdown by provider and model
- Filterable by: date range, provider, model, app tag
- SDK token management UI (create, name, revoke tokens)
- Integration guide showing SDK setup code for each provider

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API Server | Python + FastAPI |
| Frontend | React + Vite + Tailwind CSS |
| Primary DB | MongoDB |
| Cache | Redis + arq |
| Auth | JWT (python-jose) + passlib[bcrypt] |
| SDK (Python) | Pure Python, wraps openai / anthropic / google-generativeai / mistralai |
| SDK (JS/TS) | TypeScript, wraps openai / @anthropic-ai/sdk / @google/generative-ai |
| Containerization | Docker + docker-compose |
| Cost Calculation | Static pricing table per provider/model (in SDK + server) |

---

## SDK Data Flow (per API call)

1. User calls `client.chat.completions.create(...)` — identical to without SDK
2. SDK records `start_time`
3. Call goes directly to provider (e.g. `https://api.openai.com`) — TokenWatch not in path
4. Provider returns response with `usage` metadata (tokens_in, tokens_out, model)
5. SDK records `end_time`, calculates `latency_ms`
6. SDK calculates `cost_usd` from local pricing table
7. SDK spawns background thread/task: `POST /usage/` to TokenWatch with SDK token auth
8. SDK returns original provider response to user immediately — step 7 is non-blocking
9. TokenWatch API validates SDK token, inserts record into `api_calls`

---

## Security Model

- **Provider API keys**: TokenWatch never receives, stores, or sees them — they stay entirely in the user's environment
- **SDK tokens**: Write-only, scoped to usage ingestion only — cannot access user data or settings
- **Audit**: Every SDK token usage logged with timestamp and source IP
- **TLS**: All TokenWatch API traffic over TLS 1.3
- **Auth**: JWT for web app (short-lived), SDK tokens for data ingestion (long-lived, revocable)
- **Passwords**: bcrypt hashed (min cost factor 12)

---

## Post-MVP Components

### Model Optimizer
- Analyzes query complexity (1–10 score) and type (code, creative, analysis, chat)
- SDK optionally re-routes to cheapest model capable for the complexity tier before sending
- Simple queries → Haiku / Flash; complex → Sonnet / GPT-4o

### Query Classifier
- SDK scores every prompt at call time: complexity 1–10, type label
- Sent alongside usage data to TokenWatch
- Feeds the optimizer and usage summarizer

### Model Suggester
- Weekly job: compares model used vs optimal for each request
- Calculates potential savings, surfaces recommendations in dashboard

### Usage Summarizer
- Categorizes all LLM inputs by type and model
- Generates report: "for these X requests, model Y would have been optimal, saving $Z"

### SMS Alerts (Twilio)
- arq job checks usage against thresholds at 80% and 100% of quota
- Spike detection: if current 24h usage > 2x 7-day baseline → alert
- Sends SMS via Twilio to user's registered phone

### Webhooks
- Users define endpoint URLs in dashboard
- After each usage event ingested: arq enqueues POST to all registered webhooks
- Payload: `{ userId, provider, model, tokensIn, tokensOut, costUsd, timestamp }`
- Retry up to 3 times with exponential backoff
