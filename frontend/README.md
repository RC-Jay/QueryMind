# QueryMind Analytics — Frontend

Next.js 16 application providing the executive chat interface, KPI panel, conversation history, and admin pages.

---

## Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout — wraps everything in AuthProvider
│   ├── page.tsx                # Redirects / → /chat
│   ├── login/page.tsx          # Login form
│   ├── change-password/page.tsx # Forced on first login
│   ├── chat/
│   │   ├── layout.tsx          # Chat layout — auth guard, loads conversations, mounts Sidebar + KPIPanel
│   │   └── [[...id]]/page.tsx  # Chat page (new or existing conversation)
│   └── admin/
│       ├── users/page.tsx      # User management (superuser only)
│       └── business/page.tsx   # Business Setup (superuser only)
│
├── components/
│   ├── chat/
│   │   ├── ChatInterface.tsx   # Main chat component — drives SSE streaming
│   │   ├── ChatMessage.tsx     # Single message bubble (text + chart + table + metrics)
│   │   ├── MessageInput.tsx    # Textarea input with send/stop buttons
│   │   ├── PromptChips.tsx     # Starter question chips (loaded from business config)
│   │   └── ConfirmationDialog.tsx  # Expensive query approval dialog
│   ├── visualizations/
│   │   ├── PlotlyChart.tsx     # Interactive Plotly chart + PNG download
│   │   ├── DataTable.tsx       # Sortable, paginated table + CSV download
│   │   └── MetricCard.tsx      # Large headline KPI numbers
│   ├── kpi/
│   │   └── KPIPanel.tsx        # Top bar — auto-refreshes every 10 min, manual refresh
│   ├── admin/
│   │   ├── UserManagement.tsx  # User list, add user modal, deactivate, reset password
│   │   └── BusinessSetup.tsx   # Tabbed config form (connection, context, KPIs, questions)
│   └── layout/
│       ├── Sidebar.tsx         # Conversation history + Admin section (superuser only)
│       └── Header.tsx          # Business name, user name, logout
│
├── lib/
│   ├── api.ts                  # Axios instance with JWT interceptor + silent refresh
│   ├── auth.tsx                # AuthContext, AuthProvider, useAuth hook
│   ├── sse.ts                  # streamChat() — fetch-based SSE client
│   └── types.ts                # All shared TypeScript interfaces
│
└── store/
    └── chatStore.ts            # Zustand store — conversations, messages, streaming state
```

---

## Running

```bash
npm run dev       # development server on port 3000
npm run build     # production build (run to check for type errors)
```

---

## Auth Flow

1. `AuthProvider` attempts a silent token refresh on mount using **raw axios** (not the interceptor-enhanced client — this is intentional to prevent an infinite retry loop on first visit)
2. If refresh succeeds, user is restored from `/api/auth/me`
3. If refresh fails (no cookie), `loading` becomes `false` and the user sees the login page
4. On login, the access token is stored in `sessionStorage` and the refresh token is set as an httpOnly cookie by the backend
5. The axios interceptor in `api.ts` automatically retries failed requests after refreshing the token, but **never redirects to `/login` if already on an auth page**

---

## SSE Streaming

`lib/sse.ts` uses the native `fetch` API (not EventSource) to support custom `Authorization` headers. It parses the SSE stream line-by-line and fires typed callbacks:

```typescript
await streamChat(message, conversationId, {
  onTextDelta: (delta) => { /* append to message */ },
  onChart:     (data)  => { /* render Plotly */     },
  onTable:     (data)  => { /* render DataTable */  },
  onMetrics:   (items) => { /* render MetricCards */},
  onConfirmationRequired: (req) => { /* show dialog */},
  onDone:      ()      => { /* finalise message */  },
});
```

The expensive query confirmation dialog appears inline in the chat. Clicking **Yes, proceed** or **Cancel** POSTs to `/api/chat/confirm/{query_id}` which unblocks the paused backend coroutine.

---

## State Management

Zustand (`store/chatStore.ts`) holds:
- `conversations` — sidebar list
- `messages` — the active conversation's message list
- `isStreaming` — whether a response is currently streaming
- `pendingConfirmation` — set when a `confirmation_required` SSE event arrives

Messages are built up incrementally as SSE events arrive — `text_delta` appends to the text field, `chart`/`table`/`metrics` events add their respective content blocks to the same message object.

---

## Environment Variables

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Notes

- **Next.js 16 breaking change:** `params` in page/layout components is now a `Promise` and must be `await`ed. All dynamic routes in this project handle this correctly.
- **No dark mode** — this is an internal executive tool. The CSS forces light mode globally to avoid rendering issues on macOS systems with dark mode enabled.
- **No NextAuth** — authentication is handled entirely by the FastAPI backend. The frontend only manages token storage and the login form.
