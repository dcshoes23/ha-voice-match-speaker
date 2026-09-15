# Voice Match Speaker for Home Assistant

This custom integration keeps [Wyoming Voice Match](https://github.com/jxlarrea/wyoming-voice-match) speaker tags out of Assist's command text while making the speaker available to sentence automations and the LLM conversation agent. It leaves Home Assistant's local intent and sentence matching in charge.

## Requirements

- An existing Wyoming Voice Match STT entity in Home Assistant.
- Voice Match configured with `TAG_SPEAKER=true` and at least one enrolled speaker.
- A conversation agent for requests that do not match local commands.

Tested on Home Assistant Core 2026.9.2.

## Install and configure

### HACS

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dcshoes23&repository=ha-voice-match-speaker&category=integration)

Install this integration as a [HACS custom repository](https://www.hacs.dev/docs/faq/custom_repositories/):

1. In Home Assistant, open **HACS**, select the three-dot menu in the upper-right corner, then **Custom repositories**.
2. Enter `https://github.com/dcshoes23/ha-voice-match-speaker`, select **Integration** as the type, and select **Add**.
3. Find **Voice Match Speaker** in HACS, open it, and select **Download**.
4. Restart Home Assistant.

### Manual installation

Copy `custom_components/voice_match_speaker` into your Home Assistant configuration's `custom_components` directory, then restart Home Assistant.

### Configure either installation

1. Under **Settings → Devices & services**, add **Voice Match Speaker**. Select the Wyoming STT entity connected to Voice Match and your existing conversation agent.
2. Under **Settings → Voice assistants**, select **Voice Match Speaker** for both speech-to-text and conversation agent. Enable **Prefer handling commands locally**.

The STT wrapper passes the audio iterator directly to the Wyoming entity, preserving its VAD and audio settings. It removes a leading `[speaker]` only after Voice Match returns a successful transcript. The conversation wrapper passes the exact clean sentence to the selected agent and adds a short speaker note to its extra system prompt. The selected agent must honor Home Assistant's `extra_system_prompt` for speaker context to reach the LLM.

### Conversation settings shortcut

The gear beside the Voice Match conversation agent opens the underlying agent's native settings dialog, including its prompt and tools. Changes are saved to that agent and also apply to other assistants using it. For providers such as Google Gemini, the shortcut resolves the exact conversation subentry.

After installing or updating, reload the Home Assistant page or fully reopen the companion app to load the frontend extension. The extension only changes settings lookup for Voice Match Speaker entities; it leaves the selected pipeline agent in place.

Home Assistant 2026.9 has no public hook for an alternate conversation settings target. The extension uses the native picker's `_maybeFetchConfigEntry` hook, verified against the installed 2026.9.2 frontend. A future frontend change may require an update; if the hook or target is unavailable, use the underlying integration's settings under **Devices & services**.

## Use the speaker in a sentence automation

Add a `voice_match_speaker.lookup` action first, passing the native sentence trigger's text. The action returns `speaker` as the enrolled Voice Match name, or `null` if no verified tag was present.

```yaml
triggers:
  - trigger: conversation
    command: "tell me my reminder"
actions:
  - action: voice_match_speaker.lookup
    data:
      sentence: "{{ trigger.sentence }}"
    response_variable: voice_match
  - set_conversation_response: >-
      {{ "Jane's reminder is ready." if voice_match.speaker == 'jane'
         else "I don't have a reminder for you." }}
```

Place speaker-dependent conditions after `lookup` in the action sequence. Native automation-level conditions run before actions, so they cannot use the response variable. The lookup is scoped to the current voice request and checks the exact clean sentence; it cannot read another satellite's speaker.

## Streaming behavior

Audio chunks flow to Wyoming as Home Assistant produces them; this integration never accumulates audio before delegating. Voice Match currently buffers audio itself to verify and extract the speaker, then returns one final transcript. Home Assistant's current STT result carries one final text value, so partial live transcript text is not available through this interface.

When the selected conversation agent supports streamed responses, the wrapper advertises that capability and forwards through Home Assistant's active chat log so TTS can receive response chunks. The wrapper does not buffer the agent's response.

## Development checks

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q custom_components tests
node --test tests/frontend_settings.test.cjs
```
