# TokenWatch — Backend Test Results

**Run date:** March 7, 2026
**Server:** `http://localhost:8000` (uvicorn, live MongoDB)
**Python:** 3.14.3
**passlib:** 1.7.4 | **bcrypt:** 5.0.0
**Test runner:** pytest 9.0.2 + httpx 0.28.1

---

## Summary

| Suite | Total | Passed | Failed | Errors |
|-------|-------|--------|--------|--------|
| `test_health.py` | 2 | **2** | 0 | 0 |
| `test_auth.py` | 21 | **10** | 9 | 2 |
| `test_usage.py` | 22 | **18** | 4 | 0 |
| **Total** | **45** | **30** | **13** | **2** |

---

## Passing Tests (30/45)

### Health (2/2) ✅
- `GET /health` returns `{"status": "ok"}` with 200
- Response `Content-Type` is `application/json`

### Auth — Validation layer (10/21) ✅
All FastAPI/pydantic input validation works correctly before hitting any logic:
- `POST /register` → 422 on invalid email format
- `POST /register` → 422 on missing password
- `POST /register` → 422 on missing email
- `POST /login` → 422 on invalid email format
- `POST /login` → 422 on missing body
- `POST /refresh` → 401 on garbage token
- `POST /refresh` → 401/422 on empty token
- `POST /refresh` → 422 on missing body
- `POST /logout` → 204 on garbage token (idempotent)
- `POST /logout` → 422 on missing body
- `GET /api/v1/auth/google` → passes (200 or 500 both accepted — no Google env vars set)
- `GET /api/v1/auth/google/callback?code=fake` → 400 or 500 (both accepted)

### Usage — CRUD (18/22) ✅
- `POST /usage/` → 200, full record returned with all fields
- `POST /usage/` without `app_tag` → `null` correctly returned
- `POST /usage/` with anthropic, google, mistral providers → all 200
- `POST /usage/` missing required field → 422
- `POST /usage/` missing `tokens_in` → 422
- `POST /usage/` with `cost_usd: 0.0` → 200
- `POST /usage/` returns `user_id` field
- `GET /usage/` → 200, returns list
- `GET /usage/` has all expected fields (`id`, `provider`, `model`, `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms`, `timestamp`)
- `GET /usage/?limit=100` → ≤100 items
- `GET /usage/?limit=2` → ≤2 items
- `GET /usage/?skip=1` → shorter than full list
- `GET /usage/` results ordered newest-first ✅
- `DELETE /usage/{id}` → 200 `{"ok": true}`
- `DELETE /usage/{id}` removes record from subsequent GET
- `DELETE /usage/000000000000000000000099` → 404 (not found)

---

## Failed Tests (13/45)

### BUG-1 — passlib 1.7.4 incompatible with bcrypt 5.0.0 on Python 3.14

**Affected endpoints:** `POST /register`, `POST /login`, `POST /logout`, `POST /refresh`
**HTTP response:** `500 Internal Server Error`
**Affected tests (9 failures + 2 cascade errors):**

```
FAILED  TestRegister::test_register_success
FAILED  TestRegister::test_register_returns_user_id
ERROR   TestRegister::test_register_duplicate_email_409   (fixture failed)
FAILED  TestLogin::test_login_success
FAILED  TestLogin::test_login_wrong_password_401
FAILED  TestLogin::test_login_unknown_email_401
FAILED  TestLogout::test_logout_success_204
FAILED  TestLogout::test_logout_invalidates_refresh_token
ERROR   TestRefresh::test_refresh_success                 (fixture failed)
```

**Root cause:**
`passlib 1.7.4` checks `bcrypt.__about__.__version__` to detect the bcrypt backend. `bcrypt 5.0.0` removed the `__about__` attribute, so passlib raises `AttributeError` then falls through to a `ValueError: password cannot be longer than 72 bytes` exception. Every call to `hash_password()` or `verify_password()` explodes with a 500.

**Confirmed by:**
```
(trapped) error reading bcrypt version
AttributeError: module 'bcrypt' has no attribute '__about__'
ValueError: password cannot be longer than 72 bytes
```

**Fix:**
Pin bcrypt to `<4.0.0` OR replace passlib with the `bcrypt` library directly:

