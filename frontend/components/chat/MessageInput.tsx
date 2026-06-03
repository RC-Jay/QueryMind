"use client";
import { useState, KeyboardEvent, useRef, useEffect } from "react";
import { Send, Square } from "lucide-react";

interface Props {
  onSend: (message: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
  placeholder?: string;
}

export default function MessageInput({ onSend, onStop, disabled, isStreaming, placeholder }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [value]);

  function handleSend() {
    const msg = value.trim();
    if (!msg || disabled) return;
    setValue("");
    onSend(msg);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="border-t border-slate-200 bg-white px-4 py-3">
      <div className="flex items-end gap-3 max-w-4xl mx-auto">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled || isStreaming}
            placeholder={placeholder || "Ask anything about your business…"}
            rows={1}
            className="w-full px-4 py-3 border border-slate-200 rounded-xl text-sm text-slate-800 placeholder-slate-400 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-50 leading-relaxed"
            style={{ minHeight: 46 }}
          />
        </div>
        {isStreaming ? (
          <button
            onClick={onStop}
            className="flex-shrink-0 w-10 h-10 bg-red-500 hover:bg-red-600 text-white rounded-xl flex items-center justify-center transition-colors"
          >
            <Square size={16} fill="currentColor" />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!value.trim() || disabled}
            className="flex-shrink-0 w-10 h-10 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 text-white rounded-xl flex items-center justify-center transition-colors"
          >
            <Send size={16} />
          </button>
        )}
      </div>
      <p className="text-center text-xs text-slate-400 mt-1.5 max-w-4xl mx-auto">
        Press Enter to send · Shift+Enter for new line
      </p>
    </div>
  );
}
