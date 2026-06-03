"use client";
import { Message } from "@/lib/types";
import PlotlyChart from "@/components/visualizations/PlotlyChart";
import DataTable from "@/components/visualizations/DataTable";
import MetricCards from "@/components/visualizations/MetricCard";
import { clsx } from "clsx";

interface Props {
  message: Message;
  onConfirm?: (queryId: string, approved: boolean) => void;
}

export default function ChatMessage({ message, onConfirm }: Props) {
  const { role, content, isStreaming } = message;
  const isUser = role === "user";

  return (
    <div className={clsx("flex gap-3 px-4 py-3", isUser && "flex-row-reverse")}>
      {/* Avatar */}
      <div className={clsx(
        "w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold mt-0.5",
        isUser ? "bg-blue-600 text-white" : "bg-slate-200 text-slate-600"
      )}>
        {isUser ? "U" : "AI"}
      </div>

      <div className={clsx("max-w-3xl flex-1", isUser && "flex flex-col items-end")}>
        {/* Metrics */}
        {content.metrics && content.metrics.length > 0 && (
          <MetricCards items={content.metrics} />
        )}

        {/* Chart */}
        {content.chart && (
          <div className="w-full">
            <PlotlyChart plotlyJson={content.chart.plotly_json} title={content.chart.title} />
          </div>
        )}

        {/* Table */}
        {content.table && (
          <div className="w-full">
            <DataTable data={content.table} />
          </div>
        )}

        {/* Text */}
        {(content.text || isStreaming) && (
          <div className={clsx(
            "rounded-xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap",
            isUser
              ? "bg-blue-600 text-white rounded-tr-sm"
              : "bg-white border border-slate-200 text-slate-800 rounded-tl-sm"
          )}>
            {content.text || ""}
            {isStreaming && <span className="inline-block w-1.5 h-4 bg-blue-500 ml-0.5 animate-pulse align-text-bottom" />}
          </div>
        )}

        {/* Source attribution */}
        {content.source && !isUser && (
          <p className="text-xs text-slate-400 mt-1.5 px-1">
            {content.source}
          </p>
        )}

        {/* Cancelled */}
        {content.cancelled && (
          <div className="bg-amber-50 border border-amber-200 text-amber-700 text-sm px-4 py-2.5 rounded-xl">
            {content.reason || "This action was cancelled."}
          </div>
        )}
      </div>
    </div>
  );
}
