export interface User {
  id: number;
  name: string;
  email: string;
  is_superuser: boolean;
  force_password_change: boolean;
}

export interface AuthState {
  user: User | null;
  accessToken: string | null;
}

export interface KPI {
  label: string;
  value: string;
  icon: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export type MessageRole = "user" | "assistant";

export interface ChartData {
  plotly_json: Record<string, unknown>;
  title: string;
}

export interface TableData {
  columns: string[];
  rows: (string | null)[][];
  total: number;
  source?: string;
}

export interface MetricItem {
  label: string;
  value: string;
  icon?: string;
  delta?: string;
}

export interface MessageContent {
  text?: string;
  chart?: ChartData;
  table?: TableData;
  metrics?: MetricItem[];
  source?: string;
  cancelled?: boolean;
  reason?: string;
  error?: string;   // set when the turn fails — rendered as a distinct error UI
}

export interface Message {
  id: string;
  role: MessageRole;
  content: MessageContent;
  created_at?: string;
  // streaming state
  isStreaming?: boolean;
}

export interface ConfirmationRequest {
  query_id: string;
  estimated_cost: number;
  warning: string;
}
