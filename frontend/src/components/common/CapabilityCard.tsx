"use client";

import { CapabilityCard as CardType } from "@/lib/types";

interface Props {
  card: CardType;
  onClick: (prompt: string) => void;
}

export default function CapabilityCard({ card, onClick }: Props) {
  return (
    <button
      onClick={() => onClick(card.prompt)}
      className="flex flex-col items-start gap-2 p-4 bg-white border border-gray-200 rounded-xl hover:border-blue-300 hover:shadow-md transition-all text-left group"
    >
      <span className="text-2xl">{card.icon}</span>
      <span className="text-sm font-medium text-gray-800 group-hover:text-blue-600 transition-colors">
        {card.title}
      </span>
      <span className="text-xs text-gray-500 leading-relaxed">
        {card.description}
      </span>
    </button>
  );
}
