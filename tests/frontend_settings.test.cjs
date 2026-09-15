const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { test } = require("node:test");
const vm = require("node:vm");
const script = readFileSync(
  `${__dirname}/../custom_components/voice_match_speaker/frontend/voice-match-settings.js`,
  "utf8"
);

async function fixture({ target = "conversation.google", subentry = true } = {}) {
  class Picker {
    async _maybeFetchConfigEntry() {
      this.nativeCalls = (this.nativeCalls || 0) + 1;
      this._configEntry = { entry_id: "native" };
    }
  }
  await vm.runInNewContext(`(async () => { ${script} })()`, {
    customElements: { whenDefined: async () => Picker }, console,
  });
  const picker = new Picker();
  picker.value = "conversation.wrapper";
  const calls = [];
  picker.hass = {
    states: { "conversation.wrapper": { attributes: { voice_match_target_agent: target } } },
    callWS: async (message) => {
      calls.push(message);
      switch (message.type) {
        case "config/entity_registry/get":
          return message.entity_id === "conversation.wrapper"
            ? { platform: "voice_match_speaker", config_entry_id: "wrapper" }
            : { config_entry_id: "google", config_subentry_id: subentry ? "chat" : null };
        case "config_entries/get_single":
          return { config_entry: {
            entry_id: "google", supports_options: !subentry,
            supported_subentry_types: { conversation: { supports_reconfigure: true } },
          } };
        case "config_entries/subentries/list":
          return [
            { subentry_id: "other", subentry_type: "conversation" },
            { subentry_id: "chat", subentry_type: "conversation" },
          ];
        default: throw new Error(message.type);
      }
    },
  };
  return { picker, calls };
}

test("routes the native gear to the exact Google conversation subentry", async () => {
  const { picker, calls } = await fixture();
  await picker._maybeFetchConfigEntry();
  assert.equal(picker._configEntry.entry_id, "google");
  assert.equal(picker._subConfigEntry.subentry_id, "chat");
  assert.equal(picker._configEntry.supported_subentry_types.conversation.supports_reconfigure, true);
  assert.equal(picker.value, "conversation.wrapper");
  assert.equal(picker.nativeCalls, undefined);
  assert.ok(calls.every((call) => /get|list/.test(call.type)));
});

test("supports agents with an ordinary options flow or legacy entry ID", async () => {
  for (const target of ["conversation.google", "google"]) {
    const { picker } = await fixture({ target, subentry: false });
    await picker._maybeFetchConfigEntry();
    assert.equal(picker._configEntry.supports_options, true);
    assert.equal(picker._subConfigEntry, undefined);
  }
});

test("leaves normal conversation agents on the native path", async () => {
  const { picker, calls } = await fixture();
  picker.value = "conversation.google";
  await picker._maybeFetchConfigEntry();
  assert.equal(picker.nativeCalls, 1);
  assert.equal(calls.length, 0);
});

test("does not redirect an entity owned by another integration", async () => {
  const { picker } = await fixture();
  picker.hass.callWS = async () => ({ platform: "other" });
  await picker._maybeFetchConfigEntry();
  assert.equal(picker.nativeCalls, 1);
});

test("hides the shortcut when the target cannot be resolved", async () => {
  const { picker } = await fixture();
  picker.hass.callWS = async () => { throw new Error("missing target"); };
  await picker._maybeFetchConfigEntry();
  assert.equal(picker._configEntry, undefined);
  assert.equal(picker._subConfigEntry, undefined);
});

test("never substitutes a different conversation subentry", async () => {
  const { picker } = await fixture();
  const callWS = picker.hass.callWS;
  picker.hass.callWS = (message) => message.type === "config_entries/subentries/list"
    ? Promise.resolve([{ subentry_id: "other", subentry_type: "conversation" }])
    : callWS(message);
  await picker._maybeFetchConfigEntry();
  assert.equal(picker._configEntry, undefined);
});

test("a slow wrapper lookup cannot overwrite a newly selected agent", async () => {
  const { picker } = await fixture();
  let release;
  picker.hass.callWS = () => new Promise((resolve) => { release = resolve; });
  const pending = picker._maybeFetchConfigEntry();
  picker.value = "conversation.google";
  await picker._maybeFetchConfigEntry();
  release({ platform: "voice_match_speaker" });
  await pending;
  assert.equal(picker._configEntry.entry_id, "native");
});
