"use client";
import { AlertTriangle } from "lucide-react";
import { ConfirmationRequest } from "@/lib/types";
import api from "@/lib/api";

interface Props {
  request: ConfirmationRequest;
  onResolved: () => void;
}

export default function ConfirmationDialog({ request, onResolved }: Props) {
  async function respond(approved: boolean) {
    await api.post(`/api/chat/confirm/${request.query_id}`, { approved }).catch(() => {});
    onResolved();
  }

  return (
    <div className="mx-4 my-3 bg-amber-50 border border-amber-200 rounded-xl p-4 max-w-2xl">
      <div className="flex items-start gap-3">
        <AlertTriangle size={18} className="text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-medium text-amber-800 mb-1">This query may be expensive</p>
          <p className="text-sm text-amber-700 mb-3">{request.warning}</p>
          <div className="flex gap-2">
            <button
              onClick={() => respond(true)}
              className="px-4 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Yes, proceed
            </button>
            <button
              onClick={() => respond(false)}
              className="px-4 py-1.5 border border-amber-300 text-amber-700 hover:bg-amber-100 text-sm font-medium rounded-lg transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
