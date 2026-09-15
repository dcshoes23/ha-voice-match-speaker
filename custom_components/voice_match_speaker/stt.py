"""Streaming STT wrapper for Wyoming Voice Match."""

from collections.abc import AsyncIterable

from homeassistant.components import stt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SOURCE_STT
from .speaker import parse_tagged_transcript, set_request


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add one wrapper STT entity."""
    async_add_entities([VoiceMatchSpeakerStt(entry)])


class VoiceMatchSpeakerStt(stt.SpeechToTextEntity):
    """Pass audio through immediately; clean only the final transcript."""

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._source_id: str = entry.data[CONF_SOURCE_STT]
        self._attr_name = f"Voice Match Speaker ({self._source_id})"
        self._attr_unique_id = f"{entry.entry_id}-stt"

    @property
    def _source(self) -> stt.SpeechToTextEntity | None:
        return stt.async_get_speech_to_text_entity(self.hass, self._source_id)

    @property
    def available(self) -> bool:
        source = self._source
        return source is not None and source.available

    @property
    def supported_languages(self) -> list[str]:
        return source.supported_languages if (source := self._source) else []

    @property
    def supported_formats(self) -> list[stt.AudioFormats]:
        return source.supported_formats if (source := self._source) else []

    @property
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        return source.supported_codecs if (source := self._source) else []

    @property
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        return source.supported_bit_rates if (source := self._source) else []

    @property
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        return source.supported_sample_rates if (source := self._source) else []

    @property
    def supported_channels(self) -> list[stt.AudioChannels]:
        return source.supported_channels if (source := self._source) else []

    @property
    def audio_processing(self) -> stt.SpeechAudioProcessing:
        return (
            source.audio_processing
            if (source := self._source)
            else stt.DEFAULT_AUDIO_PROCESSING
        )

    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Delegate the original iterator, then remove an optional speaker tag."""
        set_request(None, None)
        source = self._source
        if source is None:
            raise HomeAssistantError(f"STT source {self._source_id} is unavailable")
        result = await source.async_process_audio_stream(metadata, stream)
        if result.result != stt.SpeechResultState.SUCCESS or not result.text:
            return result
        speaker, sentence = parse_tagged_transcript(result.text)
        set_request(speaker, sentence)
        return stt.SpeechResult(sentence, result.result)
