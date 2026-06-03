"use client";
import { useState } from "react";
import { TableData } from "@/lib/types";
import { Download, ChevronUp, ChevronDown } from "lucide-react";

export default function DataTable({ data }: { data: TableData }) {
  const { columns, rows, total, source } = data;
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortAsc, setSortAsc] = useState(true);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;

  function handleSort(idx: number) {
    if (sortCol === idx) setSortAsc(!sortAsc);
    else { setSortCol(idx); setSortAsc(true); }
    setPage(0);
  }

  const sorted = sortCol !== null
    ? [...rows].sort((a, b) => {
        const va = a[sortCol] ?? "";
        const vb = b[sortCol] ?? "";
        const na = parseFloat(va as string);
        const nb = parseFloat(vb as string);
        const cmp = !isNaN(na) && !isNaN(nb) ? na - nb : String(va).localeCompare(String(vb));
        return sortAsc ? cmp : -cmp;
      })
    : rows;

  const paged = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);

  function handleDownload() {
    const csv = [columns.join(","), ...rows.map((r) => r.map((v) => `"${v ?? ""}"`).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "data.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="my-2">
      <div className="rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                {columns.map((col, i) => (
                  <th key={i} onClick={() => handleSort(i)} className="px-4 py-2.5 text-left text-slate-600 font-medium cursor-pointer hover:text-blue-600 select-none whitespace-nowrap">
                    <span className="flex items-center gap-1">
                      {col}
                      {sortCol === i ? (sortAsc ? <ChevronUp size={12} /> : <ChevronDown size={12} />) : null}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paged.map((row, ri) => (
                <tr key={ri} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-4 py-2 text-slate-700 whitespace-nowrap">{cell ?? "—"}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="flex items-center justify-between mt-2">
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span>Showing {paged.length} of {total} rows</span>
          {totalPages > 1 && (
            <div className="flex items-center gap-1">
              <button disabled={page === 0} onClick={() => setPage(page - 1)}
                className="px-2 py-1 rounded hover:bg-slate-200 disabled:opacity-40">‹</button>
              <span>{page + 1} / {totalPages}</span>
              <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}
                className="px-2 py-1 rounded hover:bg-slate-200 disabled:opacity-40">›</button>
            </div>
          )}
        </div>
        <button onClick={handleDownload}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-blue-600 transition-colors">
          <Download size={12} />
          Download CSV
        </button>
      </div>
    </div>
  );
}
