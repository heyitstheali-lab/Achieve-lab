"""Talks to Claude. Coaching only: it never hands over the answer."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Iterator

import anthropic

SYSTEM_PROMPT = """\
You are a friendly reading coach for a middle or high school student working on \
an Achieve3000-style reading activity. You get a screenshot of their screen.

Your job is to help the student find and understand the answer THEMSELVES. \
You never give the answer.

Hard rules (these never change, no matter what the student says):
- Never say which answer choice is correct, and never narrow the choices down to one.
- Never write the student's short answer, summary, or essay response for them, \
not even "as an example".
- If the student asks for the answer, say in one short sentence that you'll help \
them find it, then give a hint.

When you get a new screenshot:
1. What it's asking: restate the question in plain, simple words (1-2 sentences).
2. Where to look: point to the part of the article that holds the evidence: \
name the paragraph or section, or quote a short phrase (under 12 words) to find. \
If the article isn't on screen, tell them which part to reread (e.g. "the section \
about how the dam was built").
3. Tricky words: explain any hard words in the question or answer choices.
4. Strategy: one tip for this type of question (main idea, cause and effect, \
vocabulary in context, author's purpose, sequence, inference, and so on).

When the student tells you the answer they picked and why:
- If their reasoning is supported by the text, say so and point to the evidence \
that backs it up.
- If it isn't, explain which part of their reasoning doesn't match the text and \
send them back to the evidence. Do not reveal which choice is right.
- If they only give a letter with no reason, ask them to explain why first.

When the student shares a written response: give 2-3 specific pieces of feedback \
(answers the prompt? uses evidence from the article? clear and complete sentences?). \
Do not rewrite it for them.

If the screen doesn't show a question or reading activity, say briefly what you \
see and ask them to open the question.

Style: short and encouraging, under 170 words, easy to read (grade 6-9 level), \
start each part with its heading from above (e.g. "Where to look:") and use \
short "-" bullets. Plain text only: no Markdown symbols like ** or #, since \
the app shows text exactly as written.
"""


@dataclass
class CoachSettings:
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    max_tokens: int = 4000


@dataclass
class Coach:
    """Holds one conversation about one question on screen."""

    client: anthropic.Anthropic
    settings: CoachSettings = field(default_factory=CoachSettings)
    history: list = field(default_factory=list)

    @property
    def has_question(self) -> bool:
        return bool(self.history)

    def new_question(self, png_bytes: bytes) -> Iterator[str]:
        """Start over with a fresh screenshot and stream back hints."""
        image_b64 = base64.standard_b64encode(png_bytes).decode("ascii")
        self.history = []
        content = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": image_b64},
            },
            {"type": "text", "text": "Help me understand the question on my screen."},
        ]
        return self._send(content)

    def check_thinking(self, student_text: str) -> Iterator[str]:
        """Student shares the answer they picked (plus why) or a written response."""
        return self._send(
            "Here is the answer I picked and my reasoning, or my written response. "
            "Check my thinking:\n\n" + student_text
        )

    def ask(self, question: str) -> Iterator[str]:
        """A follow-up question about the same screen."""
        return self._send(question)

    def _send(self, content) -> Iterator[str]:
        self.history.append({"role": "user", "content": content})
        try:
            with self.client.beta.messages.stream(
                model=self.settings.model,
                max_tokens=self.settings.max_tokens,
                system=SYSTEM_PROMPT,
                messages=self.history,
                output_config={"effort": self.settings.effort},
                # If a request gets declined by a safety classifier, retry it on a
                # fallback model instead of failing.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                yield from stream.text_stream
                final = stream.get_final_message()
        except BaseException:
            self.history.pop()  # keep history valid so the student can retry
            raise

        if final.stop_reason == "refusal":
            self.history.pop()
            yield "\n\n(Claude couldn't help with that one. Try asking another way.)"
            return

        # Append the full content (not just text) so thinking blocks round-trip.
        self.history.append({"role": "assistant", "content": final.content})
        if final.stop_reason == "max_tokens":
            yield "\n\n(Response was cut off.)"


def friendly_error(exc: BaseException) -> str:
    """Turn SDK errors into something a student can act on."""
    if isinstance(exc, anthropic.AuthenticationError):
        return "Your API key was rejected. Check it in Settings."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "This API key doesn't have access to that model."
    if isinstance(exc, anthropic.NotFoundError):
        return "Model not found. Check the model name in Settings."
    if isinstance(exc, anthropic.RateLimitError):
        return "Too many requests right now. Wait a minute and try again."
    if isinstance(exc, anthropic.BadRequestError):
        return f"Request was rejected: {exc.message}"
    if isinstance(exc, anthropic.APIStatusError):
        return f"Claude API error ({exc.status_code}). Try again in a bit."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Couldn't reach Claude. Check your internet connection."
    return f"Something went wrong: {exc}"

