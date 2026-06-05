import { create } from "zustand";
import { Message, ConversationSummary, ChartData, TableData, MetricItem, ConfirmationRequest } from "@/lib/types";
import { v4 as uuidv4 } from "uuid";

interface ChatStore {
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  messages: Message[];
  isStreaming: boolean;
  pendingConfirmation: ConfirmationRequest | null;

  setConversations: (convs: ConversationSummary[]) => void;
  setActiveConversation: (id: string | null) => void;
  setMessages: (msgs: Message[]) => void;
  addUserMessage: (text: string) => string;
  startAssistantMessage: () => string;
  appendTextDelta: (id: string, delta: string) => void;
  appendChart: (id: string, chart: ChartData) => void;
  appendTable: (id: string, table: TableData) => void;
  appendMetrics: (id: string, items: MetricItem[]) => void;
  finaliseMessage: (id: string) => void;
  setStreaming: (v: boolean) => void;
  setPendingConfirmation: (req: ConfirmationRequest | null) => void;
  addConversation: (conv: ConversationSummary) => void;
  removeConversation: (id: string) => void;
  updateConversationTitle: (id: string, title: string) => void;
  setMessageError: (id: string, error: string) => void;
  reset: () => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  conversations: [],
  activeConversationId: null,
  messages: [],
  isStreaming: false,
  pendingConfirmation: null,

  setConversations: (convs) => set({ conversations: convs }),
  setActiveConversation: (id) => set({ activeConversationId: id }),
  setMessages: (msgs) => set({ messages: msgs }),

  addUserMessage: (text) => {
    const id = uuidv4();
    set((s) => ({
      messages: [...s.messages, { id, role: "user", content: { text } }],
    }));
    return id;
  },

  startAssistantMessage: () => {
    const id = uuidv4();
    set((s) => ({
      messages: [...s.messages, { id, role: "assistant", content: {}, isStreaming: true }],
    }));
    return id;
  },

  appendTextDelta: (id, delta) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, content: { ...m.content, text: (m.content.text ?? "") + delta } } : m
      ),
    })),

  appendChart: (id, chart) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, content: { ...m.content, chart } } : m
      ),
    })),

  appendTable: (id, table) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, content: { ...m.content, table } } : m
      ),
    })),

  appendMetrics: (id, items) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, content: { ...m.content, metrics: items } } : m
      ),
    })),

  finaliseMessage: (id) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, isStreaming: false } : m)),
    })),

  setStreaming: (v) => set({ isStreaming: v }),
  setPendingConfirmation: (req) => set({ pendingConfirmation: req }),

  addConversation: (conv) =>
    set((s) => ({ conversations: [conv, ...s.conversations] })),

  removeConversation: (id) =>
    set((s) => ({ conversations: s.conversations.filter((c) => c.id !== id) })),

  updateConversationTitle: (id, title) =>
    set((s) => ({
      conversations: s.conversations.map((c) => (c.id === id ? { ...c, title } : c)),
    })),

  setMessageError: (id, error) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, content: { ...m.content, error }, isStreaming: false } : m
      ),
    })),

  reset: () => set({ messages: [], activeConversationId: null, isStreaming: false }),
}));
