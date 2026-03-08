"""
pip install tokenwatch-sdk anthropic
"""
from tokenwatch import TokenWatch
import anthropic

tw = TokenWatch(
    token="paste-your-tokenwatch-token-here",
    base_url="https://your-server.com",   # or http://localhost:8000 for local dev
)

client = tw.wrap(anthropic.Anthropic(api_key="sk-ant-..."))

response = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=256,
    messages=[{"role": "user", "content": "Explain quantum computing in one paragraph."}],
)

print(response.content[0].text)
# Token usage is now logged to your TokenWatch dashboard
