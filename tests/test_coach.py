"""Coach tests with a fake Claude client (no network, no API key)."""

from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from achieve_coach.coach import SYSTEM_PROMPT, Coach, friendly_error


class FakeStream:
    def __init__(self, chunks, stop_reason="end_turn", error=None):
        self.chunks, self.stop_reason, self.error = chunks, stop_reason, error

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        for c in self.chunks:
            yield c
        if self.error:
            raise self.error

    def get_final_message(self):
        content = [SimpleNamespace(type="text", text="".join(self.chunks))]
        return SimpleNamespace(content=content, stop_reason=self.stop_reason)


class FakeClient:
    def __init__(self, *streams):
        self.streams = list(streams)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        # Snapshot messages: the coach mutates its history list after the call.
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.streams.pop(0)


def test_new_question_sends_image_and_coaching_prompt():
    client = FakeClient(FakeStream(["**What it's ", "asking:** ..."]))
    coach = Coach(client=client)

    out = "".join(coach.new_question(b"\x89PNG fake"))

    assert out == "**What it's asking:** ..."
    call = client.calls[0]
    assert call["system"] == SYSTEM_PROMPT
    assert call["model"] == "claude-opus-5-5"
    assert call["fallbacks"] == "default"
    first = call["messages"][0]["content"]
    assert first[0]["type"] == "image"
    assert first[0]["source"]["media_type"] == "image/png"
    assert [m["role"] for m in coach.history] == ["user", "assistant"]


def test_followups_extend_the_same_conversation():
    client = FakeClient(FakeStream(["hint"]), FakeStream(["good reasoning"]))
    coach = Coach(client=client)
    "".join(coach.new_question(b"png"))

    out = "".join(coach.check_thinking("B, because paragraph 3 says so"))

    assert out == "good reasoning"
    assert len(client.calls[1]["messages"]) == 3
    assert "paragraph 3" in client.calls[1]["messages"][2]["content"]
    assert [m["role"] for m in coach.history] == ["user", "assistant"] * 2


def test_new_question_resets_history():
    client = FakeClient(FakeStream(["a"]), FakeStream(["b"]), FakeStream(["c"]))
    coach = Coach(client=client)
    "".join(coach.new_question(b"png"))
    "".join(coach.ask("what does 'arid' mean?"))
    "".join(coach.new_question(b"png2"))
    assert len(coach.history) == 2


def test_refusal_is_reported_and_not_kept_in_history():
    client = FakeClient(FakeStream([], stop_reason="refusal"))
    coach = Coach(client=client)
    out = "".join(coach.new_question(b"png"))
    assert "couldn't help" in out
    assert coach.history == []


def test_error_mid_stream_leaves_history_retryable():
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    err = anthropic.APIConnectionError(request=request)
    client = FakeClient(FakeStream(["hint"]), FakeStream(["par"], error=err))
    coach = Coach(client=client)
    "".join(coach.new_question(b"png"))

    with pytest.raises(anthropic.APIConnectionError):
        "".join(coach.ask("why?"))

    assert [m["role"] for m in coach.history] == ["user", "assistant"]
    assert "internet" in friendly_error(err)


def test_system_prompt_forbids_giving_answers():
    assert "never give the answer" in SYSTEM_PROMPT.lower()
    assert "never say which answer choice is correct" in SYSTEM_PROMPT.lower()
