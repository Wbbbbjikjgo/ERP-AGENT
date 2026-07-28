"use client";

import { MessageSquare, Trash2 } from "lucide-react";
import { Conversation } from "@/lib/types";

interface Props {
  conversation: Conversation;
  active: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

export default function HistoryItem({
  conversation,
  active,
  onSelect,
  onDelete,
}: Props) {
  return (
    <div
      className={`group flex items-center gap-2 px-3 py-2.5 mx-2 rounded-lg cursor-pointer transition-colors ${
        active
          ? "bg-blue-50 text-blue-700"
          : "text-gray-700 hover:bg-gray-100"
      }`}
      onClick={() => onSelect(conversation.thread_id)}
    >
      <MessageSquare size={14} className="shrink-0 opacity-60" />
      <span className="flex-1 text-sm truncate">{conversation.title}</span>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete(conversation.thread_id);
        }}
        className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-500 transition-all"
      >
        <Trash2 size={13} />
      </button>
    </div>
  );
}
