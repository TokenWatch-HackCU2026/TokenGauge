"""
TokenGauge SDK — Live Demo
==========================
Interactive demo with pauses between each step.

    python demo.py

Env vars (.env):
    OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, TOKENGAUGE_TOKEN
"""

import os
import sys
import time
import random

from dotenv import load_dotenv
load_dotenv()

import openai
import anthropic
from google import genai
from tokengauge import TokenGauge, BudgetExceededError

# ─── Config ───────────────────────────────────────────────────────────────────

OPENAI_KEY    = os.getenv("OPENAI_API_KEY")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_KEY    = os.getenv("GOOGLE_API_KEY")
TG_TOKEN      = os.getenv("TOKENGAUGE_TOKEN")

BULK_CALLS = 50

OPENAI_MODELS = [
    ("gpt-4o",       100),
    ("gpt-4o-mini",  200),
    ("gpt-4.1",      100),
    ("gpt-4.1-mini", 150),
    ("gpt-4.1-nano",  80),
]

ANTHROPIC_MODELS = [
    ("claude-haiku-4-5-20251001",  200),
    ("claude-3-5-sonnet-20241022", 100),
]

TAGS = ["prod", "staging", "dev", "chatbot", "batch-jobs", "summarizer", "internal-tools"]

PROMPTS = [
    "What is machine learning?",
    "Write a haiku about Python.",
    "Explain REST APIs in one sentence.",
    "What is the difference between SQL and NoSQL?",
    "Give me a fun fact about space.",
    "Write a Python function to sort a list of dicts by key.",
    "Summarize the benefits of microservices architecture.",
    "Translate 'hello world' into 5 languages.",
    "Compare TCP vs UDP in 3 bullet points.",
    "Write a regex to validate email addresses.",
    "Explain the CAP theorem simply.",
    "What are the SOLID principles?",
    "Write a limerick about debugging.",
    "List 3 pros and 3 cons of serverless.",
    "How does garbage collection work in Java?",
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

W = 62

def banner(text):
    pad = W - 4
    print()
    print(f"  ╔{'═' * pad}╗")
    print(f"  ║{text:^{pad}}║")
    print(f"  ╚{'═' * pad}╝")
    print()

def step(num, title):
    print()
    print(f"  ┌{'─' * (W - 4)}┐")
    print(f"  │  STEP {num}: {title:<{W - 13}}│")
    print(f"  └{'─' * (W - 4)}┘")
    print()

def pause(msg="Press ENTER to continue..."):
    print(f"\n  >> {msg}")
    input("  >> ")
    print()

def ok(text):
    print(f"  [OK] {text}")

def info(text):
    print(f"       {text}")

def warn(text):
    print(f"  [!!] {text}")

def status(label, val):
    dot = "loaded" if val else "MISSING"
    return f"  {'*' if val else ' '} {label:<16} {dot}"

def bar(current, total, width=30):
    pct = current / total
    filled = int(width * pct)
    return f"[{'#' * filled}{'-' * (width - filled)}] {current}/{total}"

def print_rec(label, rec):
    best = rec["best_overall"]
    within = rec.get("within_provider")
    wp = f"  within={within['model']}" if within else ""
    print(f"    {label:<10} {rec['prompt_type']:<14} cplx={rec['complexity']}  "
          f"{best['model']} ({best['success_probability']:.0%}, ${best['estimated_cost_usd']:.5f})"
          f"{wp}")

# ─── Init ─────────────────────────────────────────────────────────────────────

banner("TokenGauge SDK  —  Live Demo")

print(status("OpenAI",     OPENAI_KEY))
print(status("Anthropic",  ANTHROPIC_KEY))
print(status("Google",     GOOGLE_KEY))
print(status("TokenGauge", TG_TOKEN))
print()

if not TG_TOKEN:
    warn("TOKENGAUGE_TOKEN is required. Add it to your .env")
    sys.exit(1)

tw = TokenGauge(token=TG_TOKEN)
ok("Connected to TokenGauge!")

pause("Ready to begin the demo?")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: Hit the spend limit
# ═══════════════════════════════════════════════════════════════════════════════

step(1, "SPEND LIMIT ENFORCEMENT")

print("  The SDK checks your budget BEFORE making the API call.")
print("  If the estimated cost exceeds your remaining budget,")
print("  a BudgetExceededError is raised and NO call is made.")
print()

if OPENAI_KEY:
    client = openai.OpenAI(api_key=OPENAI_KEY)
    wrapped = tw.wrap(client, app_tag="limit-demo")

    info("Attempting:  gpt-4o  ->  \"What is 2 + 2?\"")
    print()

    try:
        response = wrapped.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "What is 2 + 2?"}],
        )
        ok("Call went through — no spend limit is set.")
        info(f"Reply:   {response.choices[0].message.content}")
        info(f"Tokens:  {response.usage.prompt_tokens} in / {response.usage.completion_tokens} out")
    except BudgetExceededError as e:
        warn("BudgetExceededError!")
        print()
        info(f"Provider:        {e.provider}")
        info(f"Estimated cost:  ${e.estimated_cost:.5f}")
        info(f"Remaining:       ${e.remaining:.5f}")
        info(f"Period:          {e.period}")
        print()
        ok("The API call was BLOCKED. No money spent.")