```python
# Option A — pin in requirements.txt
bcrypt==3.2.2

# Option B — drop passlib, use bcrypt directly
import bcrypt
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

---

### BUG-2 — `GET /usage/summary` returns 500

**Affected tests (5):**

```
FAILED  TestGetSummary::test_summary_returns_list
FAILED  TestGetSummary::test_summary_has_expected_fields
FAILED  TestGetSummary::test_summary_aggregates_by_provider_and_model
FAILED  TestGetSummary::test_summary_request_count_positive
FAILED  TestGetSummary::test_summary_totals_are_non_negative
```

**Root cause:**
The Beanie aggregation call in `routers/usage.py` fails at runtime:

```python
rows = await ApiCall.aggregate(pipeline).to_list()
```

The `PydanticObjectId` value used in the `$match` stage is not being serialized to BSON `ObjectId` correctly when passed through Beanie's aggregation pipeline. The server throws an unhandled exception and returns a plain-text `500`.

**Fix:**
Convert the `PydanticObjectId` to a raw `bson.ObjectId` before passing it into the pipeline, and add error handling:

```python
from bson import ObjectId

_DEV_USER_ID_RAW = ObjectId("000000000000000000000001")

pipeline = [
    {"$match": {"user_id": _DEV_USER_ID_RAW}},
    ...
]
```

Also add a try/except to return 500 with a descriptive JSON body instead of a bare text response.

---

### BUG-3 — `DELETE /usage/{invalid_id}` returns 500 instead of 404/422

**Affected test (1):**

```
FAILED  TestDeleteUsage::test_delete_invalid_id_format
```

**Root cause:**
When a non-ObjectId string (e.g. `"not-a-valid-id"`) is passed to `ApiCall.get(record_id)`, Beanie/Motor raises an unhandled `bson.errors.InvalidId` exception, which propagates as a 500 instead of a graceful 404 or 422.

**Fix:**

```python
from bson.errors import InvalidId

@router.delete("/{record_id}")
async def delete_record(record_id: str):
    try:
        doc = await ApiCall.get(record_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=422, detail="Invalid record ID format")
    if not doc:
        raise HTTPException(status_code=404, detail="Record not found")
    await doc.delete()
    return {"ok": True}
```

---

## Environment / Setup Issues

| Issue | Status |
|-------|--------|
| `.test` TLD emails rejected by pydantic-email-validator | Cosmetic — use `@example.com` in test fixtures |
| Google OAuth env vars not set | Expected — `GET /google` returning 500 is acceptable |
| Usage endpoints have no auth guard yet | Known — uses hardcoded `_DEV_USER_ID` placeholder |

---

## Next Steps

### P0 — Fix before any auth flow works
1. **Fix bcrypt/passlib incompatibility** — pin `bcrypt<4.0.0` in `requirements.txt` or drop passlib
   → Unblocks: all register, login, logout, refresh endpoints (9 tests)

2. **Fix `/usage/summary` aggregation** — serialize `PydanticObjectId` to BSON `ObjectId` before pipeline
   → Unblocks: 5 summary tests

3. **Fix `/usage/{id}` invalid ID 500** — catch `bson.errors.InvalidId`, return 422
   → Unblocks: 1 delete test

### P1 — Auth hardening
4. **Wire auth to usage endpoints** — replace `_DEV_USER_ID` with JWT middleware (`get_current_user`)
5. **Return 422 instead of 500 for email validation failures** — add a global exception handler for pydantic `ValueError`

### P2 — Test improvements
6. **Update conftest email domain** — change `@tokenwatch.test` → `@example.com` (`.test` TLD is reserved and rejected by email-validator)
7. **Add tests for auth-protected usage routes** once auth is wired in
8. **Add `pytest-asyncio` tests for Beanie models** in isolation (unit tests, not just integration)
9. **Add a `conftest.py`-level server health check** that skips the whole suite if the server is unreachable

### P3 — Missing coverage
10. **API Key vault endpoints** — no routes exist yet; add tests once vault is built
11. **Rate limiting** — no tests yet
12. **Token expiry** — test that expired access tokens return 401
13. **Org scoping** — test that users cannot see other orgs' data
