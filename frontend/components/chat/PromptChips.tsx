"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";

const FALLBACK_QUESTIONS = [
  "How did we perform this week vs last week?",
  "Which businesses are growing the fastest?",
  "What are the top 10 selling products this month?",
  "Show me order completion rates by campus",
];

export default function PromptChips({ onSelect }: { onSelect: (q: string) => void }) {
  const [questions, setQuestions] = useState<string[]>(FALLBACK_QUESTIONS);

  useEffect(() => {
    api.get("/api/admin/business-config")
      .then(({ data }) => {
        if (data.starter_questions?.length) setQuestions(data.starter_questions);
      })
      .catch(() => {});
  }, []);

  return (
    <div className="flex flex-col items-center justify-center h-full px-8 py-12">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-slate-800">Good morning.</h2>
        <p className="text-slate-500 mt-1">What would you like to know today?</p>
      </div>
      <div className="grid grid-cols-2 gap-3 max-w-2xl w-full">
        {questions.slice(0, 8).map((q, i) => (
          <button
            key={i}
            onClick={() => onSelect(q)}
            className="text-left px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm text-slate-700 hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700 transition-colors"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
