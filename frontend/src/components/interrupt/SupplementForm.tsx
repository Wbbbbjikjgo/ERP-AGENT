"use client";

import { useState } from "react";
import { AlertCircle, Send } from "lucide-react";
import { InterruptData } from "@/lib/types";

interface Props {
  data: InterruptData;
  onSubmit: (supplement: string) => void;
}

export default function SupplementForm({ data, onSubmit }: Props) {
  const [text, setText] = useState("");

  const handleSubmit = () => {
    if (!text.trim()) return;
    onSubmit(text.trim());
    setText("");
  };

  return (
    <div className="mx-6 mb-3 animate-fade-in">
      <div className="max-w-3xl mx-auto border border-amber-200 bg-amber-50 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <AlertCircle size={16} className="text-amber-600" />
          <span className="text-sm font-medium text-amber-800">
            需要补充订单信息
          </span>
        </div>

        {data.message && (
          <p className="text-xs text-amber-700 mb-2">{data.message}</p>
        )}

        {data.missing_fields && data.missing_fields.length > 0 && (
          <div className="mb-3">
            <span className="text-xs text-amber-600 font-medium">缺少字段: </span>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {data.missing_fields.map((f) => (
                <span
                  key={f}
                  className="px-2 py-0.5 bg-amber-100 text-amber-700 text-[11px] rounded-full border border-amber-200"
                >
                  {f}
                </span>
              ))}
            </div>
          </div>
        )}

        {data.extracted_data && Object.keys(data.extracted_data).length > 0 && (
          <div className="mb-3 p-2 bg-white/60 rounded-lg">
            <span className="text-[11px] text-amber-600 font-medium">已提取数据:</span>
            <pre className="text-[11px] text-gray-600 mt-1 whitespace-pre-wrap">
              {JSON.stringify(data.extracted_data, null, 2)}
            </pre>
          </div>
        )}

        <div className="flex gap-2">
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            placeholder="输入补充信息，如：零部件ID为P001，数量100，单价25.5"
            className="flex-1 px-3 py-2 text-sm border border-amber-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-400/30 bg-white"
          />
          <button
            onClick={handleSubmit}
            disabled={!text.trim()}
            className="px-3 py-2 bg-amber-600 hover:bg-amber-700 disabled:bg-gray-300 text-white text-sm rounded-lg transition-colors"
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
