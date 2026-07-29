"use client";

import { useState, useRef, useEffect } from "react";
import { TodoItem } from "@/lib/types";
import { CheckCircle2, Circle, Loader2, XCircle, ListTodo, ChevronDown } from "lucide-react";

interface Props {
  items: TodoItem[];
  visible: boolean;
}

const STATUS_CONFIG = {
  pending: { icon: Circle, color: "text-gray-300", label: "待处理" },
  in_progress: { icon: Loader2, color: "text-blue-500", label: "执行中", spin: true },
  complete: { icon: CheckCircle2, color: "text-green-500", label: "已完成" },
  cancelled: { icon: XCircle, color: "text-red-400", label: "已取消" },
} as const;

export default function TodoListPanel({ items, visible }: Props) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  if (!visible || items.length === 0) return null;

  const completedCount = items.filter((i) => i.status === "complete").length;
  const progress = items.length > 0 ? (completedCount / items.length) * 100 : 0;

  return (
    <div ref={panelRef} className="relative">
      {/* 触发按钮 */}
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg hover:bg-gray-100 transition-colors text-xs text-gray-600"
      >
        <ListTodo size={14} className="text-blue-600" />
        <span>{completedCount}/{items.length}</span>
        <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {/* 下拉面板 */}
      {open && (
        <div className="absolute right-0 top-full mt-1 w-72 rounded-xl border border-gray-200 bg-white shadow-lg overflow-hidden z-50 animate-fade-in">
          {/* 标题栏 */}
          <div className="flex items-center justify-between px-4 py-2.5 bg-gray-50/80 border-b border-gray-100">
            <span className="text-xs font-medium text-gray-700">任务规划</span>
            <span className="text-[11px] text-gray-400">
              {completedCount}/{items.length} 完成
            </span>
          </div>

          {/* 进度条 */}
          <div className="h-1 bg-gray-100">
            <div
              className="h-full bg-gradient-to-r from-blue-500 to-blue-400 transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* 任务列表 */}
          <div className="px-4 py-2 space-y-1.5 max-h-60 overflow-y-auto">
            {items.map((item) => {
              const config = STATUS_CONFIG[item.status] || STATUS_CONFIG.pending;
              const Icon = config.icon;
              return (
                <div key={item.id} className="flex items-center gap-2.5 py-0.5">
                  <Icon
                    size={14}
                    className={`${config.color} shrink-0 ${
                      "spin" in config && config.spin ? "animate-spin" : ""
                    }`}
                  />
                  <span
                    className={`text-xs leading-relaxed ${
                      item.status === "complete"
                        ? "text-gray-400 line-through"
                        : item.status === "in_progress"
                        ? "text-gray-800 font-medium"
                        : "text-gray-500"
                    }`}
                  >
                    {item.content}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
