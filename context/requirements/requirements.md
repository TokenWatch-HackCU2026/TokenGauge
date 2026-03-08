# TokenWatch — Requirements

## Functional Requirements

### MVP

#### FR-1: TokenWatch SDK (Python)
- FR-1.1: Provide a `tokenwatch` Python package installable via pip
- FR-1.2: SDK accepts a long-lived TokenWatch SDK token at initialization
- FR-1.3: `tw.wrap(client)` wraps any supported provider client (OpenAI, Anthropic, Google, Mistral)
- FR-1.4: Wrapped client behaves identically to the original — no API surface changes
- FR-1.5: After each API response, SDK extracts tokens_in, tokens_out, model, latency_ms from response metadata
- FR-1.6: SDK calculates cost_usd using a local pricing table
- FR-1.7: SDK fires a non-blocking background POST to `POST /usage/` with the captured data
- FR-1.8: If TokenWatch is unreachable, SDK queues the event locally and retries — user's app is never blocked or delayed
- FR-1.9: Support optional `app_tag` parameter on wrap() or per-call for per-application tracking
- FR-1.10: SDK never receives, transmits, or stores the user's provider API key

#### FR-2: TokenWatch SDK (JavaScript / TypeScript)
- FR-2.1: Provide a `tokenwatch` npm package
- FR-2.2: Same wrap() pattern as Python SDK
- FR-2.3: Works in Node.js environments (not browser — SDK token must not be exposed client-side)
- FR-2.4: TypeScript types included

#### FR-3: Authentication (Web App)
- FR-3.1: Users can register with email + password
- FR-3.2: Users can log in and receive JWT access + refresh tokens
- FR-3.3: Protected routes require a valid JWT
- FR-3.4: Token refresh endpoint to renew access tokens
- FR-3.5: Google OAuth support for sign-in

#### FR-4: SDK Token Management
- FR-4.1: Users can generate long-lived SDK tokens (`tw-...`) from their dashboard
- FR-4.2: Tokens can be named (e.g. "production", "staging", "local")
- FR-4.3: Raw token shown exactly once at creation — not stored in plaintext, only hash kept
- FR-4.4: Users can list their tokens (shows name, creation date, last used — never raw value)
- FR-4.5: Users can revoke individual tokens immediately
- FR-4.6: SDK tokens are write-only — they can only POST to `/usage/`, nothing else

#### FR-5: Usage Tracking
- FR-5.1: Every SDK-reported call is stored in the `api_calls` collection
- FR-5.2: Usage data is queryable by: date range, provider, model, app tag
- FR-5.3: Aggregated cost summaries available per provider and per model
- FR-5.4: Total tokens and cost for any time window

#### FR-6: Dashboard
- FR-6.1: Display usage chart (tokens and cost over time)
- FR-6.2: Cost breakdown by provider and by model
- FR-6.3: Date range filter (last 24h, 7d, 30d, custom)
- FR-6.4: Filter by app tag and provider
- FR-6.5: SDK token management UI (create, name, revoke)
- FR-6.6: Integration guide — shows copy-paste SDK setup code for each provider

#### FR-7: Rate Limiting (SDK token abuse prevention)
- FR-7.1: Enforce per-SDK-token ingest rate limits via Redis (e.g. 1000 events/min)
- FR-7.2: Return HTTP 429 with `Retry-After` header when limit exceeded
- FR-7.3: SDK respects 429 and backs off automatically

---

### Post-MVP

#### FR-8: Query Classifier
- FR-8.1: SDK optionally scores every prompt for complexity (1–10) before sending
- FR-8.2: Classify prompt type: code, creative, analysis, chat, other
- FR-8.3: Classification sent alongside usage record to TokenWatch

#### FR-9: Model Optimizer
- FR-9.1: SDK optionally re-routes request to cheapest capable model before sending to provider
- FR-9.2: User can enable/disable optimizer per-wrap or per-call
- FR-9.3: Complexity tiers: low (1–3) → Haiku/Flash, medium (4–7) → Sonnet/GPT-3.5, high (8–10) → Opus/GPT-4o

