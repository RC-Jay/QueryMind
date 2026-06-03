"use client";
import { useEffect, useRef } from "react";
import { Download } from "lucide-react";

interface Props {
  plotlyJson: Record<string, unknown>;
  title?: string;
}

export default function PlotlyChart({ plotlyJson, title }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    const p = plotlyJson as { data: unknown[]; layout?: Record<string, unknown> };
    import("plotly.js-dist-min").then((Plotly) => {
      if (cancelled || !ref.current) return;
      Plotly.newPlot(ref.current, p.data, p.layout ?? {}, {
        responsive: true,
        displayModeBar: false,
      });
    });
    return () => {
      cancelled = true;
      const currentRef = ref.current;
      if (currentRef) {
        import("plotly.js-dist-min").then((Plotly) => {
          Plotly.purge(currentRef);
        });
      }
    };
  }, [plotlyJson]);

  async function handleDownload() {
    const Plotly = await import("plotly.js-dist-min");
    if (!ref.current) return;
    await Plotly.downloadImage(ref.current, {
      format: "png",
      filename: title || "chart",
      width: 1200,
      height: 600,
    });
  }

  return (
    <div className="my-2">
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <div ref={ref} className="w-full" style={{ minHeight: 300 }} />
      </div>
      <div className="flex justify-end mt-1.5">
        <button onClick={handleDownload}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-blue-600 transition-colors">
          <Download size={12} />
          Download PNG
        </button>
      </div>
    </div>
  );
}
