"""
pip install tokenwatch-sdk openai
"""
from tokenwatch import TokenWatch
import openai

tw = TokenWatch(
    token="paste-your-tokenwatch-token-here",
    base_url="https://your-server.com",   # or http://localhost:8000 for local dev
)

client = tw.wrap(openai.OpenAI(api_key="sk-..."))

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Explain quantum computing in one paragraph."}],
)

print(response.choices[0].message.content)
# Token usage is now logged to your TokenWatch dashboard
