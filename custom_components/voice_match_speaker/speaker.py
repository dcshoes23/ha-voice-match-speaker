"""Per-request speaker state and Voice Match transcript parsing.

The Assist pipeline awaits STT and intent processing in the same asyncio task.
Sentence automations started by that task inherit its context variables. Keeping
this state in a ContextVar avoids mixing simultaneous satellite requests.
"""

from contextvars import ContextVar
from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class SpeakerRequest:
    """Speaker and the clean sentence associated with one voice request."""

    speaker: str
    sentence: str


_CURRENT_REQUEST: ContextVar[SpeakerRequest | None] = ContextVar(
    "voice_match_speaker_request", default=None
)
_TAG = re.compile(r"^\[([^\[\]\r\n]{1,64})\][ \t]+(.+)$", re.DOTALL)


def parse_tagged_transcript(text: str) -> tuple[str | None, str]:
    """Remove only a complete leading Voice Match tag."""
    match = _TAG.match(text)
    if not match:
        return None, text
    speaker = match.group(1).strip()
    sentence = match.group(2).strip()
    if not speaker or not sentence:
        return None, text
    return speaker, sentence


def set_request(speaker: str | None, sentence: str | None) -> None:
    """Set or clear request identity in the current asyncio context."""
    _CURRENT_REQUEST.set(
        SpeakerRequest(speaker, sentence) if speaker and sentence else None
    )


def speaker_for_sentence(sentence: str) -> str | None:
    """Return the speaker only for this exact clean transcript."""
    request = _CURRENT_REQUEST.get()
    return request.speaker if request and request.sentence == sentence else None
