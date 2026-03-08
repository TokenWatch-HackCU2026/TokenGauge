"""
TokenGauge SDK Live Demo
-------------------------
Run: python demo.py

Requires .env with:
    OPENAI_API_KEY=sk-...
    ANTHROPIC_API_KEY=sk-ant-...
    GOOGLE_API_KEY=...
    TOKENGAUGE_TOKEN=...
"""
import os
import random

from dotenv import load_dotenv
load_dotenv()

import openai
import anthropic
from google import genai
from tokengauge import TokenGauge

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TOKENGAUGE_TOKEN = os.getenv("TOKENGAUGE_TOKEN")

print("=== TokenGauge SDK Demo ===\n")
print(f"  OpenAI key:     {'loaded' if OPENAI_API_KEY else 'MISSING'}")
print(f"  Anthropic key:  {'loaded' if ANTHROPIC_API_KEY else 'MISSING'}")
print(f"  Google key:     {'loaded' if GOOGLE_API_KEY else 'MISSING'}")
print(f"  TokenGauge:     {'loaded' if TOKENGAUGE_TOKEN else 'MISSING'}")
print()

tw = TokenGauge(token=TOKENGAUGE_TOKEN)
print("Connected to TokenGauge!\n")

# ── 1. Model Recommendations (no API keys needed) ────────────────────────────
print("=" * 60)
print("1. MODEL RECOMMENDATIONS (runs locally, no API call)")
print("=" * 60)

rec = tw.recommend_model(
    messages=[{"role": "user", "content": "What is the capital of France?"}],
)
print(f"\n  Simple chat prompt:")
print(f"    Prompt type:  {rec['prompt_type']}")
print(f"    Complexity:   {rec['complexity']}/10")
print(f"    Best model:   {rec['best_overall']['model']} ({rec['best_overall']['provider']})")
print(f"    Est. cost:    ${rec['best_overall']['estimated_cost_usd']:.5f}")
print(f"    Success prob: {rec['best_overall']['success_probability']:.0%}")

rec = tw.recommend_model(
    messages=[{"role": "user", "content": """
        Refactor this Python class to use dataclasses, add type hints,
        implement __eq__ and __hash__, add a factory classmethod that
        parses from JSON, and write comprehensive unit tests with pytest.
    """}],
    provider="anthropic",
    budget_usd=0.10,
)
print(f"\n  Complex code prompt:")
print(f"    Prompt type:    {rec['prompt_type']}")
print(f"    Complexity:     {rec['complexity']}/10")
print(f"    Best overall:   {rec['best_overall']['model']} (${rec['best_overall']['estimated_cost_usd']:.5f})")
print(f"    Best Anthropic: {rec['within_provider']['model']} (${rec['within_provider']['estimated_cost_usd']:.5f})")

print(f"\n  {'Type':<16} {'Complexity':<12} {'Best Model':<24} {'Est. Cost':<12} {'Success'}")
print(f"  {'-' * 76}")
prompts = {
    "chat":          "Hey, how's it going?",
    "code":          "Write a binary search tree in Rust with insert, delete, and balance operations",
    "summarization": "Summarize the following 10-page research paper on transformer architectures...",
    "analysis":      "Analyze the correlation between GDP growth and carbon emissions across G20 nations",
    "creative":      "Write a short story about a robot discovering music for the first time",
    "translation":   "Translate the following legal document from English to Mandarin Chinese",
}
for ptype, prompt in prompts.items():
    r = tw.recommend_model(messages=[{"role": "user", "content": prompt}])
    best = r["best_overall"]
    print(f"  {r['prompt_type']:<16} {r['complexity']:<12} {best['model']:<24} ${best['estimated_cost_usd']:<11.5f} {best['success_probability']:.0%}")

