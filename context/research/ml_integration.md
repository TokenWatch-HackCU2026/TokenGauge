# TokenGauge — ML Integration Research

## Context

TokenGauge is an AI usage intelligence platform. Users wrap their AI provider clients (OpenAI, Anthropic, Google, Mistral) with the SDK, which captures tokens_in, tokens_out, model, latency_ms, cost_usd, and optional app_tag per call. Data is stored in MongoDB (`api_calls` collection) and surfaced via a React dashboard.

The data model already has scaffolded fields for ML: `complexity: Optional[int]` and `prompt_type: Optional[str]` on `ApiCall`, but no ML logic exists yet.

---

## ML Opportunity Areas

### 1. Request Classification (prompt_type)

**Problem:** Users can't see *what kind* of work their AI spend goes toward.

**Approach:** Classify each request into categories like `code`, `creative`, `analysis`, `chat`, `summarization`, `extraction`, `translation`.

**Implementation options:**

| Option | Where it runs | Pros | Cons |
|--------|--------------|------|------|
| **A. Lightweight classifier in SDK** | Client-side (SDK) | No extra latency to TokenGauge; works offline | SDK sees prompt text (privacy concern); increases SDK size; must ship model weights |
| **B. Keyword/heuristic classifier in SDK** | Client-side (SDK) | Tiny, fast, no model weights needed | Low accuracy; can't handle ambiguous prompts |
| **C. Server-side classifier** | Backend (FastAPI) | Centralized model updates; SDK stays thin | Requires SDK to send prompt text (privacy risk) or a prompt embedding |
| **D. SDK sends prompt hash/embedding, server classifies** | Both | Preserves privacy; accurate | Adds embedding computation to SDK; more complex |

**Recommendation:** **Option B (heuristic) for MVP, Option A (lightweight model) for v2.**

For MVP, use keyword matching + regex in the SDK (e.g., detect code fences, "write a function", "summarize", "translate"). For v2, ship a small distilled text classifier (~5MB) like a fine-tuned DistilBERT or a TF-IDF + logistic regression model that classifies prompt text locally without sending it to TokenGauge.

**Training data:** Can be bootstrapped from public prompt datasets (ShareGPT, LMSYS-Chat-1M) or by having users opt-in to share anonymized prompt metadata.

---

### 2. Complexity Scoring

**Problem:** Users don't know if they're using expensive models for simple tasks.

**Approach:** Score each request 1–10 for complexity, enabling model optimization recommendations.

**Signals available (without reading prompt text):**
- `tokens_in` — longer prompts tend to be more complex
- `tokens_out` — longer outputs suggest more complex tasks
- `model` — users tend to pick stronger models for harder tasks (noisy signal)
- `latency_ms` — correlated with output length but also provider load
- `app_tag` — certain features consistently produce complex requests
- `prompt_type` — code generation is generally more complex than chat

**Signals available (if SDK has access to prompt):**
- Presence of code blocks, structured data, multi-step instructions
- Vocabulary complexity / readability score
- Number of constraints or conditions in the prompt
- System prompt length and specificity

**Implementation:**
- **Phase 1:** Rule-based scoring using token counts + prompt_type (no ML needed)
  - `tokens_in < 100 and type=chat` → complexity 1–2
  - `tokens_in > 2000 and type=code` → complexity 8–10
- **Phase 2:** Train a regression model on user feedback (thumbs up/down on model suggestions) to learn the relationship between features and actual complexity

---

### 3. Cost Prediction / Estimation

**Problem:** Users want to forecast spend before it happens, not just review historical costs.

**Approach:** Time-series forecasting on per-user usage data.

**Models to consider:**
- **Prophet (Meta):** Works well with daily/weekly seasonality, handles missing data. Good fit since usage likely has day-of-week patterns.
- **ARIMA/SARIMA:** Classical approach, works well for small datasets.
- **XGBoost on time features:** Encode day-of-week, hour, rolling averages as features. Often outperforms pure time-series models.
- **Simple exponential smoothing:** Baseline — weighted moving average with decay.

