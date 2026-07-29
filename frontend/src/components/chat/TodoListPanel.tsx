"use client";

import { useState } from "react";
import { TodoItem } from "@/lib/types";
import { CheckCircle2, Circle, Loader2, XCircle, ListTodo, X } from "lucide-react";

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
  const [open, setOpen] = useState(true);

  if (!visible || items.length === 0) return null;

  const completedCount = items.filter((i) => i.status === "complete").length;
  const progress = items.length > 0 ? (completedCount / items.length) * 100 : 0;

  return (
    <>
      {/* 触发按钮（面板关闭时显示） */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg hover:bg-gray-100 transition-colors text-xs text-gray-600"
        >
          <ListTodo size={14} className="text-blue-600" />
          <span>{completedCount}/{items.length}</span>
        </button>
      )}

      {/* 浮动面板（固定在右上角） */}
      {open && (
        <div className="fixed top-24 right-4 w-72 z-[100] rounded-xl border border-gray-200 bg-white shadow-lg overflow-hidden animate-fade-in">
          {/* 标题栏 */}
          <div className="flex items-center justify-between px-4 py-2.5 bg-gray-50/80 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <ListTodo size={14} className="text-blue-600" />
              <span className="text-xs font-medium text-gray-700">任务规划</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-gray-400">
                {completedCount}/{items.length} 完成
              </span>
              <button
                onClick={() => setOpen(false)}
                className="p-0.5 hover:bg-gray-200 rounded transition-colors"
              >
                <X size={14} className="text-gray-400" />
              </button>
            </div>
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
    </>
  );
}
