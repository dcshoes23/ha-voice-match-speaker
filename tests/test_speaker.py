"""Tests for transcript parsing and request isolation without a HA runtime."""

import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "voice_match_speaker"
    / "speaker.py"
)
spec = importlib.util.spec_from_file_location("voice_match_speaker_speaker", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class SpeakerTests(unittest.TestCase):
    def test_tagged_transcript(self):
        self.assertEqual(
            module.parse_tagged_transcript("[jane] Turn on the kitchen lights"),
            ("jane", "Turn on the kitchen lights"),
        )

    def test_untagged_or_malformed_transcript_is_unchanged(self):
        for transcript in ("Turn on the lights", "[jane]", "[jane]\nTurn on"):
            self.assertEqual(
                module.parse_tagged_transcript(transcript), (None, transcript)
            )

    def test_exact_sentence_lookup(self):
        module.set_request("jane", "Turn on the lights")
        self.assertEqual(module.speaker_for_sentence("Turn on the lights"), "jane")
        self.assertIsNone(module.speaker_for_sentence("Turn off the lights"))
        module.set_request(None, None)
        self.assertIsNone(module.speaker_for_sentence("Turn on the lights"))

    def test_concurrent_requests_do_not_mix(self):
        async def voice(speaker):
            module.set_request(speaker, "same sentence")
            await asyncio.sleep(0)
            child = asyncio.create_task(asyncio.sleep(0, result=module.speaker_for_sentence("same sentence")))
            return await child

        async def run():
            return await asyncio.gather(voice("jane"), voice("john"))

        self.assertEqual(asyncio.run(run()), ["jane", "john"])


if __name__ == "__main__":
    unittest.main()
