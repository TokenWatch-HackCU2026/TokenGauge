# TokenGauge

**Zero-config AI usage tracking + model recommendations.**

TokenGauge is an open-source platform that tracks LLM API costs and usage across OpenAI, Anthropic, and Google Gemini. Wrap your existing client with one line — every call is automatically logged to a real-time dashboard. Your API keys stay with you; the SDK only reads token counts from responses and sends them to TokenGauge.

> **Live demo:** [tokengauge.onrender.com](https://tokengauge.onrender.com/)
THIS ACCOUNT DOES NOT HAVE SDK OR PHONE NUMBER ACCSES
> - Email: `demo@tokengauge.dev`
> - Password: `demodemo123`

---

## Features

- **One-line integration** — wrap any OpenAI, Anthropic, or Google Gemini client; sync and async
- **Real-time dashboard** — live WebSocket streaming, interactive charts, cost breakdowns by provider/model
- **Model recommendations** — classify your prompt locally and get the best model ranked by success probability and cost (no API call required)
- **Spend limits** — set per-provider budgets (daily/weekly/monthly); the SDK raises `BudgetExceededError` *before* the API call is made
- **App tagging** — label usage by feature (e.g. `"summarizer"`, `"chatbot"`) for granular cost attribution
- **Cost outlier detection** — Z-score flagging highlights abnormally expensive calls
- **Prompt classification** — automatic categorization (code, chat, analysis, creative, etc.) with 1-10 complexity scoring, all running locally
- **Zero overhead** — background logging; no proxying, no extra latency on your AI calls

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, MongoDB (Beanie ODM), Redis |
| Frontend | React 18, TypeScript, Vite, Recharts |
| SDK | Python (`tokengauge` on PyPI), uses httpx |
| Auth | JWT + bcrypt, Google OAuth |
| Deployment | Docker, Render.com |

## Architecture

```
┌──────────────┐       ┌──────────────────┐       ┌───────────────┐
│  Your App    │       │  TokenGauge API  │       │   Dashboard   │
│  + SDK wrap  │──────>│  (FastAPI)       │<──────│   (React)     │
│              │ POST  │                  │  GET  │               │
│  API keys    │ usage │  MongoDB, Redis  │  WS   │  Charts,      │
│  stay here   │       │                  │       │  Alerts       │
└──────────────┘       └──────────────────┘       └───────────────┘
```

The SDK intercepts AI provider responses, extracts token counts and metadata, and POSTs usage data to the TokenGauge API in a background thread. The dashboard queries the API for aggregated analytics and receives live updates over WebSocket.

## Quick Start

### 1. Install the SDK

```bash
pip install tokengauge
```

### 2. Sign up and get your token

Create an account at [tokengauge.onrender.com](https://tokengauge.onrender.com/) and copy your SDK token from **Settings**.

### 3. Wrap your client

```python
from tokengauge import TokenGauge
import openai

tw = TokenGauge(token="your-sdk-token")
client = tw.wrap(openai.OpenAI(api_key="sk-..."))

# Use exactly as before — usage appears on your dashboard automatically
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

### Provider Examples

**Anthropic:**
```python
from tokengauge import TokenGauge
import anthropic

tw = TokenGauge(token="your-sdk-token")
client = tw.wrap(anthropic.Anthropic(api_key="sk-ant-..."))

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=256,
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.content[0].text)
```

**Google Gemini:**
```python
from tokengauge import TokenGauge
from google import genai

tw = TokenGauge(token="your-sdk-token")
client = tw.wrap(genai.Client(api_key="your-gemini-key"))

response = client.models.generate_content(
    model="gemini-1.5-flash",
    contents="Hello!",
)
print(response.text)
```

**Async clients:**
```python
from tokengauge import TokenGauge
import openai, asyncio

tw = TokenGauge(token="your-sdk-token")
client = tw.wrap(openai.AsyncOpenAI(api_key="sk-..."))

async def main():
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello!"}],
    )
    print(response.choices[0].message.content)

asyncio.run(main())
```

## Model Recommendations

Not sure which model to use? `recommend_model()` classifies your prompt locally, estimates the cost, and scores every model by success probability — no API call required.

```python
tw = TokenGauge(token="your-sdk-token")

rec = tw.recommend_model(
    messages=[{"role": "user", "content": "Refactor this Python class to use dataclasses..."}],
    provider="anthropic",   # optional: filter to a specific provider
    budget_usd=0.05,        # optional: exclude models above this cost
)

