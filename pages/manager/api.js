import { createLocalBridge } from "./mock_bridge.js";
import { unwrap } from "./utils.js";

export function getBridge() {
  return window.AstrBotPluginPage || createLocalBridge();
}

export function createApi(bridge) {
  return {
    async overview() {
      return unwrap(await bridge.apiGet("overview"));
    },
    async setSubscriptionEnabled(payload) {
      return unwrap(await bridge.apiPost("subscriptions/enabled", payload));
    },
    async deleteSubscription(payload) {
      return unwrap(await bridge.apiPost("subscriptions/delete", payload));
    },
    async clearPending() {
      return unwrap(await bridge.apiPost("pending/clear", {}));
    },
    async manualLiveCheck(targetId) {
      return unwrap(await bridge.apiPost("checks/live", { target_id: targetId }));
    },
    async listTemplates() {
      return unwrap(await bridge.apiGet("templates/list"));
    },
    async previewTemplate(name) {
      return unwrap(await bridge.apiGet("templates/preview", { name }));
    },
    async generateTemplates(seed) {
      return unwrap(await bridge.apiPost("templates/generate", { seed }));
    },
  };
}
