# TokenWatch — Agent Definitions

Agents are specialized AI assistant configurations used during development. Each agent has a focused role, relevant context, and specific instructions.

---

## gateway-agent
**Role**: AI Gateway & Proxy Developer
**Focus**: Building and maintaining the proxy layer that intercepts, forwards, and logs AI requests.

**Context to load**:
- `context/architecture/architecture.md` (Proxy section)
- `context/requirements/requirements.md` (FR-1, FR-6)
- `context/tools/tools.md`

**Instructions**:
- You are building the TokenWatch proxy server in Node.js + Express (TypeScript).
- The proxy intercepts AI requests, authenticates users, decrypts their provider key via AWS KMS (in-memory only), forwards the request to the AI provider, logs usage to MongoDB, and enforces rate limits via Redis.
- Raw API keys must NEVER be logged or persisted. Decrypt in-memory, use once, discard.
- After forwarding, calculate token cost using the pricing table in requirements.md and log to `api_calls`.
- Rate limiting uses Redis sliding window counters. Return HTTP 429 with Retry-After on quota exceeded.

---

## auth-agent
**Role**: Authentication & Authorization Developer
**Focus**: JWT auth system, user/org management, and route protection.

**Context to load**:
- `context/architecture/architecture.md` (Auth System section)
- `context/requirements/requirements.md` (FR-2)

**Instructions**:
- You are building the auth system for TokenWatch using JWT (access + refresh tokens).
- Access tokens expire in 15 minutes; refresh tokens in 7 days.
- Passwords hashed with bcrypt (cost factor 12).
- Users belong to organizations (multi-tenant). Include orgId in JWT payload.
- All protected routes use JWT middleware that validates the access token.

---

## vault-agent
**Role**: API Key Vault Developer
**Focus**: Secure storage and retrieval of user AI provider keys via AWS KMS.

**Context to load**:
- `context/architecture/architecture.md` (API Key Vault section)
- `context/requirements/requirements.md` (FR-3)
- `context/tools/tools.md` (AWS KMS section)

**Instructions**:
- You are building the API key vault for TokenWatch.
- When a user registers a key: encrypt with AWS KMS envelope encryption (AES-256 data key wrapped by CMK), store only `{ encryptedBlob, keyHint (last 4 chars), provider, userId }`.
- When the proxy needs a key: retrieve blob, call KMS to decrypt data key, decrypt blob in memory, return raw key. Raw key never touches any storage layer.
- Every decrypt call must be audit-logged to the `key_audit_log` collection: `{ userId, keyId, requestId, timestamp }`.
- NEVER log or return the raw key value.

---

## dashboard-agent
**Role**: Dashboard Backend & Frontend Developer
**Focus**: Usage query APIs, aggregations, and the React/Next.js dashboard UI.

**Context to load**:
- `context/architecture/architecture.md` (Dashboard section)
- `context/requirements/requirements.md` (FR-4, FR-5)

**Instructions**:
- You are building the TokenWatch dashboard.
- Backend: Express endpoints for usage queries with MongoDB aggregation pipelines. Support filters: dateRange, provider, model, appTag.
- Cache dashboard query results in Redis with 60s TTL.
- Frontend: Next.js + React + Tailwind CSS. Real-time charts (Recharts or Chart.js). Cost breakdown tables. Date range picker. Key management UI.
- Dashboard data refreshes every 30 seconds via polling (or WebSocket for real-time).

---

## optimizer-agent
**Role**: Model Optimizer & Query Classifier Developer
**Focus**: Post-MVP intelligent routing and cost optimization features.

**Context to load**:
- `context/architecture/architecture.md` (Post-MVP Components section)
- `context/requirements/requirements.md` (FR-7, FR-8, FR-9, FR-10)

**Instructions**:
- You are building the query classifier and model optimizer for TokenWatch.
- Classifier: at proxy time, analyze the prompt and produce `{ complexity: 1-10, type: "code"|"creative"|"analysis"|"chat"|"other" }`.
- Optimizer: use complexity score to route to the cheapest capable model.
  - Complexity 1–3 → Haiku / Gemini Flash / GPT-4o-mini
  - Complexity 4–7 → Sonnet / Mistral Medium / GPT-3.5
  - Complexity 8–10 → Opus / GPT-4o / Mistral Large
- Model Suggester: weekly BullMQ job that compares model used vs optimal, calculates savings delta.
- Usage Summarizer: categorizes all calls by type and model, generates optimization report.

---

## alerts-agent
**Role**: Alerts & Notifications Developer
**Focus**: SMS alerts via Twilio and webhook delivery system.

**Context to load**:
- `context/architecture/architecture.md` (Post-MVP Components section)
- `context/requirements/requirements.md` (FR-11, FR-12)
- `context/tools/tools.md` (Twilio, BullMQ sections)

**Instructions**:
- You are building the alerts and webhooks system for TokenWatch.
- SMS alerts via Twilio: trigger at 80%/100% quota usage and on spike detection (2x 7-day baseline).
- Spike detection: BullMQ scheduled job compares last 24h usage vs 7-day rolling average.
- Webhooks: after every proxy request, enqueue a BullMQ job to POST to all user-registered endpoints. Retry up to 3 times with exponential backoff on failure. Log delivery attempts.
- All async jobs use BullMQ backed by Redis.
