import { MetricItem } from "@/lib/types";

export default function MetricCards({ items }: { items: MetricItem[] }) {
  return (
    <div className="flex flex-wrap gap-3 my-2">
      {items.map((item, i) => (
        <div key={i} className="bg-white border border-slate-200 rounded-xl px-5 py-4 min-w-[160px]">
          <p className="text-xs text-slate-500 mb-1">{item.label}</p>
          <p className="text-2xl font-bold text-slate-800">{item.value}</p>
          {item.delta && (
            <p className={`text-xs mt-1 ${item.delta.startsWith("+") ? "text-green-600" : "text-red-500"}`}>
              {item.delta}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