else:
    warn("No OpenAI key — skipping spend limit demo.")

pause("Disable or raise the spend limit in the dashboard, then press ENTER...")

# Re-init to clear cached spend status
tw = TokenGauge(token=TG_TOKEN)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Verify limit is off — single calls per provider
# ═══════════════════════════════════════════════════════════════════════════════

step(2, "PROVIDER WRAPPERS")

print("  Wrapping each provider client with one line.")
print("  Every call is automatically logged to the dashboard.")
print()

if OPENAI_KEY:
    client = openai.OpenAI(api_key=OPENAI_KEY)
    wrapped = tw.wrap(client, app_tag="demo-openai")

    resp = wrapped.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}],
    )
    ok("OpenAI  gpt-4o-mini")
    info(f"Reply:   {resp.choices[0].message.content}")
    info(f"Tokens:  {resp.usage.prompt_tokens} in / {resp.usage.completion_tokens} out")
    print()

if ANTHROPIC_KEY:
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    wrapped = tw.wrap(client, app_tag="demo-anthropic")

    resp = wrapped.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}],
    )
    ok("Anthropic  claude-haiku-4.5")
    info(f"Reply:   {resp.content[0].text}")
    info(f"Tokens:  {resp.usage.input_tokens} in / {resp.usage.output_tokens} out")
    print()

if GOOGLE_KEY:
    client = genai.Client(api_key=GOOGLE_KEY)
    wrapped = tw.wrap(client, app_tag="demo-google")

    resp = wrapped.models.generate_content(
        model="gemini-2.0-flash",
        contents="Explain quantum computing in one sentence.",
    )
    ok("Google  gemini-2.0-flash")
    info(f"Reply:   {resp.text}")
    print()

pause()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: Model Recommender
# ═══════════════════════════════════════════════════════════════════════════════

step(3, "MODEL RECOMMENDER")

print("  Classifies your prompt locally and scores every model")
print("  by success probability. No API call is made.")
print()

print("  ── Code ──")
print_rec("rec01", tw.recommend_model(
    messages=[{"role": "user", "content": "Refactor this Python class to use dataclasses..."}],
    provider="anthropic",
))
print_rec("rec02", tw.recommend_model(
    messages=[{"role": "user", "content": "Fix this bug in my JavaScript function:\n```js\nfunction add(a, b) { return a - b; }\n```"}],
    provider="openai",
))
print_rec("rec03", tw.recommend_model(
    messages=[{"role": "user", "content": "Implement a binary search tree in Rust with insert, delete, and search methods."}],
    provider="google",
))

print("\n  ── Analysis ──")
print_rec("rec04", tw.recommend_model(
    messages=[{"role": "user", "content": "Compare the pros and cons of REST vs GraphQL for a mobile app backend."}],
    provider="openai",
))
print_rec("rec05", tw.recommend_model(
    messages=[{"role": "user", "content": "Analyze the impact of interest rate hikes on emerging market currencies."}],
    provider="anthropic",
))

print("\n  ── Summarization ──")
print_rec("rec06", tw.recommend_model(
    messages=[{"role": "user", "content": "Summarize this 10-page research paper into 3 key takeaways: [paper text here...]"}],
    provider="google",
))
print_rec("rec07", tw.recommend_model(
    messages=[{"role": "user", "content": "TL;DR this meeting transcript."}],
    provider="anthropic",
))

print("\n  ── Chat ──")
print_rec("rec08", tw.recommend_model(
    messages=[{"role": "user", "content": "Hey, what's a good book to read this weekend?"}],
    provider="openai",
))
print_rec("rec09", tw.recommend_model(
    messages=[
        {"role": "user",      "content": "What's the capital of France?"},
        {"role": "assistant", "content": "Paris."},
        {"role": "user",      "content": "And Germany?"},
    ],
    provider="anthropic",
))

