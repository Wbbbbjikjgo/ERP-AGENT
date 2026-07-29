"use client";

import { useCallback, useEffect, useRef } from "react";
import Sidebar from "@/components/sidebar/Sidebar";
import ChatArea from "@/components/chat/ChatArea";
import { useChat } from "@/hooks/useChat";
import { useHistory } from "@/hooks/useHistory";
import { getMessages } from "@/lib/api";
import { ChatMessage } from "@/lib/types";

export default function Home() {
  const chat = useChat();
  const history = useHistory();
  const wasStreaming = useRef(false);

  // 聊天结束后自动刷新历史列表
  useEffect(() => {
    if (wasStreaming.current && !chat.streaming) {
      // 延迟 500ms 等待后端保存完成
      const timer = setTimeout(() => history.refresh(), 500);
      return () => clearTimeout(timer);
    }
    wasStreaming.current = chat.streaming;
  }, [chat.streaming, history]);

  const handleSelectThread = useCallback(
    async (threadId: string) => {
      try {
        const data = await getMessages(threadId);
        const msgs: ChatMessage[] = (data.messages || data || []).map(
          (m: Record<string, unknown>, idx: number) => ({
            id: (m.id as string) || `msg-${idx}`,
            role: (m.role as "user" | "assistant") || "assistant",
            content: (m.content as string) || "",
            source: m.source as string | undefined,
            toolCalls: m.toolCalls as ChatMessage["toolCalls"],
            timestamp: (m.timestamp as number) || Date.now(),
          })
        );
        chat.loadThread(threadId, msgs);
      } catch {
        // 加载失败静默处理
      }
    },
    [chat]
  );

  const handleDeleteThread = useCallback(
    (threadId: string) => {
      history.remove(threadId);
      if (threadId === chat.threadId) {
        chat.newChat();
      }
    },
    [history, chat]
  );

  const handleSupplement = useCallback(
    (text: string) => {
      chat.resumeWith({ supplement: text });
    },
    [chat]
  );

  const handleApprove = useCallback(() => {
    chat.resumeWith({ decisions: [{ type: "approve" }] });
  }, [chat]);

  const handleReject = useCallback(() => {
    chat.resumeWith({ decisions: [{ type: "reject" }] });
  }, [chat]);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        conversations={history.conversations}
        activeThreadId={chat.threadId}
        searchQuery={history.searchQuery}
        onSearchChange={history.setSearchQuery}
        onNewChat={chat.newChat}
        onSelectThread={handleSelectThread}
        onDeleteThread={handleDeleteThread}
      />
      <ChatArea
        messages={chat.messages}
        streaming={chat.streaming}
        thinking={chat.thinking}
        interrupted={chat.interrupted}
        interruptData={chat.interruptData}
        todoItems={chat.todoItems}
        todoVisible={chat.todoVisible}
        pendingQueue={chat.pendingQueue}
        phase={chat.phase}
        phaseLabel={chat.phaseLabel}
        onSend={chat.sendMessage}
        onSupplement={handleSupplement}
        onApprove={handleApprove}
        onReject={handleReject}
      />
    </div>
  );
}
