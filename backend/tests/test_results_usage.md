# Usage Endpoint Test Results
**Date:** 2026-03-08
**Server:** http://localhost:3001 (Docker)
**Result: 28/28 PASSED ✅**

---

## POST /usage/ — Log a new API call record

| Test | Status |
|------|--------|
| Log usage success (all fields returned) | ✅ PASSED |
| Log usage without optional `app_tag` | ✅ PASSED |
| Log usage for different providers (OpenAI, Anthropic, Google/Gemini, Mistral) | ✅ PASSED |
| Missing required field `provider` → 422 | ✅ PASSED |
| Missing required field `tokens_in` → 422 | ✅ PASSED |
| Zero cost allowed | ✅ PASSED |
| Response includes `user_id` | ✅ PASSED |
| Unauthenticated request → 401 | ✅ PASSED |
| Bad Bearer token → 401 | ✅ PASSED |

## GET /usage/ — List records with pagination

| Test | Status |
|------|--------|
| Returns a list | ✅ PASSED |
| Response has expected fields (id, provider, model, tokens_in, tokens_out, cost_usd, latency_ms, timestamp) | ✅ PASSED |
| Default limit is 100 | ✅ PASSED |
| `limit` query param respected | ✅ PASSED |
| `skip` query param shifts results | ✅ PASSED |
| Records ordered by timestamp descending (newest first) | ✅ PASSED |
| Users only see their own records | ✅ PASSED |
| Unauthenticated request → 401 | ✅ PASSED |

## GET /usage/summary — Aggregated summary by provider+model

| Test | Status |
|------|--------|
| Returns a list | ✅ PASSED |
| Has expected fields (provider, model, total_tokens_in, total_tokens_out, total_cost_usd, request_count) | ✅ PASSED |
| Each (provider, model) pair appears exactly once | ✅ PASSED |
| `request_count` is positive | ✅ PASSED |
| Totals are non-negative | ✅ PASSED |
| Unauthenticated request → 401 | ✅ PASSED |

## DELETE /usage/{id} — Delete a record

| Test | Status |
|------|--------|
| Delete existing record → `{"ok": true}` | ✅ PASSED |
| Deleted record no longer appears in list | ✅ PASSED |
| Delete nonexistent record → 404 | ✅ PASSED |
| Delete with invalid ID format → 404 or 422 | ✅ PASSED |
| Unauthenticated request → 401 | ✅ PASSED |

---

## Provider Coverage
The test suite covers all major providers via `test_log_usage_different_providers`:

| Provider | Model | Tested |
|----------|-------|--------|
| OpenAI | gpt-4o-mini | ✅ |
| Anthropic | claude-3-5-sonnet | ✅ |
| Google | gemini-1.5-flash | ✅ |
| Mistral | mistral-small | ✅ |

---

## Notes
- All endpoints correctly enforce JWT authentication (401 on missing/bad token)
- User data isolation confirmed (users only see their own records)
- Pagination (limit/skip) and sort order (newest first) work correctly
- Summary aggregation correctly groups by (provider, model) with no duplicates
