"use client";
import { useAuth } from "@/lib/auth";
import { LogOut } from "lucide-react";

export default function Header({ businessName }: { businessName?: string }) {
  const { user, logout } = useAuth();

  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 flex-shrink-0">
      <div className="flex items-center gap-3">
        <span className="text-lg font-bold text-blue-700">{businessName || "QueryMind"}</span>
        <span className="text-slate-400 text-sm">Analytics</span>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-sm text-slate-600">{user?.name}</span>
        <button onClick={logout} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-red-600 transition-colors">
          <LogOut size={15} />
          Logout
        </button>
      </div>
    </header>
  );
}
