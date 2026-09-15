"""Voice Match speaker integration."""

from pathlib import Path

import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import ATTR_SENTENCE, DOMAIN, SERVICE_LOOKUP
from .speaker import speaker_for_sentence

PLATFORMS = ["stt", "conversation"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the response-returning sentence lookup action."""
    settings_url = "/voice_match_speaker/voice-match-settings.js"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                settings_url,
                str(Path(__file__).parent / "frontend" / "voice-match-settings.js"),
                True,
            )
        ]
    )
    frontend.add_extra_js_url(hass, f"{settings_url}?v=0.2.2")

    async def lookup(call: ServiceCall) -> dict[str, str | None]:
        return {"speaker": speaker_for_sentence(call.data[ATTR_SENTENCE])}

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOOKUP,
        lookup,
        schema=vol.Schema({vol.Required(ATTR_SENTENCE): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the STT and conversation wrapper entities."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload wrapper entities."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
