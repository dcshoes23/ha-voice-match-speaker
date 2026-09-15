/* Route the native conversation picker settings button to the wrapped agent.
 * The picker has no public settings-target hook in Home Assistant 2026.9.
 * Keep this compatibility shim limited to Voice Match Speaker entities.
 */
const pickerClass = await customElements.whenDefined("ha-conversation-agent-picker");
const prototype = pickerClass.prototype;
const originalFetch = prototype._maybeFetchConfigEntry;
const installed = Symbol.for("voice_match_speaker.settings_installed");

if (typeof originalFetch !== "function") {
  console.warn("Voice Match Speaker: this frontend does not support the settings shortcut.");
} else if (!prototype[installed]) {
  prototype[installed] = true;
  const requests = new WeakMap();

  prototype._maybeFetchConfigEntry = async function () {
    const selected = this.value;
    const target = this.hass.states[selected]?.attributes.voice_match_target_agent;
    const request = {};
    requests.set(this, request);

    if (typeof target !== "string" || !target || !selected?.startsWith("conversation.")) {
      return originalFetch.call(this);
    }

    this._configEntry = undefined;
    this._subConfigEntry = undefined;
    const isCurrent = () => requests.get(this) === request && this.value === selected;

    try {
      // Verify ownership before changing the settings target.
      const wrapper = await this.hass.callWS({
        type: "config/entity_registry/get",
        entity_id: selected,
      });
      if (!isCurrent()) return;
      if (wrapper.platform !== "voice_match_speaker") {
        return originalFetch.call(this);
      }

      const targetRegistry = target.includes(".")
        ? await this.hass.callWS({
            type: "config/entity_registry/get",
            entity_id: target,
          })
        : { config_entry_id: target };
      if (!targetRegistry.config_entry_id || !isCurrent()) return;

      const [entry, subentries] = await Promise.all([
        this.hass.callWS({
          type: "config_entries/get_single",
          entry_id: targetRegistry.config_entry_id,
        }),
        targetRegistry.config_subentry_id
          ? this.hass.callWS({
              type: "config_entries/subentries/list",
              entry_id: targetRegistry.config_entry_id,
            })
          : [],
      ]);
      if (!isCurrent()) return;

      const subentry = subentries.find(
        (item) => item.subentry_id === targetRegistry.config_subentry_id
      );
      // Never send the user to a different subentry when the target was removed.
      if (targetRegistry.config_subentry_id && !subentry) return;

      this._subConfigEntry = subentry;
      this._configEntry = entry.config_entry;
      // The native picker renders its gear and opens the native options or
      // subentry dialog. Neither the selected agent nor any settings are changed.
    } catch (_error) {
      if (isCurrent()) {
        this._configEntry = undefined;
        this._subConfigEntry = undefined;
      }
    }
  };
}
