"use client";
import { useEffect, useState, useCallback } from "react";
import { KPI } from "@/lib/types";
import api from "@/lib/api";
import { RefreshCw, IndianRupee, Package, CheckCircle, Store } from "lucide-react";

const ICON_MAP: Record<string, React.ReactNode> = {
  rupee: <IndianRupee size={20} className="text-blue-600" />,
  package: <Package size={20} className="text-blue-600" />,
  "check-circle": <CheckCircle size={20} className="text-green-600" />,
  store: <Store size={20} className="text-blue-600" />,
};

const REFRESH_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes

export default function KPIPanel() {
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchKPIs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get("/api/kpi/snapshot");
      setKpis(data.kpis);
      setLastUpdated(new Date());
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || "Could not load KPIs — business database may be unreachable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKPIs();
    const interval = setInterval(fetchKPIs, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchKPIs]);

  function formatLastUpdated() {
    if (!lastUpdated) return "";
    const mins = Math.floor((Date.now() - lastUpdated.getTime()) / 60000);
    if (mins < 1) return "Just now";
    return `${mins}m ago`;
  }

  return (
    <div className="bg-white border-b border-slate-200 px-6 py-3">
      <div className="flex items-center justify-between">
        <div className="flex gap-6">
          {error ? (
            <div className="flex items-center gap-2 text-sm text-red-500">
              <span>⚠</span>
              <span>{error}</span>
            </div>
          ) : kpis.length === 0 && !loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-12 w-40 bg-slate-100 animate-pulse rounded-lg" />
              ))
            : kpis.map((kpi) => (
                <div key={kpi.label} className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
                    {ICON_MAP[kpi.icon] || <IndianRupee size={20} className="text-blue-600" />}
                  </div>
                  <div>
                    <p className="text-xs text-slate-500 leading-none mb-0.5">{kpi.label}</p>
                    <p className="text-lg font-bold text-slate-800 leading-none">{kpi.value}</p>
                  </div>
                </div>
              ))}
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-slate-400">Updated {formatLastUpdated()}</span>
          )}
          <button
            onClick={fetchKPIs}
            disabled={loading}
            className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors disabled:opacity-40"
            title="Refresh KPIs"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>
    </div>
  );
}
