# TokenWatch — Tools & Technologies

## Core Stack

### Node.js + Express (TypeScript)
- **Purpose**: API server, proxy gateway
- **Key packages**: `express`, `typescript`, `ts-node`, `@types/express`
- **Pattern**: Middleware-based request pipeline; modular routes in `src/routes/`

### Next.js 14
- **Purpose**: Dashboard frontend
- **Key packages**: `next`, `react`, `react-dom`, `tailwindcss`
- **Pattern**: App Router (`/app` dir), server components for initial data, client components for charts/interactivity

### MongoDB + Mongoose
- **Purpose**: Primary data store (users, orgs, api_keys, api_calls, usage_summaries, alerts)
- **Key packages**: `mongoose`, `@types/mongoose`
- **Connection**: `MONGODB_URI` env var; connection pooling via Mongoose
- **Indexes**: `api_calls` must have compound indexes on `{ userId, timestamp }`, `{ userId, provider }`, `{ userId, model }`

### Redis + ioredis
- **Purpose**: Rate limit counters, session cache, dashboard cache, BullMQ backing store
- **Key packages**: `ioredis`, `bullmq`
- **Connection**: `REDIS_URL` env var
- **Key naming conventions**:
  - `ratelimit:{userId}` — sorted set for sliding window
  - `session:{userId}` — JWT validation cache (TTL 300s)
  - `dashboard:{userId}:{hash}` — query result cache (TTL 60s)

---

## Security Tools

### AWS KMS (Key Management Service)
- **Purpose**: Master key for envelope encryption of user API keys
- **Key packages**: `@aws-sdk/client-kms`
- **Pattern**: GenerateDataKey → encrypt locally with AES-256-GCM → store encrypted data key + ciphertext
- **Required env vars**: `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `KMS_KEY_ID`
- **Reference**: See `skills/skills.md` for full implementation

### jsonwebtoken + bcrypt
- **Purpose**: JWT auth tokens + password hashing
- **Key packages**: `jsonwebtoken`, `bcrypt`, `@types/bcrypt`
- **Config**: Access token 15m expiry, refresh token 7d expiry, bcrypt cost factor 12

### zod
- **Purpose**: Runtime request validation + TypeScript type inference
- **Key packages**: `zod`
- **Pattern**: Define schema, use `validate()` middleware, `safeParse` for non-throw validation

---

## AI Provider SDKs

### Anthropic
- **Package**: `@anthropic-ai/sdk`
- **Base URL**: `https://api.anthropic.com`
- **Auth header**: `x-api-key: {key}`
- **Token fields**: `response.usage.input_tokens`, `response.usage.output_tokens`

### OpenAI
- **Package**: `openai`
- **Base URL**: `https://api.openai.com/v1`
- **Auth header**: `Authorization: Bearer {key}`
- **Token fields**: `response.usage.prompt_tokens`, `response.usage.completion_tokens`

### Google Generative AI (Gemini)
- **Package**: `@google/generative-ai`
- **Auth**: API key as query param or header
- **Token fields**: `response.usageMetadata.promptTokenCount`, `response.usageMetadata.candidatesTokenCount`

### Mistral
- **Package**: `@mistralai/mistralai`
- **Base URL**: `https://api.mistral.ai/v1`
- **Auth header**: `Authorization: Bearer {key}`
- **Token fields**: `response.usage.prompt_tokens`, `response.usage.completion_tokens`

---

## Async / Queue

### BullMQ
- **Purpose**: Job queues for alerts, webhooks, usage summarization, spike detection
- **Key packages**: `bullmq`
- **Queues**:
  - `alerts` — SMS alert jobs (Twilio)
  - `webhooks` — User webhook delivery jobs
  - `usage-summaries` — Weekly aggregation jobs
  - `spike-detection` — Hourly spike check jobs
- **Pattern**: See `skills/skills.md` for BullMQ setup

---

## Notifications

### Twilio (Post-MVP)
- **Purpose**: SMS alerts at usage thresholds and on spikes
- **Key packages**: `twilio`
- **Required env vars**: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`
- **Trigger conditions**:
  - 80% of quota consumed
  - 100% of quota consumed
  - Usage spike: current 24h > 2x 7-day rolling average

---

## Frontend Libraries

### Recharts
- **Purpose**: Usage and cost charts in the dashboard
- **Key packages**: `recharts`
- **Charts used**: LineChart (usage over time), BarChart (cost by model), PieChart (cost by provider)

### TanStack Query (React Query)
- **Purpose**: Server state management, data fetching with cache + refetch
- **Key packages**: `@tanstack/react-query`
- **Config**: `staleTime: 30_000`, `refetchInterval: 30_000` for dashboard data

### react-hook-form + zod
- **Purpose**: Form validation (key registration, user settings)
- **Key packages**: `react-hook-form`, `@hookform/resolvers`

---

## Development Tools

### Docker + docker-compose
- **Purpose**: Local development environment
- **Services**: `app` (Express API), `frontend` (Next.js), `mongo`, `redis`
- **File**: `docker-compose.yml` at repo root

### Jest + Supertest
- **Purpose**: Unit and integration tests
- **Key packages**: `jest`, `supertest`, `@types/jest`, `ts-jest`
- **Test DB**: In-memory MongoDB via `mongodb-memory-server`

### ESLint + Prettier
- **Purpose**: Code quality and formatting
- **Config**: `.eslintrc.json`, `.prettierrc` at repo root

---

## GitHub Project Board
- **URL**: https://github.com/orgs/TokenWatch-HackCU2026/projects/1
- **Repo**: https://github.com/TokenWatch-HackCU2026/TokenWatch
- Use `gh issue create` + `gh project item-add` to add todos to the board
