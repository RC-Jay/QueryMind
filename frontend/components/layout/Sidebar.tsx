"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useChatStore } from "@/store/chatStore";
import { Plus, MessageSquare, Trash2, Settings, Users, Sparkles } from "lucide-react";
import { clsx } from "clsx";
import api from "@/lib/api";

export default function Sidebar() {
  const { user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const { conversations, activeConversationId, removeConversation, setActiveConversation, setMessages, reset } = useChatStore();

  function handleNewChat() {
    reset();
    router.push("/chat");
  }

  async function handleDelete(e: React.MouseEvent, id: string) {
    e.preventDefault();
    e.stopPropagation();
    await api.delete(`/api/chat/conversations/${id}`).catch(() => {});
    removeConversation(id);
    if (activeConversationId === id) {
      reset();
      router.push("/chat");
    }
  }

  return (
    <aside className="w-64 bg-slate-900 flex flex-col h-full flex-shrink-0">
      {/* New chat */}
      <div className="p-3 border-b border-slate-700">
        <button
          onClick={handleNewChat}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-slate-700 transition-colors"
        >
          <Plus size={16} />
          New Chat
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto py-2">
        {conversations.length === 0 && (
          <p className="text-slate-500 text-xs px-4 py-3">No conversations yet</p>
        )}
        {conversations.map((conv) => (
          <div key={conv.id} className="group relative">
            <Link
              href={`/chat/${conv.id}`}
              onClick={() => setActiveConversation(conv.id)}
              className={clsx(
                "flex items-center gap-2 px-4 py-2.5 text-sm truncate transition-colors",
                activeConversationId === conv.id
                  ? "bg-slate-700 text-white"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              )}
            >
              <MessageSquare size={14} className="flex-shrink-0" />
              <span className="truncate">{conv.title || "New conversation"}</span>
            </Link>
            <button
              onClick={(e) => handleDelete(e, conv.id)}
              className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 transition-all p-1"
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))}
      </div>

      {/* Admin section — superuser only */}
      {user?.is_superuser && (
        <div className="border-t border-slate-700 p-3 space-y-1">
          <p className="text-xs text-slate-500 px-2 pb-1 uppercase tracking-wide">Admin</p>
          <Link
            href="/admin/users"
            className={clsx(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors",
              pathname.startsWith("/admin/users") ? "bg-slate-700 text-white" : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            )}
          >
            <Users size={15} />
            User Management
          </Link>
          <Link
            href="/admin/business"
            className={clsx(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors",
              pathname.startsWith("/admin/business") ? "bg-slate-700 text-white" : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            )}
          >
            <Settings size={15} />
            Business Setup
          </Link>
          <Link
            href="/admin/llm"
            className={clsx(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors",
              pathname.startsWith("/admin/llm") ? "bg-slate-700 text-white" : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            )}
          >
            <Sparkles size={15} />
            AI Model
          </Link>
        </div>
      )}
    </aside>
  );
}
