# %% [markdown]
# # TokenGauge SDK Demo
#
# Zero-config AI usage tracking + model recommendations.
# Wrap your existing OpenAI, Anthropic, or Google Gemini client with one line —
# every call is automatically logged to your [TokenGauge dashboard](https://tokengauge.onrender.com).
#
# **Your API keys stay with you.** The SDK only reads token counts from API
# responses and sends them to TokenGauge. Nothing is proxied.

# %% [markdown]
# ## 1. Install

# %%
!pip install -q tokengauge openai anthropic google-genai python-dotenv

# %% [markdown]
# ## 2. Load API Keys from .env
#
# Create a `.env` file with your keys:
# ```
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=...
# TOKENGAUGE_TOKEN=...
# ```

# %%
import os
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TOKENGAUGE_TOKEN = os.getenv("TOKENGAUGE_TOKEN")

print(f"OpenAI key:     {'loaded' if OPENAI_API_KEY else 'missing'}")
print(f"Anthropic key:  {'loaded' if ANTHROPIC_API_KEY else 'missing'}")
print(f"Google key:     {'loaded' if GOOGLE_API_KEY else 'missing'}")
print(f"TokenGauge:     {'loaded' if TOKENGAUGE_TOKEN else 'missing'}")

# %% [markdown]
# ## 3. Connect to TokenGauge

# %%
from tokengauge import TokenGauge

# Option A: SDK token from .env
tw = TokenGauge(token=TOKENGAUGE_TOKEN)

# Option B: Login with email/password (uncomment to use)
# tw = TokenGauge.login(email="demo@tokengauge.dev", password="demodemo123")

print("Connected to TokenGauge!")

# %% [markdown]
# ## 4. Model Recommendations (no API key required)
#
# `recommend_model()` classifies your prompt locally, estimates cost, and scores
# every model by success probability — **no API call is made**.

# %%
# Simple chat prompt
rec = tw.recommend_model(
    messages=[{"role": "user", "content": "What is the capital of France?"}],
)
print(f"Prompt type:  {rec['prompt_type']}")
print(f"Complexity:   {rec['complexity']}/10")
print(f"Best model:   {rec['best_overall']['model']} ({rec['best_overall']['provider']})")
print(f"Est. cost:    ${rec['best_overall']['estimated_cost_usd']:.5f}")
print(f"Success prob: {rec['best_overall']['success_probability']:.0%}")

# %%
# Complex code prompt — watch the recommendation change
rec = tw.recommend_model(
    messages=[{"role": "user", "content": """
        Refactor this Python class to use dataclasses, add type hints,
        implement __eq__ and __hash__, add a factory classmethod that
        parses from JSON, and write comprehensive unit tests with pytest.
    """}],
    provider="anthropic",
    budget_usd=0.10,
)
print(f"Prompt type:       {rec['prompt_type']}")
print(f"Complexity:        {rec['complexity']}/10")
print(f"Best overall:      {rec['best_overall']['model']} (${rec['best_overall']['estimated_cost_usd']:.5f})")
print(f"Best Anthropic:    {rec['within_provider']['model']} (${rec['within_provider']['estimated_cost_usd']:.5f})")

# %%
# Compare recommendations across prompt types
prompts = {
    "chat":          "Hey, how's it going?",
    "code":          "Write a binary search tree in Rust with insert, delete, and balance operations",
    "summarization": "Summarize the following 10-page research paper on transformer architectures...",
    "analysis":      "Analyze the correlation between GDP growth and carbon emissions across G20 nations",
    "creative":      "Write a short story about a robot discovering music for the first time",
    "translation":   "Translate the following legal document from English to Mandarin Chinese",
}

print(f"{'Type':<16} {'Complexity':<12} {'Best Model':<24} {'Est. Cost':<12} {'Success'}")
print("-" * 80)
for ptype, prompt in prompts.items():
    r = tw.recommend_model(messages=[{"role": "user", "content": prompt}])
    best = r["best_overall"]
    print(f"{r['prompt_type']:<16} {r['complexity']:<12} {best['model']:<24} ${best['estimated_cost_usd']:<11.5f} {best['success_probability']:.0%}")

# %% [markdown]
# ## 5. Wrap an OpenAI Client
#
# Every call is tracked automatically on your dashboard.

# %%
import openai

client = tw.wrap(openai.OpenAI(api_key=OPENAI_API_KEY))

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}],
)
print(response.choices[0].message.content)
print(f"\nTokens: {response.usage.prompt_tokens} in / {response.usage.completion_tokens} out")

# %% [markdown]
# ## 6. Wrap an Anthropic Client

# %%
import anthropic

client = tw.wrap(anthropic.Anthropic(api_key=ANTHROPIC_API_KEY))

response = client.messages.create(
    model="claude-sonnet-4-5-20250514",
    max_tokens=256,
    messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}],
)
print(response.content[0].text)
print(f"\nTokens: {response.usage.input_tokens} in / {response.usage.output_tokens} out")

# %% [markdown]
# ## 7. Wrap a Google Gemini Client

# %%
from google import genai

client = tw.wrap(genai.Client(api_key=GOOGLE_API_KEY))

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="Explain quantum computing in one sentence.",
)
print(response.text)

# %% [markdown]
# ## 8. Tag Calls by Feature
#
# Use `app_tag` to label which part of your app made the call.
# Filter by tag on the dashboard.

# %%
summarizer = tw.wrap(openai.OpenAI(api_key=OPENAI_API_KEY), app_tag="summarizer")
chatbot    = tw.wrap(openai.OpenAI(api_key=OPENAI_API_KEY), app_tag="chatbot")

r1 = summarizer.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Summarize: The quick brown fox jumps over the lazy dog."}],
)
print(f"[summarizer] {r1.choices[0].message.content}")

r2 = chatbot.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello! How are you today?"}],
)
print(f"[chatbot] {r2.choices[0].message.content}")

# %% [markdown]
# ## 9. Bulk Demo — Generate Dashboard Data
#
# Run a batch of calls across providers and models to populate the dashboard
# with realistic data you can explore.

# %%
import random

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

print("Generating dashboard data...\n")
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

print("\nDone! Check your dashboard: https://tokengauge.onrender.com")

# %% [markdown]
# ## 10. View Your Dashboard
#
# Head to [tokengauge.onrender.com](https://tokengauge.onrender.com) to see:
# - **Live usage chart** (Robinhood-inspired) with 1D / 1W / 1M / 3M windows
# - **Cost breakdown** by provider, model, and app tag
# - **Token usage** trends over time
# - **API key filter** to isolate traffic by key
#
# All the calls you just made are already there.
