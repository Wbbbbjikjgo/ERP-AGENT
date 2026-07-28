"use client";

import { Conversation } from "@/lib/types";
import HistoryItem from "./HistoryItem";

interface Props {
  conversations: Conversation[];
  activeThreadId: string;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

export default function HistoryList({
  conversations,
  activeThreadId,
  onSelect,
  onDelete,
}: Props) {
  if (conversations.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center px-4">
        <p className="text-sm text-gray-400">暂无对话记录</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto py-1">
      {conversations.map((conv) => (
        <HistoryItem
          key={conv.thread_id}
          conversation={conv}
          active={conv.thread_id === activeThreadId}
          onSelect={onSelect}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}
