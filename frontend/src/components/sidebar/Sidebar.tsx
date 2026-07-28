"use client";

import { Conversation } from "@/lib/types";
import Logo from "./Logo";
import NewChatButton from "./NewChatButton";
import SearchBox from "./SearchBox";
import HistoryList from "./HistoryList";

interface Props {
  conversations: Conversation[];
  activeThreadId: string;
  searchQuery: string;
  onSearchChange: (v: string) => void;
  onNewChat: () => void;
  onSelectThread: (id: string) => void;
  onDeleteThread: (id: string) => void;
}

export default function Sidebar({
  conversations,
  activeThreadId,
  searchQuery,
  onSearchChange,
  onNewChat,
  onSelectThread,
  onDeleteThread,
}: Props) {
  return (
    <aside className="w-[280px] h-screen flex flex-col bg-[#F9FAFB] border-r border-gray-200 shrink-0">
      <Logo />
      <NewChatButton onClick={onNewChat} />
      <SearchBox value={searchQuery} onChange={onSearchChange} />
      <HistoryList
        conversations={conversations}
        activeThreadId={activeThreadId}
        onSelect={onSelectThread}
        onDelete={onDeleteThread}
      />
      <div className="px-4 py-3 border-t border-gray-200">
        <span className="text-[11px] text-gray-400">DeepAgent v1.0.0</span>
      </div>
    </aside>
  );
}
