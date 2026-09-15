"""Focused wrapper tests with minimal Home Assistant interface doubles."""

import asyncio
import importlib
from pathlib import Path
import sys
import types
import unittest


INTEGRATION_DIR = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "voice_match_speaker"
)


def install_module(name: str, **attributes):
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    sys.modules[name] = module
    return module


class SpeechToTextEntity:
    pass


class ConversationEntity:
    async def async_added_to_hass(self):
        pass

    def async_on_remove(self, unsubscribe):
        self.unsubscribe = unsubscribe

    def async_write_ha_state(self):
        self.state_writes = getattr(self, "state_writes", 0) + 1


class SpeechResult:
    def __init__(self, text, result):
        self.text = text
        self.result = result


class Entry:
    entry_id = "test-entry"
    data = {"source_stt": "stt.voice_match", "target_agent": "conversation.llm"}


class WrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package = install_module("wrapper_test_package")
        package.__path__ = [str(INTEGRATION_DIR)]
        install_module("homeassistant")
        components = install_module("homeassistant.components")
        components.__path__ = []
        cls.stt_api = install_module(
            "homeassistant.components.stt",
            SpeechToTextEntity=SpeechToTextEntity,
            SpeechResult=SpeechResult,
            SpeechResultState=types.SimpleNamespace(SUCCESS="success"),
            SpeechMetadata=object,
            AudioFormats=object,
            AudioCodecs=object,
            AudioBitRates=object,
            AudioSampleRates=object,
            AudioChannels=object,
            SpeechAudioProcessing=object,
            DEFAULT_AUDIO_PROCESSING=object(),
        )
        cls.conversation_api = install_module(
            "homeassistant.components.conversation",
            ConversationEntity=ConversationEntity,
            ConversationInput=object,
            ConversationResult=object,
            ConversationEntityFeature=int,
        )
        install_module("homeassistant.config_entries", ConfigEntry=Entry)
        install_module("homeassistant.core", HomeAssistant=object, callback=lambda fn: fn)
        install_module("homeassistant.exceptions", HomeAssistantError=Exception)
        helpers = install_module("homeassistant.helpers")
        helpers.__path__ = []
        cls.state_change_listeners = []
        install_module(
            "homeassistant.helpers.event",
            async_track_state_change_event=lambda hass, ids, fn: (
                cls.state_change_listeners.append((ids, fn)) or (lambda: None)
            ),
        )
        install_module(
            "homeassistant.helpers.entity_platform",
            AddConfigEntryEntitiesCallback=object,
        )
        cls.speaker = importlib.import_module("wrapper_test_package.speaker")
        cls.stt_module = importlib.import_module("wrapper_test_package.stt")
        cls.conversation_module = importlib.import_module(
            "wrapper_test_package.conversation"
        )

    def test_audio_iterator_is_delegated_without_buffering(self):
        release_second_chunk = asyncio.Event()
        chunks = []

        async def audio():
            yield b"one"
            await release_second_chunk.wait()
            yield b"two"

        original_stream = audio()
        processing_settings = object()

        class Source:
            audio_processing = processing_settings

            async def async_process_audio_stream(self, metadata, stream):
                self_outer.assertIs(stream, original_stream)
                async for chunk in stream:
                    chunks.append(chunk)
                    if chunk == b"one":
                        release_second_chunk.set()
                return SpeechResult("[jane] Turn on the lights", "success")

        self_outer = self
        source = Source()
        self.stt_api.async_get_speech_to_text_entity = lambda hass, entity_id: source
        wrapper = self.stt_module.VoiceMatchSpeakerStt(Entry())
        wrapper.hass = object()
        self.assertIs(wrapper.audio_processing, processing_settings)

        async def run_request():
            async with asyncio.timeout(1):
                result = await wrapper.async_process_audio_stream(
                    object(), original_stream
                )
            return result, self.speaker.speaker_for_sentence(result.text)

        result, speaker = asyncio.run(run_request())
        self.assertEqual(chunks, [b"one", b"two"])
        self.assertEqual(result.text, "Turn on the lights")
        self.assertEqual(speaker, "jane")

    def test_conversation_wrapper_mirrors_streaming_and_forwards_prompt(self):
        class Target(ConversationEntity):
            available = True
            supported_languages = ["en"]
            supports_streaming = True
            supported_features = 1

        target = Target()
        calls = []
        deltas = []
        finish_response = asyncio.Event()

        async def converse(*args, **kwargs):
            calls.append(kwargs)
            deltas.append("first response chunk")
            await finish_response.wait()
            return "response"

        self.conversation_api.async_get_agent = lambda hass, agent_id: target
        self.conversation_api.async_converse = converse
        wrapper = self.conversation_module.VoiceMatchSpeakerConversation(Entry())
        wrapper.hass = object()
        self.speaker.set_request("jane", "Turn on the lights")
        user_input = types.SimpleNamespace(
            text="Turn on the lights",
            extra_system_prompt="Existing instruction.",
            conversation_id="conversation-1",
            context=object(),
            language="en",
            device_id="device-1",
            satellite_id="satellite-1",
        )

        self.assertTrue(wrapper.supports_streaming)
        self.assertEqual(wrapper.supported_features, 1)

        async def run_request():
            task = asyncio.create_task(wrapper.async_process(user_input))
            await asyncio.sleep(0)
            self.assertEqual(deltas, ["first response chunk"])
            self.assertFalse(task.done())
            finish_response.set()
            return await task

        self.assertEqual(asyncio.run(run_request()), "response")
        self.assertEqual(calls[0]["text"], "Turn on the lights")
        self.assertIn('"jane"', calls[0]["extra_system_prompt"])
        self.assertIn("'who am I?'", calls[0]["extra_system_prompt"])
        self.assertIn("Existing instruction.", calls[0]["extra_system_prompt"])
        self.assertEqual(calls[0]["conversation_id"], "conversation-1")

    def test_conversation_wrapper_refreshes_when_target_starts(self):
        target = None
        self.conversation_api.async_get_agent = lambda hass, agent_id: target
        wrapper = self.conversation_module.VoiceMatchSpeakerConversation(Entry())
        wrapper.hass = object()
        self.assertFalse(wrapper.available)
        asyncio.run(wrapper.async_added_to_hass())
        self.assertEqual(self.state_change_listeners[-1][0], ["conversation.llm"])

        class Target(ConversationEntity):
            available = True
            supported_languages = ["en"]
            supports_streaming = True
            supported_features = 1

        target = Target()
        self.state_change_listeners[-1][1](object())
        self.assertTrue(wrapper.available)
        self.assertEqual(wrapper.state_writes, 1)
        self.assertEqual(wrapper.supported_features, 1)


if __name__ == "__main__":
    unittest.main()
