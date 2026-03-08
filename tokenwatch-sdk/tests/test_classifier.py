"""Tests for the heuristic prompt classifier and complexity scorer."""

from tokengauge._tracker import _classify_prompt, _score_complexity, _extract_text


# ── _extract_text ────────────────────────────────────────────────────────────

def test_extract_text_string():
    assert _extract_text("hello world") == "hello world"


def test_extract_text_openai_messages():
    msgs = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a function to sort a list."},
    ]
    text = _extract_text(msgs)
    assert "helpful assistant" in text
    assert "sort a list" in text


def test_extract_text_content_blocks():
    msgs = [
        {"role": "user", "content": [
            {"type": "text", "text": "Explain this code:"},
            {"type": "text", "text": "def foo(): pass"},
        ]},
    ]
    text = _extract_text(msgs)
    assert "Explain this code" in text
    assert "def foo()" in text


def test_extract_text_empty():
    assert _extract_text([]) == ""
    assert _extract_text("") == ""
    assert _extract_text(None) == "None"


# ── _classify_prompt ─────────────────────────────────────────────────────────

def test_classify_code_fence():
    msgs = [{"role": "user", "content": "Fix this:\n```python\ndef broken():\n```"}]
    assert _classify_prompt(msgs) == "code"


def test_classify_code_keywords():
    assert _classify_prompt([{"role": "user", "content": "Write a function to parse JSON"}]) == "code"
    assert _classify_prompt([{"role": "user", "content": "Debug this error in my Python script"}]) == "code"
    assert _classify_prompt([{"role": "user", "content": "Refactor the login module"}]) == "code"
    assert _classify_prompt([{"role": "user", "content": "Implement a binary search algorithm"}]) == "code"


def test_classify_translation():
    assert _classify_prompt([{"role": "user", "content": "Translate this to Spanish: Hello world"}]) == "translation"
    assert _classify_prompt([{"role": "user", "content": "Convert this text into French"}]) == "translation"


def test_classify_summarization():
    assert _classify_prompt([{"role": "user", "content": "Summarize the following article"}]) == "summarization"
    assert _classify_prompt([{"role": "user", "content": "Give me the key points of this report"}]) == "summarization"
    assert _classify_prompt([{"role": "user", "content": "TLDR of this document"}]) == "summarization"


def test_classify_extraction():
    assert _classify_prompt([{"role": "user", "content": "Extract all email addresses from this text"}]) == "extraction"
    assert _classify_prompt([{"role": "user", "content": "Parse the dates from this document"}]) == "extraction"
    assert _classify_prompt([{"role": "user", "content": "Convert to JSON format"}]) == "extraction"


def test_classify_analysis():
    assert _classify_prompt([{"role": "user", "content": "Analyze the performance of this query"}]) == "analysis"
    assert _classify_prompt([{"role": "user", "content": "Compare React and Vue"}]) == "analysis"
    assert _classify_prompt([{"role": "user", "content": "Evaluate the pros and cons of microservices"}]) == "analysis"


def test_classify_creative():
    assert _classify_prompt([{"role": "user", "content": "Write a story about a robot"}]) == "creative"
    assert _classify_prompt([{"role": "user", "content": "Brainstorm names for my startup"}]) == "creative"
    assert _classify_prompt([{"role": "user", "content": "Write a poem about the ocean"}]) == "creative"


def test_classify_chat_short():
    """Short generic messages should default to chat."""
    assert _classify_prompt([{"role": "user", "content": "Hello!"}]) == "chat"
    assert _classify_prompt([{"role": "user", "content": "What's the weather like?"}]) == "chat"
    assert _classify_prompt([{"role": "user", "content": "Thanks for your help"}]) == "chat"


def test_classify_other_long():
    """Long messages without keyword matches should be 'other'."""
    long_text = "Lorem ipsum dolor sit amet. " * 50
    assert _classify_prompt([{"role": "user", "content": long_text}]) == "other"


def test_classify_empty():
    assert _classify_prompt([{"role": "user", "content": ""}]) == "other"
    assert _classify_prompt([]) == "other"


def test_classify_string_input():
    """Google SDK sometimes passes raw strings."""
    assert _classify_prompt("Write a function in Python") == "code"
    assert _classify_prompt("Summarize this article") == "summarization"


# ── _score_complexity ────────────────────────────────────────────────────────

def test_complexity_simple_chat():
    msgs = [{"role": "user", "content": "Hi there"}]
    score = _score_complexity(msgs, "chat", tokens_in=10)
    assert 1 <= score <= 3


def test_complexity_code_with_fences():
    msgs = [{"role": "user", "content": "Fix this:\n```python\ndef a():\n    pass\n```\nAnd this:\n```python\ndef b():\n    pass\n```"}]
    score = _score_complexity(msgs, "code", tokens_in=200)
    assert score >= 4  # code bias + code fences


def test_complexity_high_tokens():
    msgs = [{"role": "user", "content": "Analyze this large codebase"}]
    score = _score_complexity(msgs, "analysis", tokens_in=5000)
    assert score >= 5  # high token count + analysis bias


def test_complexity_multi_turn():
    msgs = [{"role": "user", "content": f"Message {i}"} for i in range(15)]
    score = _score_complexity(msgs, "chat", tokens_in=800)
    assert score >= 4  # many messages + moderate tokens


def test_complexity_max_cap():
    """Score should never exceed 10."""
    msgs = [{"role": "user", "content": "```py\n" * 20}] * 20
    score = _score_complexity(msgs, "code", tokens_in=10000)
    assert score <= 10


def test_complexity_min():
    """Minimum score is 1."""
    msgs = [{"role": "user", "content": "hi"}]
    score = _score_complexity(msgs, "chat", tokens_in=5)
    assert score >= 1


# ── classify=False opt-out ───────────────────────────────────────────────────

def test_classify_disabled():
    """When classify=False, _log should pass None for prompt_type and complexity."""
    from tokengauge._tracker import TokenGauge
    tw = TokenGauge(token="test-token", classify=False)
    assert tw.classify is False

    tw2 = TokenGauge(token="test-token", classify=True)
    assert tw2.classify is True

    # Default is True
    tw3 = TokenGauge(token="test-token")
    assert tw3.classify is True
