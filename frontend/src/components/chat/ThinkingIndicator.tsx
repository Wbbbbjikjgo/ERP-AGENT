"use client";

interface Props {
  visible: boolean;
}

export default function ThinkingIndicator({ visible }: Props) {
  if (!visible) return null;

  return (
    <div className="flex items-center gap-3 px-4 py-3 animate-fade-in">
      <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
        <div className="relative w-4 h-4">
          {/* 旋转环 */}
          <div className="absolute inset-0 rounded-full border-2 border-blue-200 border-t-blue-600 animate-spin" />
          {/* 中心点 */}
          <div className="absolute inset-[5px] rounded-full bg-blue-500 animate-pulse" />
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600 font-medium">正在深度思考</span>
          <span className="thinking-dots flex gap-0.5">
            <span className="w-1 h-1 bg-blue-500 rounded-full animate-bounce [animation-delay:0ms]" />
            <span className="w-1 h-1 bg-blue-500 rounded-full animate-bounce [animation-delay:150ms]" />
            <span className="w-1 h-1 bg-blue-500 rounded-full animate-bounce [animation-delay:300ms]" />
          </span>
        </div>
        <span className="text-xs text-gray-400">分析意图 · 规划步骤 · 调用工具</span>
      </div>
    </div>
  );
}
