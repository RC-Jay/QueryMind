"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { CheckCircle, XCircle, Loader } from "lucide-react";

type Tab = "connection" | "context" | "kpis" | "questions" | "tables";

interface KPIDef { name: string; sql: string; format: string; icon: string; }
interface TableDesc { table: string; description: string; }
interface BusinessRule { rule: string; }

interface Config {
  business_name: string;
  business_description: string;
  db_url_masked: string;
  domain_context: string;
  business_rules: BusinessRule[];
  table_descriptions: Record<string, string>;
  kpi_definitions: KPIDef[];
  starter_questions: string[];
  explain_cost_threshold: number;
}

export default function BusinessSetup() {
  const [activeTab, setActiveTab] = useState<Tab>("connection");
  const [config, setConfig] = useState<Partial<Config>>({});
  const [dbUrl, setDbUrl] = useState("");
  const [testStatus, setTestStatus] = useState<"idle" | "testing" | "ok" | "fail">("idle");
  const [testMsg, setTestMsg] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  useEffect(() => {
    api.get("/api/admin/business-config").then(({ data }) => {
      setConfig(data);
    }).catch(() => {});
  }, []);

  async function handleTestConnection() {
    if (!dbUrl) return;
    setTestStatus("testing");
    try {
      await api.post("/api/admin/business-config/test-connection", { db_url: dbUrl });
      setTestStatus("ok");
      setTestMsg("Connection successful");
    } catch (err: unknown) {
      setTestStatus("fail");
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setTestMsg(detail || "Connection failed");
    }
  }

  async function handleSave() {
    setSaving(true);
    setSaveMsg("");
    try {
      const payload: Record<string, unknown> = { ...config };
      if (dbUrl) payload.db_url = dbUrl;
      await api.put("/api/admin/business-config", payload);
      setSaveMsg("Saved successfully");
    } catch {
      setSaveMsg("Save failed — check all fields");
    } finally {
      setSaving(false);
    }
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "connection", label: "Connection" },
    { id: "context", label: "Context" },
    { id: "kpis", label: "KPI Panel" },
    { id: "questions", label: "Starter Questions" },
    { id: "tables", label: "Table Guide" },
  ];

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-xl font-bold text-slate-800 mb-6">Business Setup</h1>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 mb-6 gap-1">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              activeTab === t.id ? "bg-blue-50 text-blue-700 border-b-2 border-blue-600" : "text-slate-600 hover:text-slate-800"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        {activeTab === "connection" && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Business Name</label>
              <input value={config.business_name || ""} onChange={(e) => setConfig({ ...config, business_name: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Database URL</label>
              <div className="flex gap-2">
                <input type="password" placeholder={config.db_url_masked ? `Current: ${config.db_url_masked}` : "postgres://user:pass@host:5432/db"}
                  value={dbUrl} onChange={(e) => { setDbUrl(e.target.value); setTestStatus("idle"); }}
                  className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                <button onClick={handleTestConnection} disabled={!dbUrl || testStatus === "testing"}
                  className="px-4 py-2 text-sm font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2">
                  {testStatus === "testing" ? <Loader size={14} className="animate-spin" /> : null}
                  Test Connection
                </button>
              </div>
              {testStatus !== "idle" && (
                <p className={`mt-2 text-sm flex items-center gap-1.5 ${testStatus === "ok" ? "text-green-600" : "text-red-600"}`}>
                  {testStatus === "ok" ? <CheckCircle size={14} /> : testStatus === "fail" ? <XCircle size={14} /> : null}
                  {testMsg}
                </p>
              )}
              <p className="text-xs text-slate-500 mt-1">Leave blank to keep the existing connection.</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Expensive Query Threshold (EXPLAIN cost)</label>
              <input type="number" value={config.explain_cost_threshold || 50000}
                onChange={(e) => setConfig({ ...config, explain_cost_threshold: parseInt(e.target.value) })}
                className="w-40 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <p className="text-xs text-slate-500 mt-1">Queries with EXPLAIN cost above this will prompt user confirmation.</p>
            </div>
          </div>
        )}

        {activeTab === "context" && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Business Description</label>
              <textarea rows={2} value={config.business_description || ""}
                onChange={(e) => setConfig({ ...config, business_description: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Domain Model / Context</label>
              <p className="text-xs text-slate-500 mb-1">Describe your data model, key entities, and relationships. The AI uses this to understand your business.</p>
              <textarea rows={14} value={config.domain_context || ""}
                onChange={(e) => setConfig({ ...config, domain_context: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y" />
            </div>
          </div>
        )}

        {activeTab === "kpis" && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">Define the KPIs shown in the top panel. Each KPI requires a SQL query that returns a single value.</p>
            {(config.kpi_definitions || []).map((kpi, i) => (
              <div key={i} className="border border-slate-200 rounded-lg p-4 space-y-2">
                <div className="flex gap-2">
                  <input placeholder="Name" value={kpi.name}
                    onChange={(e) => { const k = [...(config.kpi_definitions || [])]; k[i] = { ...k[i], name: e.target.value }; setConfig({ ...config, kpi_definitions: k }); }}
                    className="flex-1 px-3 py-1.5 border border-slate-200 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  <select value={kpi.format}
                    onChange={(e) => { const k = [...(config.kpi_definitions || [])]; k[i] = { ...k[i], format: e.target.value }; setConfig({ ...config, kpi_definitions: k }); }}
                    className="px-3 py-1.5 border border-slate-200 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="currency">Currency</option>
                    <option value="number">Number</option>
                    <option value="percent">Percent</option>
                  </select>
                  <button onClick={() => { const k = (config.kpi_definitions || []).filter((_, j) => j !== i); setConfig({ ...config, kpi_definitions: k }); }}
                    className="px-3 py-1.5 text-red-500 hover:bg-red-50 rounded text-sm">Remove</button>
                </div>
                <textarea rows={2} placeholder="SELECT ..." value={kpi.sql}
                  onChange={(e) => { const k = [...(config.kpi_definitions || [])]; k[i] = { ...k[i], sql: e.target.value }; setConfig({ ...config, kpi_definitions: k }); }}
                  className="w-full px-3 py-1.5 border border-slate-200 rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" />
              </div>
            ))}
            <button onClick={() => setConfig({ ...config, kpi_definitions: [...(config.kpi_definitions || []), { name: "", sql: "", format: "number", icon: "package" }] })}
              className="text-sm text-blue-600 hover:text-blue-700 font-medium">+ Add KPI</button>
          </div>
        )}

        {activeTab === "questions" && (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">These questions appear as chips on the home screen to help executives get started.</p>
            {(config.starter_questions || []).map((q, i) => (
              <div key={i} className="flex gap-2">
                <input value={q} onChange={(e) => { const qs = [...(config.starter_questions || [])]; qs[i] = e.target.value; setConfig({ ...config, starter_questions: qs }); }}
                  className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                <button onClick={() => setConfig({ ...config, starter_questions: (config.starter_questions || []).filter((_, j) => j !== i) })}
                  className="px-3 text-red-500 hover:bg-red-50 rounded-lg text-sm">✕</button>
              </div>
            ))}
            <button onClick={() => setConfig({ ...config, starter_questions: [...(config.starter_questions || []), ""] })}
              className="text-sm text-blue-600 hover:text-blue-700 font-medium">+ Add Question</button>
          </div>
        )}

        {activeTab === "tables" && (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">Describe key tables so the AI can hint at them when relevant.</p>
            {Object.entries(config.table_descriptions || {}).map(([table, desc], i) => (
              <div key={i} className="flex gap-2 items-start">
                <input value={table} placeholder="table_name"
                  className="w-48 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 flex-shrink-0" readOnly />
                <input value={desc} onChange={(e) => {
                  const t = { ...config.table_descriptions }; t[table] = e.target.value; setConfig({ ...config, table_descriptions: t });
                }}
                  className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-4 mt-6">
        <button onClick={handleSave} disabled={saving}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-medium text-sm px-6 py-2.5 rounded-lg transition-colors">
          {saving ? "Saving…" : "Save Configuration"}
        </button>
        {saveMsg && <p className={`text-sm ${saveMsg.includes("successfully") ? "text-green-600" : "text-red-600"}`}>{saveMsg}</p>}
      </div>
    </div>
  );
}