**Features:**
- Historical daily cost, tokens, request count per user
- Day of week, hour of day
- Provider/model mix ratios
- Rolling 7-day and 30-day averages
- Trend (is usage growing?)

**Output:**
- Projected daily/weekly/monthly cost
- Confidence interval (e.g., "likely $45–$62 next week")
- Alerts when projected spend exceeds budget

**Where to run:** Server-side (backend job). Users have 30+ days of history; a nightly batch job can retrain per-user models or use a single global model with user features.

---

### 4. Anomaly Detection (Spike Detection)

**Problem:** `SpikeEvent` model exists but detection logic is incomplete. Currently just compares actual vs baseline with a fixed multiplier.

**Approach:** Statistical anomaly detection on usage patterns.

**Options:**
- **Z-score method:** Flag when current usage is >2–3 standard deviations from the rolling mean. Simple and interpretable.
- **Isolation Forest:** Unsupervised ML model that isolates anomalies. Good for multivariate anomalies (e.g., normal token count but abnormal cost due to model switch).
- **DBSCAN clustering:** Group normal usage patterns; flag points outside clusters.
- **Prophet anomaly detection:** Use the forecast confidence interval — anything outside is anomalous.

**Recommendation:** Start with **Z-score on hourly/daily aggregates**, upgrade to **Isolation Forest** when you have enough data. The Z-score approach can be implemented as a simple arq background job checking every hour.

**Signals:**
- Hourly request count vs 7-day hourly average
- Hourly cost vs 7-day hourly average
- Sudden model tier shift (e.g., all requests jumping from gpt-4o-mini to gpt-4o)
- Latency spikes (could indicate provider issues vs user issues)

---

### 5. Model Recommendation Engine

**Problem:** Users often use a single model for everything. Some requests could be handled by cheaper models without quality loss.

**Approach:** Recommend cheaper models for low-complexity requests.

