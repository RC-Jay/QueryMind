"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";

type Provider = "azure" | "claude";

interface LLMConfig {
  provider: Provider;
  model: string;
  endpoint: string | null;
  api_version: string | null;
  api_key_masked: string;
  updated_at: string | null;
}

const CLAUDE_MODELS = [
  "claude-sonnet-4-5",
  "claude-opus-4-1",
  "claude-3-5-haiku-latest",
];

const PROVIDER_LABEL: Record<Provider, string> = {
  azure: "Azure OpenAI",
  claude: "Claude (Anthropic)",
};

interface ActiveModel {
  provider: Provider;
  model: string;
}

export default function LLMSettings() {
  const [provider, setProvider] = useState<Provider>("azure");
  const [model, setModel] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [apiVersion, setApiVersion] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [maskedKey, setMaskedKey] = useState("");
  const [active, setActive] = useState<ActiveModel | null>(null); // saved state, not form
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  useEffect(() => {
    api.get("/api/admin/llm-config")
      .then(({ data }: { data: LLMConfig }) => {
        setProvider(data.provider);
        setModel(data.model);
        setEndpoint(data.endpoint || "");
        setApiVersion(data.api_version || "");
        setMaskedKey(data.api_key_masked);
        setActive({ provider: data.provider, model: data.model });
      })
      .catch(() => {}) // 503 when unconfigured — leave defaults
      .finally(() => setLoaded(true));
  }, []);

  async function handleSave() {
    setSaving(true);
    setMsg(null);
    try {
      const payload: Record<string, unknown> = { provider, model };
      if (provider === "azure") {
        payload.endpoint = endpoint;
        payload.api_version = apiVersion;
      }
      if (apiKey) payload.api_key = apiKey; // only send when changed
      const { data } = await api.put("/api/admin/llm-config", payload);
      setMaskedKey(data.api_key_masked);
      setApiKey("");
      setActive({ provider: data.provider, model: data.model });
      setMsg({ text: "Saved. New chats will use this model.", ok: true });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setMsg({ text: detail || "Save failed", ok: false });
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) return null;

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-xl font-bold text-slate-800 mb-1">AI Model</h1>
      <p className="text-sm text-slate-500 mb-4">
        Choose which language model powers the analytics agent. Changes apply to new conversations.
      </p>

      {/* Currently active model — reflects the SAVED config, not the form below */}
      <div className="mb-6 flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
        {active ? (
          <>
            <span className="h-2 w-2 rounded-full bg-green-500" />
            <span className="text-sm text-slate-600">Currently active:</span>
            <span className="text-sm font-semibold text-slate-800">
              {PROVIDER_LABEL[active.provider]} · {active.model}
            </span>
            {(active.provider !== provider || active.model !== model) && (
              <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                unsaved changes
              </span>
            )}
          </>
        ) : (
          <>
            <span className="h-2 w-2 rounded-full bg-slate-300" />
            <span className="text-sm text-slate-500">No model configured yet — set one up below.</span>
          </>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
        {/* Provider */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Provider</label>
          <div className="flex gap-2">
            {(["azure", "claude"] as Provider[]).map((p) => (
              <button
                key={p}
                onClick={() => setProvider(p)}
                className={`px-4 py-2 text-sm font-medium rounded-lg border transition-colors ${
                  provider === p
                    ? "bg-blue-50 border-blue-400 text-blue-700"
                    : "border-slate-200 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {p === "azure" ? "Azure OpenAI" : "Claude (Anthropic)"}
              </button>
            ))}
          </div>
        </div>

        {/* Model */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            {provider === "azure" ? "Deployment name" : "Model"}
          </label>
          {provider === "claude" ? (
            <input
              list="claude-models"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="claude-sonnet-4-5"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          ) : (
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="gpt-4o-mini"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          )}
          <datalist id="claude-models">
            {CLAUDE_MODELS.map((m) => <option key={m} value={m} />)}
          </datalist>
        </div>

        {/* Azure-only fields */}
        {provider === "azure" && (
          <>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Endpoint</label>
              <input
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder="https://my-resource.openai.azure.com/"
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">API version</label>
              <input
                value={apiVersion}
                onChange={(e) => setApiVersion(e.target.value)}
                placeholder="2025-01-01-preview"
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </>
        )}

        {/* API key */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">API key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={maskedKey ? `Current: ${maskedKey}` : "Enter API key"}
            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-slate-500 mt-1">
            Stored encrypted. Leave blank to keep the existing key.
          </p>
        </div>

        <div className="flex items-center gap-4 pt-1">
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-medium text-sm px-6 py-2.5 rounded-lg transition-colors"
          >
            {saving ? "Saving…" : "Save"}
          </button>
          {msg && (
            <p className={`text-sm ${msg.ok ? "text-green-600" : "text-red-600"}`}>{msg.text}</p>
          )}
        </div>
      </div>
    </div>
  );
}
