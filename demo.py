"""
TokenGauge SDK — Live Demo
==========================
Showcases wrapping, model recommendations, app tags, and bulk usage generation.

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
from tokengauge import TokenGauge

# ─── Config ───────────────────────────────────────────────────────────────────

OPENAI_KEY    = os.getenv("OPENAI_API_KEY")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_KEY    = os.getenv("GOOGLE_API_KEY")
TG_TOKEN      = os.getenv("TOKENGAUGE_TOKEN")

BULK_CALLS = 50  # number of calls in the bulk generation phase

OPENAI_MODELS = [
    ("gpt-4o",      100),
    ("gpt-4o-mini", 200),
    ("gpt-4.1",     100),
    ("gpt-4.1-mini", 150),
    ("gpt-4.1-nano", 80),
]

ANTHROPIC_MODELS = [
    ("claude-haiku-4-5-20251001", 200),
    ("claude-3-5-sonnet-20241022", 100),
]

TAGS = ["prod", "staging", "dev", "chatbot", "batch-jobs", "summarizer", "internal-tools"]

PROMPTS = [
    ("What is machine learning?",                                        "chat"),
    ("Write a haiku about Python.",                                      "creative"),
    ("Explain REST APIs in one sentence.",                               "chat"),
    ("What is the difference between SQL and NoSQL?",                    "analysis"),
    ("Give me a fun fact about space.",                                   "chat"),
    ("Write a Python function to sort a list of dicts by key.",          "code"),
    ("Summarize the benefits of microservices architecture.",            "summarization"),
    ("Translate 'hello world' into 5 languages.",                        "translation"),
    ("Compare TCP vs UDP in 3 bullet points.",                           "analysis"),
    ("Write a regex to validate email addresses.",                       "code"),
    ("Explain the CAP theorem simply.",                                  "chat"),
    ("What are the SOLID principles?",                                   "code"),
    ("Write a limerick about debugging.",                                "creative"),
    ("List 3 pros and 3 cons of serverless.",                            "analysis"),
    ("How does garbage collection work in Java?",                        "code"),
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

W = 60  # print width

def header(num, title):
    print(f"\n{'=' * W}")
    print(f"  {num}. {title}")
    print(f"{'=' * W}\n")

def status(label, ok):
    return f"  {label:<18} {'loaded' if ok else 'MISSING'}"

def bar(current, total, width=30):
    pct = current / total
    filled = int(width * pct)
    return f"[{'#' * filled}{'-' * (width - filled)}] {current}/{total}"

# ─── Init ─────────────────────────────────────────────────────────────────────

print()
print("  ╔════════════════════════════════════════╗")
print("  ║        TokenGauge SDK — Live Demo      ║")
print("  ╚════════════════════════════════════════╝")
print()
print(status("OpenAI",    OPENAI_KEY))
print(status("Anthropic", ANTHROPIC_KEY))
print(status("Google",    GOOGLE_KEY))
print(status("TokenGauge", TG_TOKEN))
print()

if not TG_TOKEN:
    print("  ERROR: TOKENGAUGE_TOKEN is required. Add it to your .env")
    sys.exit(1)

tw = TokenGauge(token=TG_TOKEN)
print("  Connected to TokenGauge!")

# ─── 1. Model Recommendations ────────────────────────────────────────────────

header(1, "MODEL RECOMMENDATIONS  (local — no API call)")

rec = tw.recommend_model(
    messages=[{"role": "user", "content": "What is the capital of France?"}],
)
print(f"  Prompt:       \"What is the capital of France?\"")
print(f"  Type:         {rec['prompt_type']}  |  Complexity: {rec['complexity']}/10")
print(f"  Best model:   {rec['best_overall']['model']}  ({rec['best_overall']['provider']})")
print(f"  Est. cost:    ${rec['best_overall']['estimated_cost_usd']:.5f}")
print(f"  Success:      {rec['best_overall']['success_probability']:.0%}")

rec = tw.recommend_model(
    messages=[{"role": "user", "content":
        "Refactor this Python class to use dataclasses, add type hints, "
        "implement __eq__ and __hash__, write comprehensive pytest tests."
    }],
    provider="anthropic",
    budget_usd=0.10,
)
print(f"\n  Prompt:       \"Refactor Python class...\" (complex code)")
print(f"  Type:         {rec['prompt_type']}  |  Complexity: {rec['complexity']}/10")
print(f"  Best overall: {rec['best_overall']['model']}  (${rec['best_overall']['estimated_cost_usd']:.5f})")
print(f"  Best Anthr.:  {rec['within_provider']['model']}  (${rec['within_provider']['estimated_cost_usd']:.5f})")

print(f"\n  {'Category':<16} {'Cplx':<6} {'Best Model':<26} {'Cost':<12} {'P(ok)'}")
print(f"  {'─' * 70}")
categories = [
    ("Hey, how's it going?",                                                "chat"),
    ("Write a BST in Rust with insert, delete, balance",                    "code"),
    ("Summarize this 10-page transformer paper...",                         "summarization"),
    ("Correlation between GDP growth and carbon emissions across G20",      "analysis"),
    ("Write a short story about a robot discovering music",                 "creative"),
    ("Translate this legal document from English to Mandarin",              "translation"),
]
for prompt, _ in categories:
    r = tw.recommend_model(messages=[{"role": "user", "content": prompt}])
    b = r["best_overall"]
    print(f"  {r['prompt_type']:<16} {r['complexity']:<6} {b['model']:<26} ${b['estimated_cost_usd']:<11.5f} {b['success_probability']:.0%}")

# ─── 2. Single-provider demos ────────────────────────────────────────────────

if OPENAI_KEY:
    header(2, "OPENAI")
    client = tw.wrap(openai.OpenAI(api_key=OPENAI_KEY))
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}],
    )
    print(f"  Model:   gpt-4o-mini")
    print(f"  Reply:   {resp.choices[0].message.content}")
    print(f"  Tokens:  {resp.usage.prompt_tokens} in / {resp.usage.completion_tokens} out")

if ANTHROPIC_KEY:
    header(3, "ANTHROPIC")
    client = tw.wrap(anthropic.Anthropic(api_key=ANTHROPIC_KEY))
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}],
    )
    print(f"  Model:   claude-haiku-4.5")
    print(f"  Reply:   {resp.content[0].text}")
    print(f"  Tokens:  {resp.usage.input_tokens} in / {resp.usage.output_tokens} out")

if GOOGLE_KEY:
    header(4, "GOOGLE GEMINI")
    client = tw.wrap(genai.Client(api_key=GOOGLE_KEY))
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Explain quantum computing in one sentence.",
    )
    print(f"  Model:   gemini-2.0-flash")
    print(f"  Reply:   {resp.text}")

# ─── 5. App Tags ─────────────────────────────────────────────────────────────

if OPENAI_KEY:
    header(5, "APP TAGS")
    for tag in ["summarizer", "chatbot", "batch-jobs"]:
        client = tw.wrap(openai.OpenAI(api_key=OPENAI_KEY), app_tag=tag)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": random.choice([p for p, _ in PROMPTS])}],
            max_tokens=60,
        )
        reply = resp.choices[0].message.content[:80].replace("\n", " ")
        print(f"  [{tag:<14}] {reply}...")

# ─── 6. Bulk Generation ──────────────────────────────────────────────────────

header(6, f"BULK GENERATION  ({BULK_CALLS} calls across providers)")

# Build weighted model pool
pool = []
if OPENAI_KEY:
    for model, max_tok in OPENAI_MODELS:
        pool.append(("openai", model, max_tok, openai.OpenAI(api_key=OPENAI_KEY)))
if ANTHROPIC_KEY:
    for model, max_tok in ANTHROPIC_MODELS:
        pool.append(("anthropic", model, max_tok, anthropic.Anthropic(api_key=ANTHROPIC_KEY)))

if not pool:
    print("  No API keys available — skipping bulk generation.")
else:
    total_tokens = 0
    total_cost = 0.0
    providers_hit = set()
    models_hit = set()
    start = time.time()

    for i in range(BULK_CALLS):
        provider, model, max_tok, base_client = random.choice(pool)
        tag = random.choice(TAGS)
        prompt_text, _ = random.choice(PROMPTS)

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
    print(f"\n\n  Completed in {elapsed:.1f}s")
    print(f"  Total tokens:  {total_tokens:,}")
    print(f"  Providers:     {len(providers_hit)}  ({', '.join(sorted(providers_hit))})")
    print(f"  Models:        {len(models_hit)}  ({', '.join(sorted(models_hit))})")

# ─── Done ─────────────────────────────────────────────────────────────────────

print(f"\n{'=' * W}")
print(f"  DONE — view your dashboard:")
print(f"  https://tokengauge.onrender.com")
print(f"{'=' * W}\n")
