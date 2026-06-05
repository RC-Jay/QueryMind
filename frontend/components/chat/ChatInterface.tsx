"use client";
import { useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useChatStore } from "@/store/chatStore";
import ChatMessage from "./ChatMessage";
import MessageInput from "./MessageInput";
import PromptChips from "./PromptChips";
import ConfirmationDialog from "./ConfirmationDialog";
import { streamChat } from "@/lib/sse";
import api from "@/lib/api";

interface Props {
  conversationId?: string;
}

export default function ChatInterface({ conversationId }: Props) {
  const router = useRouter();
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const assistantIdRef = useRef<string | null>(null);

  const {
    messages, setMessages, isStreaming, setStreaming,
    addUserMessage, startAssistantMessage,
    appendTextDelta, appendChart, appendTable, appendMetrics, finaliseMessage,
    activeConversationId, setActiveConversation,
    pendingConfirmation, setPendingConfirmation,
    updateConversationTitle, addConversation, setMessageError,
  } = useChatStore();

  // Load conversation history when ID changes
  useEffect(() => {
    if (!conversationId) return;
    setActiveConversation(conversationId);
    api.get(`/api/chat/conversations/${conversationId}`)
      .then(({ data }) => {
        const msgs = data.messages.map((m: { id: string; role: string; content: { text?: string; chart?: unknown; table?: unknown; metrics?: unknown } }) => ({
          id: m.id,
          role: m.role,
          content: m.content,
        }));
        setMessages(msgs);
      })
      .catch(() => {});
  }, [conversationId, setActiveConversation, setMessages]);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isStreaming]);

  const handleSend = useCallback(async (text: string) => {
    addUserMessage(text);
    const aId = startAssistantMessage();
    assistantIdRef.current = aId;
    setStreaming(true);
    setPendingConfirmation(null);

    abortRef.current = new AbortController();

    await streamChat(
      text,
      activeConversationId,
      {
        onConversationId: (id) => {
          setActiveConversation(id);
          if (!activeConversationId) {
            // New conversation — add to sidebar and navigate
            addConversation({ id, title: text.slice(0, 60), created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
            router.push(`/chat/${id}`);
          }
        },
        onTextDelta: (delta) => appendTextDelta(aId, delta),
        onChart: (data) => appendChart(aId, data),
        onTable: (data) => appendTable(aId, data),
        onMetrics: (items) => appendMetrics(aId, items),
        onConfirmationRequired: (req) => setPendingConfirmation(req),
        onDone: () => {
          finaliseMessage(aId);
          setStreaming(false);
          setPendingConfirmation(null);
        },
        onError: (msg) => {
          setMessageError(aId, msg);
          setStreaming(false);
        },
      },
      abortRef.current.signal
    );
  }, [
    activeConversationId, addUserMessage, startAssistantMessage, appendTextDelta,
    appendChart, appendTable, appendMetrics, finaliseMessage, setStreaming,
    setPendingConfirmation, setActiveConversation, addConversation, setMessageError, router,
  ]);

  function handleStop() {
    abortRef.current?.abort();
    if (assistantIdRef.current) {
      finaliseMessage(assistantIdRef.current);
    }
    setStreaming(false);
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-full">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <PromptChips onSelect={handleSend} />
        ) : (
          <div className="max-w-4xl mx-auto py-4">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            {pendingConfirmation && (
              <ConfirmationDialog
                request={pendingConfirmation}
                onResolved={() => setPendingConfirmation(null)}
              />
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <MessageInput
        onSend={handleSend}
        onStop={handleStop}
        isStreaming={isStreaming}
        placeholder={isEmpty ? "Ask anything about your business…" : "Ask a follow-up…"}
      />
    </div>
  );
}
