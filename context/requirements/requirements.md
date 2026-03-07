# TokenWatch — Requirements

## Functional Requirements

### MVP

#### FR-1: AI Gateway / Proxy
- FR-1.1: Accept AI requests for all supported providers (Anthropic, OpenAI, Google, Mistral)
- FR-1.2: Forward requests to the correct provider using the user's stored API key
- FR-1.3: Log every request: provider, model, tokens in, tokens out, cost (USD), latency (ms), app tag, timestamp
- FR-1.4: Return provider response to the caller without modification
- FR-1.5: Calculate cost from a static pricing table (per provider/model, per 1K tokens)
- FR-1.6: Support an optional `X-App-Tag` header for per-application tracking

#### FR-2: Authentication
- FR-2.1: Users can register with email + password
- FR-2.2: Users can log in and receive JWT access + refresh tokens
- FR-2.3: Protected routes require a valid JWT
- FR-2.4: Token refresh endpoint to renew access tokens

#### FR-3: API Key Vault
- FR-3.1: Users can register API keys for each AI provider
- FR-3.2: Keys are encrypted with AWS KMS before storage (AES-256 envelope encryption)
- FR-3.3: Database stores only the encrypted blob and a 4-character hint (last 4 chars of raw key)
- FR-3.4: Users can list their registered keys (shows provider + hint, never raw key)
- FR-3.5: Users can delete a registered key
- FR-3.6: Every key decryption is audit-logged (userId, keyId, timestamp, requestId)

#### FR-4: Usage Tracking
- FR-4.1: Every proxy request is stored in the `api_calls` collection
- FR-4.2: Usage data is queryable by: date range, provider, model, app tag
- FR-4.3: Aggregated cost summaries available per provider and per model
- FR-4.4: Total tokens and cost for any time window

#### FR-5: Dashboard
- FR-5.1: Display real-time usage chart (tokens and cost over time)
- FR-5.2: Cost breakdown by provider and by model
- FR-5.3: Date range filter (last 24h, 7d, 30d, custom)
- FR-5.4: Filter by app tag and provider
- FR-5.5: Display current quota usage and rate limit status
- FR-5.6: API key management UI (add, list, delete keys)

#### FR-6: Rate Limiting
- FR-6.1: Enforce per-user token quotas using Redis sliding window counters
- FR-6.2: Configurable quota tiers (e.g., tokens per minute, per day)
- FR-6.3: Return HTTP 429 with `Retry-After` header when quota exceeded
- FR-6.4: Quota resets automatically per window

---

### Post-MVP

#### FR-7: Query Classifier
- FR-7.1: Score every proxy request prompt for complexity (1–10)
- FR-7.2: Classify prompt type: code, creative, analysis, chat, other
- FR-7.3: Store classification alongside the `api_calls` record

#### FR-8: Model Optimizer
- FR-8.1: Automatically route requests to the cheapest model capable for the complexity score
- FR-8.2: User can enable/disable optimizer per-key or per-app-tag
- FR-8.3: Complexity tiers: low (1–3) → Haiku/Flash, medium (4–7) → Sonnet/GPT-3.5, high (8–10) → Opus/GPT-4o

#### FR-9: Model Suggester
- FR-9.1: Weekly job analyzes user's request history
- FR-9.2: Compare model used vs. optimal model per request
- FR-9.3: Surface potential savings in the dashboard with specific examples

#### FR-10: Usage Summarizer
- FR-10.1: Generate weekly usage summary: input types, models used, cost breakdown
- FR-10.2: For each request type, show what model would have been optimal and the cost delta

#### FR-11: SMS Alerts (Twilio)
- FR-11.1: Send SMS when user reaches 80% of their quota
- FR-11.2: Send SMS when user reaches 100% of their quota
- FR-11.3: Send SMS when usage spikes > 2x the 7-day rolling baseline
- FR-11.4: Users can configure and verify their phone number in settings

#### FR-12: Webhooks
- FR-12.1: Users can register one or more webhook URLs
- FR-12.2: After every proxy request, POST a usage event payload to all registered endpoints
- FR-12.3: Retry failed webhook deliveries up to 3 times with exponential backoff
- FR-12.4: Webhook delivery log visible in dashboard

---

## Non-Functional Requirements

### Security
- NFR-S1: Raw API keys are NEVER persisted to any database or log
- NFR-S2: All keys encrypted with AES-256 via AWS KMS envelope encryption before storage
- NFR-S3: Every KMS decryption event is audit-logged
- NFR-S4: All traffic over TLS 1.3
- NFR-S5: JWT access tokens expire after 15 minutes; refresh tokens after 7 days
- NFR-S6: Passwords hashed with bcrypt via passlib (min cost factor 12)

### Performance
- NFR-P1: Proxy overhead must add < 50ms p99 latency to provider requests
- NFR-P2: Dashboard queries must respond in < 500ms for the last 30 days of data
- NFR-P3: Rate limit check must complete in < 5ms (Redis)

### Scalability
- NFR-SC1: Stateless proxy servers; horizontal scaling via load balancer
- NFR-SC2: MongoDB indexes on: userId, timestamp, provider, model in api_calls
- NFR-SC3: Redis TTL 60s on dashboard cache entries

### Reliability
- NFR-R1: If usage logging fails, proxy request still succeeds (fire-and-forget logging)
- NFR-R2: If rate limit Redis is unavailable, fail open (allow request) with alert
- NFR-R3: Webhook and alert delivery handled by BullMQ with retry

### Developer Experience
- NFR-DX1: OpenAPI spec for all proxy and management endpoints
- NFR-DX2: SDK-compatible — proxy endpoints mirror provider API shapes
- NFR-DX3: Docker compose for local development (api + frontend + MongoDB + Redis)

---

## Supported AI Providers (MVP)

| Provider | Models |
|----------|--------|
| Anthropic | claude-3-haiku, claude-3-5-sonnet, claude-opus-4 |
| OpenAI | gpt-4o-mini, gpt-4o, gpt-4-turbo |
| Google | gemini-1.5-flash, gemini-1.5-pro |
| Mistral | mistral-small, mistral-medium, mistral-large |

---

## Cost Pricing Table (per 1M tokens, approximate)

| Model | Input | Output |
|-------|-------|--------|
| claude-3-haiku | $0.25 | $1.25 |
| claude-3-5-sonnet | $3.00 | $15.00 |
| gpt-4o-mini | $0.15 | $0.60 |
| gpt-4o | $5.00 | $15.00 |
| gemini-1.5-flash | $0.075 | $0.30 |
| gemini-1.5-pro | $3.50 | $10.50 |
| mistral-small | $1.00 | $3.00 |
| mistral-large | $8.00 | $24.00 |
