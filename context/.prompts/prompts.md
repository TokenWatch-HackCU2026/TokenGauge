# TokenGauge — Prompts

Reusable prompt templates for common development tasks on the TokenGauge project.

---

## Proxy / Gateway Prompts

### Build a new provider adapter
```
I need to add a new AI provider adapter for [PROVIDER_NAME] to the TokenGauge proxy.

Context:
- The proxy is in Node.js + Express (TypeScript)
- It must forward requests to [PROVIDER_ENDPOINT]
- Auth header format: [AUTH_FORMAT]
- Request body shape: [REQUEST_SHAPE]
- Response body shape: [RESPONSE_SHAPE]
- Token counting fields: [TOKEN_FIELDS]
- Pricing: input $[X]/1M tokens, output $[Y]/1M tokens

Create the adapter following the existing pattern in src/providers/. Include:
1. Type definitions for request/response
2. The adapter class implementing IProviderAdapter
3. Cost calculation using the pricing table
4. Error handling for provider-specific error codes
```

### Debug proxy latency issue
```
The TokenGauge proxy is adding more than 50ms overhead. Current architecture:
[paste architecture.md proxy section]

Profile the request lifecycle and identify where the latency is coming from.
Check: Redis rate limit check timing, KMS decryption timing, MongoDB write timing, HTTP forwarding timing.
```

---

## Database Prompts

### Write a MongoDB aggregation for usage
```
Write a MongoDB aggregation pipeline for the TokenGauge `api_calls` collection that returns:
- Total tokens in + out
- Total cost (USD)
- Breakdown by provider and model
- Grouped by [day/hour]
- Filtered by: userId=[X], dateRange=[start, end], provider=[optional], model=[optional]

The collection schema is defined in context/architecture/architecture.md.
Optimize for the existing indexes on: userId, timestamp, provider, model.
```

### Redis rate limit Lua script
```
Write a Redis Lua script for TokenGauge's sliding window rate limiter.
- Key format: ratelimit:{userId}:{windowStart}
- Window size: [WINDOW_MS] milliseconds
- Max tokens: [MAX_TOKENS] per window
- The script should atomically: check current count, reject if over limit, increment if under limit
- Return: { allowed: boolean, remaining: number, resetAt: timestamp }
```

---

## Security Prompts

### Review API key vault implementation
```
Review the following API key vault implementation for security issues.
Key requirements from context/requirements/requirements.md FR-3:
- Keys encrypted with AWS KMS envelope encryption (AES-256)
- DB stores only encrypted blob + 4-char hint
- Raw keys in memory only during proxy request
- Every decryption audit-logged

[paste code]

Check for:
1. Any path where a raw key could be logged or persisted
2. Correct KMS envelope encryption pattern (GenerateDataKey + local AES encrypt)
3. Proper cleanup of key material from memory after use
4. Audit log completeness
```

---

## Dashboard Prompts

### Build a usage chart component
```
Build a React component for the TokenGauge dashboard that shows [CHART_TYPE].

Stack: Next.js 14 (App Router), React, Tailwind CSS, Recharts, TanStack Query.

Data source: GET /api/usage/[endpoint]?dateRange=[range]&provider=[optional]
Data shape: [paste API response shape]

The component should:
1. Fetch data with TanStack Query (30s refetch interval)
2. Show a loading skeleton while fetching
3. Display the Recharts chart with Tailwind-styled tooltip
4. Support the date range filter (24h / 7d / 30d / custom)
```

---

## Model Optimizer Prompts

### Classify prompt complexity
```
You are the TokenGauge query classifier. Analyze the following prompt and return a JSON object with:
- complexity: integer 1-10 (1=trivial single-fact lookup, 10=deep multi-step reasoning)
- type: one of "code" | "creative" | "analysis" | "chat" | "other"
- reasoning: one sentence explaining the score

Scoring guide:
- 1-3: Simple factual questions, greetings, single-step tasks
- 4-6: Multi-step tasks, basic code, structured writing, moderate analysis
- 7-9: Complex reasoning, advanced code, nuanced analysis, long-form content
- 10: Research-level tasks, novel problem solving, complex system design

Prompt to classify:
"""
[USER_PROMPT]
"""

Return only valid JSON.
```

---

## General Development Prompts

### Generate an Express route with validation
```
Generate a TypeScript Express route handler for TokenGauge.

Endpoint: [METHOD] [PATH]
Auth required: [yes/no]
Request body schema (zod): [schema]
Business logic: [description]
MongoDB operations: [description]
Response shape: [description]

Follow the existing patterns in src/routes/. Use zod for validation, mongoose for DB, and the standard error handler middleware.
```

### Write tests for a route
```
Write Jest + Supertest integration tests for the following TokenGauge Express route:
[paste route code]

Include tests for:
1. Happy path with valid input
2. Authentication failure (missing/invalid JWT)
3. Validation errors (invalid request body)
4. Business logic edge cases: [list them]
5. Database error handling

Use the test setup in src/__tests__/setup.ts which provides a test MongoDB and Redis instance.
```
