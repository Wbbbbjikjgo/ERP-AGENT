"use client";

import { Plus } from "lucide-react";

interface Props {
  onClick: () => void;
}

export default function NewChatButton({ onClick }: Props) {
  return (
    <div className="px-4 mb-3">
      <button
        onClick={onClick}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-sm font-medium rounded-lg transition-colors"
      >
        <Plus size={16} />
        新建对话
      </button>
    </div>
  );
}
