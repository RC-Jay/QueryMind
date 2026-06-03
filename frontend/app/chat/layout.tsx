"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useChatStore } from "@/store/chatStore";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import KPIPanel from "@/components/kpi/KPIPanel";
import api from "@/lib/api";

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { setConversations } = useChatStore();

  useEffect(() => {
    if (!loading && !user) router.push("/login");
    if (!loading && user?.force_password_change) router.push("/change-password");
  }, [user, loading, router]);

  useEffect(() => {
    if (!user) return;
    api.get("/api/chat/conversations").then(({ data }) => setConversations(data)).catch(() => {});
  }, [user, setConversations]);

  if (loading || !user) return null;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header businessName="ChangePay" />
        <KPIPanel />
        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