#### FR-10: Model Suggester
- FR-10.1: Weekly job analyzes user's request history
- FR-10.2: Compare model used vs. optimal model per request
- FR-10.3: Surface potential savings in the dashboard with specific examples

#### FR-11: Usage Summarizer
- FR-11.1: Generate weekly usage summary: input types, models used, cost breakdown
- FR-11.2: For each request type, show what model would have been optimal and the cost delta

#### FR-12: SMS Alerts (Twilio)
- FR-12.1: Send SMS when user reaches 80% of their configured quota
- FR-12.2: Send SMS when user reaches 100% of their quota
- FR-12.3: Send SMS when usage spikes > 2x the 7-day rolling baseline
- FR-12.4: Users can configure and verify their phone number in settings

#### FR-13: Webhooks
- FR-13.1: Users can register one or more webhook URLs
- FR-13.2: After every usage event ingested, POST a payload to all registered endpoints
- FR-13.3: Retry failed webhook deliveries up to 3 times with exponential backoff
- FR-13.4: Webhook delivery log visible in dashboard

---

## Non-Functional Requirements

### Security
- NFR-S1: TokenWatch never receives, stores, or transmits provider API keys — they remain entirely in the user's environment
- NFR-S2: SDK tokens stored as hashed values only; raw token shown once at creation
- NFR-S3: SDK tokens are write-only — scoped to usage ingestion, cannot read data or manage account
- NFR-S4: All TokenWatch API traffic over TLS 1.3
- NFR-S5: JWT access tokens expire after 15 minutes; refresh tokens after 7 days
- NFR-S6: Passwords hashed with bcrypt (min cost factor 12)

### Performance
- NFR-P1: SDK background POST must not add measurable latency to the user's API call (async/non-blocking)
- NFR-P2: Dashboard queries must respond in < 500ms for the last 30 days of data
- NFR-P3: Rate limit check must complete in < 5ms (Redis)

### Scalability
- NFR-SC1: Stateless API servers; horizontal scaling via load balancer
- NFR-SC2: MongoDB indexes on: userId, timestamp, provider, model in api_calls
- NFR-SC3: Redis TTL 60s on dashboard cache entries

### Reliability
- NFR-R1: If usage ingestion fails (network, server down), SDK queues event and retries — user app unaffected
- NFR-R2: If Redis is unavailable, fail open on rate limiting with alert
- NFR-R3: Webhook and alert delivery handled by arq with retry

### Developer Experience
- NFR-DX1: SDK setup requires changing 2 lines of code maximum
- NFR-DX2: SDK works with existing provider client versions — no forced upgrades
- NFR-DX3: OpenAPI spec for all TokenWatch API endpoints
- NFR-DX4: Docker compose for local development (api + frontend + MongoDB + Redis)
- NFR-DX5: Dashboard shows copy-paste integration snippets for each provider + language

---

## Supported AI Providers (MVP)

| Provider | Python Client | JS/TS Client | Models |
|----------|--------------|-------------|--------|
| OpenAI | `openai` | `openai` | gpt-4o-mini, gpt-4o, gpt-4-turbo |
| Anthropic | `anthropic` | `@anthropic-ai/sdk` | claude-3-haiku, claude-3-5-sonnet, claude-opus-4 |
| Google | `google-generativeai` | `@google/generative-ai` | gemini-1.5-flash, gemini-1.5-pro, gemini-2.0-flash |
| Mistral | `mistralai` | `@mistralai/mistralai` | mistral-small, mistral-medium, mistral-large |

---

## Cost Pricing Table (per 1M tokens, approximate)

| Model | Input | Output |
|-------|-------|--------|
| claude-3-haiku | $0.25 | $1.25 |
| claude-3-5-haiku | $0.80 | $4.00 |
| claude-3-5-sonnet | $3.00 | $15.00 |
| gpt-4o-mini | $0.15 | $0.60 |
| gpt-4o | $5.00 | $15.00 |
| gemini-1.5-flash | $0.075 | $0.30 |
| gemini-2.0-flash | $0.10 | $0.40 |
| gemini-1.5-pro | $3.50 | $10.50 |
| mistral-small | $1.00 | $3.00 |
| mistral-large | $8.00 | $24.00 |
