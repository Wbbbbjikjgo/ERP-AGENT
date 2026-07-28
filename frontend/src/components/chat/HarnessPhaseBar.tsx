"use client";

import { Brain, ListChecks, Cog, SearchCheck, CheckCircle2 } from "lucide-react";

interface Props {
  phase: string;
  phaseLabel: string;
  visible: boolean;
}

const PHASES = [
  { key: "thinking", label: "思考", icon: Brain },
  { key: "planning", label: "规划", icon: ListChecks },
  { key: "executing", label: "执行", icon: Cog },
  { key: "reviewing", label: "审查", icon: SearchCheck },
  { key: "done", label: "完成", icon: CheckCircle2 },
];

const PHASE_ORDER = ["thinking", "planning", "executing", "reviewing", "done"];

/**
 * Harness 工作流阶段指示器
 * 展示: 思考 → 规划 → 执行 → 审查 → 完成
 */
export default function HarnessPhaseBar({ phase, phaseLabel, visible }: Props) {
  if (!visible || phase === "idle") return null;

  const currentIdx = PHASE_ORDER.indexOf(phase);

  return (
    <div className="px-6 py-2 bg-white/90 backdrop-blur-sm border-b border-gray-100 animate-fade-in">
      <div className="flex items-center gap-1 max-w-lg mx-auto">
        {PHASES.map((p, idx) => {
          const Icon = p.icon;
          const isPast = idx < currentIdx;
          const isCurrent = idx === currentIdx;

          return (
            <div key={p.key} className="flex items-center">
              {/* 阶段节点 */}
              <div className="flex flex-col items-center gap-0.5">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300 ${
                    isCurrent
                      ? "bg-blue-500 text-white shadow-md shadow-blue-200 scale-110"
                      : isPast
                        ? "bg-green-100 text-green-600"
                        : "bg-gray-100 text-gray-400"
                  }`}
                >
                  <Icon size={14} className={isCurrent ? "animate-pulse" : ""} />
                </div>
                <span
                  className={`text-[10px] ${
                    isCurrent ? "text-blue-600 font-medium" : isPast ? "text-green-600" : "text-gray-400"
                  }`}
                >
                  {p.label}
                </span>
              </div>

              {/* 连接线 */}
              {idx < PHASES.length - 1 && (
                <div
                  className={`w-8 h-0.5 mx-0.5 mb-3 rounded transition-colors duration-300 ${
                    idx < currentIdx ? "bg-green-400" : "bg-gray-200"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* 当前阶段标签 */}
      {phaseLabel && (
        <div className="text-center mt-1">
          <span className="text-xs text-gray-500 animate-pulse">{phaseLabel}</span>
        </div>
      )}
    </div>
  );
}