print(rec["prompt_type"])                          # "code"
print(rec["complexity"])                           # 1-10 score
print(rec["best_overall"]["model"])                # e.g. "claude-opus-4.6"
print(rec["best_overall"]["estimated_cost_usd"])   # e.g. 0.00047
print(rec["best_overall"]["success_probability"])  # e.g. 1.0
```

**How it works:** Prompt text is classified against 8 categories (code, chat, summarization, analysis, creative, extraction, translation, other) using local pattern matching. Each model is scored on type-specific quality, penalized by complexity relative to its ceiling, then ranked by success probability with cost as a tiebreaker. Prompt text is never sent anywhere.

**Supported models:**

| Provider | Models |
|----------|--------|
| OpenAI | gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-4o, gpt-4o-mini, o3, o3-mini, o4-mini |
| Anthropic | claude-opus-4.6, claude-sonnet-4.6, claude-haiku-4-5, claude-3-7-sonnet, claude-3-5-sonnet, claude-3-5-haiku |
| Google | gemini-2.5-pro, gemini-2.5-flash, gemini-2.0-flash, gemini-2.0-flash-lite |

## Spend Limits

Set per-provider budgets in the dashboard. The SDK checks your remaining budget before each call and raises `BudgetExceededError` if the estimated cost would exceed it — the underlying API call is never made.

```python
from tokengauge import TokenGauge, BudgetExceededError

tw = TokenGauge(token="your-sdk-token")
client = tw.wrap(openai.OpenAI(api_key="sk-..."))

try:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello!"}],
    )
except BudgetExceededError as e:
    print(f"Budget exceeded: {e}")
    # e.provider, e.estimated_cost, e.remaining, e.period
```

Spend status is cached for 60 seconds to avoid extra latency.

## App Tagging

Label usage by feature for granular cost attribution:

```python
summarizer = tw.wrap(openai.OpenAI(api_key="sk-..."), app_tag="summarizer")
chatbot    = tw.wrap(openai.OpenAI(api_key="sk-..."), app_tag="chatbot")
```

## Authentication

**Token-based (recommended for scripts):**
```python
tw = TokenGauge(token="your-sdk-token")
```

**Login-based:**
```python
tw = TokenGauge.login(email="you@example.com", password="your-password")
```

**Self-hosted:**
```python
tw = TokenGauge(token="your-sdk-token", base_url="http://localhost:8000")
# or
tw = TokenGauge.login(email="you@example.com", password="your-password", base_url="http://localhost:8000")
```

## What Gets Tracked

| Field | Description |
|-------|-------------|
| Provider | openai / anthropic / google |
| Model | e.g. gpt-4o-mini, claude-3-5-sonnet |
| Tokens in | Prompt token count |
| Tokens out | Completion token count |
| Cost (USD) | Calculated from current model pricing |
| Latency | End-to-end request time in ms |
| Prompt type | Auto-classified category (code, chat, analysis, etc.) |
| Complexity | Estimated complexity score 1-10 |
| App tag | Optional label you set per-client |

## Dashboard

The web dashboard provides three views:

- **Overview** — summary metrics (total tokens, cost, requests, avg latency), cost timeseries chart, cost by provider breakdown, live WebSocket stream
- **Usage** — raw API call records with filters (provider, model, app tag), cost outlier flagging, bulk cost recalculation
- **Settings** — SDK token management, per-provider spend limits (daily/weekly/monthly), spend status tracking

Date range selector: live, 1D, 1W, 1M, 3M, YTD, 1Y, ALL with automatic granularity adjustment.

## Running Locally

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Requires `MONGO_URI`, `JWT_SECRET`, and optionally `REDIS_URL` as environment variables.

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Docker:**
```bash
docker-compose up
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register a new account |
| POST | `/api/v1/auth/login` | Login |
| GET | `/api/v1/auth/sdk-token` | Get/regenerate SDK token |
| POST | `/usage/` | Log API call usage |
| GET | `/usage/` | List usage records (paginated) |
| WS | `/usage/ws/live` | Real-time usage stream |
| GET | `/dashboard/summary` | Aggregated stats |
| GET | `/dashboard/timeseries` | Daily/hourly breakdown |
| GET | `/dashboard/breakdown` | By provider/model |
| GET | `/dashboard/spend-limits` | Get spend limits |
| PUT | `/dashboard/spend-limits` | Update spend limits |
| GET | `/dashboard/spend-status` | Current spend vs limits |

## Project Structure

```
├── backend/
│   ├── main.py              # FastAPI app setup
│   ├── models.py            # MongoDB document schemas
│   ├── auth.py              # JWT + bcrypt utilities
│   ├── database.py          # MongoDB connection (Beanie)
│   ├── redis_client.py      # Redis caching
│   ├── classifier.py        # Prompt type/complexity scoring
│   ├── alerts.py            # Quota alerts (Twilio SMS)
│   └── routers/
│       ├── auth.py          # Auth endpoints
│       ├── usage.py         # Usage logging + WebSocket
│       └── dashboard.py     # Analytics endpoints
├── frontend/
│   └── src/
│       ├── App.tsx          # Root component, auth state
│       ├── api/client.ts    # Type-safe API client
│       └── components/
│           ├── Dashboard.tsx # Main dashboard
│           └── AuthPage.tsx  # Login/register
├── tokenwatch-sdk/
│   └── tokengauge/
│       ├── __init__.py      # Public API exports
│       └── _tracker.py      # Core wrapping + recommendation engine
├── docker-compose.yml
└── render.yaml              # Render.com deployment blueprint
```

## License

Built at HackCU 2026.
