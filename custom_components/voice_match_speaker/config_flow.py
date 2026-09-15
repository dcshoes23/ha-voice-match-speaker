"""Set up Voice Match Speaker through the Home Assistant UI."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import conversation, stt
from homeassistant.components.conversation.agent_manager import get_agent_manager

from .const import CONF_SOURCE_STT, CONF_TARGET_AGENT, DOMAIN


class VoiceMatchSpeakerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a Wyoming Voice Match source and downstream agent."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Select existing source and target entities."""
        sources: dict[str, str] = {}
        for entity_id in self.hass.states.async_entity_ids("stt"):
            entity = stt.async_get_speech_to_text_entity(self.hass, entity_id)
            if (
                entity
                and entity.platform
                and entity.platform.platform_name == "wyoming"
            ):
                sources[entity_id] = entity.name or entity_id

        agents: dict[str, str] = {}
        for entity_id in self.hass.states.async_entity_ids("conversation"):
            if entity_id == conversation.HOME_ASSISTANT_AGENT:
                continue
            entity = conversation.async_get_agent(self.hass, entity_id)
            if entity and entity.platform and entity.platform.platform_name != DOMAIN:
                agents[entity_id] = entity.name or entity_id
        for info in get_agent_manager(self.hass).async_get_agent_info():
            if info.id != conversation.HOME_ASSISTANT_AGENT:
                agents[info.id] = info.name

        errors: dict[str, str] = {}
        if user_input is not None:
            source = user_input[CONF_SOURCE_STT]
            target = user_input[CONF_TARGET_AGENT]
            if source not in sources:
                errors[CONF_SOURCE_STT] = "invalid_source"
            if target not in agents:
                errors[CONF_TARGET_AGENT] = "invalid_agent"
            if not errors:
                await self.async_set_unique_id(f"{source}|{target}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Voice Match Speaker ({source})",
                    data={CONF_SOURCE_STT: source, CONF_TARGET_AGENT: target},
                )

        if not sources:
            return self.async_abort(reason="no_wyoming_stt")
        if not agents:
            return self.async_abort(reason="no_conversation_agent")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCE_STT): vol.In(sources),
                    vol.Required(CONF_TARGET_AGENT): vol.In(agents),
                }
            ),
            errors=errors,
        )