# ── 2. OpenAI ─────────────────────────────────────────────────────────────────
if OPENAI_API_KEY:
    print(f"\n{'=' * 60}")
    print("2. OPENAI — wrapped with TokenGauge")
    print("=" * 60)

    client = tw.wrap(openai.OpenAI(api_key=OPENAI_API_KEY))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}],
    )
    print(f"\n  Model:  gpt-4o-mini")
    print(f"  Reply:  {response.choices[0].message.content}")
    print(f"  Tokens: {response.usage.prompt_tokens} in / {response.usage.completion_tokens} out")

# ── 3. Anthropic ──────────────────────────────────────────────────────────────
if ANTHROPIC_API_KEY:
    print(f"\n{'=' * 60}")
    print("3. ANTHROPIC — wrapped with TokenGauge")
    print("=" * 60)

    client = tw.wrap(anthropic.Anthropic(api_key=ANTHROPIC_API_KEY))
    response = client.messages.create(
        model="claude-sonnet-4-5-20250514",
        max_tokens=256,
        messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}],
    )
    print(f"\n  Model:  claude-sonnet-4-5")
    print(f"  Reply:  {response.content[0].text}")
    print(f"  Tokens: {response.usage.input_tokens} in / {response.usage.output_tokens} out")

# ── 4. Google Gemini ──────────────────────────────────────────────────────────
if GOOGLE_API_KEY:
    print(f"\n{'=' * 60}")
    print("4. GOOGLE GEMINI — wrapped with TokenGauge")
    print("=" * 60)

    client = tw.wrap(genai.Client(api_key=GOOGLE_API_KEY))
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Explain quantum computing in one sentence.",
    )
    print(f"\n  Model:  gemini-2.0-flash")
    print(f"  Reply:  {response.text}")

# ── 5. App Tags ───────────────────────────────────────────────────────────────
if OPENAI_API_KEY:
    print(f"\n{'=' * 60}")
    print("5. APP TAGS — label calls by feature")
    print("=" * 60)

    summarizer = tw.wrap(openai.OpenAI(api_key=OPENAI_API_KEY), app_tag="summarizer")
    chatbot    = tw.wrap(openai.OpenAI(api_key=OPENAI_API_KEY), app_tag="chatbot")

    r1 = summarizer.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Summarize: The quick brown fox jumps over the lazy dog."}],
    )
    print(f"\n  [summarizer] {r1.choices[0].message.content}")

    r2 = chatbot.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello! How are you today?"}],
    )
    print(f"  [chatbot]    {r2.choices[0].message.content}")

# ── 6. Bulk calls ─────────────────────────────────────────────────────────────
if OPENAI_API_KEY:
    print(f"\n{'=' * 60}")
    print("6. BULK — generating dashboard data")
    print("=" * 60)

    models_to_test = [
        ("gpt-4o-mini", openai.OpenAI(api_key=OPENAI_API_KEY)),
        ("gpt-4o",      openai.OpenAI(api_key=OPENAI_API_KEY)),
    ]
    tags = ["prod", "staging", "dev", "chatbot", "batch-jobs"]
    questions = [
        "What is machine learning?",
        "Write a haiku about Python.",
        "Explain REST APIs in one sentence.",
        "What is the difference between SQL and NoSQL?",
        "Give me a fun fact about space.",
    ]

    print()
    for i in range(10):
        model, base_client = random.choice(models_to_test)
        tag = random.choice(tags)
        question = random.choice(questions)

        wrapped = tw.wrap(base_client, app_tag=tag)
        resp = wrapped.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": question}],
            max_tokens=100,
        )
        cost_est = (resp.usage.prompt_tokens * 0.15 + resp.usage.completion_tokens * 0.6) / 1_000_000
        print(f"  [{i+1:>2}/10] {model:<14} tag={tag:<12} tokens={resp.usage.total_tokens:<6} ~${cost_est:.5f}")

# ── Done ──────────────────────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
print("DONE — check your dashboard: https://tokengauge.onrender.com")
print("=" * 60)
