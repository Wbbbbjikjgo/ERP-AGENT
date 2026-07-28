"use client";

import { useState } from "react";
import { ChatMessage, InterruptData, TodoItem } from "@/lib/types";
import MessageList from "./MessageList";
import WelcomeScreen from "./WelcomeScreen";
import InputBar from "./InputBar";
import ThinkingIndicator from "./ThinkingIndicator";
import TodoListPanel from "./TodoListPanel";
import HarnessPhaseBar from "./HarnessPhaseBar";
import ToolCallToggle from "@/components/common/ToolCallToggle";
import InterruptBanner from "@/components/interrupt/InterruptBanner";

interface Props {
  messages: ChatMessage[];
  streaming: boolean;
  thinking: boolean;
  interrupted: boolean;
  interruptData: InterruptData | null;
  todoItems: TodoItem[];
  todoVisible: boolean;
  phase: string;
  phaseLabel: string;
  onSend: (msg: string) => void;
  onSupplement: (text: string) => void;
  onApprove: () => void;
  onReject: () => void;
}

export default function ChatArea({
  messages,
  streaming,
  thinking,
  interrupted,
  interruptData,
  todoItems,
  todoVisible,
  phase,
  phaseLabel,
  onSend,
  onSupplement,
  onApprove,
  onReject,
}: Props) {
  const [showToolCalls, setShowToolCalls] = useState(true);
  const hasMessages = messages.length > 0;

  return (
    <main className="flex-1 flex flex-col h-screen bg-gray-50/50 min-w-0">
      {/* 顶部工具栏 */}
      {hasMessages && (
        <div className="flex items-center justify-between px-6 py-2 border-b border-gray-100 bg-white/80 backdrop-blur-sm">
          <span className="text-xs text-gray-400">DeepAgent 智能助手</span>
          <ToolCallToggle show={showToolCalls} onToggle={setShowToolCalls} />
        </div>
      )}

      {/* Harness 阶段指示器 */}
      <HarnessPhaseBar phase={phase} phaseLabel={phaseLabel} visible={streaming || phase === "done"} />

      {/* 消息区域 / 欢迎页 */}
      {hasMessages ? (
        <MessageList
          messages={messages}
          streaming={streaming}
          showToolCalls={showToolCalls}
        />
      ) : (
        <WelcomeScreen onPromptClick={onSend} />
      )}

      {/* 深度思考动画 */}
      {thinking && <ThinkingIndicator visible={thinking} />}

      {/* TODO 任务列表 */}
      <TodoListPanel items={todoItems} visible={todoVisible} />

      {/* 中断交互区 */}
      {interrupted && interruptData && (
        <InterruptBanner
          data={interruptData}
          onSupplement={onSupplement}
          onApprove={onApprove}
          onReject={onReject}
        />
      )}

      {/* 输入区 */}
      <InputBar onSend={onSend} disabled={streaming} />
    </main>
  );
}
