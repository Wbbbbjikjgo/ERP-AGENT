"use client";

import { useEffect, useRef } from "react";
import { ChatMessage } from "@/lib/types";
import MessageBubble from "./MessageBubble";

interface Props {
  messages: ChatMessage[];
  streaming: boolean;
  showToolCalls: boolean;
}

export default function MessageList({ messages, streaming, showToolCalls }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
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
