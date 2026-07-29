"use client";

import { useEffect, useRef, useCallback } from "react";
import { ChatMessage } from "@/lib/types";
import MessageBubble from "./MessageBubble";

interface Props {
  messages: ChatMessage[];
  streaming: boolean;
  showToolCalls: boolean;
}

export default function MessageList({ messages, streaming, showToolCalls }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef(false);

  // 检测用户是否手动滚动了（不在底部）
  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const threshold = 80;
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
    userScrolledUp.current = !isNearBottom;
  }, []);

  // 自动滚到底部（仅在用户没有手动上翻时）
  useEffect(() => {
    if (!userScrolledUp.current) {
      bottomRef.current?.scrollIntoView({ behavior: streaming ? "smooth" : "auto" });
    }
  }, [messages, streaming]);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto px-6 py-4 space-y-4"
    >
      {messages.map((msg, idx) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          isStreaming={streaming && idx === messages.length - 1 && msg.role === "assistant"}
          showToolCalls={showToolCalls}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