**Implementation:**
1. Classify each request by complexity (see #2) and type (see #1)
2. Maintain a capability matrix: which models can handle which complexity tiers
3. For each historical request, compute: "if you had used model X instead, you'd have saved $Y"
4. Surface in dashboard: "Last week, 340 of your requests were low-complexity chat. Switching from gpt-4o to gpt-4o-mini would save $12.40/week."

**Capability matrix (initial, hardcoded):**

| Complexity | Recommended Models |
|------------|-------------------|
| 1–3 (low) | gpt-4o-mini, claude-haiku, gemini-flash, mistral-small |
| 4–6 (medium) | gpt-4o, claude-sonnet, gemini-pro, mistral-large |
| 7–10 (high) | gpt-4o, claude-opus, gemini-pro |

**Phase 2:** Learn the matrix from user feedback. If a user tries the cheaper model and reports poor quality, adjust thresholds.

---

### 6. Usage Pattern Clustering

**Problem:** Users with multiple app_tags don't have insight into how their usage patterns differ across features.

**Approach:** Cluster API call patterns to identify distinct usage profiles.

**Implementation:**
- Feature vector per app_tag (or per time window): avg tokens_in, avg tokens_out, dominant model, request frequency, avg cost, avg latency
- K-means or DBSCAN clustering
- Surface insights: "Your 'customer-support' feature uses 3x more tokens per request than 'search' but costs less because it uses a cheaper model"

---

### 7. Provider Performance Comparison

**Problem:** Users don't know which provider gives the best latency/cost tradeoff for their use case.

**Approach:** For users who use multiple providers, compare latency, cost, and token efficiency across providers for similar request types.

**Implementation:**
- Group requests by prompt_type + complexity
- Compare avg latency, cost, tokens_out/tokens_in ratio across providers
- Surface: "For code generation, Anthropic averages 1.2s latency vs OpenAI's 2.1s, at similar cost"

---

## Recommended Implementation Order

| Priority | Feature | Effort | Impact | Dependencies |
|----------|---------|--------|--------|-------------|
| **P0** | Request classification (heuristic) | Low | High | SDK change |
| **P0** | Complexity scoring (rule-based) | Low | High | Request classification |
| **P1** | Anomaly/spike detection (Z-score) | Medium | High | arq job setup |
| **P1** | Model recommendation engine | Medium | High | Complexity scoring |
| **P1** | Cost forecasting (Prophet/XGBoost) | Medium | High | 30+ days user data |
| **P2** | Request classification (ML model) | High | Medium | Training data pipeline |
| **P2** | Usage pattern clustering | Medium | Medium | Enough app_tags in use |
| **P2** | Provider performance comparison | Low | Medium | Multi-provider users |
| **P3** | Learned complexity scoring | High | Medium | User feedback loop |

---

## Tech Stack Additions

| Component | Library | Purpose |
|-----------|---------|---------|
| Classification (heuristic) | Pure Python (regex) | Prompt type detection in SDK |
| Classification (ML) | scikit-learn or ONNX Runtime | Lightweight text classifier |
| Time-series forecasting | Prophet or statsforecast | Cost prediction |
| Anomaly detection | scikit-learn (IsolationForest) or numpy (Z-score) | Spike detection |
| Feature engineering | pandas | Data transformation for ML |
| Model serving | FastAPI endpoint (same server) or separate microservice | Serve predictions |
| Job scheduling | arq (already in stack) | Batch training, daily predictions |
| Model storage | MongoDB GridFS or S3 | Persist trained models |

---

## Data Requirements

**Current data captured per request:**
- user_id, provider, model, tokens_in, tokens_out, cost_usd, latency_ms, app_tag, timestamp

**Additional data needed for ML (opt-in):**
- `prompt_type` — classified by SDK (heuristic or ML)
- `complexity` — scored by SDK or server
- `prompt_length_chars` — useful for classification without storing prompt text
- `has_code_blocks` — boolean, useful signal
- `system_prompt_length` — useful for complexity estimation
- `num_messages` — conversation turn count (for chat)
- `response_quality_rating` — user feedback (for learning loop)

**Privacy note:** The SDK's zero-proxy, no-key-storage design should extend to prompts. ML features should work on **metadata only** (token counts, latency, model) or on **locally-computed features** (prompt_type, complexity) without transmitting raw prompt text to TokenGauge.

---

## Architecture Decision: SDK-side vs Server-side ML

| Consideration | SDK-side | Server-side |
|--------------|----------|-------------|
| Privacy | Better — prompt never leaves user's machine | Requires prompt transmission or embedding |
| Latency | Adds ~1–5ms to SDK (acceptable) | No impact on SDK; batch processing |
| Model updates | Requires SDK version bump | Deploy anytime |
| Complexity | Increases SDK size and dependencies | Keeps SDK thin |
| Training data | Hard to collect (runs on user's machine) | Easy — all data in MongoDB |

**Recommendation:** Hybrid approach.
- **SDK-side:** Heuristic classification + rule-based complexity (no ML dependencies)
- **Server-side:** Anomaly detection, cost forecasting, model recommendations, clustering (all work on existing metadata, no prompts needed)

---

## Next Steps

1. **Define the classification taxonomy** ✅ DONE — `code`, `chat`, `summarization`, `analysis`, `creative`, `extraction`, `translation`, `other`
2. **Implement heuristic classifier in SDK** — keyword/regex based, populate `prompt_type` field
3. **Implement rule-based complexity scoring** — populate `complexity` field
4. **Build anomaly detection arq job** — Z-score on hourly aggregates
5. **Add recommendation engine endpoint** — `/dashboard/recommendations`
6. **Build cost forecasting job** — nightly, per-user, with Prophet or XGBoost
7. **Add dashboard UI** — recommendations panel, forecast chart, anomaly timeline
