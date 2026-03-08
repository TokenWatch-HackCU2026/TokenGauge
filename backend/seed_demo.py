"""
Seed a live demo account with heavy, realistic API usage data.

Targets the production MongoDB (MONGO_URI from .env).
Creates ~2,500 API calls over 90 days across all providers, models,
app tags, and API keys so every dashboard filter has data.

Usage:
    python seed_demo.py           # skip if data exists
    python seed_demo.py --force   # wipe and reseed

Env vars:
    DEMO_EMAIL     (default: demo@tokengauge.dev)
    DEMO_PASSWORD  (default: demodemo123)
"""
import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
load_dotenv()

from auth import hash_password
from database import connect_db, disconnect_db
from models import ApiCall, User

DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@tokengauge.dev")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demodemo123")

# ── Models with realistic pricing ($/M tokens) ──────────────────────────────

MODELS = [
    # provider,     model,                  input,  output, weight
    # OpenAI
    ("openai",      "gpt-4o",               2.50,   10.00,  20),
    ("openai",      "gpt-4o-mini",          0.15,    0.60,  30),
    ("openai",      "gpt-4.1",              2.00,    8.00,  10),
    ("openai",      "gpt-4.1-mini",         0.40,    1.60,  15),
    ("openai",      "gpt-4.1-nano",         0.10,    0.40,   8),
    ("openai",      "o3-mini",              1.10,    4.40,   5),
    # Anthropic
    ("anthropic",   "claude-sonnet-4.5",    3.00,   15.00,  18),
    ("anthropic",   "claude-haiku-4.5",     1.00,    5.00,  25),
    ("anthropic",   "claude-opus-4.5",      5.00,   25.00,   4),
    ("anthropic",   "claude-3-5-sonnet",    3.00,   15.00,  12),
    ("anthropic",   "claude-3-haiku",       0.25,    1.25,  20),
    # Google
    ("google",      "gemini-2.5-pro",       1.25,   10.00,   8),
    ("google",      "gemini-2.5-flash",     0.30,    2.50,  15),
    ("google",      "gemini-2.0-flash",     0.10,    0.40,  12),
    ("google",      "gemini-1.5-pro",       1.25,    5.00,   5),
]

# Fake API key hints (last 4 chars) — gives the "Key" filter real data
API_KEYS = {
    "openai":    ["sk-a1B2", "sk-x9Z3", "sk-pQ7r"],
    "anthropic": ["sk-mN4k", "sk-vW8j"],
    "google":    ["AI-dF5g", "AI-hK2m"],
}

APP_TAGS = ["prod", "staging", "dev", "batch-jobs", "chatbot", "internal-tools", None]

PROMPT_TYPES = ["chat", "completion", "summarization", "code-gen", "embedding", "classification", None]

# ── Helpers ──────────────────────────────────────────────────────────────────

def _cost(tokens_in, tokens_out, price_in, price_out):
    return (tokens_in / 1_000_000) * price_in + (tokens_out / 1_000_000) * price_out


def _weighted_choice(models):
    """Pick a model weighted by its usage frequency."""
    population = [(p, m, pi, po) for p, m, pi, po, w in models]
    weights = [w for *_, w in models]
    return random.choices(population, weights=weights, k=1)[0]


def _usage_pattern(day_offset, total_days):
    """Simulate realistic usage: ramp up over time, weekday-heavy, with spikes."""
    # Base: more usage as time goes on (growth curve)
    growth = 0.4 + 0.6 * ((total_days - day_offset) / total_days)
    # Day of week: weekdays are 2-3x busier than weekends
    day_of_week = (datetime.now(timezone.utc) - timedelta(days=day_offset)).weekday()
    weekday_mult = 1.0 if day_of_week < 5 else 0.35
    # Random spikes (10% chance of a heavy day)
    spike = random.uniform(2.0, 4.0) if random.random() < 0.10 else 1.0
    base_calls = int(25 * growth * weekday_mult * spike)
    return max(3, base_calls + random.randint(-5, 10))


async def seed_demo():
    await connect_db()

    # ── User ─────────────────────────────────────────────────────────────────
    user = await User.find_one(User.email == DEMO_EMAIL)
    if not user:
        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            full_name="Demo Account",
        )
        await user.insert()
        print(f"[demo-seed] Created '{DEMO_EMAIL}' (password: {DEMO_PASSWORD}) -> {user.id}")
    else:
        print(f"[demo-seed] Found existing user '{DEMO_EMAIL}' -> {user.id}")

    uid = user.id

    # ── Seed data ────────────────────────────────────────────────────────────
    force = "--force" in sys.argv
    existing = await ApiCall.find(ApiCall.user_id == uid).count()
    if existing > 0 and not force:
        print(f"[demo-seed] {existing} records exist — use --force to reseed")
        await disconnect_db()
        return

    if existing > 0:
        await ApiCall.find(ApiCall.user_id == uid).delete()
        print(f"[demo-seed] Deleted {existing} existing records")

    now = datetime.now(timezone.utc)
    total_days = 365
    calls = []

    for day_offset in range(total_days):
        num_calls = _usage_pattern(day_offset, total_days)
        day_base = now - timedelta(days=day_offset)

        for _ in range(num_calls):
            provider, model, price_in, price_out = _weighted_choice(MODELS)

            # Token ranges vary by model tier
            if "opus" in model or "gpt-4o" == model or "pro" in model:
                tokens_in = random.randint(1000, 12000)
                tokens_out = random.randint(500, 6000)
                latency = random.randint(800, 5000)
            elif "haiku" in model or "mini" in model or "nano" in model or "flash" in model:
                tokens_in = random.randint(100, 2000)
                tokens_out = random.randint(50, 1000)
                latency = random.randint(80, 600)
            else:
                tokens_in = random.randint(300, 5000)
                tokens_out = random.randint(150, 3000)
                latency = random.randint(200, 2000)

            key_hint = random.choice(API_KEYS[provider])
            app_tag = random.choice(APP_TAGS)
            prompt_type = random.choice(PROMPT_TYPES)
            complexity = random.randint(1, 5) if random.random() > 0.3 else None

            ts = day_base - timedelta(
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59),
            )

            calls.append(ApiCall(
                user_id=uid,
                provider=provider,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=_cost(tokens_in, tokens_out, price_in, price_out),
                latency_ms=latency,
                key_hint=key_hint,
                app_tag=app_tag,
                prompt_type=prompt_type,
                complexity=complexity,
                timestamp=ts,
            ))

    # Insert in batches to avoid memory issues
    batch_size = 500
    for i in range(0, len(calls), batch_size):
        await ApiCall.insert_many(calls[i:i + batch_size])

    # Summary stats
    total_cost = sum(c.cost_usd for c in calls)
    total_tokens = sum(c.tokens_in + c.tokens_out for c in calls)
    providers_used = len(set(c.provider for c in calls))
    models_used = len(set(c.model for c in calls))
    keys_used = len(set(c.key_hint for c in calls if c.key_hint))

    print(f"[demo-seed] Inserted {len(calls)} API calls over {total_days} days")
    print(f"[demo-seed]   Total cost:  ${total_cost:.2f}")
    print(f"[demo-seed]   Total tokens: {total_tokens:,}")
    print(f"[demo-seed]   Providers: {providers_used}  Models: {models_used}  API keys: {keys_used}")
    print(f"[demo-seed]")
    print(f"[demo-seed] Login:  {DEMO_EMAIL} / {DEMO_PASSWORD}")

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(seed_demo())
