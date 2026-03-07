"""
Seed script for local development.
Creates a test org, test user, and fake api_calls if they don't already exist.

Usage:
    python seed.py           # skips api_calls if any exist
    python seed.py --force   # wipes api_calls and re-seeds
"""
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext

from database import connect_db, disconnect_db
from models import ApiCall, Org, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TEST_EMAIL = "test@tokenwatch.dev"
TEST_PASSWORD = "password123"
ORG_NAME = "Test Org"

_DEV_USER_ID_STR = "000000000000000000000001"

PROVIDERS = [
    ("anthropic", "claude-3-5-sonnet", 3.00, 15.00),
    ("anthropic", "claude-3-haiku",    0.25,  1.25),
    ("openai",    "gpt-4o",            5.00, 15.00),
    ("openai",    "gpt-4o-mini",       0.15,  0.60),
    ("google",    "gemini-1.5-flash",  0.075, 0.30),
]


def _cost(tokens_in: int, tokens_out: int, price_in: float, price_out: float) -> float:
    return (tokens_in / 1_000_000) * price_in + (tokens_out / 1_000_000) * price_out


async def seed() -> None:
    await connect_db()

    from beanie import PydanticObjectId
    dev_uid = PydanticObjectId(_DEV_USER_ID_STR)

    # ── Org ──────────────────────────────────────────────────────────────────
    org = await Org.find_one(Org.name == ORG_NAME)
    if not org:
        org = Org(name=ORG_NAME, plan="free", owner_id=PydanticObjectId())
        await org.insert()
        print(f"[seed] Created org '{ORG_NAME}' -> {org.id}")
    else:
        print(f"[seed] Org already exists -> {org.id}")

    # ── User ─────────────────────────────────────────────────────────────────
    user = await User.find_one(User.email == TEST_EMAIL)
    if not user:
        user = User(
            email=TEST_EMAIL,
            password_hash=pwd_context.hash(TEST_PASSWORD),
            org_id=org.id,
        )
        await user.insert()
        org.owner_id = user.id
        await org.save()
        print(f"[seed] Created user '{TEST_EMAIL}' (password: {TEST_PASSWORD}) -> {user.id}")
    else:
        print(f"[seed] User already exists -> {user.id}")

    # ── Fake api_calls ────────────────────────────────────────────────────────
    force = "--force" in sys.argv
    existing = await ApiCall.find(ApiCall.user_id == dev_uid).count()
    if existing > 0 and not force:
        print(f"[seed] {existing} api_calls already exist — run with --force to reseed")
    else:
        if existing > 0:
            await ApiCall.find(ApiCall.user_id == dev_uid).delete()
            print(f"[seed] Deleted {existing} existing api_calls")
        now = datetime.now(timezone.utc)
        calls = []
        for day_offset in range(30):
            ts_base = now - timedelta(days=day_offset)
            # 3–12 calls per day
            for _ in range(random.randint(3, 12)):
                provider, model, price_in, price_out = random.choice(PROVIDERS)
                tokens_in  = random.randint(200, 4000)
                tokens_out = random.randint(100, 2000)
                calls.append(ApiCall(
                    user_id=dev_uid,
                    provider=provider,
                    model=model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=_cost(tokens_in, tokens_out, price_in, price_out),
                    latency_ms=random.randint(120, 2800),
                    app_tag=random.choice(["prod", "dev", None]),
                    timestamp=ts_base - timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59)),
                ))

        await ApiCall.insert_many(calls)
        print(f"[seed] Inserted {len(calls)} fake api_calls over the last 30 days")

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(seed())
