"""Conversation wrapper that passes verified speaker context to an agent."""

import json

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_TARGET_AGENT
from .speaker import speaker_for_sentence


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add one wrapper conversation entity."""
    async_add_entities([VoiceMatchSpeakerConversation(entry)])


class VoiceMatchSpeakerConversation(conversation.ConversationEntity):
    """Preserve the active chat log while forwarding to the chosen agent."""

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._target_id: str = entry.data[CONF_TARGET_AGENT]
        self._attr_name = f"Voice Match Speaker ({self._target_id})"
        self._attr_unique_id = f"{entry.entry_id}-conversation"
        self._attr_extra_state_attributes = {
            "voice_match_target_agent": self._target_id,
        }

    async def async_added_to_hass(self) -> None:
        """Refresh availability and features when the target agent starts."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._target_id], self._async_target_state_changed
            )
        )

    @callback
    def _async_target_state_changed(self, _event) -> None:
        """Keep the wrapper state in sync with its target agent."""
        self.async_write_ha_state()

    @property
    def _target(self):
        target = conversation.async_get_agent(self.hass, self._target_id)
        if isinstance(target, VoiceMatchSpeakerConversation):
            return None
        return target

    @property
    def available(self) -> bool:
        target = self._target
        return target is not None and (
            not isinstance(target, conversation.ConversationEntity) or target.available
        )

    @property
    def supported_languages(self):
        return target.supported_languages if (target := self._target) else []

    @property
    def supports_streaming(self) -> bool:
        target = self._target
        return (
            isinstance(target, conversation.ConversationEntity)
            and target.supports_streaming
        )

    @property
    def supported_features(self):
        target = self._target
        return (
            target.supported_features
            if isinstance(target, conversation.ConversationEntity)
            else conversation.ConversationEntityFeature(0)
        )

    async def async_prepare(self, language: str | None = None) -> None:
        if self._target is not None and language is not None:
            await conversation.async_prepare_agent(self.hass, self._target_id, language)

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Forward without replacing Home Assistant's active streaming chat log."""
        if self._target is None:
            raise HomeAssistantError(
                f"Conversation agent {self._target_id} is unavailable"
            )

        prompt = user_input.extra_system_prompt
        if speaker := speaker_for_sentence(user_input.text):
            speaker_line = (
                "The Voice Match speaker ID for this voice request is "
                f"{json.dumps(speaker)}. If asked who is speaking or "
                "'who am I?', answer with this speaker ID. "
                "Use it for personalization, not authentication."
            )
            prompt = f"{prompt}\n{speaker_line}" if prompt else speaker_line

        return await conversation.async_converse(
            self.hass,
            text=user_input.text,
            conversation_id=user_input.conversation_id,
            context=user_input.context,
            language=user_input.language,
            agent_id=self._target_id,
            device_id=user_input.device_id,
            satellite_id=user_input.satellite_id,
            extra_system_prompt=prompt,
        )
