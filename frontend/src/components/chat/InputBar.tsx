"use client";

import { useState, useRef, useCallback } from "react";
import { Send } from "lucide-react";

interface Props {
  onSend: (message: string) => void;
  disabled?: boolean;
  queued?: number;
}

export default function InputBar({ onSend, disabled, queued = 0 }: Props) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    if (!input.trim() || disabled) return;
    onSend(input);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [input, disabled, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // 自动调整高度
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  };

  return (
    <div className="px-6 pb-4 pt-2">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-end gap-2 bg-white border border-gray-200 rounded-xl px-4 py-3 shadow-sm focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-500/10 transition-all">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={disabled ? "AI 正在回答，输入后会自动排队..." : "输入消息，Enter 发送..."}
            rows={1}
            className="flex-1 resize-none outline-none text-sm text-gray-800 placeholder-gray-400 max-h-[120px]"
          />
          {queued > 0 && (
            <span className="shrink-0 text-[10px] text-orange-500 bg-orange-50 px-1.5 py-0.5 rounded-full whitespace-nowrap">
              {queued} 条排队
            </span>
          )}
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="shrink-0 p-2 bg-[#2563EB] hover:bg-[#1D4ED8] disabled:bg-gray-300 text-white rounded-lg transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
        <p className="text-center text-[11px] text-gray-400 mt-2">
          DeepAgent 智能采购助手 · 基于 Harness Engineering 架构 · Shift+Enter 换行
        </p>
      </div>
    </div>
  );
}
