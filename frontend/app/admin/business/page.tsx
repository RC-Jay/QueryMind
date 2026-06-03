"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import BusinessSetup from "@/components/admin/BusinessSetup";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";

export default function AdminBusinessPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && (!user || !user.is_superuser)) router.push("/chat");
  }, [user, loading, router]);

  if (loading || !user?.is_superuser) return null;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <div className="flex-1 overflow-y-auto bg-slate-50">
          <BusinessSetup />
        </div>
      </div>
    </div>
  );
}