print("\n  ── Creative ──")
print_rec("rec10", tw.recommend_model(
    messages=[{"role": "user", "content": "Write a short story about a robot who learns to paint."}],
    provider="anthropic",
))
print_rec("rec11", tw.recommend_model(
    messages=[{"role": "user", "content": "Brainstorm 10 startup ideas in the climate tech space."}],
    provider="openai",
))

print("\n  ── Extraction ──")
print_rec("rec12", tw.recommend_model(
    messages=[{"role": "user", "content": "Extract all names, dates, and dollar amounts from this contract and format as JSON."}],
    provider="openai",
))
print_rec("rec13", tw.recommend_model(
    messages=[{"role": "user", "content": "Parse this HTML and list all the href links."}],
    provider="google",
))

print("\n  ── Translation ──")
print_rec("rec14", tw.recommend_model(
    messages=[{"role": "user", "content": "Translate this email into Spanish and French."}],
    provider="google",
))

print("\n  ── Budget Constrained ($0.001) ──")
print_rec("rec15", tw.recommend_model(
    messages=[{"role": "user", "content": "Analyze this dataset and explain the trends."}],
    provider="openai",
    budget_usd=0.001,
))

print("\n  ── Best Overall (no provider filter) ──")
print_rec("rec16", tw.recommend_model(
    messages=[{"role": "user", "content": "Write a Python script that scrapes product prices from a website."}],
))

print("\n  ── High Complexity (multi-turn) ──")
print_rec("rec17", tw.recommend_model(
    messages=[
        {"role": "user",      "content": "I'm building a distributed system. Here's my architecture:\n```\n[large diagram]\n```"},
        {"role": "assistant", "content": "Here are some considerations..."},
        {"role": "user",      "content": "What about fault tolerance? Also analyze the CAP theorem tradeoffs for my use case."},
        {"role": "assistant", "content": "For fault tolerance..."},
        {"role": "user",      "content": "Now compare this to a microservices approach and evaluate the pros and cons."},
    ],
    provider="anthropic",
))

pause()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: Bulk fill — flood the dashboard
# ═══════════════════════════════════════════════════════════════════════════════

step(4, f"BULK GENERATION  ({BULK_CALLS} calls)")

print("  Sending real API calls across multiple providers, models,")
print("  and app tags. Watch them appear on the dashboard live.")
print()

pool = []
if OPENAI_KEY:
    for model, max_tok in OPENAI_MODELS:
        pool.append(("openai", model, max_tok, openai.OpenAI(api_key=OPENAI_KEY)))
if ANTHROPIC_KEY:
    for model, max_tok in ANTHROPIC_MODELS:
        pool.append(("anthropic", model, max_tok, anthropic.Anthropic(api_key=ANTHROPIC_KEY)))

if not pool:
    warn("No API keys available — skipping bulk generation.")
else:
    total_tokens = 0
    providers_hit = set()
    models_hit = set()
    start = time.time()

    for i in range(BULK_CALLS):
        provider, model, max_tok, base_client = random.choice(pool)
        tag = random.choice(TAGS)
        prompt_text = random.choice(PROMPTS)

        wrapped = tw.wrap(base_client, app_tag=tag)

        try:
            if provider == "openai":
                resp = wrapped.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt_text}],
                    max_tokens=max_tok,
                )
                tok_in = resp.usage.prompt_tokens
                tok_out = resp.usage.completion_tokens
            elif provider == "anthropic":
                resp = wrapped.messages.create(
                    model=model,
                    max_tokens=max_tok,
                    messages=[{"role": "user", "content": prompt_text}],
                )
                tok_in = resp.usage.input_tokens
                tok_out = resp.usage.output_tokens
            else:
                continue

            total_tokens += tok_in + tok_out
            providers_hit.add(provider)
            models_hit.add(model)

            sys.stdout.write(f"\r  {bar(i + 1, BULK_CALLS)}  {provider:<10} {model:<24} {tag}")
            sys.stdout.flush()

        except Exception as e:
            sys.stdout.write(f"\r  {bar(i + 1, BULK_CALLS)}  SKIP ({type(e).__name__})")
            sys.stdout.flush()

    elapsed = time.time() - start
    print()
    print()
    ok(f"Completed in {elapsed:.1f}s")
    info(f"Total tokens:  {total_tokens:,}")
    info(f"Providers:     {len(providers_hit)}  ({', '.join(sorted(providers_hit))})")
    info(f"Models:        {len(models_hit)}  ({', '.join(sorted(models_hit))})")

# ─── Done ─────────────────────────────────────────────────────────────────────

banner("Demo Complete!")

print("  View your dashboard:")
print("  https://tokengauge.onrender.com")
print()
