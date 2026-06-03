import { MessageContent, ConfirmationRequest } from "./types";

export type SSEEventType =
  | { type: "conversation_id"; id: string }
  | { type: "text_delta"; delta: string }
  | { type: "chart"; plotly_json: Record<string, unknown>; title: string }
  | { type: "table"; columns: string[]; rows: (string | null)[][]; total: number; source?: string }
  | { type: "metrics"; items: { label: string; value: string; icon?: string }[] }
  | { type: "source"; description: string }
  | { type: "confirmation_required"; data: ConfirmationRequest }
  | { type: "confirmation_cancelled"; query_id: string }
  | { type: "done" }
  | { type: "error"; message: string };

export interface StreamCallbacks {
  onConversationId?: (id: string) => void;
  onTextDelta?: (delta: string) => void;
  onChart?: (data: { plotly_json: Record<string, unknown>; title: string }) => void;
  onTable?: (data: { columns: string[]; rows: (string | null)[][]; total: number; source?: string }) => void;
  onMetrics?: (items: { label: string; value: string; icon?: string }[]) => void;
  onConfirmationRequired?: (data: ConfirmationRequest) => void;
  onDone?: () => void;
  onError?: (message: string) => void;
}

export async function streamChat(
  message: string,
  conversationId: string | null,
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const token = sessionStorage.getItem("access_token");
  const response = await fetch("http://localhost:8000/api/chat/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, conversation_id: conversationId }),
    credentials: "include",
    signal,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    callbacks.onError?.(error.detail || "Request failed");
    return;
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    let eventType = "";
    let dataLine = "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        dataLine = line.slice(6).trim();
      } else if (line === "" && eventType && dataLine) {
        try {
          const payload = JSON.parse(dataLine);
          switch (eventType) {
            case "conversation_id":
              callbacks.onConversationId?.(payload.id);
              break;
            case "text_delta":
              callbacks.onTextDelta?.(payload.delta);
              break;
            case "chart":
              callbacks.onChart?.({ plotly_json: payload.plotly_json, title: payload.title });
              break;
            case "table":
              callbacks.onTable?.(payload);
              break;
            case "metrics":
              callbacks.onMetrics?.(payload.items);
              break;
            case "confirmation_required":
              callbacks.onConfirmationRequired?.(payload);
              break;
            case "done":
              callbacks.onDone?.();
              break;
            case "error":
              callbacks.onError?.(payload.message);
              break;
          }
        } catch {
          // ignore malformed JSON
        }
        eventType = "";
        dataLine = "";
      }
    }
  }
}
